from __future__ import annotations

"""
process_ai_core.media
=====================

Este módulo se encarga de **enriquecer insumos crudos (RawAsset)** para que puedan
ser usados por el motor de documentación de procesos.

Responsabilidades principales
------------------------------
- Transcribir audio.
- Procesar video:
    * extraer audio
    * transcribir con timestamps
    * inferir pasos con IA
    * extraer frames candidatos
    * seleccionar la mejor captura por paso con IA
- Manejar imágenes sueltas como evidencia visual.
- Preparar estructuras auxiliares para el render final (Markdown / PDF).

Salida clave
------------
La función principal `enrich_assets` devuelve **tres estructuras**:
1. enriched_assets:
   Lista de EnrichedAsset → se usa para construir el prompt del LLM.
2. images_by_step:
   Dict[int, List[dict]] → capturas inferidas desde video, agrupadas por paso.
3. evidence_images:
   List[dict] → imágenes sueltas aportadas por el usuario (evidencia visual).
"""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .config import get_settings
from .llm_client import (
    plan_steps_from_transcript_segments,
    select_best_frame_for_step,
    transcribe_audio,
    transcribe_audio_with_timestamps,
)
from .domain_models import EnrichedAsset, RawAsset

logger = logging.getLogger(__name__)


# ============================================================
# Helpers de filesystem y ffmpeg
# ============================================================

def _ensure_output_assets_dir(output_base: Path | None = None) -> Path:
    """
    Asegura la existencia del directorio base donde se guardan
    todos los assets generados automáticamente.

    Args:
        output_base: Directorio base opcional. Si se especifica, los assets
                     se copian ahí. Si es None, usa settings.output_dir/assets/

    Returns:
        Path al directorio de assets
    """
    if output_base:
        assets_dir = output_base / "assets"
    else:
        settings = get_settings()
        assets_dir = Path(settings.output_dir) / settings.assets_dir
    
    assets_dir.mkdir(parents=True, exist_ok=True)
    return assets_dir


def _ffmpeg_convert_audio_to_mp3(input_path: Path, output_path: Path) -> None:
    """
    Convierte un archivo de audio a MP3 usando ffmpeg.
    
    Útil para convertir formatos no soportados por OpenAI Whisper (como .ogg/.opus)
    a un formato compatible (.mp3).
    
    Args:
        input_path: Ruta al archivo de audio original.
        output_path: Ruta de salida del archivo MP3.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-acodec",
        "libmp3lame",
        "-ar",
        "16000",  # Sample rate compatible con Whisper
        "-ac",
        "1",  # Mono
        "-q:a",
        "2",  # Calidad alta
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _ffmpeg_extract_audio(video_path: Path, out_audio: Path) -> None:
    """
    Extrae el audio de un video usando ffmpeg.

    Convenciones:
    - Audio mono
    - Sample rate 16kHz
    - Codec AAC

    Args:
        video_path: Ruta al video original.
        out_audio: Ruta de salida del archivo de audio.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "aac",
        str(out_audio),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def pdf_text_or_ocr(contenido, data: bytes, nombre: str) -> str:
    """
    Texto de un PDF ya extraído, con caída a OCR si el PDF está escaneado.

    Recibe el `PdfContent` en vez de extraerlo para que el llamador que además
    necesita las imágenes no tenga que abrir el PDF dos veces.

    La caída a OCR es una decisión POR CONTENIDO —el PDF es una foto y no tiene
    texto que extraer—, no por qué extractor usar. Por eso sobrevive a la
    unificación de motores: no es un segundo camino para el mismo insumo, es el
    único camino posible para un insumo distinto.
    """
    if contenido.looks_scanned:
        return _ocr_pdf_fallback(data, nombre, contenido.text)
    return contenido.text


