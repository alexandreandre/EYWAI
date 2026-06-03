-- CSA : LegiSocial retiré (tiers non officiel). Sources : URSSAF + IA Sonar.

UPDATE public.scraping_sources
SET
    available_scrapers = '["CSA.py", "CSA_AI.py"]'::jsonb,
    updated_at = now()
WHERE source_key = 'CSA';
