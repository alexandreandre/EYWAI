# Lot 4 — Pauses, heures sup, fuseau : le badgeage devient digne de confiance

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Avant d'ouvrir le badgeage à la vague 1 : plus de « 1 h de
pause » fantôme sur les feuilles importées, un paramétrage « pause 0 »
enregistrable, une validation des heures sup qui retient réellement, des
heures badgées calculées dans le bon fuseau, et la pause réellement
badgée qui prime sur le forfait.

**Architecture:** Cinq défauts confirmés par la revue vérifiée
(`docs/revue-chaine-paie-2026-08.md` §A6, §A12-14) et leurs pièges de
correction documentés par les relecteurs. Zéro dégât historique côté
badgeuse (2 badges de test en prod) : on corrige avant l'usage réel.

**Tech Stack:** Python/FastAPI, pytest ; zoneinfo (stdlib) pour le fuseau.

## Global Constraints

- Branche `dev-lot4-pauses-hs-tz` depuis `main` à jour (APRÈS merge du
  lot 3), CI verte. Tests `cwd=backend`, aucune connexion réseau.
- Leçons acquises : tester par les VRAIS points d'entrée ; ne jamais
  moquer ensemble deux fonctions dont l'interaction est le sujet ; les
  tests existants qui se mettent à toucher le réseau après un ajout d'I/O
  révèlent l'I/O — les blinder explicitement.
- Fixes généralistes ; jamais backend/.env, docs/afaire.md, landing/,
  AGENTS.md.

---

### Task 1: Tuer le « ~1 h de pause » des imports

**Files:**
- Modify: `backend/app/modules/schedules/application/timesheet_page_schema.py:80`
  (prompt IA — retirer l'instruction de déduction, demander les heures
  BRUTES DEBUT/FIN sans calcul de pause : la pause est l'affaire du
  serveur)
