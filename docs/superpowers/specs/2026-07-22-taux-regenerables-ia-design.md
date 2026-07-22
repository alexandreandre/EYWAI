# Design — Rendre tous les taux régénérables via IA depuis l'UI

**Date :** 2026-07-22
**Branche de départ :** `fix/user-rights-update-platform-admin`
**Statut :** design validé, en attente de relecture avant plan d'implémentation

---

## 1. Contexte & problème

Sur la page **Suivi des taux** (`/super-admin/rates`), certaines catégories affichent
un « Dernier contrôle » mais **aucun bouton de régénération**. Racine confirmée :

- La section « Barèmes & abattements » affiche **génériquement toute clé
  `payroll_config`** non exclue (boucle `for key of Object.keys(data)` dans
  [`ratesSyncManifest.ts`](../../../frontend/src/lib/ratesSyncManifest.ts)).
- Le bouton n'apparaît que si `canUpdate = sources.length > 0`
  ([`RatesBaremesSection.tsx:169`](../../../frontend/src/components/rates/RatesBaremesSection.tsx#L169),
  [`RatesCategoryCard.tsx:72`](../../../frontend/src/components/rates/RatesCategoryCard.tsx#L72)).
- `sources` vient du manifeste backend
  ([`sync.py:213`](../../../backend/app/modules/rates/application/sync.py#L213)) qui
  n'itère que sur `RATE_KEY_TO_SOURCE_KEYS`
  ([`rate_source_mapping.py`](../../../backend/app/modules/rates/domain/rate_source_mapping.py)) — 12 clés seulement.

Les catégories concernées (Cdd, Comptes Avances Acomptes, Interim, Jei, Maladie,
Mandataire, Oeth, Payslip Edit Lock, Réduction générale, Stage, Taux Intérêt Légal)
**n'ont aucune source rattachée** → pas de bouton. « Dernier contrôle » = simple
`last_checked_at` de la ligne `payroll_config`, **trompeur** (aucun scraper derrière).

## 2. Objectif

Rendre **régénérable depuis l'UI** chaque taux légal de la liste, via **l'IA**
(Sonar / OpenRouter), **sans écrire de scraper HTML custom**, avec **revue humaine
avant écriture** en base. Nettoyer les 1 cas qui n'a rien à faire là.

## 3. Décisions actées (Q&A utilisateur)

1. **IA, pas de scraper HTML.** Un bouton « régénérer » dans l'UI pour chaque taux.
2. **`payslip_edit_lock`** → **retiré** de « Suivi des taux » (c'est un paramètre
   produit, pas un taux légal) et **relogé** dans une **nouvelle page
   « Paramètres paie »** (section *Référentiels* de la nav super-admin), toujours
   consultable/modifiable. Reste global plateforme (pas de bascule per-entreprise).
3. **`comptes_avances_acomptes`** → régénérable via IA en mode « confirmation du
   Plan Comptable Général » (ligne globale uniquement). Faible priorité.
4. **Mono-source IA ⇒ human-gated** : jamais d'écriture directe, toujours un
   *pending change* validé manuellement.

### 3.1 Contraintes utilisateur confirmées (garde-fous non négociables)

- **Simplicité** : livrer « un truc assez simple qui marche » pour les catégories
  qui n'avaient ni bouton ni moyen de régénération. Pas de sur-ingénierie.
- **Intégration « régénérer tout / une section »** : les nouveaux taux doivent être
  pris en compte quand on régénère une catégorie entière ou toute la page. **Garanti
  par construction** : ajouter le `config_key` à `RATE_KEY_TO_SOURCE_KEYS` suffit —
  `all_page_source_keys()` (Mise à jour complète) et le sync par section itèrent
  dessus. Aucun code additionnel.
- **Ne rien casser** : **interdiction de modifier** les orchestrateurs / générations
  de scrapers existants. Chaque nouveau taux est un ajout strictement isolé.

## 4. Architecture

### 4.1 Fabrique de spec IA mono-source

Réutiliser **le chemin existant** (aucun code UI à écrire) : un taux devient
régénérable dès qu'il a (a) une entrée `RATE_KEY_TO_SOURCE_KEYS`, (b) une ligne
`scraping_sources` active, (c) un orchestrateur.

Nouveauté : un builder générique `build_ai_rate_spec(...)` produisant une `RateSpec`
([`core/rate_spec.py`](../../../backend/scraping/core/rate_spec.py)) avec **un seul
script `_AI.py`** (pas de parser HTML primaire), sur le modèle **ALTERNANCE**
(mono-source, human-gated). Signature indicative :

```
build_ai_rate_spec(
    scraper_name: str,
    config_key: str,
    source_url: str,
    target_schema: dict,        # forme EXACTE lue par le moteur
    extract_prompt: str,        # consigne d'extraction
    validate: Callable,         # bornes anti-hallucination
    persistence_mode = FULL,
)
```

- `dual_source_consensus = False`, `warn_single_source = True` (déjà supportés).
- Extraction via [`core/ai_extractor.py`](../../../backend/scraping/core/ai_extractor.py) /
  [`openrouter_client.py`](../../../backend/scraping/openrouter_client.py).

### 4.2 Human-gating (obligatoire)

La régénération **n'écrit jamais** `payroll_config` directement. Elle crée un
*pending change* ([`core/pending.py`](../../../backend/scraping/core/pending.py),
[`apply_pending_change.py`](../../../backend/scraping/core/apply_pending_change.py))
visible dans « Validation & alertes » (`MonthlyReviewTab`), avec diff avant/après.
L'utilisateur valide → écriture. Motif : source IA unique, pas de consensus.

### 4.3 Wiring (par taux)

| Fichier | Modification |
|---|---|
| `backend/scraping/<Dir>/orchestrator.py` + `<Dir>/<X>_AI.py` | nouvel orchestrateur IA (via la fabrique) |
| `backend/scraping/core/migrated_specs.py` | `SPEC_<X>` |
| `backend/scraping/scraper_manifest.py` | `ScraperEntry` (tier + checks, pour `test_scrapers.py`) |
| `backend/app/modules/rates/domain/rate_source_mapping.py` | `RATE_KEY_TO_SOURCE_KEYS[config_key] = ["<SOURCE_KEY>"]` |
| `backend/app/modules/scraping/infrastructure/scraper_runner.py` | `SOURCE_KEY_TO_FOLDER_MAPPING` si dossier ≠ source_key |
| **Base cloud** `scraping_sources` | 1 ligne active (`source_key`, `primary_url`, `orchestrator_path`, `is_active=true`) |

Aucun changement front n'est requis pour faire apparaître les boutons : ils
s'allument dès que `RATE_KEY_TO_SOURCE_KEYS` + la ligne `scraping_sources` existent.

## 5. Catalogue des taux — schémas cibles **réels** (relus dans le moteur)

> Les schémas ci-dessous sont la forme **exacte** lue par le moteur. L'IA doit
> produire cette forme, rien d'autre. Unités = **fractions décimales** (0,10 = 10 %).

| `config_key` | Schéma cible (extrait des consommateurs) | Consommateur | Source officielle | Bornes de validation |
|---|---|---|---|---|
| `taux_interet_legal` | `{ "taux_annuel": 0.0352 }` | [`payroll_queries.py:18`](../../../backend/app/modules/employee_loans/infrastructure/payroll_queries.py#L18) | Banque de France / service-public (arrêté semestriel) | `0 ≤ taux_annuel ≤ 0.20` |
| `cdd` | `{ "precarite": {"actif": true, "taux": 0.10}, "indemnite_conges": {"taux": 0.10} }` | [`calcul_brut.py:170`](../../../backend/app/modules/payroll/engine/calcul_brut.py#L170) | service-public (C. trav. L1243-8) | `precarite.taux ∈ [0,0.15]`, `indemnite_conges.taux ∈ [0.08,0.12]` |
| `interim` | `{ "ifm": {"actif": true, "taux": 0.10}, "indemnite_conges": {"taux": 0.10} }` | [`calcul_brut.py:213`](../../../backend/app/modules/payroll/engine/calcul_brut.py#L213) | service-public (L1251-32) | idem CDD |
| `stage` | `{ "actif": true, "pct_plafond_horaire_ss": 0.15 }` (option `plafond_horaire_ss`) | [`exoneration_stage.py`](../../../backend/app/modules/payroll/engine/exoneration_stage.py) | URSSAF / service-public | `pct ∈ [0.10,0.20]` |
| `maladie` | `{ "csg_ijss": {"taux_deductible": 0.038, "taux_non_deductible": 0.029} }` | [`ijss_bulletin.py:20`](../../../backend/app/modules/payroll/engine/ijss_bulletin.py#L20) | BOSS (CSG/CRDS sur IJSS) | chaque taux `∈ [0,0.10]` |
| `mandataire` | `{ "cotisations_exclues": ["assurance_chomage","ags","chomage","apec"] }` | [`calcul_cotisations.py:429`](../../../backend/app/modules/payroll/engine/calcul_cotisations.py#L429) | URSSAF (mandataire assimilé salarié) | liste ⊆ ensemble connu de `coti_id` |
| `oeth` | `DEFAULT_OETH_CONFIG` (`taux_obligation` 0.06, `coefficients {20_249:400,250_749:500,750_plus:600,surcontribution:1500}`, `boeth_50_plus_factor` 1.5, `ecap_deduction_factor` 17, `neutralisation_years` 5, `surcontribution_years` 3, `seuil_assujettissement` 20) | [`headcount_service.py`](../../../backend/app/modules/oeth_settings/infrastructure/headcount_service.py) + [`constants.py`](../../../backend/app/modules/oeth_settings/domain/constants.py) | URSSAF (contribution DOETH) | `taux_obligation ∈ [0,0.10]`, coefficients `> 0` |
| `jei` | `{ "actif": true, "facteur_smic_plafond": 4.5, "cotisations_exonerees_patronales": [...] }` | [`exoneration_jei.py:174`](../../../backend/app/modules/payroll/engine/exoneration_jei.py#L174) | BOSS / URSSAF (JEI) | `facteur_smic_plafond ∈ [3,6]` |
| `reduction_generale` | `{ "actif": true, "tmin": ..., "p": 1.75, "point_sortie_smic": 3.0, "tdelta": {"fnal_moins_50": ..., "fnal_50_et_plus": ...} }` | [`calcul_reduction_generale.py:270`](../../../backend/app/modules/payroll/engine/calcul_reduction_generale.py#L270) | BOSS (RGDU) | `p ∈ [1,3]`, `point_sortie_smic ∈ [1.6,4]`, `tdelta.* ∈ [0,0.5]` |
| `comptes_avances_acomptes` | `{ "<type>": "425", "512": "512", ... }` (comptes PCG, **ligne globale**) | [`queries.py:63`](../../../backend/app/modules/saisies_avances/infrastructure/queries.py#L63) | Plan Comptable Général | valeurs = codes PCG numériques |

**Nuances importantes :**
- `taux_interet_legal` est publié en **%** mais stocké en **fraction** (0,0352). L'IA
  doit convertir + le taux est **semestriel** → on stocke le taux en vigueur du mois.
- `maladie.csg_ijss` recoupe conceptuellement le scraper CSG existant ; garder les
  deux distincts, valider la cohérence des taux au moment de la revue.
- `reduction_generale` est **couplé au FNAL** (déjà scrapé) : le `tdelta` dépend du
  taux FNAL. Validation croisée à la revue.
- `oeth` / `jei` : la ligne **globale** (`company_id = null`) porte les **paramètres
  légaux** (scrapables). La config **par entreprise** (statut JEI, effectif OETH,
  overrides) vit ailleurs (`jei_settings`, `oeth_settings`, `parametres_paie`) et
  **n'est jamais touchée**.
- `mandataire` est une **liste de règles**, pas un nombre → l'IA confirme la liste
  standard ; faible enjeu, faible priorité.

## 6. `payslip_edit_lock` — sortie + relogement

1. **Exclusion** de la boucle « Barèmes & abattements » : ajouter `payslip_edit_lock`
   à `BAREMES_EXCLUDED_KEYS` dans
   [`ratesSyncManifest.ts`](../../../frontend/src/lib/ratesSyncManifest.ts) → il
   disparaît de la page + plus de « Dernier contrôle » trompeur.
2. **Nouvelle page « Paramètres paie »** :
   - Route `/super-admin/payroll-settings`, entrée nav dans `ADMIN_NAV_SECTIONS`
     ([`navigation.ts`](../../../frontend/src/pages/admin/eywai/navigation.ts), section *Référentiels*).
   - Y déplacer la carte existante `PayrollPayslipEditLockCard` (aujourd'hui montée
     dans `RatesAdminPanel`) → la retirer de
     [`RatesAdminPanel.tsx:64`](../../../frontend/src/components/rates/RatesAdminPanel.tsx#L64).
   - API inchangée (`GET/PATCH /api/rates/.../payslip-edit-lock` déjà en place).
3. Reste **global plateforme** (pas de per-entreprise ; hors périmètre).

## 7. `comptes_avances_acomptes` — IA « confirmation PCG »

Régénère **uniquement la ligne globale** (défauts PCG : 425 avances/acomptes,
512 banque). Les overrides `company_id` ne sont jamais touchés. Human-gated, priorité
basse (codes quasi immuables).

## 8. Validation & anti-hallucination (par taux)

- **Schéma verrouillé** : rejet si la sortie IA ne matche pas la forme cible.
- **Bornes** (colonne du §5) : rejet si valeur hors plage.
- **Human-gating** : diff avant/après visible, validation manuelle obligatoire.
- **`test_scrapers.py`** : chaque `ScraperEntry` porte ses `ScraperCheck` (bornes,
  `year_current`, `not_null`) exécutés en test.

## 9. Base de données production (`scraping_sources`)

Ces lignes ne sont **pas versionnées** (base cloud, RLS). Les créer = écrire en prod.
Livrable : un **script contrôlé** (`backend/scripts/…`) idempotent listant les lignes
à insérer (source_key, source_name, primary_url, orchestrator_path, is_active, tier,
is_critical=false), lancé **après OK explicite** de l'utilisateur. Rappel projet :
clés `.env` Supabase potentiellement inversées → vérifier `SUPABASE_SERVICE_KEY`.

## 10. Séquencement (livrer sûr, taux par taux)

1. **Pilote `taux_interet_legal`** (source la plus stable) : builder + orchestrateur
   IA + wiring + ligne `scraping_sources` + test → valider **tout le cycle**
   (régénère → pending → validation → écriture) de bout en bout.
2. `cdd`, `interim`, `stage` (⚡ simples, C. trav.).
3. `maladie`, `mandataire`, `oeth`, `jei`, `reduction_generale` (🔶 moyens).
4. `comptes_avances_acomptes` (confirmation PCG, dernier).
5. En parallèle bloc UI : sortie + relogement `payslip_edit_lock`.

Chaque taux est un incrément **indépendant** et **testable** isolément.

## 11. Tests

- `test_scrapers.py` : une `ScraperEntry` + checks par nouveau taux.
- Test de la **fabrique** `build_ai_rate_spec` (schéma/bornes/validation) avec un
  payload IA simulé (pas d'appel réseau réel en CI).
- Test **non-régression moteur** : les valeurs par défaut du §5 sont exactement
  celles déjà lues → aucun changement de comportement paie tant qu'aucun pending
  n'est appliqué. Garder verts : payroll (~381), MBC/Colorplast/Lewis.
- Test front : `payslip_edit_lock` exclu de la section Barèmes ; nouvelle page rend
  la carte.

## 12. Risques & points de vigilance

- **Erreur de schéma** (le plus grave) : mitigé par les schémas §5 relus dans le code
  + validation de forme + human-gating.
- **Hallucination IA** : bornes + revue humaine.
- **Écriture prod** : `scraping_sources` via script contrôlé + OK explicite ; pending
  changes jamais auto-appliqués.
- **Couplages** : `maladie`↔CSG, `reduction_generale`↔FNAL → validation croisée à la
  revue.

## 13. Hors périmètre (YAGNI)

- Transformer `payslip_edit_lock` / `comptes_avances_acomptes` en per-entreprise.
- Toucher aux configs **par entreprise** JEI/OETH.
- Toute auto-application sans revue humaine.
- Refonte des scrapers HTML existants.
