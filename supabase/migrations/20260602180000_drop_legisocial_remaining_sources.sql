-- Retrait global LegiSocial : consensus dual primary + IA Sonar (sources officielles).

UPDATE public.scraping_sources
SET available_scrapers = '["CSG.py", "CSG_AI.py"]'::jsonb, updated_at = now()
WHERE source_key = 'CSG';

UPDATE public.scraping_sources
SET available_scrapers = '["AGS.py", "AGS_AI.py"]'::jsonb, updated_at = now()
WHERE source_key = 'AGS';

UPDATE public.scraping_sources
SET available_scrapers = '["FNAL.py", "FNAL_AI.py"]'::jsonb, updated_at = now()
WHERE source_key = 'FNAL';

UPDATE public.scraping_sources
SET available_scrapers = '["alloc.py", "alloc_AI.py"]'::jsonb, updated_at = now()
WHERE source_key = 'ALLOCATIONS_FAMILIALES';

UPDATE public.scraping_sources
SET available_scrapers = '["assurancechomage.py", "assurancechomage_AI.py"]'::jsonb, updated_at = now()
WHERE source_key = 'ASSURANCE_CHOMAGE';

UPDATE public.scraping_sources
SET available_scrapers = '["MMIDpatronal.py", "MMIDpatronal_AI.py"]'::jsonb, updated_at = now()
WHERE source_key = 'MMID_PATRONAL';

UPDATE public.scraping_sources
SET available_scrapers = '["MMIDsalarial.py", "MMIDsalarial_AI.py"]'::jsonb, updated_at = now()
WHERE source_key = 'MMID_SALARIAL';

UPDATE public.scraping_sources
SET available_scrapers = '["vieillessepatronal.py", "vieillessepatronal_AI.py"]'::jsonb, updated_at = now()
WHERE source_key = 'VIEILLESSE_PATRONAL';

UPDATE public.scraping_sources
SET available_scrapers = '["vieillessesalarial.py", "vieillessesalarial_AI.py"]'::jsonb, updated_at = now()
WHERE source_key = 'VIEILLESSE_SALARIAL';

UPDATE public.scraping_sources
SET available_scrapers = '["taxeapprentissage.py", "taxeapprentissage_AI.py"]'::jsonb, updated_at = now()
WHERE source_key = 'TAXE_APPRENTISSAGE';

UPDATE public.scraping_sources
SET available_scrapers = '["Avantages.py", "Avantages_AI.py"]'::jsonb, updated_at = now()
WHERE source_key = 'AVANTAGES';

UPDATE public.scraping_sources
SET available_scrapers = '["fraispro.py", "fraispro_AI.py"]'::jsonb, updated_at = now()
WHERE source_key = 'FRAIS_PRO';

UPDATE public.scraping_sources
SET available_scrapers = '["bareme-indemnite-kilometrique.py", "bareme-indemnite-kilometrique_AI.py"]'::jsonb, updated_at = now()
WHERE source_key = 'BAREME_INDEMNITE_KILOMETRIQUE';
