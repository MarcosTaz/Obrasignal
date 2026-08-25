from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import platform
import statistics
import tempfile
import time
from typing import Any


REPRESENTATIVE_ROWS = 25
BOUNDED_UPPER_ROWS = 250
DEFAULT_ITERATIONS = 20
ACCOUNT_ID = "readiness-benchmark"


def _ms(start_ns: int) -> float:
    return round((time.perf_counter_ns() - start_ns) / 1_000_000, 3)


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot compute percentile of empty sample")
    rank = max(1, math.ceil(quantile * len(ordered)))
    return round(ordered[rank - 1], 3)


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "min_ms": round(min(values), 3),
        "p50_ms": round(float(statistics.median(values)), 3),
        "p95_ms": _percentile(values, 0.95),
        "max_ms": round(max(values), 3),
    }


def _repository_modules(db_path: str):
    os.environ["OBRASIGNAL_DB"] = db_path
    os.environ["OBRASIGNAL_AUTH_MODE"] = "development"
    os.environ["OBRASIGNAL_ACCOUNT_ID"] = ACCOUNT_ID
    os.environ.pop("OBRASIGNAL_PROFILE", None)
    os.environ.pop("OBRASIGNAL_PROFILE_FILE", None)
    os.environ.pop("OBRASIGNAL_PROFILE_JSON", None)

    import app

    app.DB = db_path
    app.init_db()

    # Importing api registers the same customer API routes used by the deployed
    # service. preload is imported as part of that boundary and owns /api/v1/radar.
    import api

    return app, api


def _reset_database(app, db_path: str) -> None:
    app.DB = db_path
    os.environ["OBRASIGNAL_DB"] = db_path
    app.init_db()