def _extract_text_from_document(path: Path) -> str:
    """
    Extrae texto de un archivo de documento según su extensión.
    Soporta: .txt, .md (UTF-8), .pdf (PyMuPDF), .docx (python-docx).
    .doc (Word binario) no está soportado; usar .docx.

    Por qué PyMuPDF y no pypdf para los PDF
    ----------------------------------------
    Es el mismo motor que ubica las imágenes (`pdf_images.extract_pdf_content`),
    y tiene que serlo: si el texto lo extrajera uno y las posiciones las diera
    otro, no habría garantía de que la imagen quede donde el texto dice.

    Antes convivían los dos, y la consecuencia era peor que la redundancia: el
    MISMO PDF producía texto derivado distinto según si tenía o no una imagen que
    pasara el filtro de tamaño. Una captura de 55 pt iba por pypdf y una de 57 pt
    por PyMuPDF, y los dos no coinciden en espaciados, ligaduras ni manejo de
    columnas. Un umbral de tamaño de imagen decidiendo qué extractor de texto se
    usa es una costura de determinismo en la ingesta — y `content_html` es entrada
    congelada del artefacto de auditoría, de la misma clase que la versión del
    motor de render, las fuentes o el conversor de markdown.
    """
    ext = path.suffix.lower()
    if ext in (".txt", ".md"):
        return path.read_text(encoding="utf-8")
    if ext == ".pdf":
        from .pdf_images import extract_pdf_content

        data = path.read_bytes()
        return pdf_text_or_ocr(extract_pdf_content(data, nombre=path.name), data, path.name)
    if ext == ".docx":
        from docx import Document as DocxDocument
        doc = DocxDocument(path)
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(parts)
    if ext == ".doc":
        raise ValueError(
            "El formato .doc (Word antiguo) no está soportado. "
            "Guardá el archivo como .docx (Word actual) o exportá a PDF."
        )
    raise ValueError(
        f"Extensión de documento no soportada para extracción de texto: {ext or '(sin extensión)'}"
    )


def _ocr_pdf_fallback(data: bytes, nombre: str, texto_extraido: str) -> str:
    """
    Intenta OCR sobre un PDF (presuntamente escaneado) usando el OCR provider
    del repo, que rasteriza las páginas con PyMuPDF y las pasa por Tesseract.

    Degradación: si no hay OCR disponible (binario de Tesseract ausente, sin
    configurar, o cualquier fallo), loguea un warning y devuelve el texto que ya
    se había extraído (aunque sea vacío). Nunca lanza: el import no debe romperse
    por OCR.

    Args:
        data: Bytes del PDF.
        nombre: Nombre del archivo, para los logs.
        texto_extraido: Texto que devolvió la extracción normal (fallback si el
            OCR falla).

    Returns:
        Texto del OCR si tuvo éxito; si no, el texto ya extraído.
    """
    try:
        from .ai.factory import get_ocr_provider

        provider = get_ocr_provider()
        ocr_text = provider.extract_text(data, content_type="application/pdf")
        if ocr_text and ocr_text.strip():
            logger.info("PDF escaneado '%s': OCR extrajo %d caracteres.", nombre, len(ocr_text))
            return ocr_text
        logger.warning(
            "PDF escaneado '%s': el OCR no devolvió texto; se usa el texto extraído.", nombre
        )
        return texto_extraido
    except Exception as exc:  # noqa: BLE001 — OCR es best-effort, jamás rompe el import
        logger.warning(
            "PDF escaneado '%s': OCR no disponible (%s); se usa el texto extraído "
            "(puede estar vacío).",
            nombre,
            exc,
        )
        return texto_extraido


#: Marca de origen de un asset de imagen que salió de un PDF de entrada. Es lo
#: que distingue a las imágenes "asignables a un paso" de la evidencia suelta que
#: aportó el usuario (que ya tiene su propia sección en el documento).
ORIGEN_PDF = "pdf"


