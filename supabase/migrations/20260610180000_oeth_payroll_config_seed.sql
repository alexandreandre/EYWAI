-- Barème national OETH (Obligation d'Emploi des Travailleurs Handicapés).
INSERT INTO public.payroll_config (
    config_key, config_data, version, is_active, comment, company_id
)
SELECT
    'oeth',
    '{
        "actif": true,
        "taux_obligation": 0.06,
        "taux_obligation_mayotte": 0.05,
        "seuil_assujettissement": 20,
        "coefficients": {
            "20_249": 400,
            "250_749": 500,
            "750_plus": 600,
            "surcontribution": 1500
        },
        "boeth_50_plus_factor": 1.5,
        "ecap_deduction_factor": 17,
        "neutralisation_years": 5,
        "surcontribution_years": 3,
        "boeth_codes": {
            "01": "Travailleur reconnu handicapé (RQTH)",
            "02": "Victime AT/MP (incapacité ≥ 10 %)",
            "03": "Titulaire pension invalidité (≥ 2/3)",
            "04": "Pension militaire invalidité (L.241-2)",
            "05": "Pension militaire invalidité (L.241-3/4)",
            "06": "Allocation/rente invalidité sapeurs-pompiers",
            "07": "Carte mobilité inclusion mention invalidité",
            "08": "Titulaire AAH",
            "09": "Pension militaire invalidité (L.241-5/6)",
            "11": "Agent public allocation temporaire invalidité",
            "12": "Stage PCH/ACTP/AEEH"
        },
        "external_types": {
            "01": "Entreprise adaptée (EA)",
            "02": "ESAT",
            "03": "TIH",
            "04": "Portage salarial"
        },
        "deduction_types": {
            "060": "Déduction ECAP",
            "061": "Déduction sous-traitance EA/ESAT/TIH",
            "062": "Dépense accessibilité",
            "063": "Dépense maintien/reconversion",
            "064": "Dépense accompagnement/sensibilisation"
        },
        "dsn": {
            "statut_boeth_rubrique": "S21.G00.40.072",
            "ancien_statut_boeth_rubrique": "S21.G00.41.048",
            "ctp_contribution": "730",
            "cotisation_codes": ["065", "066", "068"]
        }
    }'::jsonb,
    1,
    true,
    'OETH — taux 6 %, coefficients contribution, codes DSN BOETH',
    NULL
WHERE NOT EXISTS (
    SELECT 1 FROM public.payroll_config
    WHERE config_key = 'oeth' AND company_id IS NULL
);
