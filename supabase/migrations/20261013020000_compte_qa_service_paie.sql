-- Compte de test (QA) : son nom d'affichage devient « Service paie ».
-- Donnée du compte, pas du code. Le compte est ciblé par son adresse e-mail,
-- comparée par empreinte SHA-256 (en minuscules) pour que l'adresse ne figure
-- pas dans un dépôt public. Sans ce compte (autre base), la migration ne fait rien.
-- Non appliquée : à passer sur la base de test seulement.
UPDATE public.profiles p
SET first_name = 'Service',
    last_name = 'paie'
FROM auth.users u
WHERE u.id = p.id
  AND encode(sha256(convert_to(lower(u.email), 'UTF8')), 'hex')
      = '494dbf4a102dbffc96c125bb7917650b9e743d3e4e5ab75a4715736467869cec';
