import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / "dependency_registry.json").read_text())


def test_registry_is_observational_not_lock_authority():
    assert REGISTRY["authority"] == "observation_only"
    assert "not a lockfile authority" in REGISTRY["principle"]


def test_all_manifest_dependencies_are_registered():
    package = json.loads((ROOT / "mobile" / "package.json").read_text())
    registered = {(item["ecosystem"], item["name"]) for item in REGISTRY["components"]}
    for name in package.get("dependencies", {}):
        assert ("npm", name) in registered

    requirements = []
    for raw in (ROOT / "requirements.txt").read_text().splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        name = raw.split("==", 1)[0].split(">=", 1)[0].strip()
        requirements.append(name)
    for name in requirements:
        assert ("python", name) in registered


def test_candidate_npm_lock_is_present_without_false_canonical_resolution_claims():
    locks = {item["ecosystem"]: item for item in REGISTRY["lockfiles"]}
    assert locks["python"]["status"] == "ABSENT"
    assert locks["python"]["resolution"] == "UNKNOWN"
    assert locks["npm"] == {
        "ecosystem": "npm",
        "package_root": "mobile",
        "manifest": "mobile/package.json",
        "lockfile": "mobile/package-lock.json",
        "status": "PRESENT_CANDIDATE",
        "resolution": "REPRODUCIBLE_CANDIDATE_NOT_CANONICAL",
    }
    assert (ROOT / "mobile" / "package-lock.json").is_file()

    proof = REGISTRY["candidate_resolution"]
    assert proof["candidate_lock_committed"] is True
    assert proof["canonical_lock_committed"] is False
    assert proof["clean_npm_ci_repeat"] == "PROVEN_EXACT_HEAD"
    assert len(proof["generated_lock_sha256"]) == 64
    assert len(proof["graph_sha256"]) == 64

    # The observation registry does not turn a noncanonical candidate lock into
    # canonical runtime authority. Component resolved versions stay UNKNOWN
    # until the owner candidate itself is authorized/integrated.
    for item in REGISTRY["components"]:
        if item["ecosystem"] in {"python", "npm"}:
            assert item["resolved_version"] == "UNKNOWN"


def test_manual_mobile_production_build_fails_closed_without_lock_and_uses_npm_ci():
    workflow = (ROOT / ".github" / "workflows" / "mobile-release-preflight.yml").read_text()
    lock_guard = workflow.index("Require canonical npm lock for manual production build")
    npm_ci = workflow.index("npm ci --no-audit --no-fund")
    eas_build = workflow.index("eas-cli@latest build")
    assert "test -f package-lock.json" in workflow
    assert lock_guard < npm_ci < eas_build
    assert "reproducibly enough" not in workflow


def test_eas_production_build_requires_lock_before_npm_ci_and_build():
    workflow = (ROOT / ".github" / "workflows" / "eas-production.yml").read_text()
    lock_guard = workflow.index("Require canonical npm lock")
    npm_ci = workflow.index("npm ci --no-audit --no-fund")
    eas_build = workflow.index("eas build --platform all")
    assert "test -f package-lock.json" in workflow
    assert "npm install --no-audit --no-fund" not in workflow
    assert lock_guard < npm_ci < eas_build


def test_current_floating_build_tools_remain_explicit_debt_not_false_green():
    components = {item["name"]: item for item in REGISTRY["components"]}
    assert components["expo-doctor"]["declared_constraint"] == "latest"
    assert components["expo-doctor"]["resolved_version"] == "UNKNOWN"
    assert components["eas-cli"]["declared_constraint"] == "latest"
    assert components["eas-cli"]["resolved_version"] == "UNKNOWN"


def test_pytest_hidden_ci_dependency_is_explicitly_recorded():
    components = {item["name"]: item for item in REGISTRY["components"]}
    assert components["pytest"]["declared_constraint"] == "UNDECLARED_CI_INSTALL"
    quality = (ROOT / ".github" / "workflows" / "quality.yml").read_text()
    assert "pip install pytest" in quality
