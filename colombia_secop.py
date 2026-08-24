"""Colombia SECOP II construction-procurement source.

Canonical official dataset:
SECOP II - Procesos de Contratación (p6dx-8zbt), published by Colombia
Compra Eficiente on datos.gov.co and refreshed daily.

SECOP uses UNSPSC, not European CPV. The normalizer therefore preserves the
source taxonomy explicitly and leaves ``cpv`` empty until an audited taxonomy
mapping exists. This prevents the current CPV-based commercial scorer from
silently misinterpreting UNSPSC codes.
"""
import os

from socrata_adapter import SocrataProcurementAdapter, SocrataSourceConfig


SECOP_PROCESS_FIELDS = (
    "entidad",
    "nit_entidad",
    "departamento_entidad",
    "ciudad_entidad",
    "ordenentidad",
    "id_del_proceso",
    "referencia_del_proceso",
    "nombre_del_procedimiento",
    "descripci_n_del_procedimiento",
    "fase",
    "fecha_de_publicacion_del",
    "fecha_de_ultima_publicaci",
    "fecha_de_recepcion_de",
    "precio_base",
    "modalidad_de_contratacion",
    "estado_del_procedimiento",
    "estado_de_apertura_del_proceso",
    "tipo_de_contrato",
    "codigo_principal_de_categoria",
    "ciudad_de_la_unidad_de",
    "nombre_de_la_unidad_de",
    "urlproceso",
)

# First production slice: explicit open works only. SECOP also exposes UNSPSC,
# but widening discovery through source taxonomy belongs in a tested taxonomy
# adapter. Starting with the source's explicit ``Obra`` contract type maximises
# precision and avoids silently treating unfamiliar source categories as CPV.
SECOP_CONSTRUCTION_WHERE = (
    "estado_de_apertura_del_proceso = 'Abierto' AND "
    "tipo_de_contrato = 'Obra'"
)

# Business dates in the live dataset can both be NULL even for open works.
# Socrata documents ``:updated_at`` and ``:id`` as datastore system fields for
# detecting changes and stable row identity. They are therefore the technical
# cursor; procurement publication dates remain business metadata only.
SECOP_CONFIG = SocrataSourceConfig(
    source="CO_SECOP",
    country="COL",
    domain="www.datos.gov.co",
    dataset_id="p6dx-8zbt",
    id_field="id_del_proceso",
    updated_field="fecha_de_ultima_publicaci",
    selected_fields=SECOP_PROCESS_FIELDS,
    page_size=1000,
    max_pages=50,
    # Open works can remain actionable well beyond one week. The first sync
    # therefore scans 90 days of datastore changes; later runs use cursor+24h overlap.
    initial_lookback_days=90,
    overlap_minutes=1440,
    app_token_env="SOCRATA_APP_TOKEN",
    market="GLOBAL",
    base_where=SECOP_CONSTRUCTION_WHERE,
    cursor_expression=":updated_at",
    cursor_alias="source_cursor_at",
    cursor_id_expression=":id",
    cursor_id_alias="source_cursor_id",
)


def _text(value):
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("url", "value", "name", "label"):
            if value.get(key):
                return str(value[key]).strip()
        return ""
    return str(value).strip()


def _unspsc_code(value):
    code = _text(value)
    if code.upper().startswith("V1."):
        code = code[3:]
    return code


def _public_process_url(value):
    """Return only a useful public SECOP process URL.

    Some official rows contain the SECOP login URL rather than a public process
    detail. We retain that raw value in sidecar metadata but never present a
    login page to the customer as if it were the opportunity itself.
    """
    raw = _text(value)
    lowered = raw.lower()
    if raw and "/sts/users/login/index" not in lowered:
        return raw
    return "https://www.datos.gov.co/d/p6dx-8zbt"


def normalize_secop_process(row):
    external_id = _text(row.get("id_del_proceso"))
    if not external_id:
        return None
    publication = _text(row.get("fecha_de_publicacion_del"))
    last_publication = _text(row.get("fecha_de_ultima_publicaci"))
    datastore_updated = _text(row.get("source_cursor_at"))
    datastore_row_id = _text(row.get("source_cursor_id"))
    city = _text(row.get("ciudad_de_la_unidad_de")) or _text(row.get("ciudad_entidad"))
    department = _text(row.get("departamento_entidad"))
    place = " | ".join(x for x in (city, department, "Colombia") if x)
    category_code = _unspsc_code(row.get("codigo_principal_de_categoria"))
    raw_url = _text(row.get("urlproceso"))
    return {
        "source": "CO_SECOP",
        "external_id": external_id,
        "title": _text(row.get("nombre_del_procedimiento")),
        "description": _text(row.get("descripci_n_del_procedimiento")),
        "buyer": _text(row.get("entidad")),
        "country": "COL",
        # Deliberately blank: SECOP taxonomy is UNSPSC, not CPV.
        "cpv": "",
        "taxonomy": "UNSPSC",
        "category_code": category_code,
        "value": _text(row.get("precio_base")),
        "deadline": _text(row.get("fecha_de_recepcion_de")),
        "publication_date": publication[:10] if publication else "",
        "published_at": publication or None,
        "source_updated_at": datastore_updated or None,
        "source_business_last_publication_at": last_publication or None,
        "source_initial_publication_at": publication or None,
        "source_row_id": datastore_row_id or None,
        "url": _public_process_url(row.get("urlproceso")),
        "source_url_raw": raw_url or None,
        "market": "GLOBAL",
        "place": place,
        "source_status": _text(row.get("estado_del_procedimiento")),
        "source_phase": _text(row.get("fase")),
        "signal_type": "TENDER",
        "procurement_method": _text(row.get("modalidad_de_contratacion")),
        "contract_type": _text(row.get("tipo_de_contrato")),
        "source_reference": _text(row.get("referencia_del_proceso")),
    }


def secop_adapter(*, session=None):
    token = os.getenv(SECOP_CONFIG.app_token_env or "", "").strip() or None
    return SocrataProcurementAdapter(
        SECOP_CONFIG,
        session=session,
        app_token=token,
    )


def fetch_secop_processes(*, watermark=None, now=None, adapter=None):
    connector = adapter or secop_adapter()
    return connector.fetch_incremental(
        normalize_secop_process,
        watermark=watermark,
        now=now,
    )
