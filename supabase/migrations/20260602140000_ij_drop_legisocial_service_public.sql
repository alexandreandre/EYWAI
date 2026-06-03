-- IJ maladie : LegiSocial retiré. Source officielle Service Public A18779 + IA Sonar.

UPDATE public.scraping_sources
SET
    primary_url = 'https://www.service-public.gouv.fr/particuliers/actualites/A18779',
    available_scrapers = '["IJmaladie.py", "IJmaladie_AI.py"]'::jsonb,
    updated_at = now()
WHERE source_key = 'IJ_MALADIE';
