-- Source scraping : Taxe d'apprentissage (part principale + solde, cotisations taxe_apprentissage*).

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
    'TAXE_APPRENTISSAGE',
    'Taxe d''Apprentissage',
    'cotisation',
    'Taux patronal part principale (métropole / Alsace-Moselle) et solde',
    'payroll_config',
    'cotisations.taxe_apprentissage',
    'https://www.urssaf.fr/accueil/employeur/cotisations/liste-cotisations/taxe-apprentissage-csa.html',
    '["taxeapprentissage.py", "taxeapprentissage_LegiSocial.py", "taxeapprentissage_AI.py"]'::jsonb,
    'scraping/taxeapprentissage/orchestrator.py',
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
