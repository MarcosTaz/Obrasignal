from pathlib import Path

from observability_static_audit import current_repository_report, scan_python_source


ROOT = Path(__file__).resolve().parents[1]


def _codes(findings):
    return [item.code for item in findings]


def test_bare_exception_pass_is_reported_without_source_or_values():
    findings = scan_python_source(
        "sample.py",
        "def run():\n    try:\n        work()\n    except Exception:\n        pass\n",
    )

    assert _codes(findings) == ["SILENT_EXCEPTION_PASS"]
    finding = findings[0]
    assert finding.function == "run"
    assert finding.severity == "DIAGNOSTIC_GAP"
    assert not hasattr(finding, "source")
    assert not hasattr(finding, "value")


def test_exception_print_is_privacy_review_not_safe_diagnostic():
    findings = scan_python_source(
        "worker.py",
        "def worker():\n    try:\n        work()\n    except Exception as exc:\n        print('failed', exc)\n",
    )

    assert _codes(findings) == ["RAW_EXCEPTION_STDOUT"]
    assert findings[0].owner_hint == "OBSERVABILITY_SECURITY_PRIVACY"


def test_raw_exception_keyword_sink_is_reported_without_exception_text():
    findings = scan_python_source(
        "source.py",
        "def fetch():\n    try:\n        work()\n    except Exception as exc:\n        record_source_result(error=exc)\n",
    )

    assert _codes(findings) == ["RAW_EXCEPTION_SINK"]
    assert findings[0].severity == "PRIVACY_REVIEW"


def test_str_of_exception_keyword_sink_is_also_reported():
    findings = scan_python_source(
        "source.py",
        "def fetch():\n    try:\n        work()\n    except Exception as exc:\n        save(detail=str(exc))\n",
    )

    assert _codes(findings) == ["RAW_EXCEPTION_SINK"]


def test_expected_handled_exception_is_not_mechanically_flagged():
    findings = scan_python_source(
        "safe.py",
        "def parse():\n    try:\n        return int('1')\n    except ValueError:\n        return None\n",
    )

    assert findings == []


def test_current_app_contains_silent_failure_and_raw_worker_exception_risks():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    findings = scan_python_source("app.py", source)

    assert any(item.code == "SILENT_EXCEPTION_PASS" and item.function == "sync_once" for item in findings)
    assert any(item.code == "RAW_EXCEPTION_STDOUT" and item.function == "worker" for item in findings)


def test_current_preload_persists_raw_connector_exception_as_diagnostic_input():
    source = (ROOT / "preload.py").read_text(encoding="utf-8")
    findings = scan_python_source("preload.py", source)

    assert any(item.code == "RAW_EXCEPTION_SINK" for item in findings)


def test_repository_report_is_bounded_and_does_not_emit_exception_or_source_text():
    report = current_repository_report(ROOT)

    assert report["paths"] == ["app.py", "preload.py", "source_health.py"]
    assert report["counts"].get("SILENT_EXCEPTION_PASS", 0) >= 1
    assert report["counts"].get("RAW_EXCEPTION_STDOUT", 0) >= 1
    assert report["counts"].get("RAW_EXCEPTION_SINK", 0) >= 1
    for finding in report["findings"]:
        assert set(finding) == {"code", "path", "function", "line", "severity", "owner_hint"}
