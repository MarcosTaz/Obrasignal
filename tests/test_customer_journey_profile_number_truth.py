from pathlib import Path


def test_profile_editor_rejects_non_finite_values_before_json_can_turn_them_into_null():
    source = Path("mobile/src/api.js").read_text(encoding="utf-8")

    assert "function validateProfileNumbersBeforeSerialization(profile)" in source
    assert "!Number.isFinite(value)" in source
    assert "INVALID_PROFILE_NUMBER" in source
    assert "validateProfileNumbersBeforeSerialization(profile);" in source
    assert source.index("validateProfileNumbersBeforeSerialization(profile);") < source.index("body:JSON.stringify(profile||{})")


def test_profile_editor_rejects_inverted_range_before_write():
    source = Path("mobile/src/api.js").read_text(encoding="utf-8")

    assert "data.min_value>data.max_value" in source
    assert "INVALID_PROFILE_RANGE" in source
    assert "O valor mínimo não pode ser superior ao valor máximo." in source
