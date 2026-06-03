-- SMIC : LegiSocial retiré (page souvent en retard vs URSSAF). Sources : primary + IA Sonar.

UPDATE public.scraping_sources
SET
    available_scrapers = '["SMIC.py", "SMIC_AI.py"]'::jsonb,
    updated_at = now()
WHERE source_key = 'SMIC';
