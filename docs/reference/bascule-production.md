# Bascule : la base de test devient la production

Document vivant. À tenir à jour à chaque étape franchie.
Dernière mise à jour : 26/09/2026.

## En bref

- **Quand** : un soir d'octobre ou de novembre 2026, quand tout est prêt. Pas de
  date fixe.
- **Quoi** : rien n'est copié. La base de test, qui porte déjà la vraie paie de
  Colorplast, devient la production. L'ancienne production est gelée.
- **D'ici là** : personne ne pousse sur `main`. Le workflow « Deploy »
  redéploierait le site de test avec le code de `main`, donc remplacerait le
  moteur de la paie réelle. On déploie une branche sur le test à la main :
  `gh workflow run deploy-test-env.yml --ref <branche>`.

Source : le plan de l'audit du code du 25/09/2026 (axes 8 et 9).

## Décisions à prendre

Elles reviennent à Alexandre. Sans elles, le jour J ne peut pas être écrit.

1. **Projets Supabase** : un seul (le test devient la production) ou deux.
   Faut-il un nouveau bac à sable pour essayer les changements après la bascule ?
2. **Ancienne production et six autres sociétés** : archiver après export, ou
   reprendre leurs données.
3. **Restauration à la minute** (option payante chez Supabase). Sinon, accepter
   par écrit de pouvoir perdre une journée de saisie.
4. **Adresse du site** : garder les services `sirh-*-test` (l'adresse « test »
   reste visible), réutiliser `sirh-backend` et `sirh-frontend`, ou créer des
   services neufs avec un domaine à soi.
5. **E-mails** : aujourd'hui, aucun e-mail ne part du site de test, pas même la
   réinitialisation d'un mot de passe. Envoyer avec une liste d'adresses
   autorisées, ou lever la redirection.
6. **Qui approuve les déploiements, qui reçoit les alertes**, et Sentry ou non.

## À préparer avant

- [x] Couper le job d'intégration de la CI, qui écrivait dans la base de test
      (26/09/2026).
- [ ] Mettre une approbation obligatoire sur l'environnement GitHub
      `production` et sur les workflows manuels qui écrivent dans la base.
- [ ] Réconcilier le registre des migrations de la base de test
      (`supabase migration repair`), puis vérifier `supabase migration list` :
      zéro en attente. D'ici là, jamais de `supabase db push` contre cette base.
- [ ] Écrire la liste de ce qui part au nettoyage des données.
- [ ] Écrire les réglages à changer (plus bas), dans un fichier de variables
      par service, gardé hors du dépôt.
- [ ] Relire le retour arrière (plus bas).
- [ ] Sauvegarder les fichiers du Storage de façon planifiée, et jouer une
      restauration à blanc une fois.
- [ ] Surveiller les nouvelles adresses : smoke horaire, alertes sur les
      erreurs 5xx.
- [ ] Traiter les alertes de sécurité et de performance de Supabase (advisors).
- [ ] Dire où l'on essaiera les changements une fois le test devenu production.

## La veille

1. Mettre le workflow « Deploy » en pause.
2. Fusionner la branche de travail dans `main` : PR, CI verte, approbation.
3. Réécrire « Deploy » pour une seule cible, avec approbation obligatoire. Le
   job qui redéploie le test vise un nouveau projet de test, ou disparaît.
4. Prévenir la gestionnaire de paie. Choisir un soir hors clôture de paie.

## Le jour J

1. **Geler.** Arrêter les tâches automatiques qui écrivent. Noter quelques
   compteurs (bulletins, salariés, fichiers du Storage) pour comparer après.
2. **Sauvegarder.** Un export complet de la base (`supabase db dump`), rangé
   hors du dépôt. Une copie complète du Storage
   (`python -m scripts.sauvegarder_stockage`, depuis `backend/`). L'identifiant
   de la sauvegarde physique du jour (`supabase backups list`).
3. **Vérifier, en lecture.** `python -m scripts.invariants_donnees` (n'écrit
   rien). Une seule société a une reprise de paie. Les bulletins importés
   couvrent janvier à juillet.
4. **Régler le backend**, d'un seul bloc :
   - `APP_ENV=prod`. Cela lève les verrous du test : signature électronique,
     dépôt de DSN par API (sans effet tant que `NET_ENTREPRISES_ENABLED=false`),
     transmission comptable. La route de resynchro de l'application refuse.
   - E-mails, selon la décision 5 : `EMAIL_FORCE_REDIRECT_TO`,
     `ACTIVATION_EMAIL_ALLOWLIST`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
     `SMTP_PASSWORD`, `FROM_EMAIL`, `FROM_NAME`, `REPLY_TO`.
   - `FRONTEND_URL` et `ALLOWED_ORIGINS_EXTRA` : la nouvelle adresse du site.
   - `SECRET_ENCRYPTION_KEY` : posée explicitement.
   - Les clés des services externes : `PISTE_CLIENT_ID`, `PISTE_CLIENT_SECRET`,
     `OPENROUTER_API_KEY`, `YOUSIGN_API_KEY`, `YOUSIGN_WEBHOOK_SECRET`,
     `YOUSIGN_BASE_URL`.
   - `COPILOT_RH_DATA_ENABLED`, `TIMESHEET_EXTRACT_MODE=native`. Retirer
     `GITHUB_REPO`.
5. **Reconstruire le frontend** sans `VITE_APP_ENV=test` (le bandeau orange est
   figé au build), avec `VITE_API_URL` = le nouveau backend.
6. **Régler GitHub.** Les secrets `SUPABASE_URL`, `SUPABASE_KEY`,
   `SUPABASE_SERVICE_KEY`, `SUPABASE_SERVICE_ROLE_KEY` et `SUPABASE_DB_URL`
   prennent les valeurs du projet de test ; les tâches planifiées suivent. Les
   variables `VITE_API_URL`, `FRONTEND_URL_PROD` et les noms de services suivent
   la décision 4. Le smoke horaire vise les nouvelles adresses. Les tests
   Playwright ne doivent plus viser cette base.
7. **Après.** Nouvelle sauvegarde complète. Smoke sur les nouvelles adresses.
   Un vrai e-mail vers une adresse autorisée. La gestionnaire de paie ouvre un
   bulletin et le vérifie.

## Retour arrière

À relire avant le jour J.

- **Code** : revenir à la révision précédente, backend puis frontend :
  `gcloud run services update-traffic <service> --to-revisions <révision>=100`.
  Les révisions précédentes restent disponibles.
- **Réglages** : réappliquer le fichier de variables d'avant, gardé hors du
  dépôt.
- **Base** : la bascule ne joue aucune migration destructrice. En cas de
  corruption, restaurer par Supabase (sauvegarde physique du jour, ou
  restauration à la minute si elle est activée).
- **Point de non-retour** : dès qu'une paie est saisie dans la nouvelle
  configuration, revenir à l'ancienne production ferait perdre ces saisies.
- **Ancienne production** : ne rien y toucher pendant 30 jours. Ses services
  restent démarrables.

## Ce qu'il ne faut pas faire

- Pousser sur `main` avant la veille.
- Lancer `supabase db push` contre la base de test avant d'avoir réconcilié son
  registre.
- Réactiver « Refresh test from prod » : la resynchro effacerait la vraie paie.
- Lancer `tests/integration` depuis un poste dont le `.env` vise la base de test.
