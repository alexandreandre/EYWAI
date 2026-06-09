-- TVA sur les notes de frais (montant existant = TTC)
ALTER TABLE expense_reports
  ADD COLUMN IF NOT EXISTS vat_rate numeric(5, 2),
  ADD COLUMN IF NOT EXISTS amount_ht numeric(12, 2),
  ADD COLUMN IF NOT EXISTS vat_amount numeric(12, 2);

COMMENT ON COLUMN expense_reports.amount IS 'Montant TTC de la dépense en euros';
COMMENT ON COLUMN expense_reports.vat_rate IS 'Taux de TVA applicable en pourcentage (ex. 20, 10, 5.5)';
COMMENT ON COLUMN expense_reports.amount_ht IS 'Montant HT calculé à partir du TTC et du taux de TVA';
COMMENT ON COLUMN expense_reports.vat_amount IS 'Montant de TVA en euros';
