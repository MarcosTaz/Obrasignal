from pathlib import Path


def test_mobile_profile_consumer_requires_canonical_envelope():
    api = Path("mobile/src/api.js").read_text(encoding="utf-8")
    assert "data?.profile||data||null" not in api
    assert "Object.prototype.hasOwnProperty.call(data,'profile')" in api
    assert "if(profile===null)return null" in api
    assert "API /profile: contrato de resposta inválido." in api
    assert "API /profile: perfil inválido." in api
