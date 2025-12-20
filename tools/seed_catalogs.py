from __future__ import annotations

from sqlalchemy import select

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models_catalog import CatalogOption


SEED = [
    # =========================================================
    # audience (a quién va dirigido el documento / modo del documento)
    # =========================================================
    dict(
        domain="audience",
        value="operativo",
        label="Operativo (pisteros / depósito)",
        prompt_text=(
            "Audiencia: personal operativo. Redacción directa, vocabulario simple, "
            "foco en pasos accionables, seguridad y evidencias básicas."
        ),
        sort_order=10,
    ),
    dict(
        domain="audience",
        value="gestion",
        label="Gestión (mandos medios / dueños)",
        prompt_text=(
            "Audiencia: gestión. Mantener claridad y brevedad, incluir controles clave, "
            "riesgos principales y un resumen ejecutivo cuando aplique."
        ),
        sort_order=20,
    ),

    # =========================================================
    # detail_level (cuán largo/detallado)
    # =========================================================
    dict(
        domain="detail_level",
        value="breve",
        label="Breve",
        prompt_text="Nivel de detalle: breve. Ir a lo esencial, evitar texto redundante.",
        sort_order=10,
    ),
    dict(
        domain="detail_level",
        value="estandar",
        label="Estándar",
        prompt_text="Nivel de detalle: estándar. Cubrir pasos, controles y evidencias sin sobrecargar.",
        sort_order=20,
    ),
    dict(
        domain="detail_level",
        value="detallado",
        label="Detallado",
        prompt_text=(
            "Nivel de detalle: detallado. Incluir variantes, excepciones, controles y evidencias "
            "con precisión. Mantener estructura ordenada."
        ),
        sort_order=30,
    ),
    dict(
        domain="detail_level",
        value="mixto",
        label="Mixto (operativo + control)",
        prompt_text=(
            "Nivel de detalle: mixto. Primero una versión operativa breve (pasos y evidencias mínimas). "
            "Luego una sección de control interno con riesgos, evidencias, métricas y puntos a validar."
        ),
        sort_order=40,
    ),

    # =========================================================
    # process_type (tipo de proceso)
    # =========================================================
    dict(
        domain="process_type",
        value="operativo",
        label="Operativo",
        prompt_text="Tipo de proceso: operativo. Priorizar seguridad, secuencia de tareas y evidencias simples.",
        sort_order=10,
    ),
    dict(
        domain="process_type",
        value="rrhh",
        label="RRHH",
        prompt_text="Tipo de proceso: RRHH. Priorizar confidencialidad, cumplimiento y trazabilidad.",
        sort_order=20,
    ),
    dict(
        domain="process_type",
        value="administracion",
        label="Administración",
        prompt_text="Tipo de proceso: administración. Priorizar controles, aprobaciones y registros.",
        sort_order=30,
    ),
    dict(
        domain="process_type",
        value="seguridad",
        label="Seguridad / Compliance",
        prompt_text="Tipo de proceso: seguridad/compliance. Priorizar controles, segregación de funciones y evidencias.",
        sort_order=40,
    ),
    dict(
        domain="process_type",
        value="it",
        label="IT / Sistemas",
        prompt_text="Tipo de proceso: IT. Priorizar pasos reproducibles, prerequisitos, logs y evidencias técnicas.",
        sort_order=50,
    ),

    # =========================================================
    # language_style (cliente)
    # =========================================================
    dict(
        domain="language_style",
        value="es_uy_formal",
        label="Español uruguayo formal",
        prompt_text="Estilo: español uruguayo formal (rioplatense), claro, profesional y sin jerga innecesaria.",
        sort_order=10,
    ),

    # =========================================================
    # business_type (cliente) - opcional pero útil para contexto
    # =========================================================
    dict(
        domain="business_type",
        value="estaciones_servicio",
        label="Estaciones de servicio / retail combustible",
        prompt_text="Tipo de negocio: estaciones de servicio. Considerar operación en pista, seguridad y turnos.",
        sort_order=10,
    ),
]


def upsert_option(session, row: dict) -> None:
    stmt = select(CatalogOption).where(
        CatalogOption.domain == row["domain"],
        CatalogOption.value == row["value"],
    )
    existing = session.execute(stmt).scalar_one_or_none()

    if existing:
        existing.label = row["label"]
        existing.prompt_text = row["prompt_text"]
        existing.sort_order = row.get("sort_order", existing.sort_order or 0)
        existing.is_active = row.get("is_active", True)
    else:
        session.add(CatalogOption(**row))


def main():
    with get_db_session() as session:
        for row in SEED:
            upsert_option(session, row)
        session.commit()

    print("✅ Catálogos seed cargados/actualizados.")


if __name__ == "__main__":
    main()