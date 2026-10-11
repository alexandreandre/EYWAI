-- Quotité saisissable : barème légal annuel en base, personnes à charge sur la saisie.
--
-- Le code appliquait un barème « simplifié » (0/10/20/30 %, 104 € ajoutés au
-- salaire par personne à charge, 1/20e laissé au salarié) qui n'était pas la loi
-- (enquête du 11/10/2026, [G12]). Le barème vit désormais dans `payroll_config`,
-- avec le SMIC et le plafond de la Sécurité sociale : une année nouvelle s'y
-- ajoute sous `par_annee` sans toucher au code, et le RSA du 1er avril s'ajoute
-- à `solde_insaisissable`.
--
-- Règles :
-- - Code du travail R3252-2 : sept tranches, du vingtième à la totalité ;
--   R3252-3 : chaque seuil relevé par personne à charge ; L3252-5 : le salarié
--   garde toujours le RSA d'une personne seule.
-- - Barème 2026 (décret du 26/12/2025) : 4 480 / 8 730 / 13 000 / 17 230 /
--   21 470 / 25 810 € par an, 1 740 € par personne à charge.
--   https://www.service-public.gouv.fr/particuliers/actualites/A15377
-- - RSA d'une personne seule : 646,52 € au 01/04/2025, 651,69 € au 01/04/2026
--   (décret n° 2026-220 du 30 mars 2026).
--   https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000053733826
--
-- Idempotente. À appliquer AVANT de déployer le code qui la lit : sans elle,
-- aucune saisie sur salaire n'est retenue (le bulletin le dit), et une saisie
-- créée avec des personnes à charge est refusée (colonne absente).

ALTER TABLE public.salary_seizures
    ADD COLUMN IF NOT EXISTS dependents_count integer NOT NULL DEFAULT 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'salary_seizures_dependents_count_positif'
    ) THEN
        ALTER TABLE public.salary_seizures
            ADD CONSTRAINT salary_seizures_dependents_count_positif
            CHECK (dependents_count >= 0);
    END IF;
END $$;

COMMENT ON COLUMN public.salary_seizures.dependents_count IS
    'Personnes à charge du salarié : chacune relève les seuils du barème de la quotité saisissable (R3252-3).';

INSERT INTO public.payroll_config (
    config_key, config_data, version, is_active, comment, company_id, source_links
)
SELECT
    'quotite_saisissable',
    '{
        "par_annee": {
            "2026": {
                "tranches": [
                    {"jusqu_a_annuel": 4480, "fraction": "1/20"},
                    {"jusqu_a_annuel": 8730, "fraction": "1/10"},
                    {"jusqu_a_annuel": 13000, "fraction": "1/5"},
                    {"jusqu_a_annuel": 17230, "fraction": "1/4"},
                    {"jusqu_a_annuel": 21470, "fraction": "1/3"},
                    {"jusqu_a_annuel": 25810, "fraction": "2/3"},
                    {"jusqu_a_annuel": null, "fraction": "1"}
                ],
                "majoration_annuelle_par_personne_a_charge": 1740
            }
        },
        "solde_insaisissable": [
            {"date_debut": "2025-04-01", "montant_mensuel": 646.52},
            {"date_debut": "2026-04-01", "montant_mensuel": 651.69}
        ]
    }'::jsonb,
    1,
    true,
    'Quotité saisissable : barème annuel (R3252-2, R3252-3) et solde insaisissable (RSA personne seule)',
    NULL,
    ARRAY[
        'https://www.service-public.gouv.fr/particuliers/actualites/A15377',
        'https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000033812428',
        'https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000053733826'
    ]
WHERE NOT EXISTS (
    SELECT 1 FROM public.payroll_config
    WHERE config_key = 'quotite_saisissable' AND company_id IS NULL
);
