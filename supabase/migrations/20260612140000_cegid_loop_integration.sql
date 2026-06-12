-- Cegid Loop : statut transmitted pour le polling d'imports FEC asynchrones

ALTER TABLE public.accounting_transmissions
  DROP CONSTRAINT IF EXISTS accounting_transmissions_status_check;

ALTER TABLE public.accounting_transmissions
  ADD CONSTRAINT accounting_transmissions_status_check
  CHECK (status IN (
    'generated', 'queued', 'sent', 'acknowledged', 'rejected',
    'manual', 'failed', 'transmitted'
  ));

COMMENT ON COLUMN public.accounting_transmissions.external_ref IS
  'Référence externe (ex. import_id Cegid Loop pour polling du statut).';
