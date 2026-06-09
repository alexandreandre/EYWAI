-- Nettoyage one-shot : retire les alertes moteur paie figées dans payslip_data
-- (alertes_baremes, synthese_net.alertes_maintien) sur tous les bulletins existants.

UPDATE public.payslips
SET payslip_data = CASE
    WHEN payslip_data ? 'synthese_net'
         AND jsonb_typeof(payslip_data->'synthese_net') = 'object'
         AND (payslip_data->'synthese_net') ? 'alertes_maintien'
    THEN jsonb_set(
        payslip_data - 'alertes_baremes',
        '{synthese_net}',
        (payslip_data->'synthese_net') - 'alertes_maintien',
        true
    )
    ELSE payslip_data - 'alertes_baremes'
END
WHERE payslip_data ? 'alertes_baremes'
   OR (
       payslip_data ? 'synthese_net'
       AND jsonb_typeof(payslip_data->'synthese_net') = 'object'
       AND (payslip_data->'synthese_net') ? 'alertes_maintien'
   );