def _seed_tenders(app, row_count: int) -> None:
    now = datetime.now(timezone.utc)
    deadline = (now + timedelta(days=30)).isoformat()
    published = now.isoformat()
    rows = []
    for index in range(row_count):
        rows.append(
            (
                "BENCH",
                f"bench-{index:04d}",
                f"Empreitada de construção e estrutura metálica {index}",
                "Execução de obra de construção, montagem de estrutura metálica e cobertura.",
                "Synthetic public buyer",
                "PRT",
                "45223000",
                "100000 EUR",
                deadline,
                published,
                f"https://example.invalid/tender/{index}",
                80,
                published,
                published,
                "PT",
            )
        )
    conn = app.db()
    try:
        conn.executemany(
            """INSERT INTO tenders(
                   source,external_id,title,description,buyer,country,cpv,value,
                   deadline,publication_date,url,score,first_seen,last_seen,market
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


@contextmanager
def _timed_api_segments(api_module):
    original_save = api_module.save_profile
    original_bootstrap = api_module.bootstrap_account
    observed: dict[str, float] = {}

    def timed_save(*args, **kwargs):
        started = time.perf_counter_ns()
        try:
            return original_save(*args, **kwargs)
        finally:
            observed["save_profile_ms"] = _ms(started)

    def timed_bootstrap(*args, **kwargs):
        started = time.perf_counter_ns()
        try:
            return original_bootstrap(*args, **kwargs)
        finally:
            observed["bootstrap_ms"] = _ms(started)

    api_module.save_profile = timed_save
    api_module.bootstrap_account = timed_bootstrap
    try:
        yield observed
    finally:
        api_module.save_profile = original_save
        api_module.bootstrap_account = original_bootstrap


def _profile_payload() -> dict[str, Any]:
    return {
        "name": "Readiness Synthetic Construction",
        "activity": "construção e estruturas metálicas",
        "contract_interests": ["empreitadas de construção"],
        "coverage_mode": "portugal",
        "countries": ["PRT"],
        "cpv_prefixes": ["45", "4522"],
        "keywords": ["construção", "estrutura metálica", "obra"],
        "services": ["construção", "estrutura metálica"],
        "economic_min_score": 0,
    }


def _run_iteration(app, api_module, row_count: int, db_path: str) -> dict[str, Any]:
    _reset_database(app, db_path)
    _seed_tenders(app, row_count)
    client = app.APP.test_client()

    with _timed_api_segments(api_module) as segments:
        profile_started = time.perf_counter_ns()
        profile_response = client.post("/api/v1/profile", json=_profile_payload())
        profile_request_ms = _ms(profile_started)

    if profile_response.status_code != 200:
        raise RuntimeError(
            f"profile POST failed: status={profile_response.status_code} body={profile_response.get_data(as_text=True)[:500]}"
        )
    profile_json = profile_response.get_json() or {}
    if profile_json.get("account_id") != ACCOUNT_ID:
        raise RuntimeError("profile response account identity drifted")
    if profile_json.get("radar_recalculated") != row_count:
        raise RuntimeError(
            f"bootstrap evaluated {profile_json.get('radar_recalculated')} rows, expected {row_count}"
        )

    radar_started = time.perf_counter_ns()
    radar_response = client.get("/api/v1/radar?limit=20&minscore=0")
    radar_get_ms = _ms(radar_started)
    if radar_response.status_code != 200:
        raise RuntimeError(
            f"Radar GET failed: status={radar_response.status_code} body={radar_response.get_data(as_text=True)[:500]}"
        )
    radar_json = radar_response.get_json() or {}
    if radar_json.get("account_id") != ACCOUNT_ID:
        raise RuntimeError("Radar response account identity drifted")
    items = radar_json.get("items") or []
    if len(items) != min(20, row_count):
        raise RuntimeError(f"Radar returned {len(items)} items, expected {min(20, row_count)}")
    undecided = [
        item.get("external_id")
        for item in items
        if (item.get("decision_summary") or {}).get("status") == "SEM DECISÃO"
    ]
    if undecided:
        raise RuntimeError(f"first Radar contained unclassified benchmark rows: {undecided[:5]}")

    conn = app.db()
    try:
        decision_count = conn.execute(
            "SELECT COUNT(*) FROM opportunity_decisions WHERE account_id=?",
            (ACCOUNT_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    if decision_count != row_count:
        raise RuntimeError(f"decision count={decision_count}, expected={row_count}")

    bootstrap_ms = float(segments["bootstrap_ms"])
    save_profile_ms = float(segments["save_profile_ms"])
    return {
        "row_count": row_count,
        "save_profile_ms": save_profile_ms,
        "bootstrap_ms": bootstrap_ms,
        "profile_request_ms": profile_request_ms,
        "radar_get_ms": radar_get_ms,
        "first_value_ms": round(profile_request_ms + radar_get_ms, 3),
        "decision_count": decision_count,
        "radar_count": len(items),
        "truth_checks": {
            "profile_account_scoped": True,
            "bootstrap_evaluated_every_seeded_row": True,
            "decision_count_matches_seeded_rows": True,
            "first_radar_has_no_sem_decisao_rows": True,
        },
    }


def measure(iterations: int = DEFAULT_ITERATIONS) -> dict[str, Any]:
    if iterations < 3:
        raise ValueError("iterations must be >= 3")

    with tempfile.TemporaryDirectory(prefix="obrasignal-first-value-") as root:
        bootstrap_db = str(Path(root) / "bootstrap.sqlite3")
        app, api_module = _repository_modules(bootstrap_db)
        cases = []
        for label, row_count in (
            ("synthetic_representative", REPRESENTATIVE_ROWS),
            ("bounded_upper", BOUNDED_UPPER_ROWS),
        ):
            samples = []
            for iteration in range(iterations):
                db_path = str(Path(root) / f"{label}-{iteration}.sqlite3")
                samples.append(_run_iteration(app, api_module, row_count, db_path))

            cases.append(
                {
                    "label": label,
                    "row_count": row_count,
                    "iterations": iterations,
                    "distribution_note": (
                        "synthetic benchmark fixture, not a claim about production customer traffic distribution"
                        if label == "synthetic_representative"
                        else "exact MAX_BOOTSTRAP_ROWS bound on current canonical implementation"
                    ),
                    "summary": {
                        metric: _summary([float(sample[metric]) for sample in samples])
                        for metric in (
                            "save_profile_ms",
                            "bootstrap_ms",
                            "profile_request_ms",
                            "radar_get_ms",
                            "first_value_ms",
                        )
                    },
                    "samples": samples,
                }
            )

    return {
        "measurement_contract": "first-value-latency.measure-first.v1",
        "canonical_main_basis": "66d43f6fd51cf9cea08016dad335aaa04b711a24",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "database": "disposable SQLite",
            "auth_mode": "development synthetic account",
        },
        "path": "POST /api/v1/profile [save_profile + synchronous bootstrap_account] -> immediate GET /api/v1/radar",
        "policy": {
            "measurement_is_not_production_slo": True,
            "measurement_is_not_release_go": True,
            "no_optimization_threshold_is_invented": True,
            "tenant_and_decision_truth_checks_are_blocking_for_measurement_validity": True,
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure first-value latency on disposable local data.")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--output", default="first_value_latency_measurement.json")
    args = parser.parse_args()

    result = measure(args.iterations)
    output = Path(args.output)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"output": str(output), "cases": [
        {"label": case["label"], "row_count": case["row_count"], "summary": case["summary"]}
        for case in result["cases"]
    ]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
