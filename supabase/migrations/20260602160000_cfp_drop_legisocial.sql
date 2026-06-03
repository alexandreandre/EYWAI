-- CFP : LegiSocial retiré (tiers non officiel). Sources : URSSAF + IA Sonar.

UPDATE public.scraping_sources
SET
    available_scrapers = '["CFP.py", "CFP_AI.py"]'::jsonb,
    updated_at = now()
WHERE source_key = 'CFP';
