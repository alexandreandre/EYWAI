-- Fusion COMITECH (reliquat) → Comitech Composite, puis suppression COMITECH.
-- Idempotent sur les inserts paramétres (ON CONFLICT DO NOTHING).

BEGIN;

DO $$
DECLARE
    v_comitech_id   uuid := '6c9e83d7-2478-4c56-956e-cb4febaa6a7d';
    v_composite_id  uuid := '12cd8c71-da13-43f9-9151-475c4d5e8812';
    v_comitech_name text;
    v_composite_name text;
    v_emp_comitech  integer;
    -- Identité légale à reprendre avant suppression COMITECH
    v_siret               text;
    v_siren               text;
    v_nic                 text;
    v_naf_ape             text;
    v_code_naf            text;
    v_phone               text;
    v_email               text;
    v_adresse_rue         text;
    v_adresse_code_postal text;
    v_adresse_ville       text;
    v_idcc                text;
    v_dsn_sync_mode       text;
BEGIN
    SELECT company_name INTO v_comitech_name
    FROM public.companies WHERE id = v_comitech_id;
    IF v_comitech_name IS NULL THEN
        RAISE NOTICE 'COMITECH (%) déjà supprimée — migration ignorée.', v_comitech_id;
        RETURN;
    END IF;

    SELECT company_name INTO v_composite_name
    FROM public.companies WHERE id = v_composite_id;
    IF v_composite_name IS NULL THEN
        RAISE EXCEPTION 'Comitech Composite (%) introuvable.', v_composite_id;
    END IF;

    SELECT count(*) INTO v_emp_comitech
    FROM public.employees WHERE company_id = v_comitech_id;
    IF v_emp_comitech > 0 THEN
        RAISE EXCEPTION 'COMITECH a encore % salarié(s).', v_emp_comitech;
    END IF;

    SELECT
        src.siret,
        src.siren,
        src.nic,
        src.naf_ape,
        src.code_naf,
        src.phone,
        src.email,
        src.adresse_rue,
        src.adresse_code_postal,
        src.adresse_ville,
        src.idcc,
        src.dsn_sync_mode
    INTO
        v_siret,
        v_siren,
        v_nic,
        v_naf_ape,
        v_code_naf,
        v_phone,
        v_email,
        v_adresse_rue,
        v_adresse_code_postal,
        v_adresse_ville,
        v_idcc,
        v_dsn_sync_mode
    FROM public.companies AS src
    WHERE src.id = v_comitech_id;

    -- Libérer la contrainte UNIQUE(siret) avant de l'affecter à Composite
    UPDATE public.companies
    SET siret = NULL, updated_at = now()
    WHERE id = v_comitech_id
      AND siret IS NOT NULL;

    UPDATE public.companies AS tgt
    SET
        siret               = COALESCE(tgt.siret, v_siret),
        siren               = COALESCE(tgt.siren, v_siren),
        nic                 = COALESCE(tgt.nic, v_nic),
        naf_ape             = COALESCE(tgt.naf_ape, v_naf_ape),
        code_naf            = COALESCE(tgt.code_naf, v_code_naf),
        phone               = COALESCE(tgt.phone, v_phone),
        email               = COALESCE(tgt.email, v_email),
        adresse_rue         = COALESCE(tgt.adresse_rue, v_adresse_rue),
        adresse_code_postal = COALESCE(tgt.adresse_code_postal, v_adresse_code_postal),
        adresse_ville       = COALESCE(tgt.adresse_ville, v_adresse_ville),
        idcc                = COALESCE(tgt.idcc, v_idcc),
        updated_at          = now()
    WHERE tgt.id = v_composite_id;
END $$;

-- Schéma CET v1 en prod (sans allow_deposit_hs / cp_unit / … — cf. 20260618140000)
INSERT INTO public.company_cet_settings (
    company_id,
    cet_enabled,
    agreement_reference,
    hours_per_rest_day,
    request_deadline_day_of_month,
    validation_mode,
    created_at,
    updated_at
)
SELECT
    '12cd8c71-da13-43f9-9151-475c4d5e8812',
    src.cet_enabled,
    src.agreement_reference,
    src.hours_per_rest_day,
    src.request_deadline_day_of_month,
    src.validation_mode,
    now(),
    now()
FROM public.company_cet_settings AS src
WHERE src.company_id = '6c9e83d7-2478-4c56-956e-cb4febaa6a7d'
ON CONFLICT (company_id) DO NOTHING;

INSERT INTO public.company_cse_settings (
    company_id,
    cse_status,
    carence_pv_document_id,
    carence_valid_until,
    notes,
    created_at,
    updated_at
)
SELECT
    '12cd8c71-da13-43f9-9151-475c4d5e8812',
    src.cse_status,
    src.carence_pv_document_id,
    src.carence_valid_until,
    src.notes,
    now(),
    now()
FROM public.company_cse_settings AS src
WHERE src.company_id = '6c9e83d7-2478-4c56-956e-cb4febaa6a7d'
ON CONFLICT (company_id) DO NOTHING;

UPDATE public.cse_election_cycles AS cyc
SET
    company_id = '12cd8c71-da13-43f9-9151-475c4d5e8812',
    updated_at = now()
WHERE cyc.company_id = '6c9e83d7-2478-4c56-956e-cb4febaa6a7d'
  AND NOT EXISTS (
      SELECT 1
      FROM public.cse_election_cycles AS existing
      WHERE existing.company_id = '12cd8c71-da13-43f9-9151-475c4d5e8812'
        AND existing.cycle_name = cyc.cycle_name
  );

INSERT INTO public.company_cp_seniority_settings (
    company_id,
    enabled,
    preset,
    seniority_reference,
    seniority_basis,
    counting_unit,
    rules,
    forfait_annual_days_default,
    forfait_reduction_enabled,
    company_agreement_overrides,
    created_at,
    updated_at
)
SELECT
    '12cd8c71-da13-43f9-9151-475c4d5e8812',
    src.enabled,
    src.preset,
    src.seniority_reference,
    src.seniority_basis,
    src.counting_unit,
    src.rules,
    src.forfait_annual_days_default,
    src.forfait_reduction_enabled,
    src.company_agreement_overrides,
    now(),
    now()
FROM public.company_cp_seniority_settings AS src
WHERE src.company_id = '6c9e83d7-2478-4c56-956e-cb4febaa6a7d'
ON CONFLICT (company_id) DO NOTHING;

DELETE FROM public.companies
WHERE id = '6c9e83d7-2478-4c56-956e-cb4febaa6a7d';

COMMIT;
