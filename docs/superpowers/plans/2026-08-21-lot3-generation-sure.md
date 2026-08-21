# Lot 3 — Génération sûre

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** La génération de bulletins cesse d'être un canon sans sécurité :
un calendrier manquant bloque au lieu de payer un salaire plein en
silence, un bulletin validé n'est plus écrasable sans trace, le salarié
n'est notifié qu'à la validation et ne voit jamais un brouillon.

**Architecture:** Tout passe par le point d'entrée unique
`generate_payslip` (backend/app/modules/payslips/application/commands.py,
~85-125) qui couvre heures ET forfait — les gardes vivent là, jamais dans
les générateurs. Fait établi : les 1308 bulletins de prod sont tous
`brouillon` (aucune validation n'a jamais eu lieu) → aucune reprise de
données, le lot pose le contrat cible pour la vague 3.

**Tech Stack:** FastAPI/Pydantic, Supabase, pytest ; frontend React
(Payroll.tsx, GeneratePayrollModal).

## Global Constraints

- Tests `cwd=backend`, `venv/bin/python -m pytest` ; AUCUNE connexion
  réseau depuis un test (Supabase toujours moqué). Baseline : 5229 verts.
- Branche `dev-lot3-generation-sure` depuis `main` à jour, CI verte.
- Commits par chemins explicites ; ne jamais toucher `backend/.env`,
  `docs/afaire.md`, `landing/`, `AGENTS.md`.
- Gardes côté SERVEUR (leçon du lot 1 : un frontend ancien ne doit jamais
  pouvoir contourner) ; les overrides sont explicites, tracés, jamais le
  défaut.

---

### Task 1: Garde « calendrier manquant/incomplet » à la génération

**Files:** `backend/app/modules/payslips/application/commands.py`,
`backend/app/modules/payslips/api/router.py` (endpoint
`/api/actions/generate-payslip`), test nouveau
`backend/tests/unit/payslips/test_generation_gardes.py`.

Comportement : avant génération, calculer la complétude du calendrier du
mois (`app.modules.schedules.domain.ecart_rules.compute_row_status` — la
même règle que la revue pré-paie ; regarder comment
`payroll/application/preflight_anomalies.py:186-206` l'appelle pour
construire ses entrées). Si `a_saisir` → HTTP 422 avec un détail
actionnable `{code: "calendrier_incomplet", message: ...}`, SAUF si le
payload porte `force_calendrier_incomplet: true` — auquel cas on génère
et la réponse porte `warnings: [{code: "calendrier_incomplet_force"}]`,
et un `logger.warning` trace l'auteur (`current_user`). Le défaut reste
le refus.

TDD : test rouge « mois sans calendrier → 422 et le générateur n'est PAS
appelé », « force → généré + warning », « mois complet → généré sans
warning ». Attention aux mocks : `generate_payslip` est appelé aussi par
`ijss_tracking/apply_to_payslip` et la boucle frontend — vérifier les
appelants internes (`grep generate_payslip`) et leur passer un
comportement explicite (apply_to_payslip régénère un mois déjà complet :
il ne doit PAS être bloqué — lui faire passer le force avec trace, ou
vérifier que son mois est complet par construction : trancher en lisant).

### Task 2: Un bulletin validé n'est plus écrasable en silence

**Files:** `backend/app/modules/payslips/application/commands.py`,
`backend/app/modules/payslips/infrastructure/comparison_queries.py`
(lecture status existante), même fichier de test.

Comportement : `generate_payslip` lit le bulletin existant
(company/employee/year/month). Si `status == "valide"` → HTTP 409
`{code: "bulletin_valide"}` SAUF `regenerer_bulletin_valide: true`.
En cas de force, AVANT l'upsert du générateur : archiver dans
`edit_history` une entrée `{action: "regeneration", previous_payslip_data,
previous_pdf_url, horodatage, auteur}` (réutiliser le format de
`payslip_editor.py:159-175`), puis APRÈS génération : repasser `status`
à `"brouillon"`, purger `payslip_data.alerts_status` (les acquittements
portaient sur l'ancien contenu) et remettre `manually_edited` à False.
Le tout via une fonction dédiée testée seule.

TDD rouge d'abord : « régénérer un valide sans force → 409, upsert non
appelé », « avec force → archive écrite AVANT, statut brouillon après,
alerts_status purgé ».

### Task 3: Notifier le salarié à la VALIDATION, une seule fois

**Files:** `backend/app/modules/payslips/application/commands.py`
(`_notify_payslip_available`, appelé ~118-121),
`backend/app/modules/payslips/application/comparison_service.py`
(`validate_payslip_for_user`, ~204-251), test.

Comportement : retirer l'appel de notification du flux de génération.
L'appeler à la fin de `validate_payslip_for_user` en cas de succès, avec
idempotence : poser `payslip_data["salarie_notifie_le"] = <iso>` et ne
jamais renotifier si présent (une re-validation après régénération
forcée renotifie car la purge de Task 2 retire aussi ce marqueur —
comportement voulu : le contenu a changé). Adapter les tests existants
qui attendaient la notification à la génération (les trouver par grep
`_notify_payslip_available`).

### Task 4: L'espace salarié ne montre que du validé

**Files:** `backend/app/modules/payslips/infrastructure/queries.py`
(`get_my_payslips`, ~51-63), test.

Ajouter `.eq("status", "valide")` à la requête. Conséquence assumée et
documentée en docstring : tant que la RH ne valide pas, l'espace salarié
est vide — c'est le contrat de la vague 3 du design d'intégration (aucun
salarié n'est connecté aujourd'hui ; 1308/1308 bulletins sont brouillon).

### Task 5: Frontend — surfacer les refus et le force

**Files:** `frontend/src/features/dashboard/widgets/GeneratePayrollModal.tsx`,
`frontend/src/pages/rh/Payroll.tsx` (+ hook `usePayrollGeneration`).

Le 422 `calendrier_incomplet` s'affiche avec le message et propose
« Générer quand même » (qui repasse l'appel avec
`force_calendrier_incomplet: true`) — le confirm existant du modal est
remplacé par ce flux serveur. Le 409 `bulletin_valide` s'affiche avec
« Régénérer (archive l'ancien) » qui repasse avec
`regenerer_bulletin_valide: true`. Défensif si les codes sont absents
(vieux backend). Lint + tests + build frontend.

### Task 6: Vérification de bout en bout

Suite complète backend 0 échec, front vert, et un test qui chaîne :
génération → validation (mock) → notification une fois → régénération
forcée → statut redevenu brouillon → re-validation → renotification.
