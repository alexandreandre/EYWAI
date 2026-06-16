-- Salariés créés via import DSN : statut actif (pas le flux onboarding EYWAI).
-- Cible les emails placeholder générés à l'import (.dsn-import.local).
UPDATE employees
SET employment_status = 'actif'
WHERE employment_status = 'en_onboarding'
  AND email LIKE '%.dsn-import.local';
