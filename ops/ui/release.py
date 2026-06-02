#!/usr/bin/env python3
"""
ops/ui/release.py

Release = build + push + record digest.

UI (Next.js) requiere inyectar NEXT_PUBLIC_* en build-time.
Esto se logra leyendo [build_args] del TOML de ops/ui y pasando esos build args
al docker build.
"""

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict


def load_toml(path: Path) -> Dict[str, Any]:
    """Carga TOML en dict (stdlib en 3.11+, fallback tomli en 3.10)."""
    try:
        import tomllib  # Python 3.11+

        return tomllib.loads(path.read_text("utf-8"))
    except ModuleNotFoundError:
        import tomli  # Python 3.10

        return tomli.loads(path.read_text("utf-8"))


SEMVER_RE = re.compile(r"^v\d+\.\d+\.\d+$")


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def out(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def git_version(version_override: str | None = None) -> str:
    if version_override and version_override.strip():
        return version_override.strip()
    try:
        tags = out(["git", "tag", "--points-at", "HEAD"]).splitlines()
    except Exception:
        tags = []
    semver = next((t for t in tags if SEMVER_RE.match(t)), "")
    sha = out(["git", "rev-parse", "--short", "HEAD"])
    return semver or f"sha-{sha}"


def create_and_push_tag(version: str) -> None:
    if not SEMVER_RE.match(version):
        raise SystemExit(f"Version must be semver (vX.Y.Z), got: {version}")
    run(["git", "tag", version])
    run(["git", "push", "origin", version])


def ensure_artifact_repo(project: str, region: str, repo: str) -> None:
    try:
        run(
            [
                "gcloud",
                "artifacts",
                "repositories",
                "describe",
                repo,
                "--location",
                region,
                "--project",
                project,
            ]
        )
    except subprocess.CalledProcessError:
        run(
            [
                "gcloud",
                "artifacts",
                "repositories",
                "create",
                repo,
                "--repository-format=docker",
                "--location",
                region,
                "--description",
                "Repo imágenes (managed by ops scripts)",
                "--project",
                project,
            ]
        )


def build_and_push(tagged_ref: str, context: str, dockerfile: str, build_args: Dict[str, str]) -> None:
    """
    Build + push con Cloud Build.

    Always usa config temporal cuando:
    - hay build_args (para inyectar NEXT_PUBLIC_*)
    - dockerfile es distinto de Dockerfile
    """
    dockerfile = (dockerfile or "Dockerfile").strip()

    if not build_args and dockerfile == "Dockerfile":
        run(["gcloud", "builds", "submit", "--tag", tagged_ref, context])
        return

    build_arg_flags: list[str] = []
    for k, v in build_args.items():
        build_arg_flags += ["--build-arg", f"{k}={v}"]

    docker_args = ["build"] + build_arg_flags + ["-f", dockerfile, "-t", tagged_ref, "."]
    docker_args_yaml = "\n".join(f"      - '{a}'" for a in docker_args)

    cloudbuild_content = (
        "steps:\n"
        "  - name: 'gcr.io/cloud-builders/docker'\n"
        "    args:\n"
        f"{docker_args_yaml}\n"
        "images:\n"
        f"  - '{tagged_ref}'\n"
        "options:\n"
        "  logging: CLOUD_LOGGING_ONLY\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
        dir=".",
        prefix="_cloudbuild_tmp_",
    ) as f:
        tmp_path = f.name
        f.write(cloudbuild_content)

    try:
        run(["gcloud", "builds", "submit", "--config", tmp_path, context])
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Release (UI): build+push image and record digest.")
    ap.add_argument("--env", required=True, help="Environment prefix (prod, test, etc.)")
    ap.add_argument("--version", default="", help="Version for image tag (e.g. v0.1.1). Creates git tag.")
    args = ap.parse_args()

    cfg_path = Path(f"ops/ui/{args.env}.config.toml")
    if not cfg_path.exists():
        raise SystemExit(f"Config not found: {cfg_path}")

    cfg = load_toml(cfg_path)

    project = cfg["gcp"]["project"]
    region = cfg["gcp"]["region"]
    repo = cfg["gcp"]["artifact_repo"]

    image_name = cfg["image"]["name"]
    context = cfg["image"].get("context", ".")
    dockerfile = cfg["image"].get("dockerfile", "Dockerfile.ui")

    build_args: Dict[str, str] = {str(k): str(v) for k, v in cfg.get("build_args", {}).items()}

    version = git_version(version_override=args.version or None)
    if args.version.strip():
        print(f"==> Creating and pushing git tag {version}")
        create_and_push_tag(version)

    ar_host = f"{region}-docker.pkg.dev"
    tagged_ref = f"{ar_host}/{project}/{repo}/{image_name}:{version}"

    releases_dir = cfg_path.parent / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)

    run(["gcloud", "config", "set", "project", project])
    run(["gcloud", "auth", "configure-docker", ar_host, "-q"])
    ensure_artifact_repo(project, region, repo)

    print(f"==> Building release: {tagged_ref}")
    if build_args:
        print(f"==> With build_args: {list(build_args.keys())}")

    build_and_push(tagged_ref, context=context, dockerfile=dockerfile, build_args=build_args)

    digest = out(
        [
            "gcloud",
            "artifacts",
            "docker",
            "images",
            "describe",
            tagged_ref,
            "--format=value(image_summary.digest)",
        ]
    )
    immutable_ref = f"{ar_host}/{project}/{repo}/{image_name}@{digest}"

    release_file = releases_dir / f"{image_name}_{version}.txt"
    release_file.write_text(immutable_ref + "\n")

    print("==> OK")
    print("env:", args.env)
    print("version:", version)
    print("tagged:", tagged_ref)
    print("immutable:", immutable_ref)
    print("release_file:", str(release_file))


if __name__ == "__main__":
    main()

