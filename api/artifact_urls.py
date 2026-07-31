"""
Rutas de los artefactos de un run.

Acá vivía `artifact_signing.py`: firma HMAC-SHA256 que metía un token en la query
string para poder servir artefactos a un `<iframe>`, un `window.open` o un `<img>`,
que no pueden mandar el header `Authorization`.

Se eliminó, y el módulo entero con ella. El motivo no es el algoritmo —la firma
estaba bien hecha— sino lo que un token en la dirección ES: un PORTADOR. El
servidor validaba la firma y el workspace, pero no podía saber QUIÉN lo
presentaba, y sin eso el permiso por carpeta no se puede aplicar. Cualquier
miembro del workspace que consiguiera un enlace (una captura de pantalla, el
historial, "copiar dirección de la imagen") veía material de una carpeta que
tenía denegada — contradiciendo una capacidad que el producto vende explícitamente.

**Nada que el navegador pida por su cuenta lleva una credencial en la dirección.**
El principio completo, con los dos patrones que lo cumplen, está escrito en
`api/routes/documents/_helpers.py`. Si aparece una superficie nueva que tiene que
mostrar un archivo, entra en uno de esos dos casos; ninguno es firmar la URL.
"""

from urllib.parse import quote


def artifact_path(run_id: str, filename: str) -> str:
    """
    Ruta del artefacto de un run. Sin token: el endpoint exige Bearer y verifica
    el permiso sobre la carpeta del documento.

    Args:
        run_id  : ID de la corrida.
        filename: Ruta relativa dentro del directorio del run (puede incluir
                  subdirectorios, ej. "assets/frame1.png").
    """
    # quote(safe="/") preserva las barras de los subdirectorios.
    return f"/api/v1/artifacts/{run_id}/{quote(filename, safe='/')}"
