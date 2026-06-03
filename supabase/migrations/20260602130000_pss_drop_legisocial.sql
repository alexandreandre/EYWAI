-- PSS : LegiSocial retiré (barème partiel → faux cas C). Sources : primary + IA Sonar.

UPDATE public.scraping_sources
SET
    available_scrapers = '["PSS.py", "PSS_AI.py"]'::jsonb,
    updated_at = now()
WHERE source_key = 'PSS';
