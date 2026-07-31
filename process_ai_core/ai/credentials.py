"""
Estado observado de la credencial del proveedor de IA.

POR QUÉ EXISTE
--------------
`/health` reportaba `openai_api_key: true` mirando si la variable de entorno
estaba definida. Con la key revocada en test, Tyto no respondía una sola pregunta
y el health seguía en verde: comprobaba que hubiera *algo* configurado, no que
sirviera. Un chequeo que no puede fallar no es un chequeo.

Acá se registra lo que el sistema APRENDE llamando de verdad al proveedor. Es la
señal más barata y más honesta que hay: no cuesta ninguna llamada extra —sale de
las que ya se hacen— y no es una opinión sobre la credencial, es el resultado de
usarla.

ALCANCE, DICHO EXPLÍCITAMENTE
-----------------------------
Es estado en memoria del proceso. En Cloud Run, con instancias que se apagan sin
tráfico, "no observado" es un estado normal y frecuente, no un error — por eso se
reporta como `null` y nunca como `false`. Decir "la credencial está mal" porque
todavía no se usó sería el mismo tipo de mentira que se está arreglando.

Para el caso en que hace falta una respuesta YA —recién rotaste una key y querés
saber si quedó bien, sin esperar a que alguien haga una consulta— está la sonda
activa de `probe_credential()`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, UTC

logger = logging.getLogger(__name__)

#: Cuánto vale una sonda activa antes de repetirla. `/health` puede consultarse
#: seguido (monitoreo, curl a mano); sin esto, cada visita sería una llamada al
#: proveedor.
_TTL_SONDA_SEGUNDOS = 60


@dataclass
class CredentialState:
    """Lo último que se sabe de la credencial, y de dónde se sabe."""

    #: True si la última operación contra el proveedor funcionó, False si falló
    #: por autenticación, None si todavía no se usó en este proceso.
    valid: bool | None = None
    #: Cuándo se supo.
    checked_at: datetime | None = None
    #: "trafico" (una llamada real del sistema) o "sonda" (chequeo explícito).
    source: str | None = None
    #: Detalle del fallo, sin material sensible.
    detail: str | None = None

    def as_dict(self) -> dict:
        return {
            "valid": self.valid,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
            "source": self.source,
            "detail": self.detail,
        }


_estado = CredentialState()


def record_success(operation: str) -> None:
    """Una llamada real funcionó: la credencial sirve."""
    global _estado
    _estado = CredentialState(
        valid=True, checked_at=datetime.now(UTC), source="trafico", detail=None
    )


def record_auth_failure(operation: str, detail: str) -> None:
    """El proveedor rechazó la credencial."""
    global _estado
    _estado = CredentialState(
        valid=False,
        checked_at=datetime.now(UTC),
        source="trafico",
        detail=f"{operation}: {detail}",
    )
    logger.error(
        "Credencial del proveedor de IA rechazada en %s. /health queda en "
        "degraded hasta que una llamada funcione.",
        operation,
    )


def get_credential_state() -> CredentialState:
    return _estado


def probe_credential() -> CredentialState:
    """
    Verifica la credencial contra el proveedor, ahora.

    Es la respuesta a "roté la key, ¿quedó bien?" sin tener que provocar tráfico
    de usuario ni leer logs. Usa el endpoint más barato que hay (listar modelos):
    no consume tokens y valida exactamente lo que interesa, que es la
    autenticación.

    El resultado se cachea `_TTL_SONDA_SEGUNDOS` para que consultar el health en
    un loop no se traduzca en una llamada por visita.
    """
    global _estado
    ahora = datetime.now(UTC)
    if (
        _estado.source == "sonda"
        and _estado.checked_at is not None
        and (ahora - _estado.checked_at).total_seconds() < _TTL_SONDA_SEGUNDOS
    ):
        return _estado

    try:
        from .factory import get_llm_provider

        provider = get_llm_provider()
        cliente = getattr(provider, "client", None) or getattr(provider, "_client", None)
        if cliente is None:
            raise RuntimeError("el proveedor no expone un cliente consultable")
        cliente.models.list()
        _estado = CredentialState(valid=True, checked_at=ahora, source="sonda")
    except Exception as exc:
        # El mensaje del SDK puede traer la key enmascarada; se guarda solo el
        # tipo de excepción, que es lo que hace falta para diagnosticar.
        _estado = CredentialState(
            valid=False, checked_at=ahora, source="sonda", detail=type(exc).__name__
        )
    return _estado
