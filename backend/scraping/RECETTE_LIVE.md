# Recette live scraping EYWAI

Document de recette pour valider les **26 orchestrateurs** scraping avant mise en production.
Trois niveaux (tiers) :

| Tier | Mode | Automatisé | Écriture BDD |
|------|------|------------|--------------|
| **0 — CI** | Compile + pytest fixtures | Oui (bloquant PR) | Non |
| **1 — Dry-run live** | Réseau, `--dry-run`, `--no-ai` | Oui (local + workflow hebdo) | Non |
| **2 — Staging** | Orchestrateurs sans dry-run | Manuel (checklist) | Oui |

L’IA (`*_AI.py`) est **hors scope** de la recette live : utiliser `--no-ai` ou `EYWAI_SCRAPING_DISABLE_AI=1`.

---

## Prérequis

### Environnement

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### Variables d’environnement

| Variable | Tier 0–1 | Tier 2 (staging) |
|----------|----------|------------------|
| `SUPABASE_URL` | Non requis | **Requis** |
| `SUPABASE_SERVICE_KEY` | Non requis | **Requis** |
| `OPENROUTER_API_KEY` | Non requis (IA désactivée) | Optionnel |
| `EYWAI_SCRAPING_DISABLE_AI=1` | Recommandé en recette | Recommandé |

Fichier : `backend/.env` (ne jamais committer).

### Migrations Supabase (Tier 2)

Appliquer toutes les migrations, notamment :

- `supabase/migrations/20260530100000_scraping_sources_complete_and_cotisations_seed.sql`
- Migrations `scraping_source_*` antérieures

### Selenium (IJ maladie uniquement)

- Chrome + ChromeDriver installés
- Tier 1 : échec IJ documenté acceptable si ameli.fr bloque l’automation
- Tier 2 : tester IJ manuellement avec navigateur visible si besoin

---

## Phase A — Dry-run global (automatisée, Tier 1)

### Commandes

```bash
cd backend

# Tous les orchestrateurs (26), sans IA, sans écriture BDD
./venv/bin/python scraping/test_scrapers.py --live --no-ai

# Sous-ensemble rapide (~10 scrapers critical, ~15 min)
./venv/bin/python scraping/test_scrapers.py --live --no-ai --tier critical

# Ciblage manuel
./venv/bin/python scraping/test_scrapers.py --live --no-ai --only SMIC,PSS,CSG
```

### Critères de succès

- **26/26 OK** en sortie JSON (`total_ko = 0`)
- Les scrapers `static` (primes, heures supp) peuvent être `WARN` sans faire échouer le run global
- Un échec sur un scraper `critical` → code retour `1`
- Rapport JSON final : `{ total_ok, total_ko, total_warn, skipped_ai, results: [...] }`

### Échecs connus (à documenter si persistants)

| Scraper | Cause fréquente | Action |
|---------|-----------------|--------|
| IJmaladie | Selenium / ameli.fr | Vérifier ChromeDriver ; accepter WARN si site indisponible |
| VM | Timeout URSSAF | Relancer avec `--only VM` ; timeout manifeste = 300 s |

### Mode hermétique (Tier 0, sans réseau)

```bash
./venv/bin/python scraping/test_scrapers.py
./venv/bin/python -m pytest tests/unit/scraping/test_parsers_primary.py \
  tests/unit/scraping/test_parsers_secondary.py \
  tests/unit/scraping/test_validation_extended.py \
  tests/unit/scraping/test_orchestrator_manifest.py \
  tests/unit/scraping/test_consensus.py -v
```

---

## Phase B — Écriture staging (manuelle, Tier 2)

Pour chaque source : lancer l’orchestrateur **sans** `--dry-run`. L’écriture va dans `payroll_config` (company_id IS NULL).

### Vérification SQL après chaque lot

```sql
SELECT config_key, version, last_checked_at, is_active
FROM payroll_config
WHERE company_id IS NULL
ORDER BY config_key;
```

### Ordre recommandé (dépendances métier)

#### Lot 1 — Paramètres clés (S01–S03)

| Id | Source | Commande | Résultat attendu | Rollback |
|----|--------|----------|------------------|----------|
| S01 | SMIC | `./venv/bin/python scraping/SMIC/orchestrator.py` | `config_key=smic`, cas_general ~11–12 €, année courante | Désactiver version N, réactiver N-1 |
| S02 | PSS | `./venv/bin/python scraping/PSS/orchestrator.py` | `config_key=pss`, annuel ~46k €, horaire non null | Idem |
| S03 | PAS | `./venv/bin/python scraping/PAS/orchestrator.py` | `config_key=pas`, barème non vide | Idem |

