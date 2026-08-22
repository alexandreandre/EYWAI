# Lien d'activation — le sésame de la vague 0

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Une RH clique « Inviter » sur la fiche d'un salarié → il reçoit
un e-mail EYWAI avec un lien `…/activation?token=…` → il choisit son mot
de passe sur une page aux couleurs EYWAI → son compte existe, scopé à sa
société. Supabase invisible de bout en bout. C'est le composant 1 du
design d'intégration (`docs/superpowers/specs/2026-08-19-integration-par-vagues-design.md`).

**Architecture:** Jetons MAISON (table + hash), pas les liens Supabase :
usage unique, expiration 7 jours et ré-envoi restent sous notre contrôle,
et rien de Supabase ne transparaît. Le backend valide le jeton puis crée
ou met à jour l'utilisateur auth par l'API admin. Contrainte majeure :
`EMAIL_FORCE_REDIRECT_TO` est posé en PROD (tout e-mail est redirigé
depuis le 07/08) → levée CIBLÉE par allowlist d'adresses exactes,
uniquement pour ce flux — jamais de retrait du redirect global.

**Tech Stack:** FastAPI/Pydantic, Supabase auth admin, migration SQL,
React (page publique + bouton RH), pytest.

## Global Constraints

- Branche `dev-lien-activation` depuis `main` à jour, CI verte. Tests
  `cwd=backend`, AUCUNE connexion réseau depuis un test.
- Leçons des 5 faux verts : tester par les VRAIS points d'entrée, jamais
  moquer ensemble deux fonctions dont l'interaction est le sujet, blinder
  les tests existants qui se mettent à toucher le réseau.
- RÈGLE ABSOLUE (mémoire projet) : jamais d'e-mail fabriqué. Un employé
  sans adresse réelle (vide ou `…@dsn-import.local`) n'est PAS invitable —
  refus explicite avec message actionnable.
- Migration : d'abord sur l'environnement de TEST (workflow
  `deploy-test-env.yml`, migration nommée), la CI d'intégration tape la
  vraie base de test (poser la migration AVANT de pousser le code qui la
  lit, sinon PGRST205).
- Sécurité : jeton haché en base (sha256), comparaison en temps constant,
  messages d'erreur indifférenciés (pas d'énumération), aucune donnée
  sensible sur l'endpoint public de vérification.
- Ne jamais toucher backend/.env, docs/afaire.md, landing/, AGENTS.md.

---

### Task 1: Migration `employee_activation_tokens`

Colonnes : id uuid pk, employee_id fk employees, company_id fk companies,
token_hash text unique, email_envoye text, expires_at timestamptz,
used_at timestamptz null, invalidated_at timestamptz null, created_by
uuid, created_at timestamptz default now(). RLS ENABLED sans policy
publique (accès service uniquement — le client backend est service_role).
Index (employee_id), (token_hash). Fichier
`supabase/migrations/<horodatage>_employee_activation_tokens.sql`.
⚠ Ne PAS l'appliquer soi-même : elle part par le déploiement (db push
prod) et le workflow test — mais les tests unitaires n'en ont pas besoin
(Supabase moqué).

### Task 2: Backend — module `app/modules/activation/`

Suivre la structure DDD des modules voisins (`modules/_template`).

**Commande RH `invite_employee(employee_id, ctx)`** :
- Gardes : employé existe et actif ; e-mail réel (non vide, pas
  `@dsn-import.local`) sinon erreur 422 `{code: "email_manquant"}` ;
  l'appelant a l'accès RH sur la société (patron des routers existants).
- Invalide les jetons antérieurs non utilisés (invalidated_at), génère
  `secrets.token_urlsafe(32)`, stocke le sha256, expires_at = +7 jours.
- Envoie l'e-mail (voir Task 3). Retourne {invited_at, email(masqué),
  expires_at}.
- Ré-envoi = même commande (les anciens jetons meurent).

**Endpoints publics** (`/api/activation/…`, sans auth) :
- `POST /verify` {token} → 200 {prenom, societe} si jeton valide (non
  utilisé, non invalidé, non expiré) ; sinon 400 générique « Lien invalide
  ou expiré » — le même message pour tous les cas.
- `POST /complete` {token, password} → valide le jeton (temps constant
  sur le hash), politique de mot de passe alignée sur l'existant (chercher
  la règle du reset actuel ; à défaut : ≥ 10 caractères), puis :
  1. utilisateur auth existant pour cet e-mail → update password +
     email_confirm ; sinon `auth.admin.create_user(email, password,
     email_confirm=True)` (patron de
     `employees/infrastructure/providers.py:85-95`) ;
  2. lier le compte au salarié : ÉTUDIER comment un compte salarié
     fonctionne aujourd'hui (`resolve_my_employee_id_for_user`,
     `employees.user_id` ?) et reproduire EXACTEMENT ce câblage — critère
     d'acceptation : après activation, `GET /api/me/payslips` répond 200
     (vide, puisque rien n'est validé) pour ce compte ;
  3. marquer le jeton used_at ; un second /complete avec le même jeton →
     400 générique.
- Throttling minimal : les erreurs de jeton loguées ; pas de détail au
  client.

**Route RH** : `POST /api/rh/employees/{id}/invitation` + un GET d'état
(dernier jeton : invité le, expiré ?, activé ? — activé = employees lié
à un compte auth). Mapping d'erreurs par codes structurés comme au lot 3.

### Task 3: E-mail — levée ciblée du redirect

Nouveau setting `ACTIVATION_EMAIL_ALLOWLIST` (adresses exactes séparées
par des virgules, comparaison casse-insensible, vide par défaut).
L'envoi d'activation : si le destinataire est dans l'allowlist → envoi
DIRECT (sans `_apply_forced_redirect`) ; sinon → flux normal (donc
redirigé en prod : le lien reste testable par nous sans jamais atteindre
un salarié par accident). Contenu : objet et corps sobres EYWAI, texte +
HTML, le lien `{FRONTEND_BASE_URL}/activation?token=…` — chercher
comment le dépôt construit déjà une URL frontend (var d'env existante ou
à créer `FRONTEND_BASE_URL`, à ajouter aux env_vars deploy.yml test+prod
avec les bonnes valeurs, et `ACTIVATION_EMAIL_ALLOWLIST` vide par
défaut). JAMAIS le mot Supabase nulle part.

### Task 4: Frontend

- Route PUBLIQUE `/activation` : lit `?token=`, appelle /verify →
  accueil « Bonjour {prenom} » + société ; champs mot de passe +
  confirmation + jauge simple ; /complete → écran de succès avec bouton
  vers la connexion. Erreur → « Lien invalide ou expiré, demandez un
  nouveau lien à votre RH ». Styles du projet, défensif.
- Fiche salarié RH : bouton « Inviter » (ou « Renvoyer l'invitation ») +
  état (jamais invité / invité le X / activé) ; désactivé avec info-bulle
  si l'e-mail est manquant ou fabriqué. Suivre les patrons de toasts et
  d'appels API du projet.

### Task 5: Vérification

Chaîne complète en test (Supabase moqué) : invite → jeton haché stocké +
e-mail construit avec la bonne URL → verify → complete → auth admin
appelé + câblage salarié + jeton consommé → second complete refusé →
jeton expiré refusé → ré-envoi invalide l'ancien. Allowlist : dedans =
direct, dehors = redirigé (vérifier par le VRAI sender avec
EMAIL_FORCE_REDIRECT_TO simulé). Suites complètes back + front + lint +
build. Puis passe adversariale (dispositif habituel) avant merge.
