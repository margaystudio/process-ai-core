"""El nombre del archivo importado no puede romper la clave de storage.

Supabase Storage **rechaza las claves con caracteres no ASCII**: importar
`Procedimiento Gestión de Deuda.docx` fallaba con `InvalidKey` mientras que el
mismo archivo sin tildes entraba sin problema. En español eso no es un caso
borde: es la mitad de los nombres de archivo de cualquier cliente.

El nombre ORIGINAL no se pierde: se guarda en `document_versions.source_file_name`
y es el que se usa al descargar. Lo que se sanea es solo la clave.
"""

from __future__ import annotations

import pytest

from process_ai_core.storage.keys import (
    nombre_seguro_para_clave,
    version_source_file_key,
    workspace_branding_key,
)


def _es_ascii(texto: str) -> bool:
    return all(ord(c) < 128 for c in texto)


# ── Los nombres reales que fallaron en producción ───────────────────────────

@pytest.mark.parametrize(
    "nombre",
    [
        "Procedimiento Gestión de Deuda Vencida y Corte Cuenta Corriente GPU.docx",
        "Procedimiento envío a Clearing de Informes GPU.docx",
        "Instrucción ñandú (v2) — copia.pdf",
        "Cómo actuar ante una fuga — versión definitiva.docx",
    ],
)
def test_un_nombre_con_tildes_produce_una_clave_ascii(nombre: str):
    clave = version_source_file_key("ws-1", "doc-1", "ver-1", nombre)
    assert _es_ascii(clave), f"la clave quedó con caracteres no ASCII: {clave!r}"


def test_las_tildes_se_transliteran_y_el_nombre_sigue_siendo_reconocible():
    """Sacar la tilde, no la letra: `Gestión` → `Gestion`, no `Gestin`."""
    assert (
        nombre_seguro_para_clave("Procedimiento Gestión de Deuda.docx")
        == "Procedimiento-Gestion-de-Deuda.docx"
    )
    assert nombre_seguro_para_clave("ñandú.pdf") == "nandu.pdf"


def test_la_extension_se_conserva_siempre():
    """Es lo que decide con qué se abre el archivo."""
    for nombre, esperada in [
        ("Instrucción.docx", ".docx"),
        ("反応.pdf", ".pdf"),          # nombre entero en otro alfabeto
        ("informe final.PDF", ".PDF"),
    ]:
        assert nombre_seguro_para_clave(nombre).endswith(esperada)


def test_un_nombre_irrecuperable_cae_al_fallback_con_su_extension():
    assert nombre_seguro_para_clave("文档.docx", fallback="source.bin") == "source.docx"
    assert nombre_seguro_para_clave("", fallback="source.bin") == "source.bin"


def test_no_se_puede_escapar_del_prefijo_del_tenant():
    """El nombre lo elige quien sube: no puede llevar la clave a otro lado."""
    clave = version_source_file_key("ws-1", "doc-1", "ver-1", "../../../etc/passwd")
    assert clave == "workspaces/ws-1/documents/doc-1/versions/ver-1/source/passwd"
    assert ".." not in clave

    clave_win = version_source_file_key("ws-1", "doc-1", "ver-1", r"..\..\secreto.docx")
    assert ".." not in clave_win
    assert clave_win.startswith("workspaces/ws-1/")


def test_un_nombre_larguisimo_no_hace_una_clave_larguisima():
    largo = "a" * 300 + ".docx"
    nombre = nombre_seguro_para_clave(largo)
    assert len(nombre) <= 90 and nombre.endswith(".docx")


def test_el_icono_de_marca_usa_el_mismo_saneo():
    clave = workspace_branding_key("ws-1", "ícono corporativo.png")
    assert _es_ascii(clave)
    assert clave == "workspaces/ws-1/branding/icono-corporativo.png"


def test_un_nombre_ya_limpio_no_se_toca():
    """Sanear no puede cambiarle el nombre a lo que ya estaba bien."""
    assert (
        nombre_seguro_para_clave("Procedimiento_Apertura-v2.docx")
        == "Procedimiento_Apertura-v2.docx"
    )
