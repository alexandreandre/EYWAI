-- Provision de congés payés et virement des acomptes (03/11/2026) : le serveur
-- accepte ces deux types d'export, la base les refusait. La provision de MAJI
-- (mai 2026) plantait à la génération sur cette contrainte.
--
-- La contrainte reprend la liste en vigueur sur la base et y ajoute les deux types.

ALTER TABLE public.exports_history
    DROP CONSTRAINT IF EXISTS exports_history_export_type_check;

ALTER TABLE public.exports_history
    ADD CONSTRAINT exports_history_export_type_check CHECK (
        export_type::text = ANY (ARRAY[
            'journal_paie',
            'charges_sociales',
            'conges_absences',
            'provision_cp',
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
            'virement_acomptes',
            'recapitulatif_montants',
            'dsn_hors_martine',
            'dsn_signalement_arret'
        ]::text[])
    );
