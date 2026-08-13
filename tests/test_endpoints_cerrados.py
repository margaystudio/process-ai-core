"""Regresión del hotfix de seguridad: ningún endpoint de datos queda sin auth.

Fija el contrato de los agujeros cerrados en la fase 1 del rediseño de
permisos:

  1. El alta de membership por HTTP NO existe (permitía otorgarse "owner" sin
     autenticación; owner bypassea el permiso por carpeta completo).
  2. Los listados de workspaces y de membresías ajenas exigen sesión.
  3. generate-pdf y las rutas de versiones/PDF/audit-log exigen sesión (y por
     dentro, permiso por carpeta — cubierto en test_frozen_pdf_endpoint.py y
     test_imagenes_autorizadas.py).

Sin dependency_overrides a propósito: se prueba el gate real, como en
test_endpoint_requiere_autenticacion de test_tyto_answer.py.
"""

from fastapi.testclient import TestClient

from api.main import app


def _client() -> TestClient:
    assert not app.dependency_overrides  # sin mocks: gate real
    return TestClient(app)


def test_alta_de_membership_por_http_no_existe():
    resp = _client().post("/api/v1/users/u1/workspaces/w1/membership?role_name=owner")
    # 404 (ruta inexistente) o 405: lo que NO puede pasar es un 2xx ni un 401
    # de "casi": la ruta tiene que haber desaparecido.
    assert resp.status_code in (404, 405)


def test_listado_de_workspaces_exige_sesion():
    assert _client().get("/api/v1/workspaces").status_code == 401


def test_detalle_de_workspace_exige_sesion():
    assert _client().get("/api/v1/workspaces/w1").status_code == 401


def test_membresias_de_un_usuario_exigen_sesion():
    assert _client().get("/api/v1/users/u1/workspaces").status_code == 401


def test_rol_de_un_usuario_exige_sesion():
    assert _client().get("/api/v1/users/u1/role/w1").status_code == 401


def test_generate_pdf_exige_sesion():
    assert _client().post("/api/v1/process-runs/r1/generate-pdf").status_code == 401


def test_versiones_y_pdf_exigen_sesion():
    c = _client()
    assert c.get("/api/v1/documents/d1/versions").status_code == 401
    assert c.get("/api/v1/documents/d1/versions/v1/pdf").status_code == 401
    assert c.get("/api/v1/documents/d1/versions/v1/preview-pdf").status_code == 401
    assert c.get("/api/v1/documents/d1/current-version").status_code == 401
    assert c.get("/api/v1/documents/d1/audit-log").status_code == 401


def test_validaciones_exigen_sesion():
    c = _client()
    assert c.post(
        "/api/v1/documents/d1/validate", json={"observations": ""}
    ).status_code == 401
    assert c.get("/api/v1/documents/d1/validations").status_code == 401


def test_roles_operativos_exigen_sesion():
    assert _client().get("/api/v1/workspaces/w1/operational-roles").status_code == 401
