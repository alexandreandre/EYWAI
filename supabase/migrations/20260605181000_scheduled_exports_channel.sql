-- Canal compta/banque pour les plannings simplifiés (un par entreprise et canal)

ALTER TABLE scheduled_exports
  ADD COLUMN IF NOT EXISTS channel TEXT CHECK (channel IN ('compta', 'banque'));

CREATE UNIQUE INDEX IF NOT EXISTS idx_scheduled_exports_company_channel
  ON scheduled_exports(company_id, channel)
  WHERE channel IS NOT NULL;
