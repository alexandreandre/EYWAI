-- Heures supplémentaires : consensus dual primary + Sonar.

UPDATE public.scraping_sources
SET
    available_scrapers = '["heuressupp.py", "heuressupp_AI.py"]'::jsonb,
    updated_at = now()
WHERE source_key = 'HEURES_SUPP';
