-- Archivo fuente de documentos importados (no generados por pipeline).
ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS source_file_key TEXT NULL;
ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS source_file_name TEXT NULL;
