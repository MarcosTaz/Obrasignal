"""Canonical CLI/public interface for the ObraSignal international coverage audit."""
from __future__ import annotations

import argparse
import json

from international_coverage_audit_core import run_audit, to_markdown

# Backwards-compatible internal name used by the first audit implementation.
_to_markdown = to_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit ObraSignal international coverage from repository state."
    )
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON.")
    parser.add_argument("--markdown", action="store_true", help="Print deterministic Markdown.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when repository contradictions are detected.",
    )
    args = parser.parse_args(argv)
    audit = run_audit(args.repo_root)
    if args.markdown:
        print(to_markdown(audit), end="")
    else:
        print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.strict and audit["contradictions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
