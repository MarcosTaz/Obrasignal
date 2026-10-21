from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_WORKFLOW = Path(__file__).with_name('.github') / 'workflows' / 'authenticated-e2e.yml'
PRODUCTION_MARKERS = ('obrasignal.onrender.com/api/v1',)
WRITE_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')


@dataclass(frozen=True)
class CiSafetyResult:
    classification: str
    automatic_triggers: tuple[str, ...]
    production_target: bool
    production_writes: tuple[str, ...]

    @property
    def read_only_automatic_production(self) -> bool:
        return self.classification == 'READ_ONLY_AUTOMATIC_PRODUCTION'


def _automatic_triggers(text: str) -> tuple[str, ...]:
    triggers: list[str] = []
    if re.search(r'(?m)^\s{2}push\s*:', text):
        triggers.append('push')
    if re.search(r'(?m)^\s{2}schedule\s*:', text):
        triggers.append('schedule')
    return tuple(triggers)


def _production_writes(text: str, production_target: bool) -> tuple[str, ...]:
    if not production_target:
        return ()
    findings: list[str] = []
    for method in WRITE_METHODS:
        pattern = re.compile(
            rf'(?:-X|--request)\s+{method}\b[^\n]*\$\{{?API_URL\}}?',
            re.IGNORECASE,
        )
        if pattern.search(text):
            findings.append(method)
    return tuple(findings)


def classify_workflow(text: str) -> CiSafetyResult:
    automatic = _automatic_triggers(text)
    production_target = any(marker in text for marker in PRODUCTION_MARKERS)
    writes = _production_writes(text, production_target)

    if automatic and production_target and writes:
        classification = 'UNSAFE_AUTOMATIC_PRODUCTION_WRITE'
    elif automatic and production_target:
        classification = 'READ_ONLY_AUTOMATIC_PRODUCTION'
    elif production_target and writes:
        classification = 'MANUAL_PRODUCTION_WRITE_REQUIRES_AUTHORIZATION'
    elif automatic and not production_target:
        classification = 'UNKNOWN_AUTOMATIC_TARGET'
    else:
        classification = 'NON_AUTOMATIC_NON_PRODUCTION'

    return CiSafetyResult(
        classification=classification,
        automatic_triggers=automatic,
        production_target=production_target,
        production_writes=writes,
    )


def load_and_classify(path: Path | str = DEFAULT_WORKFLOW) -> CiSafetyResult:
    workflow_path = Path(path)
    text = workflow_path.read_text(encoding='utf-8')
    return classify_workflow(text)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Classify whether automatic Auth E2E can mutate the production API.'
    )
    parser.add_argument('--workflow', default=str(DEFAULT_WORKFLOW))
    parser.add_argument('--json', action='store_true', dest='as_json')
    parser.add_argument('--require-read-only', action='store_true')
    args = parser.parse_args()

    try:
        result = load_and_classify(args.workflow)
    except OSError as exc:
        print(f'PRODUCTION_CI_SAFETY_ERROR: {exc}')
        return 2

    if args.as_json:
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
    else:
        print(f'classification={result.classification}')
        print(f'automatic_triggers={",".join(result.automatic_triggers) or "-"}')
        print(f'production_target={str(result.production_target).lower()}')
        print(f'production_writes={",".join(result.production_writes) or "-"}')

    if args.require_read_only and not result.read_only_automatic_production:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
