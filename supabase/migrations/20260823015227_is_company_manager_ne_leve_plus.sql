-- Fonction is_company_manager() : ne lève plus d'erreur (23/08/2026, audit).
--
-- Elle interrogeait une colonne `employees.is_manager` qui N'EXISTE PAS :
-- chaque appel levait « column is_manager does not exist ». Sept policies RLS
-- l'utilisent (absence_requests, employee_schedules, expense_reports,
-- salary_advances) : toutes échouaient, rendant ces tables ILLISIBLES pour un
-- compte connecté — y compris pour ses propres lignes.
--
-- Vérifié avant/après par impersonation du rôle authenticated, sur test ET
-- sur prod : erreur SQL avant, 12 plannings visibles après (les siens) et
-- 0 ligne appartenant à un collègue. Aucune ouverture : renvoyer false
-- reproduit exactement le comportement observable (aucun manager n'a jamais
-- été reconnu) et laisse jouer les autres branches des policies — RH sur sa
-- société, salarié sur ses propres lignes.
--
-- Quand le rôle manager sera modélisé, c'est ici qu'il faudra le brancher.
--
-- Idempotent : ré-exécutable sans erreur.

CREATE OR REPLACE FUNCTION public.is_company_manager()
RETURNS boolean
LANGUAGE plpgsql
STABLE SECURITY DEFINER
SET search_path = ''
AS $function$
BEGIN
    RETURN false;
END;
$function$;
