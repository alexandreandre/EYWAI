-- Unification Admin plateforme : droits complets + rôle RH « admin » (plus de super_admin).

-- 1. Droits plateforme maximaux pour tous les admins actifs
UPDATE super_admins
SET
  can_create_companies = true,
  can_delete_companies = true,
  can_view_all_data = true,
  can_impersonate = true
WHERE is_active = true;

-- 2. Accès RH admin sur chaque entreprise active (si absent)
INSERT INTO user_company_accesses (user_id, company_id, role, is_primary)
SELECT sa.user_id, c.id, 'admin', false
FROM super_admins sa
CROSS JOIN companies c
WHERE sa.is_active = true
  AND COALESCE(c.is_active, true) = true
  AND NOT EXISTS (
    SELECT 1
    FROM user_company_accesses uca
    WHERE uca.user_id = sa.user_id
      AND uca.company_id = c.id
  );

-- 3. Au moins un accès primaire admin par admin plateforme
UPDATE user_company_accesses uca
SET is_primary = true
WHERE uca.user_id IN (SELECT user_id FROM super_admins WHERE is_active = true)
  AND uca.role = 'admin'
  AND NOT EXISTS (
    SELECT 1
    FROM user_company_accesses u2
    WHERE u2.user_id = uca.user_id
      AND u2.is_primary = true
  )
  AND uca.company_id = (
    SELECT uca2.company_id
    FROM user_company_accesses uca2
    WHERE uca2.user_id = uca.user_id
    ORDER BY uca2.company_id
    LIMIT 1
  );

-- 4. Normaliser les rôles super_admin → admin
UPDATE profiles SET role = 'admin' WHERE role = 'super_admin';
UPDATE user_company_accesses SET role = 'admin' WHERE role = 'super_admin';