#### Lot 2 — Cotisations URSSAF (S04–S17)

| Id | Source | Commande | Résultat attendu |
|----|--------|----------|------------------|
| S04 | CSG | `scraping/CSG/orchestrator.py` | Taux salarial deductible / non_deductible dans cotisations |
| S05 | AGS | `scraping/AGS/orchestrator.py` | patronal ∈ [0, 0.01] |
| S06 | CSA | `scraping/CSA/orchestrator.py` | patronal ∈ [0, 0.01] |
| S07 | alloc | `scraping/alloc/orchestrator.py` | plein + reduit non null |
| S08 | MMID patronal | `scraping/MMIDpatronal/orchestrator.py` | plein + reduit |
| S09 | MMID salarial | `scraping/MMIDsalarial/orchestrator.py` | taux alsace |
| S10 | vieillesse patronal | `scraping/vieillessepatronal/orchestrator.py` | plafonne + deplafonne |
| S11 | vieillesse salarial | `scraping/vieillessesalarial/orchestrator.py` | plafonne + deplafonne |
| S12 | CFP | `scraping/CFP/orchestrator.py` | moins_11 + plus_11 |
| S13 | FNAL | `scraping/FNAL/orchestrator.py` | moins_50 + plus_50 |
| S14 | dialogue social | `scraping/dialoguesocial/orchestrator.py` | patronal ~0,016 % |
| S15 | assurance chômage | `scraping/assurancechomage/orchestrator.py` | patronal ~4 % |
| S16 | taxe apprentissage | `scraping/taxeapprentissage/orchestrator.py` | patronal faible |
| S17 | AGIRC-ARRCO | `scraping/AGIRC-ARRCO/orchestrator.py` | 6 items (retraite_comp_t1…apec) |

#### Lot 3 — Prévoyance (S18–S19)

| Id | Source | Commande | Résultat attendu |
|----|--------|----------|------------------|
| S18 | Prévoyance cadre | `scraping/prevoyance/orchestrator_cadre.py` | patronal cadre ~1,5–2,5 % |
| S19 | Prévoyance non-cadre | `scraping/prevoyance/orchestrator_non_cadre.py` | structure data non vide |

#### Lot 4 — Orphelins affichage (S20–S24)

| Id | Source | Commande | Résultat attendu |
|----|--------|----------|------------------|
| S20 | IJ maladie | `scraping/IJmaladie/orchestrator.py` | `ij_plafonds`, maladie + maternite |
| S21 | Frais pro | `scraping/fraispro/orchestrator.py` | sections.repas |
| S22 | Avantages | `scraping/Avantages/orchestrator.py` | repas |
| S23 | Barème km | `scraping/bareme-indemnite-kilometrique/orchestrator.py` | vehicules.voitures, année courante |
| S24 | Versement mobilité | `scraping/versement_mobilite/orchestrator.py` | `taux_vmrr`, >100 lignes |

#### Lot 5 — Statiques (S25–S26)

| Id | Source | Commande | Résultat attendu |
|----|--------|----------|------------------|
| S25 | Heures supp | `scraping/heuressupp/orchestrator.py` | majoration_hs_25 / hs_50 (catalogue) |
| S26 | Primes | `scraping/primes/orchestrator.py` | catalogue primes non vide |

> **Rollback par source** : `UPDATE payroll_config SET is_active = false WHERE config_key = '…' AND version = 'N';` puis réactiver la version précédente.

---

## Phase C — Vérification frontend (Tier 2)

1. Ouvrir `/rates` (super-admin ou rôle autorisé).
2. Lancer une **sync partielle** (une catégorie) puis une **sync globale** via le bandeau / menu actions.
3. Contrôler :
   - Bandeau de sync (progression, succès/échec)
   - Dates `last_checked_at` cohérentes avec la recette staging
   - SMIC, PSS, cotisations clés (CSG, alloc, vieillesse)
   - Sections orphelines : IJ, frais pro, barème km, VM, heures supp, primes

---

## Phase D — Rollback global

En cas d’erreur staging :

1. **Par clé** : désactiver la version erronée et réactiver N-1 dans `payroll_config`.
2. **Snapshot** : restaurer un dump Supabase staging daté d’avant la recette.
3. **Frontend** : recharger `/rates` et relancer sync pour invalider le cache client.

```sql
-- Exemple : revenir à la version précédente du SMIC
UPDATE payroll_config SET is_active = false
WHERE config_key = 'smic' AND company_id IS NULL AND is_active = true;

UPDATE payroll_config SET is_active = true
WHERE config_key = 'smic' AND company_id IS NULL AND version = '<version_cible>';
```

---

