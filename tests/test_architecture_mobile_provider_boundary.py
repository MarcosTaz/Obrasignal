from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
PROVIDER_PACKAGE = "react-native-purchases"
PROVIDER_ADAPTER = "mobile/src/billing.js"

# Existing provider-model leakage into the Billing UI. This is architecture
# debt, not an allowed public contract. The exact baseline prevents expansion
# while still allowing tokens to disappear during a later owner-proven repair.
KNOWN_PROVIDER_MODEL_LEAKS = {
    "mobile/components/BillingGate.js": {
        "availablePackages",
        "expirationDate",
        "managementURL",
        "priceString",
        "userCancelled",
    }
}


def _production_mobile_sources():
    for path in MOBILE.rglob("*"):
        if not path.is_file() or path.suffix not in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            continue
        if "node_modules" in path.parts or path.name.endswith(".test.mjs") or path.name.startswith("smoke-"):
            continue
        yield path


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_revenuecat_sdk_is_imported_only_by_the_billing_adapter():
    importers = set()
    package_pattern = re.compile(r"(?:from\s+|require\s*\(|import\s*\()\s*['\"]react-native-purchases['\"]")
    for path in _production_mobile_sources():
        if package_pattern.search(path.read_text(encoding="utf-8")):
            importers.add(_relative(path))

    assert importers == {PROVIDER_ADAPTER}


def test_revenuecat_model_leakage_does_not_expand_beyond_known_debt():
    tokens = set().union(*KNOWN_PROVIDER_MODEL_LEAKS.values())
    observed = {}
    for path in _production_mobile_sources():
        if _relative(path) == PROVIDER_ADAPTER:
            continue
        source = path.read_text(encoding="utf-8")
        found = {token for token in tokens if re.search(rf"\b{re.escape(token)}\b", source)}
        if found:
            observed[_relative(path)] = found

    assert observed == KNOWN_PROVIDER_MODEL_LEAKS
