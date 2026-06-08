-- Sources scraping manquantes sur certains environnements (VM, barème km).

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
VALUES
(
    'VM',
    'Versement mobilité',
    'bareme',
    'Tables URSSAF transport et VMRR',
    'payroll_config',
    'taux_vmrr',
    'https://fichierdirect.declaration.urssaf.fr/TablesReference.htm',
    '["VM.py"]'::jsonb,
    'scraping/versement_mobilite/orchestrator.py',
    false,
    'manual',
    false,
    true
),
(
    'BAREME_INDEMNITE_KILOMETRIQUE',
    'Barème indemnités km',
    'bareme',
    'Barème fiscal indemnités kilométriques',
    'payroll_config',
    'baremes_km',
    'https://www.service-public.fr/particuliers/vosdroits/F14686',
    '["bareme-indemnite-kilometrique.py", "bareme-indemnite-kilometrique_LegiSocial.py"]'::jsonb,
    'scraping/bareme-indemnite-kilometrique/orchestrator.py',
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
    is_active = EXCLUDED.is_active,
    updated_at = now();
