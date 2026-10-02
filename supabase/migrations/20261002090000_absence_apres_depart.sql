-- Absence d'un salarié dont le départ est créé : seuls les jours après le
-- dernier jour travaillé sont refusés. Avant, toute demande l'était dès qu'un
-- départ existait, même pour un arrêt découvert tard dans le dernier mois.
-- Même fonction, même déclencheur (trg_check_exit_before_absence). Idempotente.

CREATE OR REPLACE FUNCTION public.check_employee_exit_status_before_absence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_dernier_jour DATE;
BEGIN
    SELECT last_working_day INTO v_dernier_jour
    FROM public.employee_exits
    WHERE employee_id = NEW.employee_id
      AND status NOT IN ('annulee', 'archivee')
      AND exit_request_date <= CURRENT_DATE
    ORDER BY created_at DESC
    LIMIT 1;

    IF v_dernier_jour IS NOT NULL AND EXISTS (
        SELECT 1 FROM unnest(NEW.selected_days) AS jour WHERE jour > v_dernier_jour
    ) THEN
        RAISE EXCEPTION 'Impossible de créer une demande d''absence après le dernier jour travaillé (%).',
            to_char(v_dernier_jour, 'DD/MM/YYYY')
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;
