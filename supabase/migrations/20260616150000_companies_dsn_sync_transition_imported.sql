-- Entreprises avec au moins un import DSN committed → mode transition (suivi couverture admin).

UPDATE public.companies c
SET dsn_sync_mode = 'transition'
WHERE COALESCE(c.dsn_sync_mode, 'native') = 'native'
  AND EXISTS (
    SELECT 1
    FROM public.dsn_import_batches b
    WHERE b.status = 'committed'
      AND (
        (b.summary -> 'commit_report' ->> 'target_company_id') = c.id::text
        OR (
          b.siren IS NOT NULL
          AND c.siren IS NOT NULL
          AND regexp_replace(b.siren, '\s', '', 'g') = regexp_replace(c.siren, '\s', '', 'g')
        )
      )
  );
