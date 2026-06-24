-- Fase B — Congelar el PDF de la versión APROBADA como artefacto de auditoría.
-- Aditiva: agrega columnas a document_versions. El PDF aprobado se sube a object
-- storage (clave canónica) y acá guardamos su ubicación + hash + trazabilidad.
--
-- Nota: el DROP de la tabla `artifacts` se hace en una migración posterior, junto
-- con la remoción de sus lectores en el código (endpoints de runs). Ver
-- docs/ALMACENAMIENTO_Y_ARTEFACTOS_PLAN.md §1.bis y Fase B/C.

SET search_path TO process_ai;

ALTER TABLE document_versions
    ADD COLUMN IF NOT EXISTS pdf_storage_key   TEXT,
    ADD COLUMN IF NOT EXISTS pdf_sha256        VARCHAR(64),
    ADD COLUMN IF NOT EXISTS pdf_generated_at  TIMESTAMP,
    ADD COLUMN IF NOT EXISTS pdf_render_engine VARCHAR(50);
