-- [D1, vidéo H] Supprimer un départ en cours supprimait le salarié et ses bulletins.
--
-- `employees.current_exit_id` référençait le départ avec ON DELETE CASCADE :
-- supprimer la ligne du départ supprimait la ligne du salarié qui le pointe,
-- puis, en cascade, ses bulletins, contrats, absences… Constaté le 12/10/2026
-- sur quatre personnages de tournage chez MAJI (un départ archivé n'est plus
-- pointé, il ne déclenchait rien).
--
-- Désormais, supprimer un départ vide seulement le lien : le salarié reste.
-- Aucune donnée ne change.
ALTER TABLE public.employees
  DROP CONSTRAINT IF EXISTS employees_current_exit_id_fkey;
ALTER TABLE public.employees
  ADD CONSTRAINT employees_current_exit_id_fkey
  FOREIGN KEY (current_exit_id) REFERENCES public.employee_exits(id) ON DELETE SET NULL;
