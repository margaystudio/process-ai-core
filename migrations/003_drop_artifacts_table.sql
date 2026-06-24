-- Fase B-cleanup — Eliminar la tabla `artifacts`.
--
-- El artefacto auditable (PDF de la versión aprobada) vive ahora en columnas de
-- `document_versions` (migración 002). Los artefactos de un run (json/md/pdf/assets)
-- viven en object storage bajo la clave {run_id}/... y se sirven por convención,
-- sin tracking en una tabla. Ver docs/ALMACENAMIENTO_Y_ARTEFACTOS_PLAN.md §1.bis.
--
-- Sistema no productivo: no hay datos que preservar.

SET search_path TO process_ai;

DROP TABLE IF EXISTS process_ai.artifacts CASCADE;
