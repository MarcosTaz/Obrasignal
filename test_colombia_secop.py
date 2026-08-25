from colombia_secop import SECOP_CONFIG, normalize_secop_process


def test_secop_config_is_official_construction_first_dataset():
    assert SECOP_CONFIG.domain == "www.datos.gov.co"
    assert SECOP_CONFIG.dataset_id == "p6dx-8zbt"
    assert SECOP_CONFIG.id_field == "id_del_proceso"
    assert SECOP_CONFIG.updated_field == "fecha_de_ultima_publicaci"
    assert SECOP_CONFIG.cursor_expression == ":updated_at"
    assert SECOP_CONFIG.cursor_alias == "source_cursor_at"
    assert SECOP_CONFIG.cursor_id_expression == ":id"
    assert SECOP_CONFIG.cursor_id_alias == "source_cursor_id"
    assert SECOP_CONFIG.initial_lookback_days == 90
    assert "tipo_de_contrato = 'Obra'" in SECOP_CONFIG.base_where
    assert "V1.72" not in SECOP_CONFIG.base_where
    assert "estado_de_apertura_del_proceso = 'Abierto'" in SECOP_CONFIG.base_where


def test_secop_normalizer_preserves_unspsc_without_pretending_it_is_cpv():
    raw = {
        "entidad": "INSTITUTO DE INFRAESTRUCTURA",
        "id_del_proceso": "CO1.REQ.123",
        "referencia_del_proceso": "LP-001-2026",
        "nombre_del_procedimiento": "CONSTRUCCIÓN DE PUENTE",
        "descripci_n_del_procedimiento": "Obra civil para construcción de puente",
        "fase": "Presentación de oferta",
        "fecha_de_publicacion_del": "2026-08-20T00:00:00.000",
        "fecha_de_ultima_publicaci": "2026-08-21T11:15:00.000",
        "source_cursor_at": "2026-08-22T09:30:00.000",
        "source_cursor_id": "row-123",
        "fecha_de_recepcion_de": "2026-09-05T18:00:00.000",
        "precio_base": "1250000000",
        "modalidad_de_contratacion": "Licitación pública",
        "estado_del_procedimiento": "Publicado",
        "estado_de_apertura_del_proceso": "Abierto",
        "tipo_de_contrato": "Obra",
        "codigo_principal_de_categoria": "V1.72141000",
        "departamento_entidad": "Antioquia",
        "ciudad_de_la_unidad_de": "Medellín",
        "urlproceso": {"url": "https://community.secop.gov.co/example"},
    }
    item = normalize_secop_process(raw)

    assert item["source"] == "CO_SECOP"
    assert item["external_id"] == "CO1.REQ.123"
    assert item["country"] == "COL"
    assert item["taxonomy"] == "UNSPSC"
    assert item["category_code"] == "72141000"
    assert item["cpv"] == ""
    assert item["value"] == "1250000000"
    assert item["deadline"] == "2026-09-05T18:00:00.000"
    # Datastore change time and procurement publication time remain separate.
    assert item["source_updated_at"] == "2026-08-22T09:30:00.000"
    assert item["source_business_last_publication_at"] == "2026-08-21T11:15:00.000"
    assert item["source_row_id"] == "row-123"
    assert item["source_status"] == "Publicado"
    assert item["signal_type"] == "TENDER"
    assert item["procurement_method"] == "Licitación pública"
    assert item["contract_type"] == "Obra"
    assert item["place"] == "Medellín | Antioquia | Colombia"
    assert item["url"] == "https://community.secop.gov.co/example"
    assert item["source_url_raw"] == "https://community.secop.gov.co/example"


def test_missing_business_dates_do_not_remove_technical_change_timestamp():
    item = normalize_secop_process({
        "id_del_proceso": "CO1.REQ.9966248",
        "source_cursor_at": "2026-08-23T14:22:00.000Z",
        "source_cursor_id": "row-9966248",
        "tipo_de_contrato": "Obra",
        "estado_de_apertura_del_proceso": "Abierto",
    })
    assert item["source_updated_at"] == "2026-08-23T14:22:00.000Z"
    assert item["source_business_last_publication_at"] is None
    assert item["source_initial_publication_at"] is None
    assert item["source_row_id"] == "row-9966248"
    assert item["publication_date"] == ""


def test_login_url_is_preserved_for_audit_but_not_presented_as_opportunity():
    login = "https://community.secop.gov.co/STS/Users/Login/Index"
    item = normalize_secop_process({
        "id_del_proceso": "CO1.REQ.9966248",
        "urlproceso": {"url": login},
    })
    assert item["source_url_raw"] == login
    assert item["url"] == "https://www.datos.gov.co/d/p6dx-8zbt"


def test_secop_normalizer_rejects_rows_without_source_identity():
    assert normalize_secop_process({"nombre_del_procedimiento": "missing id"}) is None
