-- Étend le type document BDES : PV de carence CSE (Cerfa 15248).

ALTER TABLE public.cse_bdes_documents
    DROP CONSTRAINT IF EXISTS cse_bdes_documents_document_type_check;

ALTER TABLE public.cse_bdes_documents
    ADD CONSTRAINT cse_bdes_documents_document_type_check
    CHECK (document_type IN ('bdes', 'pv', 'pv_carence', 'autre'));
