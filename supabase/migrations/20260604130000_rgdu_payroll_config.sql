-- Réduction Générale Dégressive Unique (RGDU) — réforme des allègements généraux
-- au 1er janvier 2026 (LFSS 2025 art. 18, décret n°2025-887).
--
-- Remplace l'ancienne réduction Fillon (RGCP) pour les périodes >= 2026 :
--   Coefficient = Tmin + (Tdelta × [ (1/2) × (3 × SMIC / rémunération − 1) ]^P)
--   borné à [Tmin, Tmin+Tdelta], nul par discontinuité dès 3 SMIC.
--
-- Tous les paramètres sont stockés ici (jamais en dur dans le moteur), éditables
-- via l'UI « Suivi des taux ». Le SMIC de référence est calculé par le moteur à
-- partir des heures rémunérées cumulées : il n'est PAS stocké ici (pas de diviseur figé).
-- Le coefficient maximal (Tmin+Tdelta = 0,3981 / 0,4021) est calculé en code (valeur dérivée).
-- Le « 0,49 % AT/MP » est un taux de ventilation DSN, hors périmètre du coefficient : non stocké.
--
-- Le flag "actif" permet d'activer/désactiver le dispositif depuis l'admin
-- (cas d'une abrogation), sans déploiement.

-- Source de scraping PLACEHOLDER (is_active = false) : réservation du source_key
-- pour la traçabilité / maintenance manuelle via l'UI. Tmin/Tdelta/P sont des
-- valeurs de décret (pas une page de taux scrapable trivialement) et aucun scraper
-- n'existe : on NE l'active PAS pour éviter que l'orchestrateur tente de la lancer.
INSERT INTO public.scraping_sources (
    source_key,
    source_name,
    source_type,
    description,
    target_table,
    target_field,
    primary_url,
    requires_company_context,
    scraping_frequency,
    is_critical,
    is_active
)
VALUES (
    'REDUCTION_GENERALE',
    'Réduction générale (RGDU)',
    'bareme',
    'Paramètres RGDU (Tmin, Tdelta, P, point de sortie 3 SMIC). Valeurs de décret : mise à jour manuelle via « Suivi des taux ».',
    'payroll_config',
    'reduction_generale',
    'https://boss.gouv.fr/portail/accueil/allegements-de-cotisations/reduction-generale.html',
    false,
    'manual',
    true,
    false
)
ON CONFLICT (source_key) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    source_type = EXCLUDED.source_type,
    description = EXCLUDED.description,
    target_table = EXCLUDED.target_table,
    target_field = EXCLUDED.target_field,
    primary_url = EXCLUDED.primary_url,
    is_critical = EXCLUDED.is_critical,
    is_active = EXCLUDED.is_active,
    updated_at = now();

INSERT INTO public.payroll_config (
    config_key, config_data, version, is_active, comment, company_id
)
SELECT
    'reduction_generale',
    '{
        "actif": true,
        "type": "RGDU",
        "annee": 2026,
        "point_sortie_smic": 3.0,
        "p": 1.75,
        "tmin": 0.0200,
        "tdelta": {
            "fnal_moins_50": 0.3781,
            "fnal_50_et_plus": 0.3821
        }
    }'::jsonb,
    1, true,
    'Seed RGDU 2026 (réforme allègements généraux, LFSS 2025 / décret 2025-887)',
    NULL
WHERE NOT EXISTS (
    SELECT 1 FROM public.payroll_config
    WHERE config_key = 'reduction_generale' AND company_id IS NULL
);
