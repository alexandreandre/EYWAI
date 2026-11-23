-- Jours de repos « seniors » de la convention de la plasturgie (IDCC 292),
-- accord du 18 avril 2025 (non étendu, applicable au 1er juin 2025) :
-- chaque 1er juin, 1 jour à 58 et 59 ans, 2 jours dès 60 ans, à prendre
-- jusqu'au 31 mai suivant.
--
-- Décision du client du 23/11/2026 : la règle existe dans Martine, mais elle
-- n'est allumée nulle part. Le défaut est donc éteint, et aucune société ne
-- voit le compteur tant qu'on ne l'a pas activé explicitement.
--
-- Aucun solde n'est stocké : le droit se recalcule depuis la date de
-- naissance et les absences validées (domain/repos_seniors.py).

ALTER TABLE public.company_leave_settings
    ADD COLUMN IF NOT EXISTS repos_seniors_enabled boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.company_leave_settings.repos_seniors_enabled IS
    'Repos seniors de la plasturgie (accord du 18/04/2025) actifs pour la société. Éteint par défaut (décision du 23/11/2026).';
