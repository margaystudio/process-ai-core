"""
Marca visible de contenido inferido y no validado.

Vive acá y no en el renderer de procesos porque ya no es una decisión de un
dominio: la usan el documento de proceso (campos e ítems que el modelo infirió) y
las descripciones de imagen generadas con visión, que son inferencia pura —nadie
las escribió ni las validó— y tienen que llegar al lector marcadas como tales.

La escala viene de ADR-015: lo inferido es 🔴 y necesita validación humana antes
de tratarse como un hecho (ADR-006: la IA propone, el humano valida).
"""

from __future__ import annotations

#: Se pinta como chip en el PDF (el CSS lo resuelve por el texto).
CHIP_A_VALIDAR = "`A VALIDAR`"
