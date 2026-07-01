-- Export Word (.docx) des documents générés (contrats, avenants) en plus du PDF.
-- Colonnes nullable : n'existent que si un fichier Word a pu être produit
-- (modèle client .docx conservé, ou générateur interne EYWAI équivalent).

ALTER TABLE generated_documents
  ADD COLUMN IF NOT EXISTS docx_file_url TEXT,
  ADD COLUMN IF NOT EXISTS docx_file_name TEXT;
