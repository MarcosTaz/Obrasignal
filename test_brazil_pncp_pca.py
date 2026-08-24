from datetime import datetime

import brazil_pncp_pca as br


def _search_row(**overrides):
    row = {
        "id": "search-1",
        "cnpj": "08241804000194",
        "year": "2026",
        "updated": datetime(2026, 8, 24, 18, 0, 0),
        "updated_raw": "2026-08-24T18:00:00",
        "published_raw": "2026-01-01T10:00:00",
        "buyer": "MUNICIPIO TESTE",
        "value_global": 20000000,
        "cancelled": False,
        "item_url": "/pca/08241804000194/2026",
    }
    row.update(overrides)
    return row


def _unit(**overrides):
    row = {
        "cnpj": "08241804000194",
        "anoPca": 2026,
        "sequencialPca": 1,
        "numeroControlePNCP": "08241804000194-0-000001/2026",
        "codigoUnidade": "123",
        "nomeUnidade": "Secretaria de Obras",
        "razaoSocial": "MUNICIPIO TESTE",
        "dataAtualizacao": "2026-08-24T17:59:00",
        "dataPublicacaoPncp": "2026-01-01T10:00:00",
        "_updated": datetime(2026, 8, 24, 17, 59, 0),
    }
    row.update(overrides)
    return row


def _item(category="8", **overrides):
    row = {
        "cnpj": "08241804000194",
        "anoPca": 2026,
        "sequencialPca": 1,
        "numeroItem": 17,
        "categoriaItemPcaid": int(category),
        "categoriaItemPcaNome": "Obras e Serviços de Engenharia",
        "classificacaoSuperiorCodigo": "541",
        "classificacaoSuperiorNome": "Serviço de construção",
        "codigoItem": "12345",
        "descricao": "Construção de unidade pública",
        "quantidade": 1,
        "valorUnitario": 17700000,
        "valorTotal": 17700000,
        "valorOrcamentoExercicio": 17700000,
        "dataDesejada": "2026-12-23",
        "dataPublicacaoPncp": "2026-01-01T10:00:00",
        "dataInclusao": "2026-01-01T10:00:00",
        "dataAtualizacao": "2026-08-24T17:58:00",
        "grupoContratacaoCodigo": "G1",
        "grupoContratacaoNome": "Obras civis",
        "codigoUnidade": "123",
        "nomeUnidade": "Secretaria de Obras",
        "unidadeFornecimento": "UNIDADE",
        "unidadeRequisitante": "Engenharia",
        "catalogoId": 1,
        "nomeCatalogo": "CATSER",
        "classificacaoCatalogoId": 55,
        "nomeClassificacao": "Construção",
    }
    row.update(overrides)
    return row


def test_normalizes_procurement_plan_without_masquerading_target_date_as_deadline():
    signal = br._normalize_item(
        search_row=_search_row(), unit=_unit(), item=_item(), category="8"
    )

    assert signal["source"] == "BR_PNCP_PCA"
    assert signal["signal_type"] == "PROCUREMENT_PLAN"
    assert signal["country"] == "BRA"
    assert signal["external_id"] == "08241804000194-0-000001/2026:17"
    assert signal["target_date"] == "2026-12-23"
    assert signal["deadline"] == ""
    assert signal["value"] == "17700000"
    assert signal["currency"] == "BRL"
    assert signal["taxonomy"] == "PNCP_PCA_CATEGORY"
    assert signal["category_code"] == "8"
    assert signal["source_reference"] == "08241804000194-0-000001/2026"
    assert signal["classification_code"] == "541"
    assert "cpv" not in signal
    assert signal["url"] == "https://pncp.gov.br/app/pca/08241804000194/2026"


def test_title_uses_publisher_fields_not_keyword_classification():
    item = _item(
        grupoContratacaoNome="Programa de investimentos 2026",
        descricao="texto sem palavras-chave de construção",
    )
    signal = br._normalize_item(
        search_row=_search_row(), unit=_unit(), item=item, category="3"
    )
    assert signal["title"] == "Programa de investimentos 2026"
    assert signal["category_code"] == "3"


def test_category_item_filter_accepts_only_requested_publisher_category(monkeypatch):
    calls = []

    def fake(url, *, params=None):
        calls.append((url, dict(params or {})))
        return [_item(category="4", numeroItem=1)]

    monkeypatch.setattr(br, "_request_json", fake)
    rows = br._category_items("08241804000194", "2026", "1", "4")
    assert len(rows) == 1
    assert calls[0][1]["categoria"] == "4"
    assert calls[0][1]["pagina"] == 1


def test_text_that_says_obra_cannot_turn_material_or_generic_service_into_works(monkeypatch):
    def fake(url, *, params=None):
        return [_item(category="1", descricao="Material para obra", numeroItem=2)]

    monkeypatch.setattr(br, "_request_json", fake)
    try:
        br._category_items("08241804000194", "2026", "1", "3")
    except RuntimeError as exc:
        assert "category filter" in str(exc)
    else:
        raise AssertionError("publisher category mismatch must fail closed")


def test_consolidated_units_require_publisher_identity(monkeypatch):
    monkeypatch.setattr(
        br,
        "_request_json",
        lambda *args, **kwargs: [{
            "cnpj": "WRONG",
            "anoPca": 2026,
            "sequencialPca": 1,
            "numeroControlePNCP": "x",
            "dataAtualizacao": "2026-08-24T18:00:00",
        }],
    )
    try:
        br._consolidated_units("08241804000194", "2026")
    except RuntimeError as exc:
        assert "identity mismatch" in str(exc)
    else:
        raise AssertionError("mismatched consolidated identity must fail closed")
