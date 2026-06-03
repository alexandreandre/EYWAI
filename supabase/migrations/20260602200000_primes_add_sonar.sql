-- Catalogue des primes : consensus dual primary + Sonar.

UPDATE public.scraping_sources
SET
    available_scrapers = '["primes.py", "primes_AI.py"]'::jsonb,
    updated_at = now()
WHERE source_key = 'PRIMES';
