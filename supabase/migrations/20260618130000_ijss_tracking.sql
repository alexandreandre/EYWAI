-- Suivi IJSS / rapprochement CPAM (théorique paie vs décomptes vs virements)

CREATE TABLE IF NOT EXISTS public.ijss_tracking_periods (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    period_year integer NOT NULL,
    period_month integer NOT NULL CHECK (period_month BETWEEN 1 AND 12),
    status text NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'partial', 'reconciled', 'closed')),
    expected_total numeric(12, 2) NOT NULL DEFAULT 0,
    received_cpam_total numeric(12, 2) NOT NULL DEFAULT 0,
    received_bank_total numeric(12, 2) NOT NULL DEFAULT 0,
    variance_total numeric(12, 2) NOT NULL DEFAULT 0,
    variance_threshold numeric(12, 2) NOT NULL DEFAULT 1.00,
    notes text,
    closed_at timestamptz,
    closed_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, period_year, period_month)
);

CREATE INDEX IF NOT EXISTS ijss_tracking_periods_company_idx
    ON public.ijss_tracking_periods (company_id, period_year DESC, period_month DESC);

CREATE TABLE IF NOT EXISTS public.ijss_expected_lines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    period_id uuid NOT NULL REFERENCES public.ijss_tracking_periods(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL,
    absence_request_id uuid,
    payslip_id uuid,
    period_year integer NOT NULL,
    period_month integer NOT NULL,
    ijss_theorique numeric(12, 2) NOT NULL DEFAULT 0,
    ijss_subrogees_bulletin numeric(12, 2) NOT NULL DEFAULT 0,
    nb_jours_indemnises integer NOT NULL DEFAULT 0,
    subrogation_active boolean NOT NULL DEFAULT true,
    line_status text NOT NULL DEFAULT 'pending'
        CHECK (line_status IN ('pending', 'partial', 'ok', 'variance', 'justified')),
    calculation_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, employee_id, absence_request_id, period_year, period_month)
);

CREATE INDEX IF NOT EXISTS ijss_expected_lines_period_idx
    ON public.ijss_expected_lines (period_id);

CREATE INDEX IF NOT EXISTS ijss_expected_lines_employee_idx
    ON public.ijss_expected_lines (employee_id, period_year, period_month);

CREATE TABLE IF NOT EXISTS public.ijss_import_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    period_id uuid REFERENCES public.ijss_tracking_periods(id) ON DELETE SET NULL,
    batch_type text NOT NULL
        CHECK (batch_type IN ('bank_recap', 'cpam_decompte_file', 'cpam_api_sync')),
    status text NOT NULL DEFAULT 'parsed'
        CHECK (status IN ('parsed', 'previewed', 'committed', 'failed')),
    file_name text,
    file_hash text,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    preview jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_message text,
    uploaded_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ijss_import_batches_company_idx
    ON public.ijss_import_batches (company_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS ijss_import_batches_company_hash_idx
    ON public.ijss_import_batches (company_id, file_hash)
    WHERE file_hash IS NOT NULL AND status = 'committed';

CREATE TABLE IF NOT EXISTS public.ijss_import_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id uuid NOT NULL REFERENCES public.ijss_import_batches(id) ON DELETE CASCADE,
    row_index integer NOT NULL,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    mapped_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    match_status text NOT NULL DEFAULT 'unmatched'
        CHECK (match_status IN ('unmatched', 'matched', 'skipped', 'error')),
    employee_id uuid,
    anomalies text[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ijss_import_items_batch_idx
    ON public.ijss_import_items (batch_id);

CREATE TABLE IF NOT EXISTS public.ijss_received_lines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    period_id uuid REFERENCES public.ijss_tracking_periods(id) ON DELETE SET NULL,
    expected_line_id uuid REFERENCES public.ijss_expected_lines(id) ON DELETE SET NULL,
    import_batch_id uuid REFERENCES public.ijss_import_batches(id) ON DELETE SET NULL,
    source text NOT NULL
        CHECK (source IN ('cpam_decompte', 'bank_transfer', 'manual')),
    amount numeric(12, 2) NOT NULL,
    payment_date date,
    period_start date,
    period_end date,
    employee_id uuid,
    employee_nir text,
    employee_name_raw text,
    net_entreprises_ref text,
    bank_reference text,
    match_confidence text NOT NULL DEFAULT 'none'
        CHECK (match_confidence IN ('none', 'weak', 'medium', 'strong', 'manual')),
    match_status text NOT NULL DEFAULT 'unmatched'
        CHECK (match_status IN ('unmatched', 'matched', 'disputed')),
    proof_storage_path text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ijss_received_lines_period_idx
    ON public.ijss_received_lines (period_id);

CREATE INDEX IF NOT EXISTS ijss_received_lines_employee_idx
    ON public.ijss_received_lines (employee_id);

CREATE TABLE IF NOT EXISTS public.ijss_reconciliation_notes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    expected_line_id uuid REFERENCES public.ijss_expected_lines(id) ON DELETE CASCADE,
    received_line_id uuid REFERENCES public.ijss_received_lines(id) ON DELETE SET NULL,
    note_type text NOT NULL DEFAULT 'justification'
        CHECK (note_type IN ('justification', 'comment', 'audit')),
    content text NOT NULL,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.company_ijss_import_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    profile_name text NOT NULL DEFAULT 'default',
    batch_type text NOT NULL DEFAULT 'bank_recap'
        CHECK (batch_type IN ('bank_recap', 'cpam_decompte_file')),
    column_mapping jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, profile_name, batch_type)
);

COMMENT ON TABLE public.ijss_tracking_periods IS
    'Période mensuelle de suivi IJSS (rapprochement CPAM).';

ALTER TABLE public.ijss_tracking_periods ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ijss_expected_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ijss_received_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ijss_import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ijss_import_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ijss_reconciliation_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_ijss_import_profiles ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF to_regclass('public.companies') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conname = 'ijss_tracking_periods_company_id_fkey'
       )
    THEN
        ALTER TABLE public.ijss_tracking_periods
            ADD CONSTRAINT ijss_tracking_periods_company_id_fkey
            FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;
    END IF;
END $$;
