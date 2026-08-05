-- employees.periode_essai est remplacé par la table trial_periods.
--
-- La colonne n'est pas supprimée : elle est vide sur les 241 salariés actifs,
-- et la retirer casserait toute session parallèle qui la lirait encore. Elle
-- est marquée abandonnée et n'est plus ni lue ni écrite par l'application.

COMMENT ON COLUMN public.employees.periode_essai IS
    'ABANDONNÉ le 6 août 2026 au profit de la table trial_periods. Ne plus lire ni écrire.';