## Matrice de scénarios (recette exhaustive)

### Tier 0 — CI (automatisé, bloquant)

| Id | Scénario | Commande / test |
|----|----------|-----------------|
| L01 | Compile tous les scripts scraping | `python scraping/test_scrapers.py` |
| L02 | Manifeste 26 entrées, pas de doublon | `test_orchestrator_manifest.py` |
| L03 | Parsers SMIC fixture URSSAF | `test_parsers_primary.py::test_smic_*` |
| L04 | Parsers PSS / CSG / alloc fixtures | `test_parsers_primary.py` |
| L05 | Parsers LegiSocial dialogue + IJ | `test_parsers_secondary.py` |
| L06 | Validateurs CSG, IJ, AGIRC, frais pro, barème | `test_validation_extended.py` |
| L07 | Consensus primary vs secondary | `test_consensus.py` |
| L08 | Extracteur IA mocké (sans réseau) | `test_ai_extractor_offline.py` |
| L09 | PAS parser fixture BOFiP | `test_pas_scraper.py` |

### Tier 1 — Dry-run live (automatisé, non bloquant PR)

| Id | Scénario | Critère |
|----|----------|---------|
| L10 | Dry-run 26 orchestrateurs `--no-ai` | `total_ko = 0` |
| L11 | Dry-run tier `critical` | ~10 scrapers OK |
| L12 | SMIC : cas_general 10–15 €, année courante | checks manifeste |
| L13 | SMIC : jeunes ≤ cas général | validation orchestrateur |
| L14 | PSS : horaire non null | check manifeste |
| L15 | Dialogue social : patronal non null | check manifeste |
| L16 | AGIRC-ARRCO : 6 ids présents | keys_present |
| L17 | IJ maladie : Selenium ou échec documenté | requires_selenium |
| L18 | VM : >100 lignes VMRR | min_rows=100 |
| L19 | Primes / heures supp : catalogue statique | tier static → WARN OK |
| L20 | IA skippée avec `--no-ai` | `skipped_ai > 0` si scripts IA présents |

### Tier 2 — Staging manuel

| Id | Scénario |
|----|----------|
| S01–S03 | Écriture SMIC, PSS, PAS + vérif SQL |
| S04–S17 | Écriture cotisations URSSAF + AGIRC |
| S18–S19 | Prévoyance cadre / non-cadre |
| S20–S24 | IJ, frais pro, avantages, barème km, VM |
| S25–S26 | Heures supp, primes (affichage) |

### Frontend manuel

| Id | Scénario |
|----|----------|
| F01 | Page `/rates` charge sans erreur |
| F02 | Sync partielle une catégorie |
| F03 | Sync globale toutes sources |
| F04 | Bandeau progression + message succès |
| F05 | Valeurs SMIC/PSS et cotisations clés visibles |

### Tests pytest edge cases

| Id | Scénario | Test |
|----|----------|------|
| E01 | Consensus divergence → repli primary | `test_prefer_primary_on_divergence` |
| E02 | Validation AGIRC bundle incomplet → KO | `test_validate_agirc_missing_item` |
| E03 | SMIC jeunes > général → KO | `test_validate_smic_young_leq_general` |
| E04 | Barème année hors fenêtre → KO | `test_validate_bareme_year` |
| E05 | Extracteur IA réponse vide → None | `test_extract_with_web_search_returns_none_on_empty` |

---

## Enregistrement de fixtures HTML (one-shot)

Pour régénérer les snapshots dans `backend/tests/fixtures/scraping/` :

```bash
# Exemple SMIC
curl -sL 'https://www.urssaf.fr/...' -o /tmp/smic.html
# Tronquer manuellement aux blocs <table> pertinents (~50–200 lignes)
cp /tmp/smic_trunc.html tests/fixtures/scraping/smic/urssaf.html
```

Fixtures existantes :

| Dossier | Parser testé |
|---------|--------------|
| `smic/urssaf.html` | `SMIC.extract_smic_data` |
| `pss/urssaf.html` | `PSS` |
| `csg/urssaf.html` | `CSG.get_taux_csg` |
| `alloc/urssaf.html` | `alloc.py` |
| `dialogue/legisocial.html` | `dialoguesocial_LegiSocial` |
| `ij/legisocial.html` | `IJmaladie` LegiSocial |
| `bareme/service_public.html` | barème km |
| `pas/bofip_snippet.html` | PAS |

---

## Références

- Manifeste : `backend/scraping/scraper_manifest.py`
- Harness : `backend/scraping/test_scrapers.py`
- Validation : `backend/scraping/core/validation.py`
- Workflow hebdo dry-run : `.github/workflows/scraping-live-dry-run.yml`
