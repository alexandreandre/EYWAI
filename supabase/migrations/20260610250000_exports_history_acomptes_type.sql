-- Autoriser le type d'export « acomptes » dans exports_history.
-- Le backend enregistre export_type = 'acomptes' après génération, mais la contrainte
-- CHECK ne l'incluait pas → erreur 23514 (exports_history_export_type_check).

ALTER TABLE public.exports_history
    DROP CONSTRAINT IF EXISTS exports_history_export_type_check;

ALTER TABLE public.exports_history
    ADD CONSTRAINT exports_history_export_type_check
    CHECK (
        export_type IN (
            'journal_paie',
            'charges_sociales',
            'conges_absences',
            'notes_frais',
            'acomptes',
            'ecritures_comptables',
            'od_salaires',
            'od_charges_sociales',
            'od_pas',
            'od_globale',
            'export_cabinet_generique',
            'export_cabinet_quadra',
            'export_cabinet_sage',
            'dsn_mensuelle',
            'virement_salaires',
            'recapitulatif_montants'
        )
    );
