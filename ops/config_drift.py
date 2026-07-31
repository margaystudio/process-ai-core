#!/usr/bin/env python3
"""
Mide la DERIVA entre lo declarado en los `*.config.toml` y lo que las revisiones
vivas de Cloud Run realmente montan.

Por qué existe
--------------
`ops/deploy.py` despliega con `--update-env-vars` / `--update-secrets`, que en
gcloud son MERGE: agregan y pisan las claves que se les pasan, y dejan intactas
las que no. Consecuencia: **borrar una clave del TOML no la borra del servicio**,
y el deploy no avisa. La configuración declarada y la real pueden separarse sin
que nadie lo note.

Este script mide de qué tamaño es esa separación hoy, para decidir con números si
conviene cambiar la herramienta.

Tres categorías, por servicio:
  - en ambos          : declarado y montado (se marca aparte si el VALOR difiere).
  - solo en el TOML   : declarado y NO aplicado. Alguien escribió una config que
                        el servicio no tiene — el deploy no la llegó a aplicar.
  - solo en la revisión: montado sin estar declarado. **Es la deriva que importa**:
                        lo que quedó de un deploy anterior y ya nadie declara. Un
                        secreto acá es uno que no se puede borrar sin romper el
                        servicio, y nadie lo sabe leyendo el repo.

SOLO LECTURA. Los únicos comandos que ejecuta son `gcloud run services describe`
y `gcloud run jobs describe`. No hay ninguna ruta de código que modifique nada.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover — py<3.11
    import tomli as tomllib  # type: ignore

#: Verbos de gcloud permitidos. Cualquier otro es un bug de este script.
_VERBOS_DE_LECTURA = {"describe", "list"}

#: Cloud Run la inyecta sola en los services; `deploy.py` la saca del [env] antes
#: de mandarla (ver `env_for_cloud_run_service`). Declararla no es deriva.
_RESERVADAS_EN_SERVICES = {"PORT"}

#: La inyecta `deploy.py` a propósito, derivada del release file (deploy.py:368),
#: así que aparece en TODA revisión y en ningún TOML. Es esperado, no deriva: se
#: cuenta aparte para que el número de deriva signifique algo.
_INYECTADAS_POR_EL_DEPLOY = {"APP_VERSION"}


def gcloud(args: list[str]) -> str | None:
    """Corre un gcloud de LECTURA. Devuelve stdout, o None si el recurso no existe."""
    if not any(v in args for v in _VERBOS_DE_LECTURA):
        raise SystemExit(f"BLOQUEADO: este script es de solo lectura, no ejecuta {args}")
    proceso = subprocess.run(
        ["gcloud", *args], capture_output=True, text=True, check=False
    )
    if proceso.returncode != 0:
        return None
    return proceso.stdout


@dataclass
class Deriva:
    servicio: str
    repo: str
    config: str
    proyecto: str
    tipo: str
    desplegado: bool = True
    en_ambos: list[str] = field(default_factory=list)
    valores_distintos: list[str] = field(default_factory=list)
    solo_toml: list[str] = field(default_factory=list)
    solo_revision: list[str] = field(default_factory=list)
    secretos_solo_revision: list[str] = field(default_factory=list)
    inyectadas_por_el_deploy: list[str] = field(default_factory=list)


def descubrir_configs(raices: list[Path]) -> list[Path]:
    """Todos los `*.config.toml` reales (sin `.example` ni `.bak`) bajo `ops/`."""
    encontrados: list[Path] = []
    for raiz in raices:
        ops = raiz / "ops"
        if not ops.is_dir():
            continue
        for ruta in sorted(ops.rglob("*.config.toml")):
            if any(parte in ruta.name for parte in (".example", ".bak")):
                continue
            encontrados.append(ruta)
    return encontrados


def leer_declarado(config: Path) -> tuple[dict, dict, dict]:
    """(gcp, env, secrets) declarados en el TOML."""
    datos = tomllib.loads(config.read_text("utf-8"))
    return datos.get("gcp", {}), datos.get("env", {}) or {}, datos.get("secrets", {}) or {}


def leer_revision(nombre: str, tipo: str, proyecto: str, region: str) -> tuple[dict, dict] | None:
    """
    (env plano, secretos) que monta la revisión viva.

    Devuelve None si el recurso no está desplegado en ese proyecto.
    """
    recurso = "jobs" if tipo == "job" else "services"
    salida = gcloud(
        ["run", recurso, "describe", nombre, "--project", proyecto,
         "--region", region, "--format", "json"]
    )
    if salida is None:
        return None

    datos = json.loads(salida)
    plantilla = datos.get("spec", {}).get("template", {}).get("spec", {})
    if recurso == "jobs":
        plantilla = plantilla.get("template", {}).get("spec", {})
    contenedores = plantilla.get("containers", [])
    if not contenedores:
        return {}, {}

    env_plano: dict[str, str] = {}
    secretos: dict[str, str] = {}
    for variable in contenedores[0].get("env", []) or []:
        nombre_var = variable.get("name")
        if not nombre_var:
            continue
        referencia = (variable.get("valueFrom") or {}).get("secretKeyRef")
        if referencia:
            secretos[nombre_var] = f"{referencia.get('name')}:{referencia.get('key')}"
        else:
            env_plano[nombre_var] = str(variable.get("value", ""))

    # Un secreto cuya clave en el TOML es una RUTA (`"/secrets/x/id_rsa" = ...`)
    # gcloud lo monta como ARCHIVO, no como env var: aparece en `volumes` +
    # `volumeMounts` y no en `env`. Sin esto se contarían como "declarados y no
    # aplicados" secretos que sí están montados — un falso positivo que
    # inflaría el número que este script existe para medir. Caso real:
    # margay-gpu-ops-api y sus dos claves SSH.
    volumenes = {
        v.get("name"): v.get("secret", {})
        for v in plantilla.get("volumes", []) or []
        if v.get("secret")
    }
    for montaje in contenedores[0].get("volumeMounts", []) or []:
        secreto = volumenes.get(montaje.get("name"))
        if not secreto:
            continue
        base = (montaje.get("mountPath") or "").rstrip("/")
        for item in secreto.get("items", []) or []:
            ruta = f"{base}/{item.get('path')}"
            secretos[ruta] = f"{secreto.get('secretName')}:{item.get('key')}"
    return env_plano, secretos


def comparar(config: Path, raiz: Path, proyecto_filtro: str | None) -> Deriva | None:
    gcp, env_declarado, secretos_declarados = leer_declarado(config)
    proyecto = gcp.get("project", "")
    region = gcp.get("region", "")
    if proyecto_filtro and proyecto != proyecto_filtro:
        return None

    datos = tomllib.loads(config.read_text("utf-8"))
    runtime = datos.get("runtime", {})
    nombre = runtime.get("name", "")
    tipo = runtime.get("type", "service")
    if not nombre:
        return None

    resultado = Deriva(
        servicio=nombre, repo=raiz.name,
        config=str(config.relative_to(raiz)), proyecto=proyecto, tipo=tipo,
    )

    vivo = leer_revision(nombre, tipo, proyecto, region)
    if vivo is None:
        resultado.desplegado = False
        return resultado
    env_vivo, secretos_vivos = vivo

    if tipo != "job":
        env_declarado = {
            k: v for k, v in env_declarado.items() if k not in _RESERVADAS_EN_SERVICES
        }

    # env plano
    declaradas = {k: str(v) for k, v in env_declarado.items()}
    for clave in sorted(set(declaradas) | set(env_vivo)):
        if clave in declaradas and clave in env_vivo:
            resultado.en_ambos.append(clave)
            if declaradas[clave] != env_vivo[clave]:
                resultado.valores_distintos.append(clave)
        elif clave in declaradas:
            resultado.solo_toml.append(clave)
        elif clave in _INYECTADAS_POR_EL_DEPLOY:
            resultado.inyectadas_por_el_deploy.append(clave)
        else:
            resultado.solo_revision.append(clave)

    # secretos: el TOML dice "nombre:version", la revisión "nombre:key"
    for clave in sorted(set(secretos_declarados) | set(secretos_vivos)):
        if clave in secretos_declarados and clave in secretos_vivos:
            resultado.en_ambos.append(f"[secreto] {clave}")
            if str(secretos_declarados[clave]) != secretos_vivos[clave]:
                resultado.valores_distintos.append(f"[secreto] {clave}")
        elif clave in secretos_declarados:
            resultado.solo_toml.append(f"[secreto] {clave}")
        else:
            resultado.solo_revision.append(f"[secreto] {clave}")
            resultado.secretos_solo_revision.append(clave)

    return resultado


def informar(resultados: list[Deriva]) -> None:
    print(f"\n{'servicio':<28} {'repo':<20} {'ambos':>6} {'≠valor':>7} "
          f"{'solo TOML':>10} {'solo revisión':>14} {'(deploy)':>9}")
    print("─" * 100)
    for r in resultados:
        if not r.desplegado:
            print(f"{r.servicio:<28} {r.repo:<20} {'— no desplegado en este proyecto —':>40}")
            continue
        print(f"{r.servicio:<28} {r.repo:<20} {len(r.en_ambos):>6} "
              f"{len(r.valores_distintos):>7} {len(r.solo_toml):>10} "
              f"{len(r.solo_revision):>14} {len(r.inyectadas_por_el_deploy):>9}")

    desplegados = [r for r in resultados if r.desplegado]
    print("\n── Detalle de la deriva (montado sin estar declarado) ──")
    hubo = False
    for r in desplegados:
        if not r.solo_revision:
            continue
        hubo = True
        print(f"\n  {r.servicio} ({r.repo}/{r.config})")
        for clave in r.solo_revision:
            print(f"    · {clave}")
    if not hubo:
        print("  (ninguna)")

    print("\n── Declarado con OTRO valor que el que está vivo ──")
    hubo = False
    for r in desplegados:
        if not r.valores_distintos:
            continue
        hubo = True
        print(f"\n  {r.servicio} ({r.repo}/{r.config})")
        for clave in r.valores_distintos:
            print(f"    · {clave}")
    if not hubo:
        print("  (ninguna)")

    print("\n── Declarado y no aplicado (solo en el TOML) ──")
    hubo = False
    for r in desplegados:
        if not r.solo_toml:
            continue
        hubo = True
        print(f"\n  {r.servicio} ({r.repo}/{r.config})")
        for clave in r.solo_toml:
            print(f"    · {clave}")
    if not hubo:
        print("  (ninguna)")

    print("\n── Totales ──")
    print(f"  servicios comparados        : {len(desplegados)}")
    print(f"  claves en ambos             : {sum(len(r.en_ambos) for r in desplegados)}")
    print(f"    de esas, con valor distinto: {sum(len(r.valores_distintos) for r in desplegados)}")
    print(f"  solo en el TOML             : {sum(len(r.solo_toml) for r in desplegados)}")
    print(f"  solo en la revisión (DERIVA): {sum(len(r.solo_revision) for r in desplegados)}")
    secretos = sum(len(r.secretos_solo_revision) for r in desplegados)
    print(f"    de esas, SECRETOS          : {secretos}")
    if secretos:
        print("      (un secreto montado y no declarado no se puede borrar de "
              "Secret Manager sin romper el servicio, y no se ve leyendo el repo)")
    print(f"  inyectadas por el deploy    : "
          f"{sum(len(r.inyectadas_por_el_deploy) for r in desplegados)} "
          f"({', '.join(sorted(_INYECTADAS_POR_EL_DEPLOY))} — esperado, no es deriva)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="Filtrar por proyecto GCP")
    parser.add_argument(
        "--roots", nargs="+", default=["/Users/santi/src"],
        help="Directorios donde buscar repos con ops/*.config.toml",
    )
    args = parser.parse_args()

    raices: list[Path] = []
    for root in args.roots:
        base = Path(root)
        if (base / "ops").is_dir():
            raices.append(base)
        raices.extend(sorted(d for d in base.iterdir() if (d / "ops").is_dir()))

    resultados: list[Deriva] = []
    for raiz in raices:
        for config in descubrir_configs([raiz]):
            r = comparar(config, raiz, args.project)
            if r is not None:
                resultados.append(r)

    if not resultados:
        print("No se encontró ninguna config para ese proyecto.")
        return 1

    print(f"\nProyecto: {args.project or '(todos)'} — {len(resultados)} config(s)")
    informar(resultados)
    return 0


if __name__ == "__main__":
    sys.exit(main())
