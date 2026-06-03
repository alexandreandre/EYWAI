-- Sources scraping : vieillesse sécurité sociale (plafonnée + déplafonnée), taux patronal et salarial.

INSERT INTO public.scraping_sources (
    source_key,
    source_name,
    source_type,
    description,
    target_table,
    target_field,
    primary_url,
    available_scrapers,
    orchestrator_path,
    requires_company_context,
    scraping_frequency,
    is_critical,
    is_active
)
VALUES (
    'VIEILLESSE_PATRONAL',
    'Vieillesse sécurité sociale (patronal)',
    'cotisation',
    'Taux patronal vieillesse plafonnée et déplafonnée',
    'payroll_config',
    'cotisations.retraite_secu_plafond',
    'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html',
    '["vieillessepatronal.py", "vieillessepatronal_LegiSocial.py", "vieillessepatronal_AI.py"]'::jsonb,
    'scraping/vieillessepatronal/orchestrator.py',
    false,
    'manual',
    false,
    true
)
ON CONFLICT (source_key) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    source_type = EXCLUDED.source_type,
    description = EXCLUDED.description,
    target_table = EXCLUDED.target_table,
    target_field = EXCLUDED.target_field,
    primary_url = EXCLUDED.primary_url,
    available_scrapers = EXCLUDED.available_scrapers,
    orchestrator_path = EXCLUDED.orchestrator_path,
    is_critical = EXCLUDED.is_critical,
    is_active = EXCLUDED.is_active,
    updated_at = now();

INSERT INTO public.scraping_sources (
    source_key,
    source_name,
    source_type,
    description,
    target_table,
    target_field,
    primary_url,
    available_scrapers,
    orchestrator_path,
    requires_company_context,
    scraping_frequency,
    is_critical,
    is_active
)
VALUES (
    'VIEILLESSE_SALARIAL',
    'Vieillesse sécurité sociale (salarial)',
    'cotisation',
    'Taux salarial vieillesse plafonnée et déplafonnée',
    'payroll_config',
    'cotisations.retraite_secu_deplafond',
    'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html',
    '["vieillessesalarial.py", "vieillessesalarial_LegiSocial.py", "vieillessesalarial_AI.py"]'::jsonb,
    'scraping/vieillessesalarial/orchestrator.py',
    false,
    'manual',
    false,
    true
)
ON CONFLICT (source_key) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    source_type = EXCLUDED.source_type,
    description = EXCLUDED.description,
    target_table = EXCLUDED.target_table,
    target_field = EXCLUDED.target_field,
    primary_url = EXCLUDED.primary_url,
    available_scrapers = EXCLUDED.available_scrapers,
    orchestrator_path = EXCLUDED.orchestrator_path,
    is_critical = EXCLUDED.is_critical,
    is_active = EXCLUDED.is_active,
    updated_at = now();
