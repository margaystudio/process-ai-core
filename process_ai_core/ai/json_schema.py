"""
Generación del JSON Schema para Structured Outputs de OpenAI.

Antes el esquema se describía en prosa dentro del system prompt (~45 líneas de
llaves) y se validaba después con Pydantic, con un reintento correctivo cuando el
modelo se desviaba. Eso tenía dos costos: el esquema del prompt y el modelo
Pydantic eran dos fuentes de verdad que se desincronizaban solas, y una clase
entera de error —JSON con la forma equivocada— quedaba librada al reintento.

Con `response_format={"type":"json_schema", "strict": true}` el proveedor
garantiza la forma. La validación Pydantic se queda igual, pero pasa a ser una
red y no la primera línea de defensa.

Restricciones del modo estricto de OpenAI, que este módulo resuelve
-------------------------------------------------------------------
1. TODAS las propiedades tienen que estar en `required`. Un campo opcional se
   expresa como nullable (`type: ["string","null"]`), no omitiéndolo.
2. `additionalProperties: false` en todos los objetos.
3. Sin `default`, `format`, `minimum` ni validadores de rango.
"""

from __future__ import annotations

from typing import Any


def _strictify(nodo: Any) -> Any:
    """Adapta recursivamente un JSON Schema de Pydantic al modo estricto."""
    if isinstance(nodo, list):
        return [_strictify(x) for x in nodo]
    if not isinstance(nodo, dict):
        return nodo

    salida = {k: _strictify(v) for k, v in nodo.items() if k not in _CLAVES_NO_SOPORTADAS}

    if salida.get("type") == "object" or "properties" in salida:
        salida["additionalProperties"] = False
        propiedades = salida.get("properties") or {}
        # Todas requeridas: la opcionalidad se expresa con null, no con ausencia.
        salida["required"] = list(propiedades.keys())

    # Pydantic emite los Optional como anyOf[..., null]; el modo estricto lo
    # acepta, pero un `anyOf` de un solo elemento sobra y confunde.
    if "anyOf" in salida and len(salida["anyOf"]) == 1:
        unico = salida.pop("anyOf")[0]
        salida.update(unico)

    return salida


#: Claves que el modo estricto rechaza o ignora. `default` es la importante: con
#: todas las propiedades en `required`, un default no significa nada y OpenAI lo
#: rechaza explícitamente.
_CLAVES_NO_SOPORTADAS = {
    "default", "format", "minimum", "maximum", "exclusiveMinimum",
    "exclusiveMaximum", "minLength", "maxLength", "pattern", "minItems",
    "maxItems", "examples", "discriminator",
}


def build_strict_schema(model: type, *, name: str) -> dict:
    """
    `response_format` completo para Structured Outputs a partir de un modelo Pydantic.

    Args:
        model: clase Pydantic (BaseModel) que define el contrato de salida.
        name: nombre del esquema; OpenAI lo exige y lo usa en los mensajes de error.
    """
    esquema = _strictify(model.model_json_schema())
    return {
        "type": "json_schema",
        "json_schema": {"name": name, "strict": True, "schema": esquema},
    }
