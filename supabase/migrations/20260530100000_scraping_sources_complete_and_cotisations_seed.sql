-- Sources scraping manquantes + seed minimal catalogue cotisations.

INSERT INTO public.scraping_sources (
    source_key, source_name, source_type, description, target_table, target_field,
    primary_url, available_scrapers, orchestrator_path, requires_company_context,
    scraping_frequency, is_critical, is_active
)
VALUES
(
    'SMIC', 'SMIC', 'bareme',
    'Salaire minimum interprofessionnel de croissance',
    'payroll_config', 'smic',
    'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/montant-smic.html',
    '["SMIC.py", "SMIC_LegiSocial.py", "SMIC_AI.py"]'::jsonb,
    'scraping/SMIC/orchestrator.py', false, 'manual', true, true
),
(
    'PSS', 'Plafond Sécurité sociale', 'plafond',
    'Plafonds SS annuel, mensuel, horaire',
    'payroll_config', 'pss',
    'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/plafonds-securite-sociale.html',
    '["PSS.py", "PSS_LegiSocial.py", "PSS_AI.py"]'::jsonb,
    'scraping/PSS/orchestrator.py', false, 'manual', true, true
),
(
    'PAS', 'Prélèvement à la source', 'bareme',
    'Barèmes PAS taux neutre',
    'payroll_config', 'pas',
    'https://bofip.impots.gouv.fr/',
    '["PAS.py", "PAS_AI.py"]'::jsonb,
    'scraping/PAS/orchestrator.py', false, 'manual', false, true
),
(
    'CSG', 'CSG / CRDS', 'cotisation',
    'Cotisations CSG et CRDS',
    'payroll_config', 'cotisations.csg',
    'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html',
    '["CSG.py", "CSG_LegiSocial.py", "CSG_AI.py"]'::jsonb,
    'scraping/CSG/orchestrator.py', false, 'manual', true, true
),
(
    'AGIRC-ARRCO', 'AGIRC-ARRCO', 'cotisation',
    'Retraite complémentaire AGIRC-ARRCO',
    'payroll_config', 'cotisations',
    'https://www.agirc-arrco.fr/',
    '["AGIRC-ARRCO.py", "AGIRC-ARRCO_LegiSocial.py", "AGIRC-ARRCO_AI.py"]'::jsonb,
    'scraping/AGIRC-ARRCO/orchestrator.py', false, 'manual', true, true
),
(
    'AGS', 'AGS', 'cotisation',
    'Allocation de garantie des salaires',
    'payroll_config', 'cotisations.ags',
    'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html',
    '["AGS.py", "AGS_LegiSocial.py", "AGS_AI.py"]'::jsonb,
    'scraping/AGS/orchestrator.py', false, 'manual', false, true
),
(
    'FNAL', 'FNAL', 'cotisation',
    'Fonds national d''aide au logement',
    'payroll_config', 'cotisations.fnal',
    'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html',
    '["FNAL.py", "FNAL_LegiSocial.py", "FNAL_AI.py"]'::jsonb,
    'scraping/FNAL/orchestrator.py', false, 'manual', false, true
),
(
    'ALLOCATIONS_FAMILIALES', 'Allocations familiales', 'cotisation',
    'Cotisations allocations familiales',
    'payroll_config', 'cotisations.allocations_familiales',
    'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html',
    '["alloc.py", "alloc_LegiSocial.py", "alloc_AI.py"]'::jsonb,
    'scraping/alloc/orchestrator.py', false, 'manual', false, true
),
(
    'ASSURANCE_CHOMAGE', 'Assurance chômage', 'cotisation',
    'Cotisation assurance chômage',
    'payroll_config', 'cotisations.assurance_chomage',
    'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html',
    '["assurancechomage.py", "assurancechomage_LegiSocial.py", "assurancechomage_AI.py"]'::jsonb,
    'scraping/assurancechomage/orchestrator.py', false, 'manual', false, true
),
(
    'MMID_PATRONAL', 'Maladie patronal', 'cotisation',
    'Cotisation maladie patronale',
    'payroll_config', 'cotisations.securite_sociale_maladie',
    'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html',
    '["MMIDpatronal.py", "MMIDpatronal_LegiSocial.py", "MMIDpatronal_AI.py"]'::jsonb,
    'scraping/MMIDpatronal/orchestrator.py', false, 'manual', false, true
),
(
    'MMID_SALARIAL', 'Maladie salarial Alsace-Moselle', 'cotisation',
    'Cotisation maladie salariale Alsace-Moselle',
    'payroll_config', 'cotisations.securite_sociale_maladie',
    'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html',
    '["MMIDsalarial.py", "MMIDsalarial_LegiSocial.py", "MMIDsalarial_AI.py"]'::jsonb,
    'scraping/MMIDsalarial/orchestrator.py', false, 'manual', false, true
),
(
    'FRAIS_PRO', 'Frais professionnels', 'bareme',
    'Barèmes frais professionnels URSSAF',
    'payroll_config', 'frais_pro',
    'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/frais-professionnels.html',
    '["fraispro.py", "fraispro_LegiSocial.py", "fraispro_AI.py"]'::jsonb,
    'scraping/fraispro/orchestrator.py', false, 'manual', false, true
),
(
    'BAREME_INDEMNITE_KILOMETRIQUE', 'Barème indemnités km', 'bareme',
    'Barème fiscal indemnités kilométriques',
    'payroll_config', 'baremes_km',
    'https://www.service-public.fr/particuliers/vosdroits/F14686',
    '["bareme-indemnite-kilometrique.py", "bareme-indemnite-kilometrique_LegiSocial.py"]'::jsonb,
    'scraping/bareme-indemnite-kilometrique/orchestrator.py', false, 'manual', false, true
),
(
    'VM', 'Versement mobilité', 'bareme',
    'Tables URSSAF transport et VMRR',
    'payroll_config', 'taux_vmrr',
    'https://fichierdirect.declaration.urssaf.fr/TablesReference.htm',
    '["VM.py"]'::jsonb,
    'scraping/versement_mobilite/orchestrator.py', false, 'manual', false, true
)
ON CONFLICT (source_key) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    available_scrapers = EXCLUDED.available_scrapers,
    orchestrator_path = EXCLUDED.orchestrator_path,
    is_active = EXCLUDED.is_active,
    updated_at = now();

-- Seed minimal cotisations (cold start) — lignes non patchées par scrapers individuels
INSERT INTO public.payroll_config (
    config_key, config_data, version, is_active, comment, company_id
)
SELECT
    'cotisations',
    '{"cotisations": [
        {"id": "at_mp", "libelle": "Accidents du travail", "base": "brut", "patronal": "specifique_entreprise", "salarial": null},
        {"id": "versement_mobilite", "libelle": "Versement mobilité", "base": "brut", "patronal": "specifique_entreprise", "salarial": null},
        {"id": "mutuelle", "libelle": "Mutuelle", "base": "brut", "patronal": null, "salarial": null}
    ]}'::jsonb,
    1, true, 'Seed catalogue cotisations minimal', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM public.payroll_config
    WHERE config_key = 'cotisations' AND company_id IS NULL
);
