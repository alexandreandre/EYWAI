-- AGIRC-ARRCO : LegiSocial retiré (risque obsolescence). Sources : agirc-arrco.fr + IA Sonar.

UPDATE public.scraping_sources
SET
    available_scrapers = '["AGIRC-ARRCO.py", "AGIRC-ARRCO_AI.py"]'::jsonb,
    updated_at = now()
WHERE source_key = 'AGIRC-ARRCO';
