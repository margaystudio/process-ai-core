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
    # El `prompt_text` de cada rubro es donde viven los EJEMPLOS concretos. El
    # prompt base es genérico a propósito: cuando los ejemplos de logística
    # ("Encargado de depósito recibe mercadería", "remito firmado") estaban en el
    # prompt del sistema, sesgaban el vocabulario de un trámite municipal o un
    # cierre de caja. Acá cada workspace los edita para su realidad.
    dict(
        domain="business_type",
        value="estaciones_servicio",
        label="Estaciones de servicio / retail combustible",
        prompt_text=(
            "Tipo de negocio: estaciones de servicio. Considerar operación en pista, "
            "seguridad y turnos.\n"
            "Actores habituales: playero, encargado de turno, cajero, jefe de estación.\n"
            "Controles habituales: arqueo de caja, varillado de tanques, control de "
            "precintos, conciliación de turno contra reporte de surtidores.\n"
            "Evidencias habituales: planilla de turno firmada, ticket de arqueo, "
            "remito de descarga, registro en el sistema de playa."
        ),
        sort_order=10,
    ),
    dict(
        domain="business_type",
        value="logistica_deposito",
        label="Logística y depósito",
        prompt_text=(
            "Tipo de negocio: logística y depósito. Considerar recepción, "
            "almacenamiento y despacho de mercadería.\n"
            "Actores habituales: encargado de depósito, operario de picking, "
            "responsable de despacho.\n"
            "Controles habituales: validación contra orden de compra, conteo físico, "
            "control de estado de la mercadería, tiempos de registro.\n"
            "Evidencias habituales: remito firmado, foto de la factura, registro en "
            "sistema, checklist de recepción, acta de discrepancia."
        ),
        sort_order=20,
    ),
    dict(
        domain="business_type",
        value="administracion_publica",
        label="Administración pública / trámites",
        prompt_text=(
            "Tipo de negocio: administración pública. Considerar trámites con "
            "ciudadanos, plazos reglamentarios y requisitos formales.\n"
            "Actores habituales: funcionario de mesa de entrada, técnico revisor, "
            "jerarca que resuelve.\n"
            "Controles habituales: verificación de requisitos, control de plazos, "
            "firma autorizada, número de expediente.\n"
            "Evidencias habituales: expediente foliado, constancia de recepción, "
            "resolución firmada, notificación al interesado."
        ),
        sort_order=30,
    ),

    # document_type ya NO vive en el catálogo: es una entidad por-tenant
    # (tabla document_type). El vocabulario y sus defaults viven en
    # process_ai_core/domains/document_types/defaults.py y se siembran por workspace.
    # Ver docs/PLAN_DOCUMENT_TYPES.md.
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