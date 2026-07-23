#!/usr/bin/env python3
"""
ops/deploy.py

Deploy/Promote = tomar un artefacto ya construido (digest) y aplicarlo al runtime.

Este script implementa la mitad "Deploy/Promote" del esquema:
    Release (produce digest)  ->  Deploy/Promote (consume digest)

Qué NO hace:
- No buildea nada.
- No pushea imágenes.
- No calcula versión.

Qué hace:
1) Lee config desde: ops/{env}.config.toml
2) Decide qué imagen (digest) deployar con prioridad:
   - Si pasás --image, usa ese digest.
   - Si pasás --release-file, lee ese archivo.
   - Si no, toma el último archivo en ops/releases/ que matchee <image>_*.txt
3) Deploya según runtime.type:
   - job: Cloud Run Jobs (create/update)
   - service: Cloud Run Service (deploy)
4) Aplica env vars y secrets declarados en el TOML.

Uso típico:
    python ops/deploy.py --env prod                     # último release local
    python ops/deploy.py --env prod --version v0.1.1    # deploy/rollback a una versión exacta
    python ops/deploy.py --env prod --component api --version v0.2.0   # monorepo

Deploy explícito por digest:
    python ops/deploy.py --env prod --image region-docker.pkg.dev/.../imagen@sha256:...

Además setea la env var APP_VERSION en el runtime (derivada del release file),
para que la app pueda exponer su versión (ej. en /health).

Requisitos:
- Python 3.10+ (si es 3.10 necesita `tomli`)
- gcloud instalado y autenticado
"""

import re
import subprocess
from pathlib import Path
from typing import Any


def load_toml(path: Path) -> dict[str, Any]:
    """Carga TOML (stdlib en 3.11+, fallback tomli en 3.10)."""
    try:
        import tomllib

        return tomllib.loads(path.read_text("utf-8"))
    except ModuleNotFoundError:
        import tomli

        return tomli.loads(path.read_text("utf-8"))


def run(cmd: list[str]) -> None:
    """Ejecuta un comando mostrando qué corre."""
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def exists(cmd: list[str]) -> bool:
    """True si el comando devuelve exit code 0 (útil para saber si existe el job)."""
    return subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def kv_csv(d: dict[str, Any]) -> str:
    """
    Convierte dict a formato esperado por gcloud para --update-env-vars / --update-secrets.

    Caso simple:    {"A": 1, "B": "x"} -> "A=1,B=x"
    Con comas en valores (ej. CORS_ORIGINS con JSON array): usa el delimitador
    custom de gcloud (^<delim>^...) para que las comas internas no rompan el parseo.
    """
    if not d:
        return ""
    pairs = [f"{k}={v}" for k, v in d.items()]
    if all("," not in p for p in pairs):
        return ",".join(pairs)
    for delim in ("@", "|", "~", "#", ";", ":"):
        if all(delim not in p for p in pairs):
            return f"^{delim}^" + delim.join(pairs)
    raise SystemExit(
        "No se pudo serializar env vars para gcloud: ningún delimitador seguro "
        "disponible para valores con comas."
    )


def env_for_cloud_run_service(env: dict[str, Any]) -> dict[str, Any]:
    """Cloud Run Services reservan ciertas variables (PORT la setea la plataforma)."""
    reserved = {"PORT"}
    return {k: v for k, v in env.items() if k not in reserved}


def pick_latest_release(releases_dir: Path, image_name: str) -> Path:
    """
    Elige el release "más nuevo". Convención: ops/releases/<image>_<version>.txt

    Ordena por versión semver (determinístico, funciona en un checkout limpio de
    CI donde todos los mtime son iguales). Los release sha-* (sin semver) van al
    fondo y se desempatan por mtime. Prioriza siempre la mayor vX.Y.Z.
    """
    files = list(releases_dir.glob(f"{image_name}_*.txt"))
    if not files:
        raise SystemExit(
            f"No release files found in {releases_dir}. Run: python ops/release.py --env <env>"
        )

    def sort_key(p: Path) -> tuple:
        v = version_from_release_file(p, image_name)
        m = re.match(r"^v(\d+)\.(\d+)\.(\d+)$", v)
        if m:
            # (es_semver, major, minor, patch, mtime)
            return (1, int(m[1]), int(m[2]), int(m[3]), p.stat().st_mtime)
        return (0, 0, 0, 0, p.stat().st_mtime)

    return sorted(files, key=sort_key)[-1]