def _promote_pdf_images(
    asset: RawAsset,
    pdf_path: Path,
    output_assets: Path,
) -> List[EnrichedAsset]:
    """
    Convierte las imágenes de contenido de un PDF de entrada en assets del run.

    Cada imagen se escribe bajo `assets/pdf_{asset_id}/` (que es de donde las lee
    el renderer y lo que `sync_run_dir_to_storage` sube a object storage) y viaja
    con su contexto textual: el texto que la rodeaba en el PDF, que es lo que le
    permite al modelo decidir qué paso ilustra.

    Best-effort: si algo falla, el PDF sigue aportando su texto y el run continúa
    sin sus imágenes.
    """
    from .pdf_images import describe_image, extract_pdf_images, figure_title

    try:
        candidatas = extract_pdf_images(pdf_path.read_bytes(), nombre=pdf_path.name)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "No se pudieron extraer las imágenes de '%s' (%s); el PDF aporta solo texto.",
            pdf_path.name, exc,
        )
        return []

    if not candidatas:
        return []

    destino = output_assets / f"pdf_{asset.id}"
    destino.mkdir(parents=True, exist_ok=True)

    salida: List[EnrichedAsset] = []
    for imagen in candidatas:
        nombre_archivo = imagen.filename(asset.id)
        (destino / nombre_archivo).write_bytes(imagen.data)
        render_path = f"assets/{destino.name}/{nombre_archivo}"

        descripcion = describe_image(imagen, nombre=pdf_path.name)
        titulo = figure_title(imagen, descripcion)
        img_id = f"{asset.id}_img{imagen.order:02d}"

        salida.append(
            EnrichedAsset(
                id=img_id,
                kind="image",
                raw_path=str(destino / nombre_archivo),
                metadata={
                    "titulo": titulo,
                    "origen": ORIGEN_PDF,
                    "source_document": asset.id,
                    "pagina": str(imagen.page),
                    "contexto": imagen.context,
                    "descripcion": descripcion.descripcion if descripcion else "",
                    "path": render_path,
                },
                # Lo que ve el modelo: dónde estaba la imagen y qué la rodea. La
                # ruta va igual porque el resumen de activos la referencia, pero
                # el modelo NO escribe markdown de imágenes (ver prompts.py).
                extracted_text=(
                    f"[IMAGEN:{img_id}] titulo='{titulo}' archivo='{render_path}' "
                    f"origen='{pdf_path.name}' pagina={imagen.page}"
                    + (f"\nContexto en el documento: {imagen.context}" if imagen.context else "")
                    + (
                        f"\nQué muestra (descripción automática, sin validar): "
                        f"{descripcion.descripcion}"
                        if descripcion and descripcion.descripcion
                        else ""
                    )
                ),
            )
        )

    print(f"🖼️  {pdf_path.name}: {len(salida)} imagen(es) promovidas a assets del run")
    return salida


