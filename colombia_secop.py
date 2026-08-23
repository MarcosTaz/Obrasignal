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

# Construction-first acquisition. ``tipo_de_contrato = 'Obra'`` captures
# explicit works contracts while UNSPSC segment 72 captures building,
# construction and maintenance services. The open-state condition keeps this
# source focused on actionable discovery; awards/contracts will be separate
# lifecycle sources rather than overloading one dataset.
SECOP_CONSTRUCTION_WHERE = (
    "estado_de_apertura_del_proceso = 'Abierto' AND "
    "(tipo_de_contrato = 'Obra' OR "
    "starts_with(codigo_principal_de_categoria, 'V1.72'))"
)

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
    initial_lookback_days=7,
    overlap_minutes=1440,
    app_token_env="SOCRATA_APP_TOKEN",
    market="GLOBAL",
    base_where=SECOP_CONSTRUCTION_WHERE,
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


def normalize_secop_process(row):
    external_id = _text(row.get("id_del_proceso"))
    if not external_id:
        return None
    publication = _text(row.get("fecha_de_publicacion_del"))
    updated = _text(row.get("fecha_de_ultima_publicaci"))
    city = _text(row.get("ciudad_de_la_unidad_de")) or _text(row.get("ciudad_entidad"))
    department = _text(row.get("departamento_entidad"))
    place = " | ".join(x for x in (city, department, "Colombia") if x)
    category_code = _unspsc_code(row.get("codigo_principal_de_categoria"))
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
        "source_updated_at": updated or None,
        "url": _text(row.get("urlproceso")) or "https://www.datos.gov.co/d/p6dx-8zbt",
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