def resolve_release(
    cfg_path: Path,
    image_name: str,
    image_override: str,
    release_file: str,
    version: str,
) -> tuple[str, str]:
    """
    Decide qué digest deployar (promote). Devuelve (immutable_ref, version).

    Prioridad:
    1) --image (version desconocida -> "")
    2) --release-file
    3) --version vX.Y.Z  -> ops/releases/<image>_<version>.txt
    4) último archivo en ops/releases/
    """
    if image_override.strip():
        return image_override.strip(), ""

    if release_file.strip():
        p = Path(release_file)
        if not p.exists():
            raise SystemExit(f"Release file not found: {p}")
        return p.read_text().strip(), version_from_release_file(p, image_name)

    releases_dir = cfg_path.parent / "releases"

    if version.strip():
        p = releases_dir / f"{image_name}_{version.strip()}.txt"
        if not p.exists():
            available = (
                ", ".join(sorted(f.name for f in releases_dir.glob(f"{image_name}_*.txt")))
                or "(ninguno)"
            )
            raise SystemExit(f"No existe release para {version}: {p}\nDisponibles: {available}")
        return p.read_text().strip(), version.strip()

    latest = pick_latest_release(releases_dir, image_name)
    return latest.read_text().strip(), version_from_release_file(latest, image_name)


def version_from_release_file(p: Path, image_name: str) -> str:
    """ops/releases/<image>_<version>.txt -> <version>"""
    stem = p.stem
    prefix = f"{image_name}_"
    return stem[len(prefix) :] if stem.startswith(prefix) else ""


def deploy_job(
    project: str,
    region: str,
    name: str,
    service_account: str,
    immutable: str,
    job_cfg: dict[str, Any],
    env_csv: str,
    secrets_csv: str,
) -> None:
    """
    Deploy a Cloud Run Job:
    - Si existe: update
    - Si no: create
    Aplica recursos, env vars, y secrets.
    """
    cpu = str(job_cfg.get("cpu", "1"))
    memory = str(job_cfg.get("memory", "512Mi"))
    timeout = str(job_cfg.get("timeout", "3600s"))
    max_retries = str(job_cfg.get("max_retries", 0))
    tasks = str(job_cfg.get("tasks", 1))
    # Override de entrypoint (para reusar una imagen con otro comando, ej. un runner
    # que comparte la imagen de la API). command = ENTRYPOINT, args = CMD (CSV).
    command = str(job_cfg.get("command", ""))
    args_csv = str(job_cfg.get("args", ""))

    # Detectar si el job existe
    if exists(
        [
            "gcloud",
            "run",
            "jobs",
            "describe",
            name,
            "--region",
            region,
            "--project",
            project,
        ]
    ):
        cmd = ["gcloud", "run", "jobs", "update", name]
        secrets_flag = "--update-secrets"
    else:
        cmd = ["gcloud", "run", "jobs", "create", name]
        secrets_flag = "--set-secrets"

    cmd += [
        "--project",
        project,
        "--region",
        region,
        "--image",
        immutable,
        "--service-account",
        service_account,
        "--cpu",
        cpu,
        "--memory",
        memory,
        "--task-timeout",
        timeout,
        "--max-retries",
        max_retries,
        "--tasks",
        tasks,
    ]

    # Override de entrypoint/args si la config lo define (ej. runner que reusa la imagen API)
    if command:
        cmd += ["--command", command]
    if args_csv:
        cmd += ["--args", args_csv]

    # env vars: siempre con update (gcloud maneja merge)
    if env_csv:
        cmd += ["--update-env-vars", env_csv]

    # secrets: flag depende de create/update
    if secrets_csv:
        cmd += [secrets_flag, secrets_csv]

    run(cmd)