def _ffmpeg_frame_at_time(video_path: Path, t_s: float, out_img: Path) -> None:
    """
    Extrae un frame de un video en un timestamp específico.

    Args:
        video_path: Ruta al video.
        t_s: Tiempo en segundos desde el inicio del video.
        out_img: Ruta de salida de la imagen PNG.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{t_s:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(out_img),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _pick_candidate_times(start_s: float, end_s: float, n: int = 3) -> List[float]:
    """
    Selecciona timestamps candidatos dentro de un intervalo [start_s, end_s].

    Estrategia:
    - Si el intervalo es muy corto, devuelve el punto medio.
    - Si es más largo, evita bordes y genera N puntos equiespaciados.

    Args:
        start_s: Inicio del segmento (segundos).
        end_s: Fin del segmento (segundos).
        n: Cantidad de timestamps a generar.

    Returns:
        Lista de tiempos (en segundos) >= 0.
    """
    if end_s < start_s:
        start_s, end_s = end_s, start_s

    dur = max(0.0, end_s - start_s)
    if dur < 0.75:
        return [max(0.0, start_s + dur / 2.0)]

    pad = min(1.0, dur * 0.2)
    a = start_s + pad
    b = end_s - pad
    if b <= a:
        return [max(0.0, start_s + dur / 2.0)]

    if n <= 1:
        return [max(0.0, (a + b) / 2.0)]

    step = (b - a) / (n - 1)
    return [max(0.0, a + i * step) for i in range(n)]


def _join_segments_text(segments: List[Dict[str, Any]]) -> str:
    """
    Concatena texto de segmentos de transcripción.

    Args:
        segments: Lista de dicts con clave "text".

    Returns:
        Texto concatenado, separado por espacios.
    """
    out: List[str] = []
    for s in segments:
        t = str(s.get("text", "")).strip()
        if t:
            out.append(t)
    return " ".join(out).strip()


# ============================================================
# API principal
# ============================================================

def enrich_assets(
    raw_assets: List[RawAsset],
    output_base: Path | None = None,
) -> tuple[List[EnrichedAsset], Dict[int, List[Dict[str, str]]], List[Dict[str, str]]]:
    """
    Enriquecimiento central de assets.

    Qué hace según el tipo:
    -----------------------
    - audio:
        * Transcribe audio completo.
    - text:
        * Lee archivo de texto.
    - image:
        * Copia a output/assets/evidence/
        * Se trata como evidencia visual (no como paso).
    - video:
        * Copia video a output/assets/
        * Extrae audio
        * Transcribe con timestamps
        * IA infiere pasos
        * Extrae frames candidatos por paso
        * IA selecciona el mejor frame por paso

    Returns:
        enriched_assets:
            Lista de EnrichedAsset para construir el prompt del LLM.
        images_by_step:
            Dict { paso_n: [ {"path": "assets/...", "title": "..."} ] }
            Capturas inferidas desde video.
        evidence_images:
            Lista de {"path": "...", "title": "..."} para sección "Evidencia visual".
    """
    enriched: List[EnrichedAsset] = []
    images_by_step: Dict[int, List[Dict[str, str]]] = {}
    evidence_images: List[Dict[str, str]] = []

    settings = get_settings()
    output_assets = _ensure_output_assets_dir(output_base)
    evidence_dir = output_assets / settings.evidence_dir
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # Debug de conteo inicial
    counts = {"audio": 0, "video": 0, "image": 0, "text": 0}
    for a in raw_assets:
        counts[a.kind] = counts.get(a.kind, 0) + 1
    print(
        "📦 Activos detectados: "
        f"audio={counts.get('audio', 0)} | "
        f"video={counts.get('video', 0)} | "
        f"image={counts.get('image', 0)} | "
        f"text={counts.get('text', 0)}"
    )

    for a in raw_assets:
        path = a.path_or_url

        # ----------------------------
        # AUDIO
        # ----------------------------
        if a.kind == "audio":
            override = (a.metadata.get("extracted_text_override") or "").strip()
            extracted = override if override else transcribe_audio(path)
            print(f"🎧 Transcripción de {a.id}:\n{extracted}\n{'-'*60}")
            enriched.append(
                EnrichedAsset(
                    id=a.id,
                    kind=a.kind,
                    raw_path=path,
                    metadata=a.metadata,
                    extracted_text=extracted,
                )
            )
            continue

        # ----------------------------
        # TEXT (incluye .txt, .md, .pdf, .docx)
        # ----------------------------
        if a.kind == "text":
            text_path = Path(path)
            if not text_path.exists():
                raise FileNotFoundError(f"No se encontró el archivo de texto: {text_path}")
            override = (a.metadata.get("extracted_text_override") or "").strip()
            extracted = override if override else _extract_text_from_document(text_path)
            enriched.append(
                EnrichedAsset(
                    id=a.id,
                    kind=a.kind,
                    raw_path=path,
                    metadata=a.metadata,
                    extracted_text=extracted,
                )
            )
            # Un PDF puede ser UNA PARTE del insumo, no el procedimiento entero:
            # el manual del POS junto a la entrevista y las notas. Sus capturas
            # son la evidencia de pasos concretos, así que se promueven a assets
            # de imagen del run. De ahí en adelante ya funciona todo lo que
            # existe: el modelo dice qué paso ilustra cada una, y el pipeline de
            # assets las inserta.
            if text_path.suffix.lower() == ".pdf":
                enriched.extend(_promote_pdf_images(a, text_path, output_assets))
            continue

        # ----------------------------
        # IMAGE (evidencia suelta)
        # ----------------------------
        if a.kind == "image":
            src = Path(path)
            if not src.exists():
                raise FileNotFoundError(f"No se encontró la imagen: {src}")

            dest = evidence_dir / f"{a.id}_{src.name}"
            shutil.copy(src, dest)

            titulo = (a.metadata.get("titulo") or src.stem).strip() or src.stem
            rel_path = f"assets/evidence/{dest.name}"

            override = (a.metadata.get("extracted_text_override") or "").strip()
            if override:
                extracted = override
            else:
                extracted = f"[IMAGEN:{a.id}] titulo='{titulo}' archivo='{rel_path}'"

            enriched.append(
                EnrichedAsset(
                    id=a.id,
                    kind=a.kind,
                    raw_path=path,
                    metadata=a.metadata,
                    extracted_text=extracted,
                )
            )

            evidence_images.append({"path": rel_path, "title": titulo})
            continue

        # ----------------------------
        # VIDEO
        # ----------------------------
        if a.kind == "video":
            src = Path(path)
            if not src.exists():
                raise FileNotFoundError(f"No se encontró el video: {src}")

            # Copiar video
            dest_video = output_assets / f"{a.id}_{src.name}"
            shutil.copy(src, dest_video)

            # Extraer audio
            dest_audio = output_assets / f"{a.id}.m4a"
            _ffmpeg_extract_audio(dest_video, dest_audio)

            # Transcripción con timestamps
            verbose = transcribe_audio_with_timestamps(str(dest_audio), granularity="segment")
            if isinstance(verbose, dict):
                segments = verbose.get("segments", []) or []
                transcript_text = str(verbose.get("text") or "").strip() or _join_segments_text(segments)
            else:
                segments = getattr(verbose, "segments", []) or []
                transcript_text = str(getattr(verbose, "text", "") or "").strip() or _join_segments_text(segments)

            print(f"🎥 Transcripción de {a.id} (desde video):\n{transcript_text}\n{'-'*60}")

            # Inferir pasos con IA
            try:
                planned_steps = plan_steps_from_transcript_segments(segments, max_steps=15)
            except Exception as e:
                planned_steps = []
                print(f"⚠️ No se pudo inferir pasos ({e}). Se continúa sin screenshots.")

            selected_images: List[Tuple[int, Path, str]] = []

            if planned_steps:
                frames_dir = output_assets / f"frames_{a.id}"
                frames_dir.mkdir(parents=True, exist_ok=True)

                print(f"🧩 Pasos inferidos para {a.id}: {len(planned_steps)}")
                for st in planned_steps:
                    if isinstance(st, dict):
                        order = int(st.get("order", 0) or 0)
                        start_s = float(st.get("start_s", 0.0) or 0.0)
                        end_s = float(st.get("end_s", start_s) or start_s)
                        summary = str(st.get("summary", "")).strip() or f"Paso {order}"
                    else:
                        order = int(getattr(st, "order", 0) or 0)
                        start_s = float(getattr(st, "start_s", 0.0) or 0.0)
                        end_s = float(getattr(st, "end_s", start_s) or start_s)
                        summary = str(getattr(st, "summary", "")).strip() or f"Paso {order}"

                    cand_times = _pick_candidate_times(start_s, end_s, n=3)
                    candidate_paths: List[str] = []

                    for i, t in enumerate(cand_times, start=1):
                        out_img = frames_dir / f"step{order:02d}_{i}.png"
                        try:
                            _ffmpeg_frame_at_time(dest_video, t, out_img)
                            candidate_paths.append(str(out_img))
                        except Exception as e:
                            print(f"⚠️ No se pudo extraer frame t={t:.2f}s (paso {order}): {e}")

                    if not candidate_paths:
                        continue

                    try:
                        choice = select_best_frame_for_step(summary, candidate_paths)
                        if isinstance(choice, dict):
                            idx = int(choice.get("selected_index", -1))
                            title = str(choice.get("title", "")).strip() or summary
                        else:
                            idx = int(getattr(choice, "selected_index", -1))
                            title = str(getattr(choice, "title", "")).strip() or summary

                        if 0 <= idx < len(candidate_paths):
                            chosen_path = Path(candidate_paths[idx])
                            selected_images.append((order, chosen_path, title))
                            print(f"🖼️  Paso {order}: seleccionado {chosen_path.name} — {title}")
                        else:
                            print(f"🖼️  Paso {order}: sin imagen seleccionada")
                    except Exception as e:
                        print(f"⚠️ No se pudo seleccionar frame con IA (paso {order}): {e}")

            # EnrichedAsset del video
            url = a.metadata.get("url", "")
            titulo = (a.metadata.get("titulo") or dest_video.stem).strip() or dest_video.stem
            extracted_video = transcript_text + (
                f"\n\n[VIDEO_REF:{a.id}] titulo='{titulo}' archivo='assets/{dest_video.name}'"
                + (f" url='{url}'" if url else "")
            )

            enriched.append(
                EnrichedAsset(
                    id=a.id,
                    kind=a.kind,
                    raw_path=path,
                    metadata=a.metadata,
                    extracted_text=extracted_video,
                )
            )

            # Imágenes seleccionadas
            for order, img_path, title in selected_images:
                img_id = f"{a.id}_img{order:02d}"
                rel = img_path.relative_to(output_assets).as_posix()
                render_path = f"assets/{rel}"

                images_by_step.setdefault(order, []).append(
                    {"path": render_path, "title": title}
                )

                extracted_img = f"[IMAGEN:{img_id}] titulo='{title}' archivo='{render_path}'"
                enriched.append(
                    EnrichedAsset(
                        id=img_id,
                        kind="image",
                        raw_path=str(img_path),
                        metadata={
                            "titulo": title,
                            "paso_sugerido": str(order),
                            "source_video": a.id,
                        },
                        extracted_text=extracted_img,
                    )
                )

            # Video procesado; seguimos con el resto de los assets (puede haber
            # más de un video, o imágenes/texto/audio adicionales). Antes acá se
            # hacía `return`, lo que descartaba en silencio todo lo que viniera
            # después del primer video.
            continue

        raise ValueError(f"Tipo de asset no soportado: {a.kind}")

    return enriched, images_by_step, evidence_images