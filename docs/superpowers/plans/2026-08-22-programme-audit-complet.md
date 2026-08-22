# Programme d'audit complet EYWAI — re-vérification du code et du système

Écrit le 22/08/2026, à la veille de l'arrivée des premiers utilisateurs
réels (vague 0 le 24/08). Rien d'opérationnel ici : c'est le programme.

## Pourquoi ce plan, et pas une relecture ligne à ligne

Le dépôt fait des centaines de fichiers ; relire tout le code trouverait
peu. Ce qui a réellement attrapé les problèmes jusqu'ici : les passes
adversariales (5 faux verts attrapés), les tests par les vrais points
d'entrée HTTP, le sabotage (prouver qu'un test mord), et la confrontation
au réel (backtests bulletin par bulletin, requêtes sur la base prod, appels
curl sur l'infra déployée — c'est un appel réel qui a trouvé le 500 de
collision, pas une relecture). Le programme applique ces méthodes, axe par
axe, ordonnées par risque.

**Méthode standard de chaque axe** : inventaire → finders adversariaux
(chacun cherche à casser, pas à confirmer) → vérification indépendante de
chaque conclusion (preuve exécutée, jamais « ça a l'air bon ») → sabotage
des gardes pour prouver que les tests mordent → rapport avec verdict par
point. Un point sans preuve exécutée reste « non vérifié », jamais « OK ».

---

## Axe A — Sécurité et accès (À FAIRE EN PREMIER : semaine du 25/08)

Les utilisateurs réels arrivent ; c'est l'axe dont le coût d'un raté est
immédiat. Dépôt GitHub PUBLIC (choix assumé) : la surface est mondiale.

1. **RLS Supabase** : solder les 6 policies `{public} USING(true)`
   résiduelles (dont `company_work_time_periods` et
   `employee_overtime_routing_decisions` en ALL) ; advisor complet
   prod + test (4 ERROR côté test connus) ; vérifier que chaque table
   nominative est inaccessible avec la clé anon (test réel par curl,
   pas par lecture des policies).
2. **Surfaces publiques** : inventaire exhaustif des routes sans
   authentification (activation, health, quoi d'autre ?) ; pour chacune,
   test d'énumération, d'injection et de volumétrie (rate limiting —
   absent aujourd'hui sur l'activation, finding connu).
3. **RBAC effectif** : matrice rôle × action testée par de VRAIS appels
   authentifiés par rôle (le bug « directeurs privés de tout » venait
   d'un écart entre permissions déclarées et accès effectif) ; vérifier
   les 181 permissions sur les routes sensibles (paie, salaires,
   documents).
4. **Comptes auth** : recenser les comptes orphelins (cas Elsa — combien
   d'autres ?), les doubles fiches (cas Gaëlle Bouali/KEWITZ), les 227
   placeholders DSN ; politique de mot de passe identique sur TOUS les
   chemins (activation ✔, reset ?, création admin ?, provisionnement ?).
5. **Secrets et données personnelles** : gitleaks sur l'historique
   complet (pas seulement les nouveaux commits) ; vérifier qu'aucune
   table nominative n'est revenue dans le code (règle : tout dans
   `data/`, jamais dans un `.py`).

Livrable : rapport `docs/audit-securite-<date>.md` + correctifs en lots
TDD adversariaux. Effort estimé : 2-3 jours de sessions.

## Axe B — Moteur de paie (dès le 27/08 : données de juillet)

L'audit du moteur, c'est le backtest — pas la relecture.

1. **Backtest juillet 2026 systématique** sur les 7 sociétés dès
   réception des bulletins + DSN + virements du 27 (méthode DSN codes
   S21.G00.xx, réconciliateur existant, `pdftotext -layout` pour les
   bulletins Cegid 2 pages).
2. **Lot 2 (vocabulaire CP)** : `conge` vs `conges_payes` — LE chantier
   restant de la revue §G, à backtester avec juillet.
3. **Lots 5-8** de la revue §G (revue-chaine-paie-2026-08.md).
4. **Invariants moteur** : petite suite de propriétés (net jamais > brut,
   cotisations bornées, prorata ∈ [0,1], totaux DSN = totaux bulletins)
   exécutée sur TOUS les bulletins prod à chaque génération.

Livrable : écarts au centime par société, familles d'écarts, correctifs
généralistes uniquement (jamais de code spécifique à un salarié).

## Axe C — Chaîne RH → paie : re-vérifier la revue du 20/08

Reprendre les 25 problèmes confirmés de `docs/revue-chaine-paie-2026-08.md`
et re-vérifier UN PAR UN, preuve exécutée à l'appui, ce qui est réellement
soldé par les lots 0/1/3/4 et ce qui reste. Le document dit « corrigé » ;
l'audit exige la preuve rejouée sur la prod actuelle (les 5 faux verts sont
nés exactement de cette confiance-là).

Livrable : tableau 25 lignes → soldé (preuve) / restant (lot).

## Axe D — Intégrité des données prod

Script d'invariants rejouable (lecture seule) exécuté périodiquement :
soldes CP négatifs ou aberrants, doublons NIR (`nir_match_key`), fiches
sans contrat cohérent, `prior_service_months` double ancienneté (latent,
~237 fiches), absences sans jour calendrier, bulletins orphelins,
e-mails placeholder sur fiche (interdits), incohérences fiche ↔ compte
auth. Chaque anomalie : compte + exemples + gravité.

Livrable : `scripts/invariants_donnees.py --rapport` + cron hebdo.

## Axe E — Fiabilité opérationnelle

1. **Workflows CI/CD eux-mêmes** : l'historique des faux verts (« Deploy
   success » sans rien prouver, prod bloquée 3 jours sans alerte) montre
   que la CI est un objet d'audit à part entière. Vérifier : chaque job
   critique casse-t-il vraiment le pipeline quand il échoue ? (sabotage
   de CI en branche).
2. **Migrations** : diff du schéma RÉEL prod vs test vs dépôt (jamais via
   l'historique `supabase_migrations`, non fiable des deux côtés).
3. **Alerte** : aujourd'hui, un échec silencieux en prod n'alerte
   personne. Définir le minimum : échec de cron, taux d'erreurs 5xx,
   échec d'envoi d'e-mail `require_delivery`.
4. **Sauvegarde/restauration** : la restauration n'a jamais été testée ;
   la resynchro test est cassée depuis le 29/07 (pooler Supavisor —
   action utilisateur connue). Un test de restauration réel sur l'env
   test vaut audit.

## Axe F — Qualité du code (dernier : n'empêche rien de marcher)

Le stock de findings non bloquants déjà collectés : dédup du câblage de
compte (4e copie sans allocation de username → réutiliser
account_provisioning), invitabilité renvoyée par le backend (tuer le
miroir front), 4 copies du layout e-mail, TOCTOU delete/edit bulletins,
`elif` mort punch_accounting_service ~l.219, rate limiting activation.
Traiter en un lot « ménage » TDD, sans urgence.

---

## Ordre et cadence proposés

| Quand | Quoi |
| --- | --- |
| Avant le 24/08 | Rien — l'état est vérifié et stable pour la démo |
| Semaine du 25/08 | Axe A (sécurité) complet |
| Dès le 27/08 | Axe B (backtest juillet + lot 2) — prioritaire sur tout |
| Puis | Axe C (re-vérif des 25), Axe D (invariants) |
| Ensuite | Axe E (ops), Axe F (ménage) |

Règles transverses (leçons de session, non négociables) : jamais deux
fonctions moquées ensemble quand leur interaction est le sujet ; tests par
les vrais points d'entrée ; sabotage avant de croire un vert ; backtest
lourd en session directe, pas en sous-agent ; vérifier le ref de base
avant tout `--apply` ; attendre la fin d'un Deploy avant de re-pousser.
