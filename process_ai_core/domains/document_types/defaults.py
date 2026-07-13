"""Template de tipos documentales por defecto (Fase 1).

Fuente de verdad, versionada en git, de los tipos con los que se **siembra cada tenant
nuevo** (copy-on-provision) y con los que se backfillean los tenants existentes.

- `key`: slug estable; es lo que guarda `Document.document_type`. NO cambiar sin migración.
- `prompt_text`: se inyecta al prompt de generación del tipo.
- `behaviors`: toggles (allowlist `BEHAVIOR_KEYS`).
- `icon` / `color`: identidad visual por defecto (el tenant los puede cambiar).

Los prompts salen del catálogo actual; los behaviors, del diseño de comportamientos MVP.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

# Allowlist de comportamientos (MVP). La API valida contra esta lista.
BEHAVIOR_KEYS: tuple[str, ...] = (
    "versionado",
    "aprobacion",
    "tyto",
    "relaciones",
    "metadatos",
)


def _behaviors(*enabled: str) -> dict[str, bool]:
    """Dict completo de behaviors: todas las keys presentes, True las habilitadas."""
    enabled_set = set(enabled)
    return {key: key in enabled_set for key in BEHAVIOR_KEYS}


def normalize_behaviors(raw: Any) -> dict[str, bool]:
    """Normaliza behaviors de entrada a un dict con exactamente las keys conocidas.

    Ignora keys desconocidas y castea a bool. Útil en la API y al leer de la DB.
    """
    if not isinstance(raw, dict):
        return _behaviors()
    return {key: bool(raw.get(key, False)) for key in BEHAVIOR_KEYS}


# Los 14 tipos actuales. `origin="default"` los marca como sembrados (vs. creados por el tenant).
DEFAULT_DOCUMENT_TYPES: list[dict[str, Any]] = [
    {
        "key": "procedimiento",
        "label": "Procedimiento",
        "prompt_text": "Tipo documental: procedimiento. Secuencia formal de trabajo, con pasos ordenados, responsables y evidencias.",
        "behaviors": _behaviors("versionado", "aprobacion", "tyto", "relaciones", "metadatos"),
        "sort_order": 10,
        "icon": "ListChecks",
        "color": "#48569C",
    },
    {
        "key": "instructivo",
        "label": "Instructivo",
        "prompt_text": "Tipo documental: instructivo. Guía puntual para una tarea concreta, breve y accionable.",
        "behaviors": _behaviors("versionado", "tyto", "metadatos"),
        "sort_order": 20,
        "icon": "BookOpen",
        "color": "#2E8B8B",
    },
    {
        "key": "manual_interno",
        "label": "Manual interno",
        "prompt_text": "Tipo documental: manual interno. Documentación amplia propia de la organización.",
        "behaviors": _behaviors("versionado", "aprobacion", "tyto", "metadatos"),
        "sort_order": 30,
        "icon": "Book",
        "color": "#2F9E62",
    },
    {
        "key": "manual_externo",
        "label": "Manual externo",
        "prompt_text": "Tipo documental: manual externo. Documento de proveedor o fabricante; es referencia, no procedimiento interno.",
        "behaviors": _behaviors("tyto", "metadatos"),
        "sort_order": 40,
        "icon": "BookMarked",
        "color": "#64748B",
    },
    {
        "key": "manual",
        "label": "Manual",
        "prompt_text": "Tipo documental: manual. Documentacion amplia, estructurada y reutilizable.",
        "behaviors": _behaviors("versionado", "aprobacion", "tyto", "metadatos"),
        "sort_order": 45,
        "icon": "Book",
        "color": "#2F9E62",
    },
    {
        "key": "politica",
        "label": "Política",
        "prompt_text": "Tipo documental: política. Regla o criterio organizacional; foco en el qué y el por qué, no en pasos.",
        "behaviors": _behaviors("versionado", "aprobacion", "tyto"),
        "sort_order": 50,
        "icon": "Scale",
        "color": "#C99A2E",
    },
    {
        "key": "normativa",
        "label": "Normativa",
        "prompt_text": "Tipo documental: normativa. Ordenanza, regulación, ley o estándar; lenguaje preciso y citable.",
        "behaviors": _behaviors("aprobacion", "tyto"),
        "sort_order": 60,
        "icon": "Gavel",
        "color": "#C99A2E",
    },
    {
        "key": "formulario",
        "label": "Formulario",
        "prompt_text": "Tipo documental: formulario. Documento a completar o generar; describir campos y su propósito.",
        "behaviors": _behaviors("versionado", "metadatos"),
        "sort_order": 70,
        "icon": "FileInput",
        "color": "#6366F1",
    },
    {
        "key": "contrato",
        "label": "Contrato",
        "prompt_text": "Tipo documental: contrato. Acuerdo formal entre partes; priorizar obligaciones, aprobaciones y metadatos clave.",
        "behaviors": _behaviors("aprobacion", "metadatos"),
        "sort_order": 75,
        "icon": "FileSignature",
        "color": "#CB4242",
    },
    {
        "key": "nda",
        "label": "NDA",
        "prompt_text": "Tipo documental: NDA. Acuerdo de confidencialidad; priorizar aprobacion y trazabilidad.",
        "behaviors": _behaviors("aprobacion"),
        "sort_order": 76,
        "icon": "Lock",
        "color": "#CB4242",
    },
    {
        "key": "checklist",
        "label": "Checklist",
        "prompt_text": "Tipo documental: checklist. Lista de verificación con ítems controlables (sí/no/observación).",
        "behaviors": _behaviors("versionado", "metadatos"),
        "sort_order": 80,
        "icon": "ListTodo",
        "color": "#2E8B8B",
    },
    {
        "key": "tramite",
        "label": "Trámite",
        "prompt_text": "Tipo documental: trámite. Procedimiento ciudadano o administrativo; requisitos, costo, oficina, plazos.",
        "behaviors": _behaviors("tyto", "metadatos"),
        "sort_order": 90,
        "icon": "Stamp",
        "color": "#8B5CF6",
    },
    {
        "key": "faq_validada",
        "label": "FAQ validada",
        "prompt_text": "Tipo documental: FAQ validada. Pregunta frecuente con respuesta aprobada, clara y autocontenida.",
        "behaviors": _behaviors("aprobacion", "tyto"),
        "sort_order": 100,
        "icon": "HelpCircle",
        "color": "#2E8B8B",
    },
    {
        "key": "presupuesto",
        "label": "Presupuesto",
        "prompt_text": "Tipo documental: presupuesto. Cotización con cliente, ítems, cantidades, importes y vigencia.",
        "behaviors": _behaviors("aprobacion", "metadatos"),
        "sort_order": 110,
        "icon": "Receipt",
        "color": "#8B5CF6",
    },
]


def build_default_rows(workspace_id: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Filas completas de `document_type` para sembrar un workspace con los defaults.

    Fuente única usada por la migración de backfill y por el hook de provisión de
    tenant. `origin="default"` marca estas filas como sembradas. `behaviors` se
    serializa a JSON.
    """
    ts = now or datetime.utcnow()
    rows: list[dict[str, Any]] = []
    for dt in DEFAULT_DOCUMENT_TYPES:
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "workspace_id": workspace_id,
                "key": dt["key"],
                "label": dt["label"],
                "prompt_text": dt["prompt_text"],
                "behaviors_json": json.dumps(dt["behaviors"]),
                "is_active": True,
                "sort_order": dt["sort_order"],
                "origin": "default",
                "icon": dt["icon"],
                "color": dt["color"],
                "created_at": ts,
                "updated_at": ts,
            }
        )
    return rows