- Modify: `backend/app/modules/schedules/application/handwritten_weekly.py:159-205`
  (le repli serveur `-60 min` en dur ET la condition `recompute` : le
  serveur recalcule TOUJOURS depuis DEBUT/FIN + réglage société ; sans
  réglage société → AUCUNE déduction + warning `pause_non_parametree`
  dans les warnings d'import — plus jamais une heure silencieuse)
- Modify: `backend/app/modules/schedules/application/punch_accounting_service.py:32`
  (bump `PUNCH_CALC_RULES_VERSION` — piège documenté : l'empreinte de
  cache des aperçus ignore la version du prompt, sans bump les aperçus
  resserviraient l'ancien calcul)
- Test: `backend/tests/unit/schedules/test_pauses_imports.py` (nouveau)

Vérité de référence : `test_normalize_keeps_ai_hours_without_company_settings`
(backend/tests/unit/schedules/test_handwritten_weekly.py:128-149)
verrouille l'ANCIEN comportement — il doit être retourné (rouge d'abord).

### Task 2: « Pause 0 » et « tolérance 0 » enregistrables — 5 sites

**Files:**
- Modify: `backend/app/modules/schedules/infrastructure/punch_accounting_repository.py:31-32`
  (`or 30`/`or 45` → `x if x is not None else défaut`)
- Modify: `backend/app/modules/schedules/application/punch_accounting_commands.py:27-29,96`
  (idem sur la réponse API — l'UI réaffichait 45 avec un toast « enregistré »)
- Modify: `backend/app/modules/schedules/domain/punch_accounting_rules.py:73,84`
  (créneaux : `break_deduct_minutes or 45` et `theoretical_gross_minutes or 465`
  — précisément ce qu'une société qui badge ses pauses configurerait)
- Test: rouge d'abord — enregistrer 0, relire 0, calculer avec 0.
  Les colonnes sont NOT NULL DEFAULT en base : 0 est une valeur légale.

### Task 3: La validation des heures sup retient vraiment

**Files:**
- Modify: `backend/app/modules/schedules/domain/punch_accounting_rules.py:275-286`
- Modify: `backend/app/modules/schedules/application/punch_accounting_commands.py`
  (approbation/refus → recalcul)
- Test: `backend/tests/unit/schedules/test_hs_validation_effective.py` (nouveau)

Constats vérifiés : quand une revue est requise, la branche retient le
POINTÉ COMPLET (HS incluses) — exiger la validation paie PLUS que ne pas
l'exiger ; approuver n'injecte jamais (la fonction n'est branchée que sur
calculate_payroll_events, que le générateur écrase) ; refuser est un no-op.
⚠ Piège documenté : NE PAS brancher l'injection sur le générateur
(double comptage garanti, les HS sont déjà dans accounted_hours).

Correction :
1. `needs_review` → `accounted = theoretical` (les HS en attente ne sont
   PAS payées) + la revue créée porte le détail.
2. Approbation → recalcul du jour : `accounted = theoretical + overtime`
   écrit dans `actual_hours.calendrier_reel` (le chemin que TOUS les
   recalculs lisent), via la fusion préservante du lot 1.
3. Refus → `accounted = theoretical` confirmé + trace.
4. Chaîne testée de bout en bout : badge avec dépassement → heures
   retenues sans HS → approbation → heures avec HS → analyzer les
   qualifie (test qui traverse punch_accounting → calendrier → analyzer).

### Task 4: Les heures badgées vivent en Europe/Paris

**Files:**
- Modify: `backend/app/modules/schedules/application/badgeuse_import.py:62-104`
  (`_first_last_punch_minutes` : projeter les timestamps en Europe/Paris
  avant d'en tirer des minutes murales)
- Modify: `backend/app/modules/badgeuse/domain/time_tracking.py:144-162`
  (regroupement par jour LOCAL, pas par date UTC — les nuits < 2 h du
  matin ne se coupent plus)
- Modify: `backend/app/modules/badgeuse/application/_internals.py:213`,
  `qr_service.py:101-107`, `punch_service.py:161`,
  `badgeuse/infrastructure/repository.py:42-76`
  (horodatage aware UTC à l'écriture ; fenêtres de jour construites en
  Europe/Paris converties en UTC pour les requêtes)
- Test: `backend/tests/unit/badgeuse/test_fuseau_horaire.py` (nouveau)

⚠ Contexte vérifié : les timestamps STOCKÉS sont corrects (timestamptz) ;
le bug est l'arithmétique murale sans conversion (badge 8 h Paris l'été
lu comme 6 h → 2 h de fausses HS « entrée en avance »). Poser `TZ=` sur
le conteneur n'est PAS le fix (fragile, et l'INSERT naïf dépendrait du
fuseau de la base). Le fuseau est une constante applicative
(`Europe/Paris`) dans un module partagé, pas un réglage par appel.
Zéro donnée historique à migrer (badgeuse jamais utilisée en prod).

### Task 5: La pause réellement badgée prime

**Files:**
- Modify: `backend/app/modules/schedules/application/badgeuse_import.py:62-104`
  (retourner AUSSI la pause mesurée = amplitude − somme des séquences)
- Modify: `backend/app/modules/schedules/domain/punch_accounting_rules.py:92-141`
  (`resolve_break_minutes` accepte `measured_break_minutes`, prioritaire
  sur créneau/forfait ; le seuil `break_threshold` se compare au NET)
- Test: le scénario du relecteur — 08:00-19:00 avec 2 h de pause badgée =
  9 h travaillées, PAS 10,25 h ni HS fantômes.

Constat vérifié : moteur activé = première entrée/dernière sortie
seulement → la pause badgée est réintégrée en temps travaillé puis une
pause forfaitaire retirée → HS fantômes. Activer le moteur DÉGRADAIT le
chemin badgeuse par rapport au moteur éteint.

### Task 6: Vérification adversariale puis merge

Même dispositif que les lots 1 et 3 : relecteurs indépendants
(efficacité par exécution sur les vrais chemins, régression — notamment
Colorplast et MBC déjà paramétrées dont le double run papier/badge ne
doit pas bouger —, chasse aux contournements), delta final, merge sur
verdict PRÊT uniquement.
