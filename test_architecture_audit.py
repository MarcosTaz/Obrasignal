from pathlib import Path

import architecture_audit as audit


def test_current_repository_passes_strict_architecture_audit():
    report = audit.run_audit(Path(__file__).resolve().parent)
    assert report.status == "HEALTHY", report.to_dict()
    assert report.violations == ()


def test_source_identity_validator_rejects_duplicate_stable_identity():
    sources = {
        "SOURCE_A": {"source_id": "publisher_native"},
        "SOURCE_B": {"source_id": "publisher_native"},
    }
    assert audit._source_identity_violations(sources) == [
        "duplicate source_id 'publisher_native': SOURCE_A, SOURCE_B"
    ]


def test_source_identity_validator_rejects_missing_stable_identity():
    assert audit._source_identity_violations({"SOURCE_A": {}}) == [
        "SOURCE_A: missing stable source_id"
    ]


def test_duplicate_literal_registry_keys_are_detected_before_python_overwrite(tmp_path):
    path = tmp_path / "registry.py"
    path.write_text('SOURCES = {"A": 1, "A": 2, "B": 3}\n', encoding="utf-8")
    keys = audit._literal_dict_keys(path, "SOURCES")
    assert audit._duplicate_values(keys) == ["A"]


def test_runtime_scan_rejects_second_production_flask_constructor(tmp_path):
    (tmp_path / "app.py").write_text(
        "from flask import Flask\nAPP = Flask(__name__)\n", encoding="utf-8"
    )
    (tmp_path / "shadow_app.py").write_text(
        "from flask import Flask\nAPP = Flask(__name__)\n", encoding="utf-8"
    )
    findings = list(audit._check_runtime_single_flask(tmp_path))
    assert len(findings) == 1
    assert findings[0].state == "VIOLATION"
    assert "shadow_app.py" in findings[0].evidence


def test_runtime_scan_ignores_test_flask_instances(tmp_path):
    (tmp_path / "app.py").write_text(
        "from flask import Flask\nAPP = Flask(__name__)\n", encoding="utf-8"
    )
    (tmp_path / "test_fake_app.py").write_text(
        "from flask import Flask\nAPP = Flask(__name__)\n", encoding="utf-8"
    )
    findings = list(audit._check_runtime_single_flask(tmp_path))
    assert len(findings) == 1
    assert findings[0].state == "HEALTHY"


def test_render_entrypoint_rejects_hidden_second_web_runtime(tmp_path):
    (tmp_path / "render.yaml").write_text(
        "services:\n"
        "  - type: web\n"
        "    startCommand: gunicorn cors_app:APP\n"
        "  - type: web\n"
        "    startCommand: gunicorn alternate_app:APP\n",
        encoding="utf-8",
    )
    findings = list(audit._check_render_entrypoint(tmp_path))
    assert len(findings) == 1
    assert findings[0].state == "VIOLATION"
