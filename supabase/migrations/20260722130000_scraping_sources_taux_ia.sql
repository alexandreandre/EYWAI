-- supabase/migrations/20260722120000_scraping_sources_taux_ia.sql
-- Sources scraping IA mono-source pour les taux jusque-là non régénérables.
INSERT INTO public.scraping_sources (
    source_key, source_name, source_type, description, target_table, target_field,
    primary_url, available_scrapers, orchestrator_path, requires_company_context,
    scraping_frequency, is_critical, is_active
)
VALUES
(
    'TAUX_INTERET_LEGAL', 'Taux d''intérêt légal', 'bareme',
    'Taux d''intérêt légal semestriel en vigueur',
    'payroll_config', 'taux_interet_legal',
    'https://www.service-public.fr/particuliers/vosdroits/F2100',
    '["taux_interet_legal_AI.py"]'::jsonb,
    'scraping/taux_interet_legal/orchestrator.py', false, 'manual', false, true
),
(
    'CDD', 'CDD — précarité & ICCP', 'bareme',
    'Taux prime de précarité et indemnité congés CDD',
    'payroll_config', 'cdd',
    'https://www.service-public.fr/particuliers/vosdroits/F40',
    '["cdd_AI.py"]'::jsonb,
    'scraping/cdd/orchestrator.py', false, 'manual', false, true
),
(
    'INTERIM', 'Intérim — IFM & ICCP', 'bareme',
    'Taux indemnité de fin de mission et congés intérim',
    'payroll_config', 'interim',
    'https://www.service-public.fr/particuliers/vosdroits/F13851',
    '["interim_AI.py"]'::jsonb,
    'scraping/interim/orchestrator.py', false, 'manual', false, true
),
(
    'STAGE', 'Gratification de stage', 'bareme',
    'Pourcentage du plafond horaire SS pour la gratification de stage',
    'payroll_config', 'stage',
    'https://www.urssaf.fr/accueil/employeur/embaucher-salarie/stagiaire.html',
    '["stage_AI.py"]'::jsonb,
    'scraping/stage/orchestrator.py', false, 'manual', false, true
),
(
    'MALADIE', 'CSG/CRDS sur IJSS', 'bareme',
    'Taux CSG déductible et non déductible sur les IJSS',
    'payroll_config', 'maladie',
    'https://boss.gouv.fr/portail/accueil/indemnisation-ijss.html',
    '["maladie_AI.py"]'::jsonb,
    'scraping/maladie/orchestrator.py', false, 'manual', false, true
),
(
    'JEI', 'Plafond exonération JEI', 'bareme',
    'Plafond de rémunération exonérée JEI (multiple du SMIC)',
    'payroll_config', 'jei',
    'https://boss.gouv.fr/portail/accueil/exonerations-zonees-et-ciblees/jei.html',
    '["jei_AI.py"]'::jsonb,
    'scraping/jei/orchestrator.py', false, 'manual', false, true
),
(
    'OETH', 'Taux OETH', 'bareme',
    'Taux légal d''obligation d''emploi des travailleurs handicapés',
    'payroll_config', 'oeth',
    'https://www.urssaf.fr/accueil/employeur/cotisations/liste-cotisations/oeth.html',
    '["oeth_AI.py"]'::jsonb,
    'scraping/oeth/orchestrator.py', false, 'manual', false, true
),
(
    'REDUCTION_GENERALE', 'Paramètres RGDU', 'bareme',
    'Coefficients T, P, Tmin, point de sortie de la réduction générale',
    'payroll_config', 'reduction_generale',
    'https://boss.gouv.fr/portail/accueil/allegements-et-exonerations/reduction-generale.html',
    '["reduction_generale_AI.py"]'::jsonb,
    'scraping/reduction_generale/orchestrator.py', false, 'manual', false, true
),
(
    'MANDATAIRE', 'Cotisations exclues mandataire', 'bareme',
    'Liste des cotisations dont le mandataire social est exclu',
    'payroll_config', 'mandataire',
    'https://www.urssaf.fr/accueil/employeur/dirigeants.html',
    '["mandataire_AI.py"]'::jsonb,
    'scraping/mandataire/orchestrator.py', false, 'manual', false, true
),
(
    'COMPTES_AVANCES_ACOMPTES', 'Comptes PCG avances/acomptes', 'bareme',
    'Comptes du Plan Comptable Général pour avances, acomptes, banque',
    'payroll_config', 'comptes_avances_acomptes',
    'https://www.plancomptable.com/titre-IV/titre-IV.htm',
    '["comptes_avances_acomptes_AI.py"]'::jsonb,
    'scraping/comptes_avances_acomptes/orchestrator.py', false, 'manual', false, true
)
ON CONFLICT (source_key) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    description = EXCLUDED.description,
    primary_url = EXCLUDED.primary_url,
    available_scrapers = EXCLUDED.available_scrapers,
    orchestrator_path = EXCLUDED.orchestrator_path,
    is_active = EXCLUDED.is_active;
