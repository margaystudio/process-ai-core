#!/usr/bin/env python3
"""
ops/release.py

Release = build + push + record digest.

Este script implementa la mitad "Release" del esquema:
    Release (produce artefacto)  ->  Deploy/Promote (consume artefacto)

Qué hace exactamente:
1) Lee config desde: ops/{env}.config.toml  (o ops/{component}/{env}.config.toml con --component)
2) Calcula una "versión" para etiquetar la imagen:
   - Si pasás --version vX.Y.Z: usa esa, crea el tag git en HEAD y lo pushea (salvo --no-tag).
   - Si HEAD ya tiene un tag semver (vX.Y.Z, o <component>-vX.Y.Z en monorepos), usa ese.
   - Si no: usa sha-<shortsha> — SOLO permitido fuera de prod (o con --allow-sha).
3) Ejecuta build+push con Cloud Build:
      gcloud builds submit --tag <TAGGED_REF> <context>
4) Resuelve el DIGEST (sha256...) y construye el identificador inmutable:
      <image>@sha256:<digest>
5) Guarda ese identificador en un archivo de release:
      ops/[<component>/]releases/<image>_<version>.txt
   Estos archivos SE COMMITEAN (son el registro auditable versión -> digest).

Convención de tags git (norma Margay):
- Repo con 1 deployable:        v1.4.2
- Monorepo (api/ui/...):        api-v1.4.2 / ui-v0.3.0  (usar --component api)
  El tag de imagen queda sin prefijo (la imagen ya distingue: margay-oms-api:v1.4.2).

Uso:
    python ops/release.py --env prod --version v0.1.1        # releasea y taggea git
    python ops/release.py --env prod                          # requiere tag semver en HEAD
    python ops/release.py --env test                          # permite sha-<shortsha>
    python ops/release.py --env prod --component api --version v0.2.0   # monorepo
    python ops/release.py --env prod --version v0.1.1 --no-tag          # CI: el tag ya existe

En GitHub Actions (CI), el flujo es: push del tag -> workflow corre
    python ops/release.py --env prod --version ${GITHUB_REF_NAME#*-} --component <c> --no-tag

Requisitos:
- Python 3.10+ (si es 3.10 necesita `tomli`)
- gcloud instalado y autenticado (local) o Workload Identity Federation (CI)
- git
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


# -----------------------------
# TOML loader (compatible 3.10+)
# -----------------------------
def load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib  # Python 3.11+

        return tomllib.loads(path.read_text("utf-8"))
    except ModuleNotFoundError:
        import tomli  # Python 3.10

        return tomli.loads(path.read_text("utf-8"))


# Tag semver: v1.2.3
SEMVER_RE = re.compile(r"^v\d+\.\d+\.\d+$")


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def out(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


# -----------------------------
# Versionado
# -----------------------------
def head_semver(tag_prefix: str) -> str:
    """Devuelve la versión (vX.Y.Z) si HEAD tiene tag '{prefix}vX.Y.Z', o ''."""
    try:
        tags = out(["git", "tag", "--points-at", "HEAD"]).splitlines()
    except Exception:
        tags = []
    for t in tags:
        if t.startswith(tag_prefix) and SEMVER_RE.match(t[len(tag_prefix) :]):
            return t[len(tag_prefix) :]
    return ""


def resolve_version(version_override: str, tag_prefix: str, env: str, allow_sha: bool) -> str:
    """
    Decide la versión del release (norma Margay):
    - --version vX.Y.Z manda.
    - Tag semver en HEAD ({prefix}vX.Y.Z).
    - Fallback sha-<shortsha>: solo fuera de prod, o con --allow-sha.
    """
    if version_override.strip():
        v = version_override.strip()
        if not SEMVER_RE.match(v):
            raise SystemExit(f"--version debe ser semver (vX.Y.Z), recibido: {v}")
        return v

    v = head_semver(tag_prefix)
    if v:
        return v

    sha = out(["git", "rev-parse", "--short", "HEAD"])
    if env == "prod" and not allow_sha:
        raise SystemExit(
            "HEAD no tiene tag semver y env=prod.\n"
            f"Norma: los releases de prod llevan versión. Opciones:\n"
            f"  python ops/release.py --env prod --version vX.Y.Z   (crea y pushea el tag)\n"
            f"  o taggeá antes: git tag {tag_prefix}vX.Y.Z && git push origin {tag_prefix}vX.Y.Z\n"
            f"  (escape: --allow-sha para releasear sha-{sha}, no recomendado)"
        )
    return f"sha-{sha}"


def ensure_clean_tree() -> None:
    """Prohíbe releasear con cambios TRACKEADOS sin commitear (el build no reflejaría el commit).

    Ignora untracked (-uno): en CI, la action de auth de Google deja un
    gha-creds-*.json en el workspace que no es un cambio real del repo.
    """
    dirty = out(["git", "status", "--porcelain", "-uno"])
    if dirty:
        raise SystemExit(
            "Working tree con cambios sin commitear. Commiteá (o stasheá) antes de releasear:\n"
            + dirty
        )


def create_and_push_tag(version: str, tag_prefix: str) -> None:
    tag = f"{tag_prefix}{version}"
    existing = out(["git", "tag", "--list", tag])
    if existing:
        # El tag ya existe: verificar que apunte a HEAD
        head = out(["git", "rev-parse", "HEAD"])
        target = out(["git", "rev-list", "-n", "1", tag])
        if head != target:
            raise SystemExit(f"El tag {tag} ya existe y apunta a otro commit. Elegí otra versión.")
        print(f"==> Tag {tag} ya existe en HEAD, no se recrea")
        return
    run(["git", "tag", tag])
    run(["git", "push", "origin", tag])


# -----------------------------
# Artifact Registry: ensure repo
# -----------------------------
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


# -----------------------------
# Cloud Build: simple vs build_args
# -----------------------------
def build_and_push(
    tagged_ref: str,
    context: str,
    build_args: dict[str, str],
    dockerfile: str = "Dockerfile",
) -> None:
    """
    Caso simple (sin build_args y Dockerfile por defecto): usa el shorthand --tag.
    Con build_args (ej. NEXT_PUBLIC_* de Next.js) o un Dockerfile no estándar (ej.
    monorepos con Dockerfile.api / Dockerfile.ui): genera un cloudbuild.yaml temporal
    FUERA del repo (system temp, para no ensuciar ni arriesgar commitear credenciales).
    """
    dockerfile = (dockerfile or "Dockerfile").strip()
    if not build_args and dockerfile == "Dockerfile":
        run(["gcloud", "builds", "submit", "--tag", tagged_ref, context])
        return

    docker_args = ["build"]
    for k, v in build_args.items():
        docker_args += ["--build-arg", f"{k}={v}"]
    docker_args += ["-f", dockerfile, "-t", tagged_ref, "."]
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
    # dir=system-temp (no el repo): un build interrumpido no deja basura versionable.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, prefix="margay_cloudbuild_"
    ) as f:
        tmp_path = f.name
        f.write(cloudbuild_content)
    try:
        run(["gcloud", "builds", "submit", "--config", tmp_path, context])
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Release: build+push image and record digest.")
    ap.add_argument("--env", required=True, help="Environment prefix (prod, test, etc.)")
    ap.add_argument(
        "--version",
        default="",
        help="Versión semver (vX.Y.Z). Crea y pushea el tag git salvo --no-tag.",
    )
    ap.add_argument(
        "--component",
        default="",
        help="Monorepo: componente (api, ui, ...). Usa ops/<component>/<env>.config.toml y tag '<component>-vX.Y.Z'.",
    )
    ap.add_argument(
        "--no-tag",
        action="store_true",
        help="No crear/pushear tag git (CI: el tag ya existe).",
    )
    ap.add_argument(
        "--allow-sha",
        action="store_true",
        help="Permitir release sha-<shortsha> en prod (escape hatch).",
    )
    args = ap.parse_args()

    # Convención: ops/<env>.config.toml, o ops/<component>/<env>.config.toml
    ops_dir = Path("ops") / args.component if args.component else Path("ops")
    cfg_path = ops_dir / f"{args.env}.config.toml"
    if not cfg_path.exists():
        raise SystemExit(f"Config not found: {cfg_path}")

    cfg = load_toml(cfg_path)

    project = cfg["gcp"]["project"]
    region = cfg["gcp"]["region"]
    repo = cfg["gcp"]["artifact_repo"]

    image_name = cfg["image"]["name"]
    context = cfg["image"].get("context", ".")

    # build_args: se hornean en build-time (ej. NEXT_PUBLIC_* de Next.js)
    build_args = {str(k): str(v) for k, v in cfg.get("build_args", {}).items()}
    # dockerfile: monorepos con Dockerfile.api / Dockerfile.ui (default: Dockerfile)
    dockerfile = cfg["image"].get("dockerfile", "Dockerfile")

    tag_prefix = f"{args.component}-" if args.component else ""

    # ---- Versión ----
    ensure_clean_tree()
    version = resolve_version(args.version, tag_prefix, args.env, args.allow_sha)
    if args.version.strip() and not args.no_tag:
        print(f"==> Creating and pushing git tag {tag_prefix}{version}")
        create_and_push_tag(version, tag_prefix)

    ar_host = f"{region}-docker.pkg.dev"
    tagged_ref = f"{ar_host}/{project}/{repo}/{image_name}:{version}"

    releases_dir = cfg_path.parent / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)

    # ---- gcloud setup ----
    run(["gcloud", "config", "set", "project", project])
    run(["gcloud", "auth", "configure-docker", ar_host, "-q"])
    ensure_artifact_repo(project, region, repo)

    # ---- Build+push con Cloud Build ----
    print(f"==> Building release: {tagged_ref}")
    if build_args:
        print(f"==> With build_args: {list(build_args.keys())}")
    if dockerfile != "Dockerfile":
        print(f"==> With dockerfile: {dockerfile}")
    build_and_push(tagged_ref, context, build_args, dockerfile)

    # ---- Resolver digest (inmutable) ----
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

    # ---- Outputs para GitHub Actions ----
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"version={version}\n")
            f.write(f"immutable={immutable_ref}\n")
            f.write(f"release_file={release_file}\n")

    print("==> OK")
    print("env:", args.env)
    print("version:", version)
    print("tagged:", tagged_ref)
    print("immutable:", immutable_ref)
    print("release_file:", str(release_file))
    print("\nRecordá commitear el release file (registro versión -> digest):")
    print(f"  git add {release_file} && git commit -m 'release: {image_name} {version}'")


if __name__ == "__main__":
    main()
