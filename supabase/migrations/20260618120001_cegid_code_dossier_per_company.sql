-- Code dossier Cegid Loop (codeIbs) par filiale ; clés cabinet au niveau plateforme.
-- cegid_auth_mode : shared (clés cabinet groupe) ou dedicated (clés propres à la filiale).

ALTER TABLE public.company_accounting_config
  ADD COLUMN IF NOT EXISTS code_dossier_cegid text;

ALTER TABLE public.company_accounting_config
  ADD COLUMN IF NOT EXISTS cegid_auth_mode text NOT NULL DEFAULT 'shared';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'company_accounting_config_cegid_auth_mode_check'
  ) THEN
    ALTER TABLE public.company_accounting_config
      ADD CONSTRAINT company_accounting_config_cegid_auth_mode_check
      CHECK (cegid_auth_mode IN ('shared', 'dedicated'));
  END IF;
END $$;

COMMENT ON COLUMN public.company_accounting_config.code_dossier_cegid IS
  'Code dossier Cegid Loop (codeIbs) pour cette filiale ; clés cabinet au niveau plateforme.';

COMMENT ON COLUMN public.company_accounting_config.cegid_auth_mode IS
  'Mode auth Cegid : shared = clés cabinet plateforme ; dedicated = clés propres à la filiale.';
