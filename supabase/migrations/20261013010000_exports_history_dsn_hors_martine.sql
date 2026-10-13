-- « DSN déposée hors de Martine » (décision du 12/10/2026) : l'étape « DSN et
-- export comptable faits » de la liste de contrôle du mois se marque faite à la
-- main tant que la DSN se dépose depuis l'ancien logiciel. La marque est une
-- ligne de l'historique des exports (qui, quand, quel mois), sans fichier.
--
-- La contrainte reprend la liste en vigueur sur la base et y ajoute le type.

ALTER TABLE public.exports_history
    DROP CONSTRAINT IF EXISTS exports_history_export_type_check;

ALTER TABLE public.exports_history
    ADD CONSTRAINT exports_history_export_type_check CHECK (
        export_type::text = ANY (ARRAY[
            'journal_paie',
            'charges_sociales',
            'conges_absences',
            'notes_frais',
            'acomptes',
            'saisies',
            'prets_employeur',
            'paiement_organismes',
            'attestations_annexes',
            'fec',
            'od_salaires',
            'od_charges_sociales',
            'od_pas',
            'od_globale',
            'od_paie_unifiee',
            'export_cabinet_generique',
            'export_cabinet_quadra',
            'export_cabinet_sage',
            'dsn_mensuelle',
            'virement_salaires',
            'recapitulatif_montants',
            'dsn_hors_martine'
        ]::text[])
    );
