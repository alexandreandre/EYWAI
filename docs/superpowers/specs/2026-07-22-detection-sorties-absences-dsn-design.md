# Détection des sorties, absences prolongées et versements post-départ depuis la DSN

Date : 2026-07-22
Statut : approuvé (design), lecture seule

## Contexte / cause racine

Cas déclencheur : Mohamed Imad OSMANI (matricule `OSMANI2`, MBC), supposé « sorti »
depuis février 2026, mais EYWAI génère encore des bulletins (net ≈ −80 € en avril/juin,
≈ 3 016 € en mai = participation).

Preuves tirées des DSN réelles MBC (`Config/MBC/DSN/`, jan→mai 2026) :

- Il est **présent dans chaque DSN**, contrat `S21.G00.40` déclaré ouvert, **aucun bloc
  fin de contrat `S21.G00.62`**.
- Blocs arrêt `S21.G00.60` : arrêt maladie **continu depuis le 23/02/2026** (23/02→27/03,
  31/03→30/04, 03/05→31/05, sans reprise).
- Net réel : jan 1490,58 · fév 1507,19 · mars −234,59 · avr 766,45 · mai 2519,93
  (dont participation FY2025 `S21.G00.54`=11 : 2974,29).

**Conclusion : ce n'est pas une sortie mais une absence prolongée (arrêt maladie).**
`employment_status='actif'` est correct. Le net ≈ 0/négatif = seule la mutuelle salariale
(46,86 €) reste prélevée pendant l'arrêt non rémunéré ; mai = participation universelle.

Pourquoi EYWAI produit de mauvais bulletins :

1. Les arrêts DSN n'ont jamais été importés comme absences (réimport config resté en
   `manual_workforce_reconciliation`, non committé) → moteur sans absence → bulletin dégénéré.
2. La réconciliation d'effectifs est inopérante :
   - ne tourne qu'en mode `monthly`, pas à la config ;
   - **bug de matching NIR** : base = NIR 15 chiffres, DSN = NIR 13 chiffres (sans clé)
     → 0 correspondance → ~73-75 faux « manquants » par mois = bruit ;
   - ne connaît que « absent de la DSN » et « fin de contrat explicite » — pas la
     catégorie « présent mais inactif » (absence prolongée).

## Objectif

Détecter, **avant la paie** et sans mutation automatique, les 3 situations et présenter
une recommandation fiable :

- **sortie** : `S21.G00.62` présent (ce mois ou antérieur), ou individu disparu de la DSN ;
- **absence prolongée** : individu déclaré, sans G62, arrêt/suspension couvrant ~tout le
  mois et brut DSN ≈ 0 ;
- **versement postérieur au départ** : sortie déjà connue + réapparition avec
  participation/STC uniquement.

Général, sans hardcode salarié/entreprise.

## Conception

### 1. Fix prérequis — matching NIR 13↔15

`nir_match_key(nir)` (pur) dans `app/modules/dsn_import/domain/normalize.py` :
ne garde que les chiffres ; si 15 → tronque à 13 (retire la clé) ; sinon garde tel quel ;
`""` si vide. Utilisée des deux côtés (`_normalize_nir`) dans la réconciliation.

### 2. Classifieur de situation — domaine pur

Nouveau module `app/modules/dsn_import/domain/employee_dsn_situation.py`, sans dépendance
DB/FastAPI.

```
class DsnSituation(str, Enum):
    ACTIVE_NORMAL, LIKELY_DEPARTURE, PROLONGED_ABSENCE, POST_EXIT_PAYMENT

@dataclass(frozen=True)
class DsnSituationSignals:
    employment_status, period_start, period_end, working_days_in_period,
    present_in_dsn, has_fin_contrat, fin_contrat_last_working_day,
    exit_last_working_day, absence_days_in_period, period_brut, period_net,
    has_only_post_exit_remuneration

@dataclass(frozen=True)
class DsnSituationResult:
    situation, recommendation, evidence

def classify(signals) -> DsnSituationResult
```

Priorité de classification :

1. Sortie déjà connue (`exit_last_working_day < period_start` ou G62 antérieur) + présent
   avec versement post-départ uniquement → `POST_EXIT_PAYMENT`.
2. G62 dont le dernier jour ouvré tombe dans/à proximité de la période → `LIKELY_DEPARTURE`.
3. Absent de la DSN → `LIKELY_DEPARTURE`.
4. Présent + arrêt couvrant une large part de la période (seuil ≥ 80 % des jours ouvrés)
   + `period_brut` ≈ 0 (seuil bas) → `PROLONGED_ABSENCE`.
5. Sinon `ACTIVE_NORMAL`.

Chaque situation non-normale porte une `recommendation` (texte RH) et `evidence`
(jours d'arrêt, brut, dates).

### 3. Câblage dans la réconciliation

Dans `workforce_reconciliation.compute_workforce_gaps` :

- grouper les items par `nir_match_key` (employee / absence / exit / cumul) ;
- appliquer le fix NIR aux deux ensembles comparés ;
- pour chaque individu **présent** rapproché d'un salarié actif, construire
  `DsnSituationSignals` (arrêts → `absence_days_in_period` ; cumul `month_totals` → brut/net ;
  exit item / `current_exit` → G62) et appeler `classify` ;
- `PROLONGED_ABSENCE` / `POST_EXIT_PAYMENT` → **advisories non bloquantes** ajoutées au
  `workforce_summary` (`advisories`) et aux `anomalies` (severity `warning`, avec reco).
  Le comportement bloquant existant (`missing_from_dsn`, `contract_end_in_dsn`) est conservé.

Le classifieur reste réutilisable tel quel par un futur service pré-paie autonome.

### Hors périmètre (non demandé)

Import automatique des arrêts, ouverture automatique des sorties (mutations = risque de
régression paie).

## Tests

- `nir_match_key` : 13 / 15 / espaces / NTT / vide.
- `classify` : les 4 situations + limites (profil OSMANI = absence prolongée ; départ G62 ;
  disparu ; participation post-départ ; actif normal ; arrêt partiel = actif normal).
- Intégration réconciliation : items « présent + arrêts couvrant le mois + cumul brut≈0 »
  → advisory `prolonged_absence` ; NIR 13/15 rapproché (plus de faux manquants).
