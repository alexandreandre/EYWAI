# Refonte du socle IA et de l'import calendrier

**Date** : 2026-08-28 · **Statut** : en revue · **Trajectoire validée** : « C puis A » (pansement config appliqué le 29/08, ce document couvre le chantier A).

## 1. Contexte et problème

Diagnostic du 29/08 sur l'import d'un relevé Colorplast (env de test) :

- **OOM** : le rendu 300 DPI garde en RAM les PNG de toutes les pages, plus un
  double passage OCR ; l'instance Cloud Run 2 Gi est tuée en plein job
  (« Memory limit exceeded », logs 03:20–03:26 UTC).
- **Job zombie** : le job meurt avec l'instance mais reste en « extracting » ;
  le front polle indéfiniment — l'échec ressemble à une attente infinie.
- **Lenteur structurelle** : OCR Tesseract en force brute (3 PSM × jusqu'à
  5 orientations sur la page 1, double OCR du document, poppler relancé par
  page), jusqu'à 2 appels LLM par page, le tout en `BackgroundTasks` sur un
  CPU throttlé par Cloud Run après la réponse HTTP.
- **Socle IA embryonnaire** (`app/shared/infrastructure/ai/`, 336 lignes) :
  client OpenRouter synchrone sans timeout explicite (défaut SDK 600 s), pas
  de retry/backoff centralisé, pas de trace coût/latence, aucune entrée PDF
  native — d'où la dépendance à l'OCR local. Appels bloquants dans des
  handlers `async` : l'event loop gèle pendant chaque appel IA.

Le pansement C (fait, hors spec) : services `sirh-backend` et
`sirh-backend-test` passés à 4 Gi / 2 vCPU / `--no-cpu-throttling`
(prod plafonnée à 5 instances pour le quota régional), workflows de
déploiement alignés.

## 2. Objectifs

- **P1 — Import calendrier** : extraction fiable et rapide d'un relevé de
  pointeuse (objectif : ~10 pages en < 30 s, < 1 Gi de RAM, zéro job zombie).
- **P2 — Remplissage calendrier par IA** : même socle, latence réduite,
  event loop jamais bloqué.
- **Socle commun** : les autres modules IA (copilot, contrats, recrutement…)
  migrent ensuite sans réécriture, chantier par chantier.

## 3. Architecture cible

### 3.1 Socle `app/shared/infrastructure/ai/` v2

- **Client async** : `AsyncOpenAI` vers OpenRouter, timeouts explicites
  (connexion ~10 s, lecture par défaut 120 s, surchargables), retries
  centralisés avec backoff sur 429/5xx (2 tentatives), et journalisation
  systématique par appel : cas d'usage, modèle, tokens, latence, succès.
  Le client sync actuel reste pendant la transition ; les endpoints encore
  synchrones enveloppent les appels via `run_in_threadpool`.
- **Entrée document native** : `extract_structured_json_from_document(...)`
  accepte un PDF (ou une image) envoyé **nativement** au modèle via les
  file parts OpenRouter (Gemini lit le PDF sans OCR préalable), avec
  découpage par lots de pages pour les gros documents et appels parallèles
  plafonnés (asyncio, plafond partagé avec `TIMESHEET_PAGE_CONCURRENCY`).
- `models.py` inchangé (le nettoyage des `gpt-4o-mini` hérités est un
  chantier séparé, voir Hors scope).

### 3.2 P1 — pipeline d'import cible

1. **Fast path déterministe inchangé** : texte pdfplumber → parseur Cegid ;
   s'il matche avec confiance suffisante, aucun appel IA.
2. **Sinon, extraction native** : le PDF est découpé en lots de pages
   (pypdf, sans rendu image ; 4 pages par lot par défaut, configurable)
   envoyés en parallèle au modèle avec le schéma JSON de page existant
   (`PAGE_EXTRACTION_JSON_SCHEMA`), enrichi de la période détectée — la
   détection de mois se fait dans le même appel, le pré-scan OCR disparaît.
   Le consensus/merge actuel est conservé côté code.
3. **Tesseract sort du chemin critique.** Le mode est piloté par le flag
   existant `TIMESHEET_EXTRACT_MODE` qui gagne une valeur `native`
   (défaut après validation) ; `hybrid` reste disponible en repli immédiat
   (rollback par variable d'env, sans redéploiement de code).
4. **Mémoire bornée** : jamais plus d'un lot de pages en vol par worker ;
   plafond de pages inchangé (120).
5. **Progression** : `pages_done` alimenté à la complétion de chaque lot,
   comme aujourd'hui.

### 3.3 Robustesse des jobs (P1 et au-delà)

- **Watchdog stale-jobs** : heartbeat émis au début **et** à la fin de chaque
  lot (`updated_at`) ; au `GET /jobs/{id}`, un job « extracting » sans
  heartbeat depuis plus de 5 minutes (> 2 × le pire cas d'un lot : lecture
  120 s × 2 tentatives) est marqué `failed` avec un message explicite.
  Le front affiche l'erreur et propose « Relancer » (le fichier est déjà en
  storage : relance sans re-upload).
- L'exécution reste en `BackgroundTasks` : avec le CPU non throttlé et un
  pipeline devenu essentiellement I/O, un worker dédié (option B) n'est pas
  justifié aujourd'hui.

### 3.4 P2 — remplissage par consigne

Migration sur le client async du socle (timeout lecture 60 s, retries du
socle). Un seul appel, pas de parallélisme : le bénéfice est la fin du gel de
l'event loop et des erreurs mieux racontées. Aucun changement de contrat API.

## 4. Découpage du chantier

1. Socle v2 (client async + retries + journalisation + entrée document native)
   — testable seul, sans toucher aux modules.
2. Watchdog stale-jobs + bouton « Relancer » côté front.
3. P1 : mode `native` derrière le flag, éval comparative, bascule du défaut.
4. P2 : migration du remplissage NL sur le socle.
5. (Séparé) migration progressive des autres modules et nettoyage `models.py`.

## 5. Validation

- **Unitaires** : socle (transport mocké : timeouts, retries, parsing),
  découpage en lots, watchdog (job périmé → failed).
- **Éval comparative avant bascule** : script rejouant un panier de relevés
  réels (Colorplast, Cegid, manuscrits — réutiliser `scripts/backtest/`)
  en `hybrid` vs `native` ; critère de bascule : qualité ≥ hybrid sur le
  panier, temps et RAM mesurés.
- **E2E existants** : la suite `qa-e2e-test-env` reste verte.

## 6. Risques et parades

- **Qualité sans le consensus OCR** : c'est le pari du natif ; l'éval
  comparative tranche avant la bascule, et le flag permet le retour arrière
  instantané.
- **Limites d'entrée** : cap upload actuel 15 Mo conservé ; un PDF > taille
  acceptée par le fournisseur est découpé en lots plus petits (pypdf).
- **Coût tokens** : le natif supprime un des deux appels par page ; à
  surveiller via la journalisation du socle.

## 7. Hors scope

Worker dédié avec queue (option B), refonte du copilot, nettoyage des modèles
hérités `gpt-4o-mini`, OCR pour les images seules (une photo de feuille passe
déjà par l'entrée image native).
