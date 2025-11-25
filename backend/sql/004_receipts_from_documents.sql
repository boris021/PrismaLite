-- флаг, чтобы не импортировать документ повторно
ALTER TABLE pos_documents
    ADD COLUMN IF NOT EXISTS imported BOOLEAN DEFAULT false;
