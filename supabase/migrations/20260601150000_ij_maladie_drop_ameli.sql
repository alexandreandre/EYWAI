-- IJ maladie : plus de scraper Ameli (403 anti-bot). Sources : LegiSocial + IA Sonar.

UPDATE public.scraping_sources
SET
    primary_url = 'https://www.legisocial.fr/reperes-sociaux/indemnites-journalieres-de-securite-sociale-ijss-2026.html',
    available_scrapers = '["IJmaladie_LegiSocial.py", "IJmaladie_AI.py"]'::jsonb,
    updated_at = now()
WHERE source_key = 'IJ_MALADIE';
