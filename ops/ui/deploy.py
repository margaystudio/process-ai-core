#!/usr/bin/env python3
"""
ops/ui/deploy.py

Deploy/Promote = tomar un artefacto ya construido (digest) y aplicarlo al runtime.

Para UI es común permitir invocación sin auth a nivel Cloud Run.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict


def load_toml(path: Path) -> Dict[str, Any]:
    try:
        import tomllib

        return tomllib.loads(path.read_text("utf-8"))
    except ModuleNotFoundError:
        import tomli

        return tomli.loads(path.read_text("utf-8"))


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def exists(cmd: list[str]) -> bool:
    return subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def kv_csv(d: Dict[str, Any]) -> str:
    """Convierte dict a formato esperado por gcloud para flags tipo --update-env-vars."""
    if not d:
        return ""
    pairs = [f"{k}={v}" for k, v in d.items()]
    csv = ",".join(pairs)
    if all("," not in p for p in pairs):
        return csv
    for delim in ("@", "|", "~", "#", ";", ":"):
        if all(delim not in p for p in pairs):
            return f"^{delim}^" + delim.join(pairs)
    raise SystemExit(
        "No se pudo serializar env vars para gcloud: no hay delimitador seguro disponible para valores con comas."
    )


def env_for_cloud_run_service(env: Dict[str, Any]) -> Dict[str, Any]:
    reserved = {"PORT"}
    return {k: v for k, v in env.items() if k not in reserved}


def pick_latest_release(releases_dir: Path, image_name: str) -> Path:
    files = sorted(releases_dir.glob(f"{image_name}_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit(
            f"No release files found in {releases_dir}. Run: python ops/ui/release.py --env <env>"
        )
    return files[0]


def resolve_immutable(cfg_path: Path, image_name: str, image_override: str, release_file: str) -> str:
    if image_override.strip():
        return image_override.strip()
    if release_file.strip():
        p = Path(release_file)
        if not p.exists():
            raise SystemExit(f"Release file not found: {p}")
        return p.read_text().strip()
    releases_dir = cfg_path.parent / "releases"
    latest = pick_latest_release(releases_dir, image_name)
    return latest.read_text().strip()


def deploy_job(
    project: str,
    region: str,
    name: str,
    service_account: str,
    immutable: str,
    job_cfg: Dict[str, Any],
    env_csv: str,
    secrets_csv: str,
) -> None:
    cpu = str(job_cfg.get("cpu", "1"))
    memory = str(job_cfg.get("memory", "512Mi"))
    timeout = str(job_cfg.get("timeout", "3600s"))
    max_retries = str(job_cfg.get("max_retries", 0))
    tasks = str(job_cfg.get("tasks", 1))

    if exists(["gcloud", "run", "jobs", "describe", name, "--region", region, "--project", project]):
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

    if env_csv:
        cmd += ["--update-env-vars", env_csv]
    if secrets_csv:
        cmd += [secrets_flag, secrets_csv]
    run(cmd)


def deploy_service(
    project: str,
    region: str,
    name: str,
    service_account: str,
    immutable: str,
    svc_cfg: Dict[str, Any],
    env_csv: str,
    secrets_csv: str,
) -> None:
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

    cmd.append("--allow-unauthenticated" if allow_public else "--no-allow-unauthenticated")

    if env_csv:
        cmd += ["--update-env-vars", env_csv]
    if secrets_csv:
        cmd += ["--update-secrets", secrets_csv]

    run(cmd)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Deploy/Promote (UI): promote digest to Cloud Run.")
    ap.add_argument("--env", required=True, help="Environment prefix (prod, test, etc.)")
    ap.add_argument("--image", default="", help="Optional immutable image ref: image@sha256:...")
    ap.add_argument("--release-file", default="", help="Optional path to ops/releases/<...>.txt")
    args = ap.parse_args()

    cfg_path = Path(f"ops/ui/{args.env}.config.toml")
    if not cfg_path.exists():
        raise SystemExit(f"Config not found: {cfg_path}")

    cfg = load_toml(cfg_path)

    project = cfg["gcp"]["project"]
    region = cfg["gcp"]["region"]
    image_name = cfg["image"]["name"]

    runtime = cfg["runtime"]
    runtime_type = runtime["type"]
    runtime_name = runtime["name"]
    service_account = runtime["service_account"]

    immutable = resolve_immutable(cfg_path, image_name, args.image, args.release_file)

    run(["gcloud", "config", "set", "project", project])
    run(["gcloud", "config", "set", "run/region", region])

    env_raw: Dict[str, Any] = dict(cfg.get("env", {}))
    if runtime_type == "service":
        env_raw = env_for_cloud_run_service(env_raw)
    env_csv = kv_csv(env_raw)
    secrets_csv = kv_csv(cfg.get("secrets", {}))

    print(f"==> Deploy {runtime_type} {runtime_name}")
    print(f"==> Using {immutable}")

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