def deploy_service(
    project: str,
    region: str,
    name: str,
    service_account: str,
    immutable: str,
    svc_cfg: dict[str, Any],
    env_csv: str,
    secrets_csv: str,
) -> None:
    """
    Deploy a Cloud Run Service (stateless web/api).
    """
    cpu = str(svc_cfg.get("cpu", "1"))
    memory = str(svc_cfg.get("memory", "512Mi"))
    timeout = str(svc_cfg.get("timeout", "60s"))
    min_instances = str(svc_cfg.get("min_instances", 0))
    max_instances = str(svc_cfg.get("max_instances", 10))
    concurrency = str(svc_cfg.get("concurrency", 80))
    allow_public = bool(svc_cfg.get("allow_unauthenticated", False))

    cmd = [
        "gcloud",
        "run",
        "deploy",
        name,
        "--project",
        project,
        "--region",
        region,
        "--image",
        immutable,
        "--service-account",
        service_account,
        "--cpu",
        cpu,
        "--memory",
        memory,
        "--timeout",
        timeout,
        "--min-instances",
        min_instances,
        "--max-instances",
        max_instances,
        "--concurrency",
        concurrency,
        "--quiet",
    ]

    # Web pública que la UI llama desde el browser: sin identidad GCP (evita 403).
    # La seguridad es el JWT en la app, no el IAM de Cloud Run.
    if allow_public:
        cmd.append("--allow-unauthenticated")

    if env_csv:
        cmd += ["--update-env-vars", env_csv]
    if secrets_csv:
        cmd += ["--update-secrets", secrets_csv]

    run(cmd)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Deploy: promote a digest to Cloud Run.")
    ap.add_argument("--env", required=True, help="Environment prefix (prod, test, etc.)")
    ap.add_argument("--image", default="", help="Optional immutable image ref: image@sha256:...")
    ap.add_argument("--release-file", default="", help="Optional path to ops/releases/<...>.txt")
    ap.add_argument(
        "--version",
        default="",
        help="Deploy una versión exacta (vX.Y.Z) desde ops/releases/. Sirve para rollback.",
    )
    ap.add_argument(
        "--component",
        default="",
        help="Monorepo: componente (api, ui, ...). Usa ops/<component>/<env>.config.toml.",
    )
    args = ap.parse_args()

    # Convención: ops/<env>.config.toml, o ops/<component>/<env>.config.toml
    ops_dir = Path("ops") / args.component if args.component else Path("ops")
    cfg_path = ops_dir / f"{args.env}.config.toml"
    if not cfg_path.exists():
        raise SystemExit(f"Config not found: {cfg_path}")

    cfg = load_toml(cfg_path)

    # ---- Parse config ----
    project = cfg["gcp"]["project"]
    region = cfg["gcp"]["region"]

    image_name = cfg["image"]["name"]

    runtime = cfg["runtime"]
    runtime_type = runtime["type"]  # "job" o "service"
    runtime_name = runtime["name"]
    service_account = runtime["service_account"]

    # ---- Resolve which digest to deploy ----
    immutable, version = resolve_release(
        cfg_path, image_name, args.image, args.release_file, args.version
    )

    # ---- Set gcloud context ----
    run(["gcloud", "config", "set", "project", project])
    run(["gcloud", "config", "set", "run/region", region])

    # ---- Prepare env/secrets ----
    env_vars = dict(cfg.get("env", {}))
    if version:
        env_vars["APP_VERSION"] = version  # la app puede exponerla (ej. /health)
    if runtime_type == "service":
        env_vars = env_for_cloud_run_service(env_vars)  # saca PORT (reservada)
    env_csv = kv_csv(env_vars)
    secrets_csv = kv_csv(cfg.get("secrets", {}))

    print(f"==> Deploy {runtime_type} {runtime_name}")
    print(f"==> Using {immutable}" + (f" (version {version})" if version else ""))

    # ---- Deploy based on runtime.type ----
    if runtime_type == "job":
        deploy_job(
            project=project,
            region=region,
            name=runtime_name,
            service_account=service_account,
            immutable=immutable,
            job_cfg=cfg.get("job", {}),
            env_csv=env_csv,
            secrets_csv=secrets_csv,
        )
    elif runtime_type == "service":
        deploy_service(
            project=project,
            region=region,
            name=runtime_name,
            service_account=service_account,
            immutable=immutable,
            svc_cfg=cfg.get("service", {}),
            env_csv=env_csv,
            secrets_csv=secrets_csv,
        )
    else:
        raise SystemExit("runtime.type must be 'job' or 'service'")

    print("==> OK")


if __name__ == "__main__":
    main()
