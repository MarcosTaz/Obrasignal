from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time

import measure_first_value_latency as base


DEFAULT_ITERATIONS = 12


def _elapsed_ms(start_ns: int) -> float:
    return (time.perf_counter_ns() - start_ns) / 1_000_000


@contextmanager
def _instrument_funnel_phases():
    import funnel_integration

    originals = {
        "load_profile": funnel_integration.load_profile,
        "evaluate_row": funnel_integration.evaluate_row,
        "record_decision": funnel_integration.record_decision,
    }
    phase = {
        "load_profile_ms": 0.0,
        "evaluate_row_ms": 0.0,
        "record_decision_ms": 0.0,
        "load_profile_calls": 0,
        "evaluate_row_calls": 0,
        "record_decision_calls": 0,
    }

    def timed(name, func):
        def wrapper(*args, **kwargs):
            started = time.perf_counter_ns()
            try:
                return func(*args, **kwargs)
            finally:
                phase[f"{name}_ms"] += _elapsed_ms(started)
                phase[f"{name}_calls"] += 1
        return wrapper

    funnel_integration.load_profile = timed("load_profile", originals["load_profile"])
    funnel_integration.evaluate_row = timed("evaluate_row", originals["evaluate_row"])
    funnel_integration.record_decision = timed("record_decision", originals["record_decision"])
    try:
        yield phase
    finally:
        funnel_integration.load_profile = originals["load_profile"]
        funnel_integration.evaluate_row = originals["evaluate_row"]
        funnel_integration.record_decision = originals["record_decision"]


def _summarize(samples, metric):
    return base._summary([float(sample[metric]) for sample in samples])


def measure(iterations: int = DEFAULT_ITERATIONS):
    if iterations < 3:
        raise ValueError("iterations must be >= 3")

    with tempfile.TemporaryDirectory(prefix="obrasignal-bootstrap-phases-") as root:
        bootstrap_db = str(Path(root) / "bootstrap.sqlite3")
        app, api_module = base._repository_modules(bootstrap_db)
        cases = []

        for label, row_count in (
            ("synthetic_representative", base.REPRESENTATIVE_ROWS),
            ("bounded_upper", base.BOUNDED_UPPER_ROWS),
        ):
            samples = []
            for iteration in range(iterations):
                db_path = str(Path(root) / f"{label}-{iteration}.sqlite3")
                with _instrument_funnel_phases() as phases:
                    result = base._run_iteration(app, api_module, row_count, db_path)

                for name in ("load_profile", "evaluate_row", "record_decision"):
                    if phases[f"{name}_calls"] != row_count:
                        raise RuntimeError(
                            f"{name} calls={phases[f'{name}_calls']}, expected={row_count}"
                        )

                measured_internal = sum(
                    float(phases[f"{name}_ms"])
                    for name in ("load_profile", "evaluate_row", "record_decision")
                )
                bootstrap_ms = float(result["bootstrap_ms"])
                sample = {
                    "row_count": row_count,
                    "bootstrap_ms": bootstrap_ms,
                    "load_profile_ms": round(phases["load_profile_ms"], 3),
                    "evaluate_row_ms": round(phases["evaluate_row_ms"], 3),
                    "record_decision_ms": round(phases["record_decision_ms"], 3),
                    "other_bootstrap_ms": round(max(0.0, bootstrap_ms - measured_internal), 3),
                    "load_profile_calls": phases["load_profile_calls"],
                    "evaluate_row_calls": phases["evaluate_row_calls"],
                    "record_decision_calls": phases["record_decision_calls"],
                    "first_value_ms": result["first_value_ms"],
                }
                samples.append(sample)

            summaries = {
                metric: _summarize(samples, metric)
                for metric in (
                    "bootstrap_ms",
                    "load_profile_ms",
                    "evaluate_row_ms",
                    "record_decision_ms",
                    "other_bootstrap_ms",
                    "first_value_ms",
                )
            }
            median_bootstrap = summaries["bootstrap_ms"]["p50_ms"]
            phase_share_p50 = {}
            for metric in (
                "load_profile_ms",
                "evaluate_row_ms",
                "record_decision_ms",
                "other_bootstrap_ms",
            ):
                phase_share_p50[metric.replace("_ms", "_share_of_bootstrap_p50")] = round(
                    summaries[metric]["p50_ms"] / median_bootstrap, 4
                ) if median_bootstrap else None

            cases.append(
                {
                    "label": label,
                    "row_count": row_count,
                    "iterations": iterations,
                    "summary": summaries,
                    "phase_share_p50": phase_share_p50,
                    "samples": samples,
                }
            )

    return {
        "measurement_contract": "first-value-bootstrap-phases.measure-first.v1",
        "canonical_main_basis": "66d43f6fd51cf9cea08016dad335aaa04b711a24",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "method": "instrument actual funnel_integration global calls during the real profile-save synchronous bootstrap path; wrappers time without changing return values or commit behavior",
        "policy": {
            "measurement_is_not_production_slo": True,
            "measurement_is_not_release_go": True,
            "phase_dominance_required_before_optimization": True,
            "no_commit_or_profile_loading_behavior_changed": True
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure internal phases of first-value bootstrap.")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--output", default="bootstrap_phase_measurement.json")
    args = parser.parse_args()
    result = measure(args.iterations)
    output = Path(args.output)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "cases": [
            {
                "label": case["label"],
                "row_count": case["row_count"],
                "summary": case["summary"],
                "phase_share_p50": case["phase_share_p50"],
            }
            for case in result["cases"]
        ]
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
