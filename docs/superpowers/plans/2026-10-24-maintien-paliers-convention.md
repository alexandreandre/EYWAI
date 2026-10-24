# Paliers de la convention du maintien de salaire — plan d'exécution

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Sur ce chantier : exécution par `superpowers:executing-plans`, sans sous-agent (brief du 24/10).

**Goal :** un barème « Plasturgie (IDCC 0292) » que la société choisit dans la carte « Maintien de salaire ». Il applique les paliers de la convention (100 % puis 75 % ou 50 %), les durées par statut et par ancienneté, la carence des non-cadres (levée au premier arrêt de l'année), aucune pour les cadres, et une limite par arrêt et par année civile. Sans barème, rien ne bouge au centime ni à la clé.

**Architecture :**
- **Le barème** vit en données dans le domaine (`baremes_maintien.py`).
- **Un module pur** (`paliers_convention.py`) rejoue les arrêts connus du salarié et rend le taux de chaque jour.
- **Le moteur** (`maintien_salaire_service.py`) prend une branche quand `settings["bareme_convention"]` porte un barème :
  - valeur des jours : salaire du mois quand tout le mois est en arrêt, journées par bloc sinon ;
  - plancher légal calculé à part, comparé sur le versé ;
  - IJSS des jours maintenus déduites par palier ;
  - clés `bareme`, `paliers`, `regle_retenue` sur le maintien.
- **Autour** : le réglage (colonne, API, route qui décrit le barème), l'empreinte, l'explication de la ligne et l'écran (choix, tableau, champs masqués, détail des paliers).

**Tech Stack :** Python 3.11 (FastAPI, Pydantic v2, pytest), SQL Supabase, React + TypeScript (vitest, environnement node).

**Conception :** `docs/superpowers/specs/2026-10-24-maintien-paliers-convention-design.md` (8c9dc436, précisée en 42b59571). Elle fait foi.

**Répétition du 24/10.** Ce plan a été joué en entier sur une copie jetable de 8c9dc436, hors dépôt :
- chaque tâche échoue au Step 2, puis passe au Step 4 ;
- ensuite, `tests/unit` est vert (hors un test qui demande un vrai dépôt git), vitest passe 233 fichiers sur 233, le typecheck est propre ;
- les valeurs attendues des tests viennent de cette répétition.

Chaque bloc « remplacer » ou « insérer » cite le texte exact du fichier à 8c9dc436. Un bloc introuvable veut dire que le fichier a bougé : relire avant d'appliquer.
Un bloc inséré se colle tel quel, séparé de son voisin par les lignes vides d'usage : deux avant un `def` ou une `class` de module en Python, une ailleurs.

## Global Constraints

- **Sans barème** (colonne nulle ou clé absente du dict) : bulletin identique au centime et clé pour clé. Aucune clé nouvelle, aucun texte nouveau. Les tests existants restent verts sans modification.
- **L'empreinte** ne change que si la ligne de réglages porte un barème.
- **Sous le barème, le moteur ne lit aucun champ masqué** : `custom_duration_days`, `maintain_100_percent`, `taux_maintien_conventionnel`, `employer_waiting_days`, `remove_employer_waiting`, `annual_unique_waiting`, `differentiated_at_illness`, `no_seniority_condition`, `min_seniority_months`, `min_seniority_months_at_mp`, `paid_waiting_days_per_year`, `paid_waiting_min_seniority_months`, `apply_legal_maintenance`.
- **Lecture A** :
  - paliers comptés par arrêt ; limite par arrêt et par année civile ;
  - ancienneté en mois complets au début de l'arrêt ;
  - accident de trajet sans condition d'ancienneté ni carence, mais hors du minimum de 2 ans des cadres.
- **Base des jours** : mois entier en arrêt = salaire du mois (base et heures sup structurelles), au prorata des jours ; sinon des journées comptées par bloc (`_valeur_de_jours_ouvres`).
- **Plancher légal** toujours comparé, chaque mois, sur le versé, avec des règles fixes : 12 mois complets, 7 jours de carence (0 en accident du travail et maladie professionnelle hors trajet), durées de `duree_maintien_par_taux`.
- **IJSS** : la règle du 23/10 (IJSS des jours maintenus), par palier, plancher à 0 sur le mois.
- **Écran sans piège** : jamais un champ que le moteur ignore ; succès confirmé ; un choix non enregistré est rappelé. Textes en français simples ; le produit s'appelle « Martine ».
- Aucun nom de salarié dans le code, les tests ni les commits : initiales.
- Python 3.11 : aucune syntaxe propre à 3.12.
- **Rien n'est poussé, déployé ni appliqué en base. Aucun bulletin régénéré.** Colorplast et Comitech ne changent pas de réglage.
- Commits : `feat(paie): …`, ligne vide, `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Commandes** :
  - tests backend, depuis `backend/` : `APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest …` ;
  - front, depuis `frontend/` : `npx vitest run …`, `npm run typecheck`.
- **Référence locale du 24/10 sur 531773b8** : `tests/unit` est vert. `tests/integration/legacy` a déjà 24 échecs, sans lien avec le chantier : `test_bonus_types`, `test_employee_exit_non_regression`, `test_forfait_jour_complet`, `test_non_regression_bulletin`, `test_saisies_avances`, `test_saisies_avances_integration`.

## Fichiers

| Fichier | Rôle |
|---|---|
| `backend/app/modules/payroll/domain/baremes_maintien.py` | créer : le barème en données, la tranche d'un arrêt, la description de l'écran |
| `backend/app/modules/payroll/engine/paliers_convention.py` | créer : rejouer les arrêts connus, le taux de chaque jour |
| `supabase/migrations/20261024120000_bareme_convention_maintien.sql` | créer : la colonne `bareme_convention` |
| `backend/app/modules/maintenance_settings/schemas/{requests,responses}.py`, `application/{queries,commands}.py`, `api/router.py` | le réglage, la route qui décrit le barème |
| `backend/app/modules/payroll/engine/maintien_salaire_service.py` | valeur des jours, maintien au barème, plancher légal, autres lecteurs |
| `backend/app/modules/payroll/domain/paliers_affiches.py` | créer : carence, alertes, détail, explication |
| `backend/app/modules/payroll/domain/ijss_deduites.py` | la suite « moins … d'IJSS », réutilisée |
| `backend/app/modules/payroll/domain/explications_lignes.py` | la ligne de maintien dit ses paliers |
| `backend/app/modules/payroll/application/empreinte_entrees_service.py` | le barème n'entre que choisi |
| `frontend/src/api/maintenanceSettings.ts` | type, route des barèmes, deux champs morts retirés |
| `frontend/src/features/company/components/baremeConvention.ts` | créer : choix, champs remplacés, textes |
| `frontend/src/features/company/components/MaintenanceSettingsCard.tsx` | le choix, le tableau du barème, les champs masqués |
| `frontend/src/api/absences.ts`, `frontend/src/lib/paliersAffichage.ts` (créer), `frontend/src/components/payslip/MaintenanceDetailModal.tsx`, `frontend/src/components/absences/MaintenancePreviewBlock.tsx` | le détail des paliers |


---

### Task 1 : Le barème de la plasturgie, en données

**Files :**
- Create : `backend/app/modules/payroll/domain/baremes_maintien.py`
- Test : `backend/tests/unit/payroll/test_baremes_maintien.py`

**Interfaces :**
- Consumes : rien.
- Produces :
  - `CODE_PLASTURGIE = "plasturgie_0292"`, `CLE_BAREME = "bareme_convention"` ;
  - `FAMILLE_MALADIE`, `FAMILLE_ACCIDENT_TRAVAIL`, `FAMILLE_TRAJET`, `FAMILLE_PARENTALITE` ;
  - dataclasses gelées `Palier(taux, jours)`, `Tranche(des_mois, paliers)` avec `.limite` et `.taux_du_rang(rang) -> float`, `Categorie(titre, tranches, carence_jours, minimum_accident_travail_mois, notes)`, `Source`, `Bareme(code, libelle, nom_court, anciennete_requise_mois, non_cadres, cadres, sources, regles)` avec `.categorie(est_cadre)` ;
  - `PLASTURGIE`, `BAREMES: dict[str, Bareme]` ;
  - `bareme_par_code(code) -> Bareme | None`, `bareme_des_reglages(settings) -> Bareme | None` ;
  - `famille_du_type(arret_type) -> str`, `mois_complets(debut, jour) -> int` ;
  - `tranche_pour(bareme, *, est_cadre, mois_anciennete, famille) -> Tranche | None` ;
  - `pourcent(taux) -> str` (« 66,67 % »), `libelle_tranche(categorie, tranche) -> str`, `texte_paliers(tranche) -> str`, `description_lisible(bareme) -> dict`.

- [ ] **Step 1 : les tests, qui échouent**

Créer `backend/tests/unit/payroll/test_baremes_maintien.py` :

```python
"""Le barème de la plasturgie en données : tranches, paliers, limites, textes.

Avenant non-cadres du 15/05/1991, art. 13 ; accord cadres du 17/12/1992, art. 5
(Légifrance, 24/10/2026). Conception du 24/10/2026.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.domain.baremes_maintien import (
    FAMILLE_ACCIDENT_TRAVAIL,
    FAMILLE_MALADIE,
    FAMILLE_PARENTALITE,
    FAMILLE_TRAJET,
    PLASTURGIE,
    bareme_des_reglages,
    description_lisible,
    famille_du_type,
    mois_complets,
    pourcent,
    tranche_pour,
)

pytestmark = pytest.mark.unit


def _paliers(est_cadre, mois, famille=FAMILLE_MALADIE):
    tranche = tranche_pour(PLASTURGIE, est_cadre=est_cadre, mois_anciennete=mois, famille=famille)
    return None if tranche is None else [(p.taux, p.jours) for p in tranche.paliers]


@pytest.mark.parametrize(
    "mois, attendu",
    [
        (11, None),
        (12, [(1.0, 45), (0.75, 60)]),
        (59, [(1.0, 45), (0.75, 60)]),
        (60, [(1.0, 60), (0.75, 75)]),
        (274, [(1.0, 60), (0.75, 75)]),
    ],
)
def test_non_cadres_maladie(mois, attendu):
    assert _paliers(False, mois) == attendu


@pytest.mark.parametrize(
    "mois, attendu",
    [
        (11, None),
        (12, [(1.0, 45), (0.5, 45)]),
        (24, [(1.0, 60), (0.5, 60)]),
        (36, [(1.0, 90), (0.5, 90)]),
        (60, [(1.0, 120), (0.5, 120)]),
        (119, [(1.0, 120), (0.5, 120)]),
        (120, [(1.0, 150), (0.5, 150)]),
    ],
)
def test_cadres_maladie(mois, attendu):
    assert _paliers(True, mois) == attendu


def test_les_limites_sont_la_somme_des_paliers():
    assert [t.limite for t in PLASTURGIE.non_cadres.tranches] == [105, 135]
    assert [t.limite for t in PLASTURGIE.cadres.tranches] == [90, 120, 180, 240, 300]


def test_accident_du_travail_sans_condition_d_anciennete():
    assert _paliers(False, 6, FAMILLE_ACCIDENT_TRAVAIL) == [(1.0, 45), (0.75, 60)]
    # Cadres : au moins la tranche de 2 ans, hors trajet.
    assert _paliers(True, 6, FAMILLE_ACCIDENT_TRAVAIL) == [(1.0, 60), (0.5, 60)]
    assert _paliers(True, 40, FAMILLE_ACCIDENT_TRAVAIL) == [(1.0, 90), (0.5, 90)]
    assert _paliers(True, 6, FAMILLE_TRAJET) == [(1.0, 45), (0.5, 45)]
    assert _paliers(False, 6, FAMILLE_TRAJET) == [(1.0, 45), (0.75, 60)]


def test_la_parentalite_n_est_pas_dans_le_bareme():
    assert _paliers(False, 120, FAMILLE_PARENTALITE) is None


def test_le_taux_du_rang():
    tranche = tranche_pour(PLASTURGIE, est_cadre=False, mois_anciennete=60, famille=FAMILLE_MALADIE)
    assert [tranche.taux_du_rang(r) for r in (1, 60, 61, 135, 136)] == [1.0, 1.0, 0.75, 0.75, 0.0]


@pytest.mark.parametrize(
    "type_arret, famille",
    [
        ("maladie_simple", FAMILLE_MALADIE),
        ("maladie", FAMILLE_MALADIE),
        ("ald", FAMILLE_MALADIE),
        ("mi_temps_therapeutique", FAMILLE_MALADIE),
        ("accident_travail", FAMILLE_ACCIDENT_TRAVAIL),
        ("maladie_professionnelle", FAMILLE_ACCIDENT_TRAVAIL),
        ("rechute_at", FAMILLE_ACCIDENT_TRAVAIL),
        ("accident_trajet", FAMILLE_TRAJET),
        ("maternite", FAMILLE_PARENTALITE),
        ("paternite_accueil_enfant", FAMILLE_PARENTALITE),
    ],
)
def test_famille_du_type(type_arret, famille):
    assert famille_du_type(type_arret) == famille


def test_mois_complets_a_l_anniversaire():
    # Entrée le 28/05/2025 : 11 mois le 05/05/2026, 12 le 28/05/2026.
    assert mois_complets(date(2025, 5, 28), date(2026, 5, 5)) == 11
    assert mois_complets(date(2025, 5, 28), date(2026, 5, 28)) == 12
    assert mois_complets(date(2003, 7, 15), date(2026, 5, 4)) == 273


def test_le_bareme_se_lit_dans_les_reglages():
    assert bareme_des_reglages({"bareme_convention": "plasturgie_0292"}) is PLASTURGIE
    assert bareme_des_reglages({"bareme_convention": None}) is None
    assert bareme_des_reglages({}) is None
    assert bareme_des_reglages({"bareme_convention": "inconnu"}) is None


def test_pourcent():
    assert [pourcent(t) for t in (1.0, 0.75, 0.5, 0.9, 2 / 3)] == [
        "100 %", "75 %", "50 %", "90 %", "66,67 %",
    ]


def test_la_description_lisible_de_l_ecran():
    d = description_lisible(PLASTURGIE)
    assert d["code"] == "plasturgie_0292"
    assert d["libelle"] == "Plasturgie (IDCC 0292)"
    assert [c["titre"] for c in d["categories"]] == ["Non-cadres", "Cadres"]
    assert d["categories"][0]["lignes"] == [
        {"anciennete": "1 an à moins de 5 ans",
         "paliers": "45 jours à 100 %, puis 60 jours à 75 %", "limite": "105 jours"},
        {"anciennete": "5 ans et plus",
         "paliers": "60 jours à 100 %, puis 75 jours à 75 %", "limite": "135 jours"},
    ]
    assert [l["anciennete"] for l in d["categories"][1]["lignes"]] == [
        "1 an à moins de 2 ans", "2 ans à moins de 3 ans", "3 ans à moins de 5 ans",
        "5 ans à moins de 10 ans", "10 ans et plus",
    ]
    assert d["categories"][1]["lignes"][-1]["paliers"] == "150 jours à 100 %, puis 150 jours à 50 %"
    assert d["categories"][1]["notes"][0] == "Pas de carence."
    assert all(s["url"].startswith("https://www.legifrance.gouv.fr/") for s in d["sources"])
    assert "Chaque mois, Martine compare avec le maintien légal et verse le plus favorable." in d["regles"]
```

- [ ] **Step 2 : les lancer, ils échouent**

Run : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_baremes_maintien.py -q`
Expected : FAIL — ModuleNotFoundError: No module named 'app.modules.payroll.domain.baremes_maintien'

- [ ] **Step 3 : le code**

Créer `backend/app/modules/payroll/domain/baremes_maintien.py` :

```python
"""Barèmes conventionnels du maintien de salaire : les paliers en données.

Un barème a deux catégories, non-cadres et cadres. Chaque catégorie a ses
tranches d'ancienneté (« à partir de N mois complets ») ; chaque tranche, ses
paliers (taux, jours calendaires). La limite d'une tranche est la somme de ses
paliers : elle vaut par arrêt et par année civile.

Plasturgie (IDCC 0292), textes ouverts sur Légifrance le 24/10/2026 :
- non-cadres : avenant du 15/05/1991, art. 13 ;
- cadres : accord du 17/12/1992, art. 5.
Conception : docs/superpowers/specs/2026-10-24-maintien-paliers-convention-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Optional

CODE_PLASTURGIE = "plasturgie_0292"
CLE_BAREME = "bareme_convention"

FAMILLE_MALADIE = "maladie"
FAMILLE_ACCIDENT_TRAVAIL = "accident_travail"  # accident du travail, maladie professionnelle, rechute
FAMILLE_TRAJET = "trajet"
FAMILLE_PARENTALITE = "parentalite"

_TYPES_ACCIDENT_TRAVAIL = frozenset({"accident_travail", "maladie_professionnelle", "rechute_at"})


@dataclass(frozen=True)
class Palier:
    taux: float
    jours: int


@dataclass(frozen=True)
class Tranche:
    des_mois: int
    paliers: tuple[Palier, ...]

    @property
    def limite(self) -> int:
        return sum(p.jours for p in self.paliers)

    def taux_du_rang(self, rang: int) -> float:
        """Le taux du rang-ième jour indemnisé de l'arrêt (1 = le premier)."""
        cumul = 0
        for palier in self.paliers:
            cumul += palier.jours
            if 1 <= rang <= cumul:
                return palier.taux
        return 0.0


@dataclass(frozen=True)
class Categorie:
    titre: str
    tranches: tuple[Tranche, ...]
    carence_jours: int
    #: Accident du travail (hors trajet) et maladie professionnelle : au moins
    #: la tranche de cette ancienneté (cadres : 2 ans).
    minimum_accident_travail_mois: int
    notes: tuple[str, ...]


@dataclass(frozen=True)
class Source:
    titre: str
    url: str


@dataclass(frozen=True)
class Bareme:
    code: str
    libelle: str
    nom_court: str
    #: Ancienneté qui ouvre le droit en maladie (accident : sans condition).
    anciennete_requise_mois: int
    non_cadres: Categorie
    cadres: Categorie
    sources: tuple[Source, ...]
    regles: tuple[str, ...]

    def categorie(self, est_cadre: bool) -> Categorie:
        return self.cadres if est_cadre else self.non_cadres


def _paliers(*couples: tuple[float, int]) -> tuple[Palier, ...]:
    return tuple(Palier(taux, jours) for taux, jours in couples)


PLASTURGIE = Bareme(
    code=CODE_PLASTURGIE,
    libelle="Plasturgie (IDCC 0292)",
    nom_court="Plasturgie",
    anciennete_requise_mois=12,
    non_cadres=Categorie(
        titre="Non-cadres",
        tranches=(
            Tranche(12, _paliers((1.0, 45), (0.75, 60))),
            Tranche(60, _paliers((1.0, 60), (0.75, 75))),
        ),
        carence_jours=3,
        minimum_accident_travail_mois=0,
        notes=(
            "Carence de 3 jours par arrêt de maladie ; aucune pour le premier arrêt "
            "de l'année civile (s'il a duré moins de 3 jours, la carence du suivant "
            "est égale à sa durée) ; aucune en accident du travail, maladie "
            "professionnelle, accident de trajet ou affection de longue durée.",
            "Accident du travail, maladie professionnelle ou accident de trajet : "
            "sans condition d'ancienneté.",
        ),
    ),
    cadres=Categorie(
        titre="Cadres",
        tranches=(
            Tranche(12, _paliers((1.0, 45), (0.5, 45))),
            Tranche(24, _paliers((1.0, 60), (0.5, 60))),
            Tranche(36, _paliers((1.0, 90), (0.5, 90))),
            Tranche(60, _paliers((1.0, 120), (0.5, 120))),
            Tranche(120, _paliers((1.0, 150), (0.5, 150))),
        ),
        carence_jours=0,
        minimum_accident_travail_mois=24,
        notes=(
            "Pas de carence.",
            "Accident du travail ou maladie professionnelle : sans condition "
            "d'ancienneté, au moins la ligne « 2 ans à moins de 3 ans » ; accident "
            "de trajet : sans condition d'ancienneté.",
        ),
    ),
    sources=(
        Source(
            "Avenant du 15/05/1991, article 13 (non-cadres)",
            "https://www.legifrance.gouv.fr/conv_coll/id/KALIARTI000005856705?idConteneur=KALICONT000005635856",
        ),
        Source(
            "Accord du 17/12/1992, article 5 (cadres)",
            "https://www.legifrance.gouv.fr/conv_coll/id/KALIARTI000005856723?idConteneur=KALICONT000005635856",
        ),
    ),
    regles=(
        "Jours calendaires ; l'ancienneté se lit au début de l'arrêt.",
        "La limite vaut par arrêt et par année civile ; les paliers repartent à "
        "chaque nouvel arrêt.",
        "Les IJSS des jours maintenus sont déduites selon le réglage « Arrêt sans "
        "subrogation » ; avec subrogation, toujours.",
        "Chaque mois, Martine compare avec le maintien légal et verse le plus favorable.",
    ),
)

BAREMES: dict[str, Bareme] = {PLASTURGIE.code: PLASTURGIE}


def bareme_par_code(code: Any) -> Optional[Bareme]:
    return BAREMES.get(str(code)) if code else None


def bareme_des_reglages(settings: Mapping[str, Any]) -> Optional[Bareme]:
    """Le barème choisi par la société ; None sans barème (le calcul d'avant)."""
    return bareme_par_code(settings.get(CLE_BAREME)) if isinstance(settings, Mapping) else None


def famille_du_type(arret_type: Any) -> str:
    t = str(arret_type or "").strip().lower()
    if t in _TYPES_ACCIDENT_TRAVAIL:
        return FAMILLE_ACCIDENT_TRAVAIL
    if t == "accident_trajet":
        return FAMILLE_TRAJET
    if "matern" in t or "patern" in t or "adoption" in t or "naissance" in t:
        return FAMILLE_PARENTALITE
    return FAMILLE_MALADIE


def mois_complets(debut: date, jour: date) -> int:
    """Mois d'ancienneté révolus au `jour` (l'anniversaire du mois compte)."""
    mois = (jour.year - debut.year) * 12 + (jour.month - debut.month)
    if jour.day < debut.day:
        mois -= 1
    return max(0, mois)


def tranche_pour(
    bareme: Bareme, *, est_cadre: bool, mois_anciennete: int, famille: str
) -> Optional[Tranche]:
    """La tranche d'un arrêt, ou None s'il n'ouvre aucun droit."""
    if famille == FAMILLE_PARENTALITE:
        return None
    categorie = bareme.categorie(est_cadre)
    mois = mois_anciennete
    if famille == FAMILLE_ACCIDENT_TRAVAIL:
        mois = max(mois, categorie.minimum_accident_travail_mois)
    elif famille == FAMILLE_MALADIE and mois < bareme.anciennete_requise_mois:
        return None
    applicable = categorie.tranches[0]
    for tranche in categorie.tranches:
        if mois >= tranche.des_mois:
            applicable = tranche
    return applicable


def pourcent(taux: float) -> str:
    valeur = round(float(taux) * 100, 2)
    if float(valeur).is_integer():
        return f"{int(valeur)} %"
    return f"{valeur:.2f}".replace(".", ",") + " %"


def _ans(mois: int) -> str:
    ans = mois // 12
    return "1 an" if ans == 1 else f"{ans} ans"


def libelle_tranche(categorie: Categorie, tranche: Tranche) -> str:
    """« 1 an à moins de 5 ans », « 5 ans et plus »."""
    suivantes = [t.des_mois for t in categorie.tranches if t.des_mois > tranche.des_mois]
    if not suivantes:
        return f"{_ans(tranche.des_mois)} et plus"
    return f"{_ans(tranche.des_mois)} à moins de {_ans(min(suivantes))}"


def texte_paliers(tranche: Tranche) -> str:
    """« 45 jours à 100 %, puis 60 jours à 75 % »."""
    return ", puis ".join(f"{p.jours} jours à {pourcent(p.taux)}" for p in tranche.paliers)


def description_lisible(bareme: Bareme) -> dict[str, Any]:
    """Le barème tel que l'écran le montre : la même source que le moteur."""
    categories = []
    for categorie in (bareme.non_cadres, bareme.cadres):
        categories.append(
            {
                "titre": categorie.titre,
                "lignes": [
                    {
                        "anciennete": libelle_tranche(categorie, tranche),
                        "paliers": texte_paliers(tranche),
                        "limite": f"{tranche.limite} jours",
                    }
                    for tranche in categorie.tranches
                ],
                "notes": list(categorie.notes),
            }
        )
    return {
        "code": bareme.code,
        "libelle": bareme.libelle,
        "sources": [{"titre": s.titre, "url": s.url} for s in bareme.sources],
        "categories": categories,
        "regles": list(bareme.regles),
    }


__all__ = [
    "BAREMES",
    "CLE_BAREME",
    "CODE_PLASTURGIE",
    "FAMILLE_ACCIDENT_TRAVAIL",
    "FAMILLE_MALADIE",
    "FAMILLE_PARENTALITE",
    "FAMILLE_TRAJET",
    "PLASTURGIE",
    "Bareme",
    "Categorie",
    "Palier",
    "Source",
    "Tranche",
    "bareme_des_reglages",
    "bareme_par_code",
    "description_lisible",
    "famille_du_type",
    "libelle_tranche",
    "mois_complets",
    "pourcent",
    "texte_paliers",
    "tranche_pour",
]
```

- [ ] **Step 4 : les relancer, ils passent**

Run : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_baremes_maintien.py -q`
Expected : PASS — 30 passed

Puis, sans régression : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll tests/unit/maintenance_settings tests/integration/legacy/test_maintien_salaire_service.py -q` → tout vert.

- [ ] **Step 5 : commit**

```bash
git add backend/app/modules/payroll/domain/baremes_maintien.py backend/tests/unit/payroll/test_baremes_maintien.py
git commit -m "feat(paie): le barème de la plasturgie en données, tranches et paliers des non-cadres et des cadres" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 2 : Le plan conventionnel des jours d'arrêt

**Files :**
- Create : `backend/app/modules/payroll/engine/paliers_convention.py`
- Test : `backend/tests/unit/payroll/test_paliers_convention.py`

**Interfaces :**
- Consumes (tâche 1) : `Bareme`, `Categorie`, `Tranche`, `FAMILLE_MALADIE`, `FAMILLE_PARENTALITE`, `famille_du_type`, `mois_complets`, `tranche_pour` ; et `prolongation_arret.ECART_MAX_PROLONGATION_JOURS`, `famille_d_arret` (existants).
- Produces :
  - `ArretDuPlan(debut: date, fin: date, type_arret: str)` (gelée) ;
  - `ArretRejoue` : `debut`, `fin`, `type_arret`, `famille`, `mois_anciennete`, `tranche`, `carence_jours`, `raison_carence`, `jours_de_carence: tuple[date, ...]`, `bascules: list[tuple[date, float]]`, `limite_atteinte: date | None`, `jours: tuple[date, ...]`, `.contient(jour)` ;
  - `PlanConventionnel(taux_par_jour: dict[date, float], arrets: list[ArretRejoue])` avec `.arret_du_jour(jour) -> ArretRejoue | None` ;
  - `RAISON_CADRE`, `RAISON_ACCIDENT`, `RAISON_ALD`, `RAISON_PREMIER_ARRET`, `RAISON_RELIQUAT`, `RAISON_CARENCE` ;
  - `arrets_pour_le_plan(arrets_connus, debut, fin, type_arret) -> list[ArretDuPlan]` ;
  - `plan_conventionnel(arrets, *, bareme, est_cadre, date_anciennete) -> PlanConventionnel`.

- [ ] **Step 1 : les tests, qui échouent**

Créer `backend/tests/unit/payroll/test_paliers_convention.py` :

```python
"""Plan conventionnel des jours d'arrêt, barème de la plasturgie (pur).

Carence, paliers par arrêt, limite par arrêt et par année civile, ancienneté
au début de l'arrêt (conception du 24/10/2026). Initiales seulement.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.domain.baremes_maintien import PLASTURGIE
from app.modules.payroll.engine.paliers_convention import (
    RAISON_ACCIDENT,
    RAISON_ALD,
    RAISON_CADRE,
    RAISON_CARENCE,
    RAISON_PREMIER_ARRET,
    RAISON_RELIQUAT,
    ArretDuPlan,
    arrets_pour_le_plan,
    plan_conventionnel,
)

pytestmark = pytest.mark.unit

D = date.fromisoformat


def _arret(debut, fin, type_arret="maladie_simple"):
    return ArretDuPlan(D(debut), D(fin), type_arret)


def _plan(*arrets, cadre=False, entree="2015-01-01"):
    return plan_conventionnel(list(arrets), bareme=PLASTURGIE, est_cadre=cadre, date_anciennete=D(entree))


def _jours_a(plan, taux):
    return sorted(j for j, t in plan.taux_par_jour.items() if t == taux)


def _bornes(jours):
    return (jours[0], jours[-1], len(jours)) if jours else None


def test_s_g_2026_cent_pour_cent_jusqu_au_02_07_puis_75_jusqu_au_15_09():
    """Non-cadre, 22 ans d'ancienneté, premier arrêt de 2026 du 04/05, prolongé jusqu'au 12/10."""
    plan = _plan(
        _arret("2026-05-04", "2026-05-31"), _arret("2026-06-01", "2026-06-30"),
        _arret("2026-07-01", "2026-07-31"), _arret("2026-08-01", "2026-08-31"),
        _arret("2026-09-01", "2026-09-30"), _arret("2026-10-02", "2026-10-12"),
        entree="2003-07-15",
    )
    assert _bornes(_jours_a(plan, 1.0)) == (D("2026-05-04"), D("2026-07-02"), 60)
    assert _bornes(_jours_a(plan, 0.75)) == (D("2026-07-03"), D("2026-09-15"), 75)
    (arret,) = plan.arrets  # le 02/10 prolonge (un jour de reprise)
    assert arret.carence_jours == 0 and arret.raison_carence == RAISON_PREMIER_ARRET
    assert arret.bascules == [(D("2026-05-04"), 1.0), (D("2026-07-03"), 0.75)]
    assert arret.limite_atteinte == D("2026-09-15")
    assert D("2026-10-05") not in plan.taux_par_jour


def test_un_deuxieme_arret_de_l_annee_a_trois_jours_de_carence():
    plan = _plan(_arret("2026-02-02", "2026-02-06"), _arret("2026-03-02", "2026-03-13"))
    premier, second = plan.arrets
    assert (premier.carence_jours, premier.raison_carence) == (0, RAISON_PREMIER_ARRET)
    assert _bornes([j for j in plan.taux_par_jour if j.month == 2]) == (D("2026-02-02"), D("2026-02-06"), 5)
    assert (second.carence_jours, second.raison_carence) == (3, RAISON_CARENCE)
    assert second.jours_de_carence == (D("2026-03-02"), D("2026-03-03"), D("2026-03-04"))
    assert _bornes(sorted(j for j in plan.taux_par_jour if j.month == 3)) == (
        D("2026-03-05"), D("2026-03-13"), 9,
    )


def test_un_premier_arret_de_deux_jours_donne_deux_jours_de_carence_au_suivant():
    plan = _plan(
        _arret("2026-02-02", "2026-02-03"),
        _arret("2026-03-02", "2026-03-13"),
        _arret("2026-04-06", "2026-04-17"),
    )
    assert [(a.carence_jours, a.raison_carence) for a in plan.arrets] == [
        (0, RAISON_PREMIER_ARRET), (2, RAISON_RELIQUAT), (3, RAISON_CARENCE),
    ]


def test_la_carence_repart_avec_l_annee_civile():
    plan = _plan(_arret("2025-11-03", "2025-11-07"), _arret("2026-01-05", "2026-01-09"))
    assert [a.raison_carence for a in plan.arrets] == [RAISON_PREMIER_ARRET, RAISON_PREMIER_ARRET]


@pytest.mark.parametrize(
    "type_arret, raison",
    [("ald", RAISON_ALD), ("accident_travail", RAISON_ACCIDENT),
     ("maladie_professionnelle", RAISON_ACCIDENT), ("accident_trajet", RAISON_ACCIDENT)],
)
def test_pas_de_carence_en_ald_ni_en_accident(type_arret, raison):
    plan = _plan(_arret("2026-02-02", "2026-02-06"), _arret("2026-03-02", "2026-03-13", type_arret))
    assert (plan.arrets[1].carence_jours, plan.arrets[1].raison_carence) == (0, raison)
    assert D("2026-03-02") in plan.taux_par_jour


def test_une_prolongation_apres_deux_jours_de_reprise_reste_le_meme_arret():
    plan = _plan(
        _arret("2026-02-02", "2026-02-04"),
        _arret("2026-03-02", "2026-03-06"), _arret("2026-03-09", "2026-03-13"),
    )
    assert len(plan.arrets) == 2
    assert plan.arrets[1].carence_jours == 3
    mars = sorted(j for j in plan.taux_par_jour if j.month == 3)
    assert mars == [D("2026-03-05"), D("2026-03-06")] + [date(2026, 3, j) for j in range(9, 14)]


def test_un_cadre_n_a_jamais_de_carence():
    plan = _plan(_arret("2026-02-02", "2026-02-06"), _arret("2026-03-02", "2026-03-04"),
                 cadre=True, entree="2022-06-01")
    assert [(a.carence_jours, a.raison_carence) for a in plan.arrets] == [
        (0, RAISON_CADRE), (0, RAISON_CADRE),
    ]
    assert len(plan.taux_par_jour) == 8


def test_cadre_accident_du_travail_a_six_mois_la_tranche_de_deux_ans():
    plan = _plan(_arret("2026-03-02", "2026-07-31", "accident_travail"), cadre=True, entree="2025-09-01")
    assert _bornes(_jours_a(plan, 1.0)) == (D("2026-03-02"), D("2026-04-30"), 60)
    assert _bornes(_jours_a(plan, 0.5)) == (D("2026-05-01"), D("2026-06-29"), 60)
    assert plan.arrets[0].limite_atteinte == D("2026-06-29")


def test_cadre_accident_de_trajet_a_six_mois_la_premiere_tranche():
    plan = _plan(_arret("2026-03-02", "2026-07-31", "accident_trajet"), cadre=True, entree="2025-09-01")
    assert len(_jours_a(plan, 1.0)) == 45 and len(_jours_a(plan, 0.5)) == 45


def test_onze_mois_rien_en_maladie_les_paliers_en_accident_du_travail():
    maladie = _plan(_arret("2026-05-05", "2026-05-13"), entree="2025-05-28")
    assert maladie.taux_par_jour == {}
    assert maladie.arrets[0].tranche is None and maladie.arrets[0].mois_anciennete == 11
    at = _plan(_arret("2026-05-05", "2026-09-30", "accident_travail"), entree="2025-05-28")
    assert len(_jours_a(at, 1.0)) == 45 and len(_jours_a(at, 0.75)) == 60


def test_la_limite_annuelle_cumule_les_arrets():
    """Moins de 5 ans : 80 jours au premier arrêt, il en reste 25 pour le second, à 100 %."""
    plan = _plan(_arret("2026-01-05", "2026-03-25"), _arret("2026-06-01", "2026-07-31"),
                 entree="2023-01-01")
    premier = [j for j in plan.taux_par_jour if j < D("2026-04-01")]
    assert len(premier) == 80
    second = sorted(j for j in plan.taux_par_jour if j >= D("2026-06-01"))
    assert _bornes(second) == (D("2026-06-04"), D("2026-06-28"), 25)
    assert {plan.taux_par_jour[j] for j in second} == {1.0}
    assert plan.arrets[1].limite_atteinte == D("2026-06-28")


def test_un_arret_a_cheval_sur_deux_annees_garde_la_limite_de_l_arret():
    plan = _plan(_arret("2026-11-02", "2027-04-30"), entree="2015-01-01")
    assert _bornes(_jours_a(plan, 1.0)) == (D("2026-11-02"), D("2026-12-31"), 60)
    assert _bornes(_jours_a(plan, 0.75)) == (D("2027-01-01"), D("2027-03-16"), 75)
    assert plan.arrets[0].limite_atteinte == D("2027-03-16")


def test_cinq_ans_atteints_pendant_l_arret_ne_changent_pas_sa_tranche():
    plan = _plan(_arret("2026-05-04", "2026-09-30"), entree="2021-06-15")
    assert plan.arrets[0].mois_anciennete == 58
    assert _bornes(_jours_a(plan, 1.0)) == (D("2026-05-04"), D("2026-06-17"), 45)
    assert _bornes(_jours_a(plan, 0.75)) == (D("2026-06-18"), D("2026-08-16"), 60)


def test_les_conges_de_parentalite_ne_sont_pas_rejoues():
    plan = _plan(_arret("2026-02-02", "2026-03-31", "maternite"), _arret("2026-05-04", "2026-05-08"))
    assert len(plan.arrets) == 1
    assert plan.arrets[0].raison_carence == RAISON_PREMIER_ARRET


def test_l_arret_calcule_s_ajoute_aux_arrets_connus_s_il_n_y_est_pas():
    connus = [{"debut": "2026-02-02", "fin": "2026-02-06", "type": "maladie"}]
    assert len(arrets_pour_le_plan(connus, D("2026-03-02"), D("2026-03-06"), "maladie_simple")) == 2
    assert len(arrets_pour_le_plan(connus, D("2026-02-03"), D("2026-02-05"), "maladie_simple")) == 1
    assert arrets_pour_le_plan(None, D("2026-03-02"), D("2026-03-06"), "ald") == [
        ArretDuPlan(D("2026-03-02"), D("2026-03-06"), "ald"),
    ]


def test_arret_du_jour():
    plan = _plan(_arret("2026-02-02", "2026-02-06"), _arret("2026-03-02", "2026-03-13"))
    assert plan.arret_du_jour(D("2026-03-05")).debut == D("2026-03-02")
    assert plan.arret_du_jour(D("2026-02-20")) is None
```

- [ ] **Step 2 : les lancer, ils échouent**

Run : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_paliers_convention.py -q`
Expected : FAIL — ModuleNotFoundError: No module named 'app.modules.payroll.engine.paliers_convention'

- [ ] **Step 3 : le code**

Créer `backend/app/modules/payroll/engine/paliers_convention.py` :

```python
"""Plan conventionnel des jours d'arrêt : quel jour est maintenu, à quel taux.

Pur, sans base. Les arrêts connus du salarié (lus aux calendriers, de l'année
d'avant jusqu'au mois du bulletin) sont rejoués dans l'ordre, avec le barème de
la société (conception du 24/10/2026) :

- un arrêt est une chaîne de demandes de même nature séparées de 2 jours de
  reprise au plus (`prolongation_arret`) : une prolongation n'est jamais un
  nouvel arrêt ;
- l'ancienneté se lit en mois complets au début de l'arrêt ;
- carence (non-cadres, maladie hors ALD) : 3 jours calendaires, levée pour le
  premier arrêt de l'année civile qui ouvre droit ; si celui-ci a duré moins de
  3 jours, la carence du suivant vaut sa durée ;
- chaque jour indemnisé prend un rang dans l'arrêt ; le rang fixe le palier
  (lecture A : les paliers repartent à chaque arrêt) ;
- un jour n'est indemnisé que si l'arrêt et l'année civile du jour comptent
  moins de jours indemnisés que la limite de la tranche.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable, Mapping, Optional

from app.modules.payroll.domain.baremes_maintien import (
    FAMILLE_MALADIE,
    FAMILLE_PARENTALITE,
    Bareme,
    Categorie,
    Tranche,
    famille_du_type,
    mois_complets,
    tranche_pour,
)

from .prolongation_arret import ECART_MAX_PROLONGATION_JOURS, famille_d_arret

#: Pourquoi un arrêt a (ou n'a pas) de carence.
RAISON_CADRE = "cadre"
RAISON_ACCIDENT = "accident"
RAISON_ALD = "ald"
RAISON_PREMIER_ARRET = "premier_arret"
RAISON_RELIQUAT = "reliquat"
RAISON_CARENCE = "carence"


@dataclass(frozen=True)
class ArretDuPlan:
    debut: date
    fin: date
    type_arret: str


@dataclass
class ArretRejoue:
    debut: date
    fin: date
    type_arret: str
    famille: str
    mois_anciennete: int
    tranche: Optional[Tranche]
    carence_jours: int = 0
    raison_carence: str = RAISON_CARENCE
    jours_de_carence: tuple[date, ...] = ()
    #: (premier jour, taux) de chaque palier atteint, dans l'ordre.
    bascules: list[tuple[date, float]] = field(default_factory=list)
    #: Dernier jour indemnisé quand la limite (de l'arrêt ou de l'année) coupe
    #: le maintien alors que l'arrêt continue.
    limite_atteinte: Optional[date] = None
    jours: tuple[date, ...] = ()

    def contient(self, jour: date) -> bool:
        return self.debut <= jour <= self.fin


@dataclass
class PlanConventionnel:
    taux_par_jour: dict[date, float]
    arrets: list[ArretRejoue]

    def arret_du_jour(self, jour: date) -> Optional[ArretRejoue]:
        for arret in self.arrets:
            if arret.contient(jour):
                return arret
        return None


def _date(valeur: Any) -> Optional[date]:
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except (TypeError, ValueError):
        return None


def _jours(debut: date, fin: date) -> Iterable[date]:
    jour = debut
    while jour <= fin:
        yield jour
        jour += timedelta(days=1)


def arrets_pour_le_plan(
    arrets_connus: Iterable[Mapping[str, Any]] | None,
    debut: date,
    fin: date,
    type_arret: str,
) -> list[ArretDuPlan]:
    """Les arrêts connus, et l'arrêt calculé s'il n'y est pas encore."""
    arrets: list[ArretDuPlan] = []
    for autre in arrets_connus or []:
        d = _date((autre or {}).get("debut"))
        f = _date((autre or {}).get("fin")) or d
        if d is None or f is None:
            continue
        arrets.append(ArretDuPlan(d, f, str(autre.get("type") or "maladie_simple")))
    if not any(a.debut <= fin and debut <= a.fin for a in arrets):
        arrets.append(ArretDuPlan(debut, fin, type_arret))
    return arrets


def _chaines(arrets: Iterable[ArretDuPlan]) -> list[list[ArretDuPlan]]:
    tries = sorted(
        {a for a in arrets if a.fin >= a.debut and famille_du_type(a.type_arret) != FAMILLE_PARENTALITE},
        key=lambda a: (a.debut, a.fin),
    )
    chaines: list[list[ArretDuPlan]] = []
    for arret in tries:
        if chaines:
            derniere = chaines[-1]
            fin = max(a.fin for a in derniere)
            if (
                famille_d_arret(derniere[0].type_arret) == famille_d_arret(arret.type_arret)
                and (arret.debut - fin).days <= ECART_MAX_PROLONGATION_JOURS
            ):
                derniere.append(arret)
                continue
        chaines.append([arret])
    return chaines


def _carence(
    categorie: Categorie,
    famille: str,
    type_arret: str,
    annee: int,
    duree: int,
    premiers: set[int],
    reliquats: dict[int, int],
) -> tuple[int, str]:
    if categorie.carence_jours <= 0:
        return 0, RAISON_CADRE
    if famille != FAMILLE_MALADIE:
        return 0, RAISON_ACCIDENT
    if str(type_arret or "").strip().lower() == "ald":
        return 0, RAISON_ALD
    if annee not in premiers:
        premiers.add(annee)
        if duree < categorie.carence_jours:
            reliquats[annee] = duree
        return 0, RAISON_PREMIER_ARRET
    if annee in reliquats:
        return reliquats.pop(annee), RAISON_RELIQUAT
    return categorie.carence_jours, RAISON_CARENCE


def plan_conventionnel(
    arrets: Iterable[ArretDuPlan],
    *,
    bareme: Bareme,
    est_cadre: bool,
    date_anciennete: Optional[date],
) -> PlanConventionnel:
    """Rejoue les arrêts : le taux de chaque jour indemnisé, et chaque arrêt."""
    categorie = bareme.categorie(est_cadre)
    taux_par_jour: dict[date, float] = {}
    rejoues: list[ArretRejoue] = []
    premiers: set[int] = set()
    reliquats: dict[int, int] = {}
    indemnises_par_an: dict[int, int] = {}
    dernier_par_an: dict[int, date] = {}
    for chaine in _chaines(arrets):
        debut = chaine[0].debut
        type_arret = chaine[0].type_arret
        famille = famille_du_type(type_arret)
        mois = mois_complets(date_anciennete, debut) if date_anciennete else 0
        jours = tuple(sorted({j for a in chaine for j in _jours(a.debut, a.fin)}))
        tranche = tranche_pour(bareme, est_cadre=est_cadre, mois_anciennete=mois, famille=famille)
        rejoue = ArretRejoue(
            debut=debut, fin=jours[-1], type_arret=type_arret, famille=famille,
            mois_anciennete=mois, tranche=tranche, jours=jours,
        )
        rejoues.append(rejoue)
        if tranche is None:
            continue
        carence, raison = _carence(
            categorie, famille, type_arret, debut.year, len(jours), premiers, reliquats
        )
        rejoue.carence_jours = carence
        rejoue.raison_carence = raison
        rejoue.jours_de_carence = jours[:carence]
        rang = 0
        taux_precedent: Optional[float] = None
        refus: Optional[date] = None
        for jour in jours[carence:]:
            if rang >= tranche.limite or indemnises_par_an.get(jour.year, 0) >= tranche.limite:
                refus = refus or jour
                if rang >= tranche.limite:
                    break
                continue
            rang += 1
            indemnises_par_an[jour.year] = indemnises_par_an.get(jour.year, 0) + 1
            dernier_par_an[jour.year] = jour
            taux = tranche.taux_du_rang(rang)
            taux_par_jour[jour] = taux
            if taux != taux_precedent:
                rejoue.bascules.append((jour, taux))
                taux_precedent = taux
        if refus is not None:
            avant = [j for j in jours if j < refus and j in taux_par_jour]
            rejoue.limite_atteinte = avant[-1] if avant else dernier_par_an.get(refus.year)
    return PlanConventionnel(taux_par_jour=taux_par_jour, arrets=rejoues)


__all__ = [
    "ArretDuPlan",
    "ArretRejoue",
    "PlanConventionnel",
    "RAISON_ACCIDENT",
    "RAISON_ALD",
    "RAISON_CADRE",
    "RAISON_CARENCE",
    "RAISON_PREMIER_ARRET",
    "RAISON_RELIQUAT",
    "arrets_pour_le_plan",
    "plan_conventionnel",
]
```

- [ ] **Step 4 : les relancer, ils passent**

Run : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_paliers_convention.py -q`
Expected : PASS — 19 passed

Puis, sans régression : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll tests/unit/maintenance_settings tests/integration/legacy/test_maintien_salaire_service.py -q` → tout vert.

- [ ] **Step 5 : commit**

```bash
git add backend/app/modules/payroll/engine/paliers_convention.py backend/tests/unit/payroll/test_paliers_convention.py
git commit -m "feat(paie): le plan conventionnel des jours d'arrêt, carence, paliers par arrêt et limite par arrêt et par année" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 3 : Le réglage « barème de la convention », de la base à l'API

**Files :**
- Create : `supabase/migrations/20261024120000_bareme_convention_maintien.sql`
- Modify : `backend/app/modules/maintenance_settings/schemas/requests.py`, `schemas/responses.py`, `application/queries.py`, `application/commands.py`, `api/router.py`
- Test : `backend/tests/unit/maintenance_settings/test_bareme_convention.py`

**Interfaces :**
- Consumes (tâche 1) : `BAREMES`, `description_lisible`.
- Produces :
  - `MaintenanceSettings.bareme_convention: Optional[Literal["plasturgie_0292"]] = None`, et le même champ dans `MaintenanceSettingsUpdate` (un `null` explicite revient à « Aucun ») ;
  - `"bareme_convention"` dans `commands._DB_WRITABLE_KEYS` ;
  - `router.baremes_lisibles() -> list[dict]` et la route `GET /api/maintenance-settings/baremes`.

- [ ] **Step 1 : les tests, qui échouent**

Créer `backend/tests/unit/maintenance_settings/test_bareme_convention.py` :

```python
"""Le réglage « barème de la convention », de la ligne à l'écran.

Sans ligne, ou sur une ligne lue avant la migration, aucun barème : le calcul
d'avant. Le PUT choisit le barème, puis revient à « Aucun » (null).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.modules.maintenance_settings.api.router import baremes_lisibles
from app.modules.maintenance_settings.application import commands, queries
from app.modules.maintenance_settings.schemas.requests import MaintenanceSettingsUpdate

pytestmark = pytest.mark.unit

MIGRATION = (
    Path(__file__).resolve().parents[4]
    / "supabase" / "migrations" / "20261024120000_bareme_convention_maintien.sql"
)

SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
CLE = "bareme_convention"
LIGNE = {
    "id": "bbbbbbbb-2222-2222-2222-222222222222",
    "company_id": SOCIETE,
    "subrogation_mode": "never",
    "maintain_working_days": True,
    "deduire_ijss_sans_subrogation": False,
}


def _lire(monkeypatch, ligne):
    monkeypatch.setattr(
        queries.maintenance_settings_repository, "get_by_company", lambda _cid: ligne
    )


def _ecrire(monkeypatch, ligne):
    _lire(monkeypatch, ligne)
    ecrit: dict = {}

    def upsert(cid, data):
        ecrit.clear()
        ecrit.update(data)
        return {**data, "company_id": cid}

    monkeypatch.setattr(commands.maintenance_settings_repository, "upsert", upsert)
    return ecrit


@pytest.mark.parametrize("ligne", [None, dict(LIGNE), {**LIGNE, CLE: None}])
def test_sans_ligne_avant_la_migration_ou_a_null_aucun_bareme(monkeypatch, ligne):
    _lire(monkeypatch, ligne)
    reglages = queries.get_maintenance_settings(SOCIETE)
    assert reglages.bareme_convention is None
    assert reglages.model_dump(mode="json")[CLE] is None


def test_la_ligne_porte_le_bareme(monkeypatch):
    _lire(monkeypatch, {**LIGNE, CLE: "plasturgie_0292"})
    assert queries.get_maintenance_settings(SOCIETE).bareme_convention == "plasturgie_0292"


def test_le_put_choisit_le_bareme_puis_revient_a_aucun(monkeypatch):
    ecrit = _ecrire(monkeypatch, dict(LIGNE))
    sauve = commands.save_maintenance_settings(
        SOCIETE, MaintenanceSettingsUpdate(bareme_convention="plasturgie_0292")
    )
    assert ecrit[CLE] == "plasturgie_0292"
    assert sauve.bareme_convention == "plasturgie_0292"
    ecrit = _ecrire(monkeypatch, {**LIGNE, CLE: "plasturgie_0292"})
    commands.save_maintenance_settings(SOCIETE, MaintenanceSettingsUpdate(bareme_convention=None))
    assert ecrit[CLE] is None


def test_un_autre_reglage_enregistre_garde_le_bareme(monkeypatch):
    ecrit = _ecrire(monkeypatch, {**LIGNE, CLE: "plasturgie_0292"})
    commands.save_maintenance_settings(SOCIETE, MaintenanceSettingsUpdate(employer_waiting_days=3))
    assert ecrit[CLE] == "plasturgie_0292"


def test_un_bareme_inconnu_est_refuse():
    with pytest.raises(ValidationError):
        MaintenanceSettingsUpdate(bareme_convention="metallurgie")


def test_la_route_rend_le_tableau_du_bareme():
    (plasturgie,) = baremes_lisibles()
    assert plasturgie["code"] == "plasturgie_0292"
    assert plasturgie["libelle"] == "Plasturgie (IDCC 0292)"
    assert plasturgie["categories"][0]["lignes"][1]["paliers"] == (
        "60 jours à 100 %, puis 75 jours à 75 %"
    )


def test_la_migration_ajoute_la_colonne_sans_toucher_aux_lignes():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "add column if not exists bareme_convention text" in sql
    assert "check (bareme_convention is null or bareme_convention in ('plasturgie_0292'))" in sql
    assert "update public" not in sql
```

- [ ] **Step 2 : les lancer, ils échouent**

Run : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/maintenance_settings -q`
Expected : FAIL — ImportError: cannot import name 'baremes_lisibles' from 'app.modules.maintenance_settings.api.router'

- [ ] **Step 3 : le code**

Créer `supabase/migrations/20261024120000_bareme_convention_maintien.sql` :

```sql
-- Barème de la convention du maintien de salaire, par société
-- (conception du 24/10/2026).
--
--   null              : les réglages manuels, le calcul d'avant ;
--   'plasturgie_0292' : les paliers de la plasturgie (avenant non-cadres du
--                       15/05/1991, art. 13 ; accord cadres du 17/12/1992, art. 5).
-- Aucune ligne existante n'est touchée : la colonne naît nulle.
-- Rejouable : la colonne n'est ajoutée que si elle manque, la contrainte est
-- reposée à l'identique.
-- À appliquer AVANT de déployer le code qui l'écrit : sans elle,
-- l'enregistrement des réglages de maintien échoue (colonne inconnue).

alter table public.company_maintenance_settings
  add column if not exists bareme_convention text;

alter table public.company_maintenance_settings
  drop constraint if exists company_maintenance_settings_bareme_convention_check;

alter table public.company_maintenance_settings
  add constraint company_maintenance_settings_bareme_convention_check
  check (bareme_convention is null or bareme_convention in ('plasturgie_0292'));

comment on column public.company_maintenance_settings.bareme_convention is
  'Barème de la convention du maintien : null, les réglages manuels ; plasturgie_0292, les paliers de la plasturgie.';
```

`backend/app/modules/maintenance_settings/schemas/requests.py` — insérer **après** le bloc :

```python
SubrogationModeLiteral = Literal["when_maintien", "automatic", "at_mp_only", "per_case", "never"]
```

le code :

```python
#: Barème de la convention (conception du 24/10/2026) ; None : réglages manuels.
BaremeConventionLiteral = Literal["plasturgie_0292"]
```

`backend/app/modules/maintenance_settings/schemas/requests.py` — insérer **après** le bloc :

```python
    deduire_ijss_sans_subrogation: Optional[bool] = None
```

le code :

```python
    bareme_convention: Optional[BaremeConventionLiteral] = None
```

`backend/app/modules/maintenance_settings/schemas/responses.py` — insérer **après** le bloc :

```python
SubrogationMode = Literal["when_maintien", "automatic", "at_mp_only", "per_case", "never"]
```

le code :

```python
BaremeConvention = Literal["plasturgie_0292"]
```

`backend/app/modules/maintenance_settings/schemas/responses.py` — insérer **après** le bloc :

```python
    deduire_ijss_sans_subrogation: bool = True
```

le code :

```python
    #: Barème de la convention (24/10/2026) : None, les réglages manuels ;
    #: "plasturgie_0292", les paliers de la plasturgie (non-cadres et cadres).
    bareme_convention: Optional[BaremeConvention] = None
```

`backend/app/modules/maintenance_settings/application/queries.py` — insérer **après** le bloc :

```python
        deduire_ijss_sans_subrogation=True,
```

le code :

```python
        bareme_convention=None,
```

`backend/app/modules/maintenance_settings/application/commands.py` — remplacer :

```python
        "deduire_ijss_sans_subrogation",
    }
```

par :

```python
        "deduire_ijss_sans_subrogation",
        "bareme_convention",
    }
```

`backend/app/modules/maintenance_settings/api/router.py` — insérer **avant** le bloc :

```python
from fastapi import APIRouter, Depends, HTTPException
```

le code :

```python
from typing import Any
```

`backend/app/modules/maintenance_settings/api/router.py` — insérer **après** le bloc :

```python
from app.core.security import get_current_user
```

le code :

```python
from app.modules.payroll.domain.baremes_maintien import BAREMES, description_lisible
```

`backend/app/modules/maintenance_settings/api/router.py` — insérer **avant** le bloc :

```python
@router.put("/", response_model=MaintenanceSettings)
```

le code :

```python
def baremes_lisibles() -> list[dict[str, Any]]:
    """Les barèmes que la société peut choisir, tels que l'écran les montre."""
    return [description_lisible(bareme) for bareme in BAREMES.values()]


@router.get("/baremes")
def get_baremes_route(
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Le tableau de chaque barème, construit depuis le barème du moteur."""
    return baremes_lisibles()
```

- [ ] **Step 4 : les relancer, ils passent**

Run : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/maintenance_settings -q`
Expected : PASS — 19 passed

Puis, sans régression : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll tests/unit/maintenance_settings tests/integration/legacy/test_maintien_salaire_service.py -q` → tout vert.

- [ ] **Step 5 : commit**

```bash
git add backend/app/modules/maintenance_settings/api/router.py backend/app/modules/maintenance_settings/application/commands.py backend/app/modules/maintenance_settings/application/queries.py backend/app/modules/maintenance_settings/schemas/requests.py backend/app/modules/maintenance_settings/schemas/responses.py backend/tests/unit/maintenance_settings/test_bareme_convention.py supabase/migrations/20261024120000_bareme_convention_maintien.sql
git commit -m "feat(paie): le réglage « barème de la convention », de la base à l'API, et la route qui décrit le barème" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 4 : Sous le barème, la valeur des jours maintenus

**Files :**
- Modify : `backend/app/modules/payroll/engine/maintien_salaire_service.py` (import de `dataclass` ; nouveau bloc avant `# --- Prolongation et arrêts du mois ---`)
- Test : `backend/tests/unit/payroll/test_maintien_paliers_valeur.py`

**Interfaces :**
- Consumes : `_valeur_de_jours_ouvres`, `_heures_sup_structurelles_par_jour`, `_compter_jours_calendaires`, `_parse_date` (existants) ; `salaire_contractuel.salaire_hors_hs_structurelles`, `calcul_brut.compute_hs_structurelles_mensuelles`, `calcul_brut._get_salaire_horaire_base` (existants).
- Produces :
  - `_salaire_du_mois(contexte, duree_hebdo, taux_horaire_base) -> float` ;
  - `BaseDesJours` (dataclass) : `jours_ouvres`, `mois_entier`, `jours_du_mois`, `salaire_du_mois`, `taux_horaire_base`, `duree_hebdo`, `quotite`, `.compte(jour) -> bool`, `.valeur(nb_jours) -> float` ;
  - `_base_des_jours(arret, contexte, date_debut_periode, date_fin_periode) -> BaseDesJours` ; lit `arret["mois_entier_en_arret"]` s'il est posé (tâche 6), sinon les dates de l'arrêt.

- [ ] **Step 1 : les tests, qui échouent**

Créer `backend/tests/unit/payroll/test_maintien_paliers_valeur.py` :

```python
"""Sous le barème, un jour maintenu vaut ce que son absence a retiré du salaire.

Mois entier en arrêt : le salaire du mois, réparti au prorata des jours.
Mois partiel : la journée, comptée par bloc comme le cabinet (conception du
24/10/2026, §3.3). Salaires de la fiche de Comitech, initiales seulement.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.maintien_salaire_service import _base_des_jours

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JUIN = (date(2026, 6, 1), date(2026, 6, 30))
JUILLET = (date(2026, 7, 1), date(2026, 7, 31))
MAI = (date(2026, 5, 1), date(2026, 5, 31))
AVRIL = (date(2026, 4, 1), date(2026, 4, 30))


def _sg():
    return build_test_contexte(
        salaire_base=1952.60, duree_hebdo=39.0, date_entree="2003-07-15",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )


def _ds():
    return build_test_contexte(
        statut="Cadre", salaire_base=3368.60, duree_hebdo=39.0, date_entree="2003-09-01",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )


def _base(contexte, debut, fin, periode, **extra):
    arret = {"date_debut": debut, "date_fin": fin, "maintien_base_ouvree": True, **extra}
    return _base_des_jours(arret, contexte, *periode)


def test_mois_entier_le_salaire_du_mois():
    base = _base(_sg(), "2026-05-04", "2026-09-30", JUIN)
    assert base.mois_entier and base.jours_du_mois == 22
    assert base.salaire_du_mois == 2231.48  # 1 952,60 + 17,33 h à 16,0925
    assert base.valeur(22) == 2231.48
    assert _base(_ds(), "2026-04-27", "2026-07-17", MAI).valeur(21) == 3849.73


def test_mois_entier_partage_entre_deux_paliers_au_prorata_des_jours_ouvres():
    base = _base(_sg(), "2026-05-04", "2026-09-30", JUILLET)
    assert base.jours_du_mois == 23
    assert (base.valeur(2), base.valeur(21)) == (194.04, 2037.44)


def test_mois_partiel_les_journees_comptees_par_bloc():
    assert _base(_sg(), "2026-05-04", "2026-05-31", MAI).valeur(20) == 2059.84
    ds = _base(_ds(), "2026-04-27", "2026-07-17", AVRIL)
    assert not ds.mois_entier
    assert ds.valeur(4) == 710.72
    assert _base(_ds(), "2026-07-18", "2026-07-26", JUILLET).valeur(5) == 888.40


def test_les_week_ends_ne_comptent_qu_en_jours_calendaires():
    ouvres = _base(_sg(), "2026-05-04", "2026-09-30", JUIN)
    assert not ouvres.compte(date(2026, 6, 6)) and ouvres.compte(date(2026, 6, 8))
    calendaires = _base_des_jours(
        {"date_debut": "2026-05-04", "date_fin": "2026-09-30"}, _sg(), *JUIN
    )
    assert calendaires.compte(date(2026, 6, 6))


def test_mode_calendaire_mois_entier_et_mois_partiel():
    contexte = build_test_contexte(salaire_base=2500.0)
    entier = _base_des_jours({"date_debut": "2026-05-04", "date_fin": "2026-09-30"}, contexte, *JUIN)
    assert entier.jours_du_mois == 30 and entier.valeur(30) == 2500.0
    partiel = _base_des_jours({"date_debut": "2026-06-08", "date_fin": "2026-06-17"}, contexte, *JUIN)
    assert partiel.valeur(10) == 821.83  # 2 500 / 30,42 × 10


def test_temps_partiel_la_quotite_ne_touche_que_la_journee():
    contexte = build_test_contexte(salaire_base=1500.0, duree_hebdo=21.0, is_temps_partiel=True)
    extra = {"is_temps_partiel": True, "quotite_temps_partiel": 0.6}
    assert _base(contexte, "2026-06-08", "2026-06-12", JUIN).valeur(5) == 576.92  # 35 h à 16,4835
    assert _base(contexte, "2026-06-08", "2026-06-12", JUIN, **extra).valeur(5) == 346.15
    entier = _base(contexte, "2026-05-04", "2026-09-30", JUIN, **extra)
    assert entier.valeur(22) == 1500.0


def test_plusieurs_arrets_qui_couvrent_le_mois_le_disent():
    base = _base(_sg(), "2026-06-16", "2026-06-30", JUIN, mois_entier_en_arret=True)
    assert base.mois_entier and base.valeur(11) == 1115.74
```

- [ ] **Step 2 : les lancer, ils échouent**

Run : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_maintien_paliers_valeur.py -q`
Expected : FAIL — ImportError: cannot import name '_base_des_jours' from 'app.modules.payroll.engine.maintien_salaire_service'

- [ ] **Step 3 : le code**

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — insérer **avant** le bloc :

```python
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
```

le code :

```python
from dataclasses import dataclass
```

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — insérer **avant** le bloc :

```python
# --- Prolongation et arrêts du mois ---
```

le code :

```python
# --- Barème de la convention : la valeur des jours maintenus ---


def _salaire_du_mois(
    contexte: ContextePaie, duree_hebdo: float, taux_horaire_base: float
) -> float:
    """Le salaire d'un mois entièrement travaillé : la base et ses heures sup
    structurelles, comme les lignes du bulletin. Comitech, juin 2026 : 1 952,60
    de base et 17,33 h à 16,0925, soit 2 231,48."""
    from .salaire_contractuel import salaire_hors_hs_structurelles

    base = round(float(contexte.salaire_base_mensuel or 0.0), 2)
    heures_jour, majoration = _heures_sup_structurelles_par_jour(contexte, duree_hebdo)
    if not heures_jour or not salaire_hors_hs_structurelles(contexte.contrat):
        return base
    from .calcul_brut import compute_hs_structurelles_mensuelles

    heures = compute_hs_structurelles_mensuelles(duree_hebdo)
    return round(base + round(heures * taux_horaire_base * (1 + majoration), 2), 2)


@dataclass
class BaseDesJours:
    """Ce que vaut un jour maintenu sous le barème (conception du 24/10, §3.3).

    Mois entier en arrêt : le salaire du mois, réparti au prorata des jours
    (ouvrés en jours ouvrés). Sinon, la journée : en jours ouvrés, 7 h et la
    quote-part d'heures sup structurelles, comptées par bloc comme le cabinet ;
    sinon salaire / 30,42 par jour calendaire. La quotité d'un temps partiel ne
    s'applique qu'à la journée : le salaire du mois est déjà au temps partiel.
    """

    contexte: Any
    jours_ouvres: bool
    mois_entier: bool
    jours_du_mois: int
    salaire_du_mois: float
    taux_horaire_base: float
    duree_hebdo: float
    quotite: float

    def compte(self, jour: date) -> bool:
        return not self.jours_ouvres or jour.weekday() < 5

    def valeur(self, nb_jours: int) -> float:
        if nb_jours <= 0:
            return 0.0
        if self.mois_entier and self.jours_du_mois > 0:
            return round(self.salaire_du_mois * nb_jours / self.jours_du_mois, 2)
        if self.jours_ouvres:
            brut = _valeur_de_jours_ouvres(
                self.contexte, self.duree_hebdo, self.taux_horaire_base, nb_jours
            )
        else:
            salaire = float(self.contexte.salaire_base_mensuel or 0.0)
            brut = salaire / lc.DIVISEUR_JOURS_CALENDAIRES * nb_jours
        return round(brut * self.quotite, 2)


def _base_des_jours(
    arret: Dict[str, Any],
    contexte: ContextePaie,
    date_debut_periode: date,
    date_fin_periode: date,
) -> BaseDesJours:
    jours_ouvres = bool(arret.get("maintien_base_ouvree"))
    duree_hebdo = float(contexte.duree_hebdo_contrat or 0.0)
    try:
        from .calcul_brut import _get_salaire_horaire_base

        taux_horaire_base = _get_salaire_horaire_base(contexte, duree_hebdo)
    except Exception:
        taux_horaire_base = 0.0
    mois_entier = arret.get("mois_entier_en_arret")
    if mois_entier is None:
        debut = _parse_date(arret.get("date_debut"))
        fin = _parse_date(arret.get("date_fin")) or debut
        mois_entier = bool(
            debut and fin and debut <= date_debut_periode and fin >= date_fin_periode
        )
    jours_du_mois = sum(
        1
        for k in range(_compter_jours_calendaires(date_debut_periode, date_fin_periode))
        if not jours_ouvres or (date_debut_periode + timedelta(days=k)).weekday() < 5
    )
    salaire = (
        _salaire_du_mois(contexte, duree_hebdo, taux_horaire_base)
        if jours_ouvres
        else round(float(contexte.salaire_base_mensuel or 0.0), 2)
    )
    quotite = 1.0
    if bool(arret.get("is_temps_partiel")):
        q = float(arret.get("quotite_temps_partiel") or 1.0)
        if q > 0:
            quotite = q
    return BaseDesJours(
        contexte=contexte,
        jours_ouvres=jours_ouvres,
        mois_entier=bool(mois_entier),
        jours_du_mois=jours_du_mois,
        salaire_du_mois=salaire,
        taux_horaire_base=taux_horaire_base,
        duree_hebdo=duree_hebdo,
        quotite=quotite,
    )
```

- [ ] **Step 4 : les relancer, ils passent**

Run : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_maintien_paliers_valeur.py -q`
Expected : PASS — 7 passed

Puis, sans régression : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll tests/unit/maintenance_settings tests/integration/legacy/test_maintien_salaire_service.py -q` → tout vert.

- [ ] **Step 5 : commit**

```bash
git add backend/app/modules/payroll/engine/maintien_salaire_service.py backend/tests/unit/payroll/test_maintien_paliers_valeur.py
git commit -m "feat(paie): sous le barème, un jour maintenu vaut ce que son absence a retiré du salaire" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 5 : Le moteur applique le barème, plancher légal comparé sur le versé

**Files :**
- Create : `backend/app/modules/payroll/domain/paliers_affiches.py`
- Modify : `backend/app/modules/payroll/engine/maintien_salaire_service.py` (imports ; bloc « Barème de la convention : plan, plancher légal, maintien » ; `calculer_maintien`)
- Test : `backend/tests/unit/payroll/test_maintien_paliers_bareme.py`

**Interfaces :**
- Consumes : tâches 1, 2 et 4 (`bareme_des_reglages`, `mois_complets`, `plan_conventionnel`, `arrets_pour_le_plan`, `PlanConventionnel`, `BaseDesJours`, `_base_des_jours`) ; `_verse_avec_subrogation`, `_verse_sans_subrogation`, `_ijss_des_jours_maintenus`, `duree_maintien_par_taux`, `_taux_legal_pour_jour_maintien`, `_jours_deja_en_arret`, `_date_anciennete`, `_statut_est_cadre`, `_jours_fr` (existants).
- Produces :
  - `paliers_affiches` : `ALERTE_STATUT_ABSENT`, `detail_du_bareme(bareme, est_cadre, arret)`, `motif_sans_droit(bareme, arret)`, `motif_carence_du_bareme(bareme, arret)`, `alertes_du_bareme(bareme, maintien, plan, debut_arret, fin_arret, *, statut, debut_periode, fin_periode)` ;
  - MSS : `CARENCE_LEGALE_EMPLOYEUR_JOURS = 7`, `ANCIENNETE_LEGALE_MOIS = 12`, `_est_cadre(contexte)`, `_plan_au_bareme(arret, contexte, bareme, arret_type, date_debut_arret, date_fin_arret)`, `_carence_au_bareme(carence, plan, bareme, date_debut_arret, date_fin_arret)`, `_anciennete_legale_atteinte(arret, contexte, date_debut_arret)`, `_taux_legaux_au_bareme(arret, qualification, contexte, anciennete_mois, date_debut_arret, jours) -> dict[date, float]`, `_option_au_bareme(...)`, `_calculer_maintien_au_bareme(...) -> tuple[dict, dict[date, float]]` ;
  - dans `calculer_maintien`, la variable locale `taux_retenus` (taux de chaque jour de la règle retenue) et `plan_conv`, que la tâche 6 passe à la prévoyance ;
  - clés du maintien, sous le barème seulement : `bareme`, `bareme_detail`, `regle_retenue` (`"convention"` ou `"legal"`), `paliers` (liste de `{taux, du, au, jours, jours_calendaires, valeur, garanti[, ijss_deduites]}`), `paliers_en_jours_ouvres`.

- [ ] **Step 1 : les tests, qui échouent**

Créer `backend/tests/unit/payroll/test_maintien_paliers_bareme.py` :

```python
"""Le moteur applique le barème de la plasturgie (conception du 24/10/2026).

Au centime, les cas de Comitech que le texte explique : IJ au montant validé
relevé sur Quadra (41,19 €/jour pour S.G., 41,95 € pour D.S.), salaires de la
fiche. Puis le plancher légal, comparé sur le versé, les alertes, la
subrogation, et la compatibilité : sans barème, rien ne change. Initiales
seulement.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

AVRIL = (date(2026, 4, 1), date(2026, 4, 30))
MAI = (date(2026, 5, 1), date(2026, 5, 31))
JUIN = (date(2026, 6, 1), date(2026, 6, 30))
JUILLET = (date(2026, 7, 1), date(2026, 7, 31))
SEPTEMBRE = (date(2026, 9, 1), date(2026, 9, 30))

#: Comitech : jamais de subrogation, jours ouvrés, IJSS déduites, barème.
BAREME = {
    "bareme_convention": "plasturgie_0292",
    "subrogation_mode": "never",
    "maintain_working_days": True,
    "deduire_ijss_sans_subrogation": True,
}
#: Réglages manuels que le barème remplace : sous le barème, ils ne comptent pas.
MANUELS = {
    "apply_legal_maintenance": False,
    "employer_waiting_days": 3,
    "min_seniority_months": 10,
    "paid_waiting_days_per_year": 3,
    "custom_duration_days": 57,
    "maintain_100_percent": True,
}
ALERTE_LEGAL = "Règle conventionnelle moins favorable que la règle légale — application de la règle légale"


def _contexte(entree="2003-07-15", salaire=1952.60, statut="Non-Cadre"):
    return build_test_contexte(
        statut=statut, salaire_base=salaire, duree_hebdo=39.0, date_entree=entree,
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )


def _sg(entree="2003-07-15"):
    return _contexte(entree)


def _ds():
    return _contexte("2003-09-01", 3368.60, "Cadre")


def _arret(debut, fin, connus, override=None, type_arret="maladie_simple", **extra):
    arret = {
        "arret_type": type_arret,
        "date_debut": debut,
        "date_fin": fin,
        "subrogation_active": False,
        "nombre_enfants": 0,
        "salaire_periode_reelle": 0.0,
        "arrets_connus": [{"debut": d, "fin": f, "type": type_arret} for d, f in connus],
        **extra,
    }
    if override is not None:
        arret["ijss_brut_override"] = override
    return arret


CHAINE_SG = [("2026-05-04", "2026-05-31"), ("2026-06-01", "2026-06-30"),
             ("2026-07-01", "2026-07-31"), ("2026-08-01", "2026-08-31"),
             ("2026-09-01", "2026-09-30")]


def _mois_sg(mois, periode, override, contexte=None, reglages=BAREME, **extra):
    debut, fin = CHAINE_SG[mois - 5]
    arret = _arret(debut, fin, CHAINE_SG[: mois - 4], override, **extra)
    return calculer_maintien(arret, contexte or _sg(), dict(reglages), *periode)


# --- Comitech, au centime ----------------------------------------------------


def test_s_g_mai_premier_arret_de_l_annee_sans_carence():
    r = _mois_sg(5, MAI, 1029.75)
    m = r["maintien"]
    assert (m["maintien_cible"], m["ijss_deduites"], m["maintien_verse"]) == (2059.84, 1029.75, 1030.09)
    assert m["paliers"] == [{
        "taux": 1.0, "du": "2026-05-04", "au": "2026-05-31", "jours": 20,
        "jours_calendaires": 28, "valeur": 2059.84, "garanti": 2059.84, "ijss_deduites": 1029.75,
    }]
    assert m["bareme"] == "plasturgie_0292" and m["regle_retenue"] == "convention"
    assert m["bareme_detail"] == "Plasturgie (IDCC 0292), non-cadres, 5 ans et plus"
    assert r["carence"]["carence_employeur_jours"] == 0
    assert "premier arrêt de l'année, pas de carence" in r["carence"]["motif_carence"]


def test_s_g_juin_mois_entier_le_salaire_du_mois():
    m = _mois_sg(6, JUIN, 1235.70)["maintien"]
    assert (m["maintien_cible"], m["ijss_deduites"], m["maintien_verse"]) == (2231.48, 1235.70, 995.78)


def test_d_s_cadre_avril_et_mai():
    arret = _arret("2026-04-27", "2026-07-17", [("2026-04-27", "2026-07-17")])
    avril = calculer_maintien({**arret, "ijss_brut_override": 41.95}, _ds(), dict(BAREME), *AVRIL)
    assert (avril["maintien"]["maintien_cible"], avril["maintien"]["maintien_verse"]) == (710.72, 668.77)
    assert "cadres : pas de carence" in avril["carence"]["motif_carence"]
    mai = calculer_maintien({**arret, "ijss_brut_override": 1300.45}, _ds(), dict(BAREME), *MAI)
    assert (mai["maintien"]["maintien_cible"], mai["maintien"]["maintien_verse"]) == (3849.73, 2549.28)
    assert mai["maintien"]["bareme_detail"] == "Plasturgie (IDCC 0292), cadres, 10 ans et plus"


def test_d_s_prolongation_du_18_au_26_07():
    arret = _arret("2026-07-18", "2026-07-26",
                   [("2026-04-27", "2026-07-17"), ("2026-07-18", "2026-07-26")], 377.55)
    m = calculer_maintien(arret, _ds(), dict(BAREME), *JUILLET)["maintien"]
    assert (m["maintien_cible"], m["ijss_deduites"], m["maintien_verse"]) == (888.40, 377.55, 510.85)


def test_les_reglages_manuels_ne_comptent_pas_sous_le_bareme():
    reference = _mois_sg(5, MAI, 1029.75)
    for extra in (MANUELS, {**MANUELS, "apply_legal_maintenance": True}):
        assert _mois_sg(5, MAI, 1029.75, reglages={**BAREME, **extra}) == reference


# --- Paliers dans le mois ----------------------------------------------------


def test_passage_a_75_pour_cent_dans_le_mois():
    """Non-cadre de 6 ans, juillet : 2 jours à 100 %, puis 75 % dès le 03/07."""
    r = _mois_sg(7, JUILLET, 1276.89, contexte=_sg("2020-01-15"))
    m = r["maintien"]
    assert m["paliers"] == [
        {"taux": 1.0, "du": "2026-07-01", "au": "2026-07-02", "jours": 2, "jours_calendaires": 2,
         "valeur": 194.04, "garanti": 194.04, "ijss_deduites": 82.38},
        {"taux": 0.75, "du": "2026-07-03", "au": "2026-07-31", "jours": 21, "jours_calendaires": 29,
         "valeur": 2037.44, "garanti": 1528.08, "ijss_deduites": 1194.51},
    ]
    assert (m["maintien_cible"], m["maintien_verse"]) == (1722.12, 445.23)
    assert "Plasturgie : passage à 75 % le 03/07/2026." in r["alertes"]


# --- Plancher légal, comparé sur le versé ------------------------------------


def test_le_legal_l_emporte_en_juillet_pour_un_non_cadre_de_22_ans():
    r = _mois_sg(7, JUILLET, 1276.89)
    m = r["maintien"]
    assert m["regle_retenue"] == "legal" and m["conflit_convention"] is True
    assert [(p["taux"], p["du"], p["au"], p["jours"], p["garanti"]) for p in m["paliers"]] == [
        (0.9, "2026-07-01", "2026-07-19", 13, 1135.14),
        (0.6667, "2026-07-20", "2026-07-31", 10, 646.81),
    ]
    assert (m["maintien_cible"], m["maintien_verse"]) == (1781.95, 505.06)
    assert ALERTE_LEGAL in r["alertes"]


def test_en_septembre_le_bareme_l_emporte_sur_le_verse_meme_si_le_garanti_legal_est_plus_haut():
    """Légal : 1 284,79 garantis, 172,66 versés ; barème : 836,81 et 218,96."""
    r = _mois_sg(9, SEPTEMBRE, 1235.70)
    m = r["maintien"]
    assert m["regle_retenue"] == "convention"
    assert (m["maintien_cible"], m["ijss_deduites"], m["maintien_verse"]) == (836.81, 617.85, 218.96)
    assert (
        "Plasturgie : limite de 135 jours atteinte le 15/09/2026, plus de maintien ensuite. "
        "Vérifier la prévoyance."
    ) in r["alertes"]


# --- Subrogation et réglage des IJSS -----------------------------------------


def test_avec_subrogation_le_garanti_moins_les_ijss_des_jours_maintenus():
    reglages = {**BAREME, "subrogation_mode": "when_maintien"}
    r = _mois_sg(6, JUIN, 1235.70, reglages=reglages, subrogation_active=True)
    assert r["subrogation_active"] is True
    m = r["maintien"]
    assert (m["maintien_cible"], m["maintien_verse"]) == (2231.48, 995.78)
    assert "ijss_deduites" not in m
    assert m["paliers"][0]["ijss_deduites"] == 1235.70


def test_sans_subrogation_garanti_en_entier():
    m = _mois_sg(6, JUIN, 1235.70, reglages={**BAREME, "deduire_ijss_sans_subrogation": False})["maintien"]
    assert m["maintien_verse"] == m["maintien_cible"] == 2231.48
    assert "ijss_deduites" not in m and "ijss_deduites" not in m["paliers"][0]


# --- Droit, carence, statut --------------------------------------------------


def test_onze_mois_rien_en_maladie_mais_les_paliers_en_accident_du_travail():
    contexte = _contexte("2025-05-28", 1918.32)
    maladie = calculer_maintien(
        _arret("2026-05-05", "2026-05-13", [("2026-05-05", "2026-05-13")]), contexte, dict(BAREME), *MAI
    )
    motif = "Plasturgie : un an d'ancienneté requis pour une maladie (11 mois au début de l'arrêt)."
    assert maladie["maintien"]["maintien_applicable"] is False
    assert maladie["maintien"]["motif_non_maintien"] == motif
    assert motif in maladie["alertes"]
    at = calculer_maintien(
        _arret("2026-05-05", "2026-05-07", [("2026-05-05", "2026-05-07")], type_arret="accident_travail"),
        contexte, dict(BAREME), *MAI,
    )
    assert at["maintien"]["maintien_applicable"] is True
    assert [(p["taux"], p["jours"]) for p in at["maintien"]["paliers"]] == [(1.0, 3)]


def test_un_deuxieme_arret_a_trois_jours_de_carence():
    connus = [("2026-02-02", "2026-02-06"), ("2026-03-02", "2026-03-13")]
    r = calculer_maintien(_arret("2026-03-02", "2026-03-13", connus), _sg(), dict(BAREME),
                          date(2026, 3, 1), date(2026, 3, 31))
    assert r["carence"]["carence_employeur_jours"] == 3
    assert r["carence"]["motif_carence"] == (
        "Carence SS : 3 jours. Plasturgie : 3 jours de carence, du 02/03/2026 au 04/03/2026."
    )
    assert r["maintien"]["paliers"][0]["du"] == "2026-03-05"


def test_un_statut_absent_est_lu_non_cadre_et_le_bulletin_le_dit():
    r = _mois_sg(5, MAI, 1029.75, contexte=_contexte(statut=""))
    assert "Statut absent de la fiche : barème des non-cadres appliqué." in r["alertes"]
    assert r["maintien"]["maintien_verse"] == 1030.09


# --- Compatibilité : sans barème, rien ne change ------------------------------


@pytest.mark.parametrize("mois, periode, override", [(5, MAI, 1029.75), (6, JUIN, 1235.70)])
def test_sans_bareme_le_resultat_est_celui_d_avant_cle_pour_cle(mois, periode, override):
    sans = {k: v for k, v in {**BAREME, **MANUELS}.items() if k != "bareme_convention"}
    avant = _mois_sg(mois, periode, override, reglages=sans)
    assert _mois_sg(mois, periode, override, reglages={**sans, "bareme_convention": None}) == avant
    assert "paliers" not in avant["maintien"] and "bareme" not in avant["maintien"]
```

- [ ] **Step 2 : les lancer, ils échouent**

Run : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_maintien_paliers_bareme.py -q`
Expected : FAIL — 13 failed, 2 passed (les deux tests de compatibilité passent déjà)

- [ ] **Step 3 : le code**

Créer `backend/app/modules/payroll/domain/paliers_affiches.py` :

```python
"""Le maintien au barème de la convention : les textes du bulletin.

Carence, alertes, détail du barème appliqué, explication de la ligne de
maintien (conception du 24/10/2026). Ces textes n'existent que sous un barème :
sans barème, le bulletin garde ses textes d'avant.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Optional

from app.modules.payroll.domain.baremes_maintien import Bareme, libelle_tranche, pourcent

#: Raisons de carence posées par le plan (`paliers_convention`).
_RAISON_CADRE = "cadre"
_RAISON_ACCIDENT = "accident"
_RAISON_ALD = "ald"
_RAISON_PREMIER_ARRET = "premier_arret"
_RAISON_RELIQUAT = "reliquat"

ALERTE_STATUT_ABSENT = "Statut absent de la fiche : barème des non-cadres appliqué."


def _date_fr(jour: date) -> str:
    return jour.strftime("%d/%m/%Y")


def _jours(n: int) -> str:
    return f"{n} jour{'s' if n > 1 else ''}"


def detail_du_bareme(bareme: Bareme, est_cadre: bool, arret: Any) -> str:
    """« Plasturgie (IDCC 0292), non-cadres, 5 ans et plus »."""
    categorie = bareme.categorie(est_cadre)
    texte = f"{bareme.libelle}, {categorie.titre.lower()}"
    tranche = getattr(arret, "tranche", None)
    if tranche is not None:
        texte += f", {libelle_tranche(categorie, tranche)}"
    return texte


def motif_sans_droit(bareme: Bareme, arret: Any) -> str:
    mois = int(getattr(arret, "mois_anciennete", 0) or 0)
    return (
        f"{bareme.nom_court} : un an d'ancienneté requis pour une maladie "
        f"({mois} mois au début de l'arrêt)."
    )


def motif_carence_du_bareme(bareme: Bareme, arret: Any) -> str:
    nom = bareme.nom_court
    if getattr(arret, "tranche", None) is None:
        return motif_sans_droit(bareme, arret)
    raison = getattr(arret, "raison_carence", "")
    if raison == _RAISON_CADRE:
        return f"{nom}, cadres : pas de carence."
    if raison == _RAISON_ACCIDENT:
        return (
            f"{nom} : pas de carence pour un accident du travail, une maladie "
            "professionnelle ou un accident de trajet."
        )
    if raison == _RAISON_ALD:
        return f"{nom} : pas de carence pour une affection de longue durée."
    if raison == _RAISON_PREMIER_ARRET:
        return f"{nom} : premier arrêt de l'année, pas de carence."
    jours = tuple(getattr(arret, "jours_de_carence", ()) or ())
    texte = f"{nom} : {_jours(len(jours))} de carence"
    if len(jours) > 1:
        texte += f", du {_date_fr(jours[0])} au {_date_fr(jours[-1])}"
    elif jours:
        texte += f", le {_date_fr(jours[0])}"
    if raison == _RAISON_RELIQUAT:
        texte += " (le premier arrêt de l'année a duré moins de 3 jours)"
    return texte + "."


def alertes_du_bareme(
    bareme: Bareme,
    maintien: Mapping[str, Any],
    plan: Any,
    debut_arret: date,
    fin_arret: date,
    *,
    statut: str,
    debut_periode: date,
    fin_periode: date,
) -> list[str]:
    """Statut absent, droit fermé, passage de palier, limite atteinte."""
    alertes: list[str] = []
    if not str(statut or "").strip():
        alertes.append(ALERTE_STATUT_ABSENT)
    arret = plan.arret_du_jour(debut_arret)
    if not maintien.get("maintien_applicable", True):
        alertes.append(str(maintien.get("motif_non_maintien") or motif_sans_droit(bareme, arret)))
        return alertes
    if arret is None or arret.tranche is None:
        return alertes
    for jour, taux in arret.bascules[1:]:
        if debut_periode <= jour <= fin_periode:
            alertes.append(f"{bareme.nom_court} : passage à {pourcent(taux)} le {_date_fr(jour)}.")
    limite = arret.limite_atteinte
    if limite is not None:
        refuses = [
            j for j in arret.jours
            if j > limite
            and debut_periode <= j <= fin_periode
            and debut_arret <= j <= fin_arret
            and j not in plan.taux_par_jour
        ]
        if refuses:
            alertes.append(
                f"{bareme.nom_court} : limite de {arret.tranche.limite} jours atteinte le "
                f"{_date_fr(limite)}, plus de maintien ensuite. Vérifier la prévoyance."
            )
    return alertes


__all__ = [
    "ALERTE_STATUT_ABSENT",
    "alertes_du_bareme",
    "detail_du_bareme",
    "motif_carence_du_bareme",
    "motif_sans_droit",
]
```

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — remplacer :

```python
from app.modules.payroll.domain.ijss_deduites import (
    CLE_IJSS_DEDUITES,
    CLE_SOURCE,
    SOURCE_ESTIMEES,
    SOURCE_VALIDEES,
    alerte_ijss_au_salarie,
    est_alerte_ijss_au_salarie,
)
```

par :

```python
from app.modules.payroll.domain.baremes_maintien import (
    Bareme,
    bareme_des_reglages,
    mois_complets,
)
from app.modules.payroll.domain.ijss_deduites import (
    CLE_IJSS_DEDUITES,
    CLE_SOURCE,
    SOURCE_ESTIMEES,
    SOURCE_VALIDEES,
    alerte_ijss_au_salarie,
    est_alerte_ijss_au_salarie,
)
from app.modules.payroll.domain.paliers_affiches import (
    alertes_du_bareme,
    detail_du_bareme,
    motif_carence_du_bareme,
    motif_sans_droit,
)
```

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — insérer **avant** le bloc :

```python
from .prolongation_arret import chainer_arret
```

le code :

```python
from .paliers_convention import PlanConventionnel, arrets_pour_le_plan, plan_conventionnel
```

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — insérer **avant** le bloc :

```python
# --- Prolongation et arrêts du mois ---
```

le code :

```python
# --- Barème de la convention : plan, plancher légal, maintien ---

#: Plancher légal sous le barème : 7 jours de carence, comme le moteur
#: aujourd'hui (MSS, `_calculer_carence`), 0 en accident du travail et maladie
#: professionnelle hors trajet.
CARENCE_LEGALE_EMPLOYEUR_JOURS = 7
#: Plancher légal sous le barème : une année d'ancienneté (L1226-1).
ANCIENNETE_LEGALE_MOIS = 12


def _est_cadre(contexte: ContextePaie) -> bool:
    try:
        return _statut_est_cadre(str(contexte.statut_salarie or ""))
    except Exception:
        return False


def _plan_au_bareme(
    arret: Dict[str, Any],
    contexte: ContextePaie,
    bareme: Bareme,
    arret_type: str,
    date_debut_arret: date,
    date_fin_arret: date,
) -> PlanConventionnel:
    """Les arrêts connus du salarié, rejoués avec le barème de la société."""
    return plan_conventionnel(
        arrets_pour_le_plan(
            arret.get("arrets_connus") or [], date_debut_arret, date_fin_arret, arret_type
        ),
        bareme=bareme,
        est_cadre=_est_cadre(contexte),
        date_anciennete=_date_anciennete(contexte),
    )


def _carence_au_bareme(
    carence: Dict[str, Any],
    plan: PlanConventionnel,
    bareme: Bareme,
    date_debut_arret: date,
    date_fin_arret: date,
) -> Dict[str, Any]:
    """La carence employeur du barème, à la place de celle des réglages manuels."""
    rejoue = plan.arret_du_jour(date_debut_arret)
    jours = [
        j for j in (rejoue.jours_de_carence if rejoue else ())
        if date_debut_arret <= j <= date_fin_arret
    ]
    sortie = {
        **carence,
        "carence_employeur_jours": len(jours),
        "carence_employeur_jours_arret": rejoue.carence_jours if rejoue else 0,
    }
    if rejoue is not None and not carence.get("prolongation_de"):
        ss = int(carence.get("carence_ss_jours") or 0)
        sortie["motif_carence"] = (
            f"Carence SS : {_jours_fr(ss)}. {motif_carence_du_bareme(bareme, rejoue)}"
        )
    return sortie


def _anciennete_legale_atteinte(
    arret: Dict[str, Any], contexte: ContextePaie, date_debut_arret: date
) -> bool:
    date_anc = _date_anciennete(contexte)
    debut_chaine = _parse_date(arret.get("date_debut_chaine")) or date_debut_arret
    return date_anc is not None and mois_complets(date_anc, debut_chaine) >= ANCIENNETE_LEGALE_MOIS


def _taux_legaux_au_bareme(
    arret: Dict[str, Any],
    qualification: Dict[str, Any],
    contexte: ContextePaie,
    anciennete_mois: int,
    date_debut_arret: date,
    jours: List[date],
) -> Dict[date, float]:
    """Le maintien légal sous le barème, sans aucun réglage de la société."""
    if not _anciennete_legale_atteinte(arret, contexte, date_debut_arret):
        return {}
    trajet = str(arret.get("arret_type") or "").strip() == "accident_trajet"
    carence = 0 if (qualification.get("est_at_mp") and not trajet) else CARENCE_LEGALE_EMPLOYEUR_JOURS
    duree = duree_maintien_par_taux(anciennete_mois)
    jours_deja = _jours_deja_en_arret(arret)
    taux: Dict[date, float] = {}
    for jour in jours:
        rang = jours_deja + (jour - date_debut_arret).days + 1 - carence
        t = _taux_legal_pour_jour_maintien(rang, duree)
        if t > 0:
            taux[jour] = t
    return taux


def _repartir_les_ijss(
    paliers: List[Dict[str, Any]],
    retenues: float,
    ijss: Dict[str, Any],
    ijss_par_jour: Optional[Dict[date, float]],
    releve_du_mois: Optional[ReleveIjss],
) -> None:
    """Les IJSS déduites, palier par palier ; le dernier prend l'arrondi."""
    if retenues > 0 and ijss_par_jour is not None and paliers:
        parts = [
            _ijss_des_jours_maintenus(set(p["_jours"]), ijss, ijss_par_jour, releve_du_mois)[0]
            for p in paliers
        ]
        total = sum(parts)
        reste = round(retenues, 2)
        for rang, palier in enumerate(paliers):
            if rang == len(paliers) - 1:
                part = reste
            else:
                part = round(retenues * parts[rang] / total, 2) if total > 0 else 0.0
            palier["ijss_deduites"] = round(part, 2)
            reste = round(reste - part, 2)
    for palier in paliers:
        palier.pop("_jours", None)


def _option_au_bareme(
    taux_par_jour: Dict[date, float],
    *,
    base: BaseDesJours,
    arret: Dict[str, Any],
    settings: Dict[str, Any],
    ijss: Dict[str, Any],
    ijss_par_jour: Optional[Dict[date, float]],
    releve_du_mois: Optional[ReleveIjss],
) -> Dict[str, Any]:
    """Une règle (barème ou légal) : ses paliers du mois, son garanti, son versé."""
    paliers: List[Dict[str, Any]] = []
    for taux in set(taux_par_jour.values()):
        jours = sorted(j for j, t in taux_par_jour.items() if t == taux)
        nb = sum(1 for j in jours if base.compte(j))
        valeur = base.valeur(nb)
        paliers.append(
            {
                "taux": round(taux, 4),
                "du": jours[0].isoformat(),
                "au": jours[-1].isoformat(),
                "jours": nb,
                "jours_calendaires": len(jours),
                "valeur": valeur,
                "garanti": round(valeur * taux, 2),
                "_jours": jours,
            }
        )
    paliers.sort(key=lambda p: p["du"])
    cible = round(sum(p["garanti"] for p in paliers), 2)
    jours_maintenus = set(taux_par_jour)
    deduction: Dict[str, Any] = {}
    if bool(arret.get("subrogation_active")):
        verse = _verse_avec_subrogation(
            cible, arret, jours_maintenus, ijss, ijss_par_jour, releve_du_mois
        )
        retenues = round(cible - verse, 2)
    else:
        verse, deduction = _verse_sans_subrogation(
            cible, settings, jours_maintenus, ijss, ijss_par_jour, releve_du_mois
        )
        retenues = float(deduction.get(CLE_IJSS_DEDUITES) or 0.0)
    _repartir_les_ijss(paliers, retenues, ijss, ijss_par_jour, releve_du_mois)
    return {
        "cible": cible,
        "verse": round(verse, 2),
        "paliers": paliers,
        "deduction": deduction,
        "taux_par_jour": dict(taux_par_jour),
    }


def _calculer_maintien_au_bareme(
    arret: Dict[str, Any],
    qualification: Dict[str, Any],
    carence: Dict[str, Any],
    ijss: Dict[str, Any],
    contexte: ContextePaie,
    settings: Dict[str, Any],
    date_debut_arret: date,
    anciennete_mois: int,
    date_debut_periode: date,
    date_fin_periode: date,
    *,
    plan: PlanConventionnel,
    bareme: Bareme,
    ijss_par_jour: Optional[Dict[date, float]],
    releve_du_mois: Optional[ReleveIjss],
) -> Tuple[Dict[str, Any], Dict[date, float]]:
    """Le maintien sous le barème, et le taux de chaque jour retenu.

    Le barème et le maintien légal valorisent les jours de la même façon
    (`BaseDesJours`) ; Martine verse le plus favorable des deux, jugé sur ce
    que l'employeur verse (garanti moins les IJSS de ses jours), pas sur le
    garanti seul (conception du 24/10, §3.4).
    """
    date_fin_arret = _parse_date(arret.get("date_fin")) or date_debut_arret
    rejoue = plan.arret_du_jour(date_debut_arret)
    duree_par_taux = duree_maintien_par_taux(anciennete_mois)
    commun: Dict[str, Any] = {
        "carence_employeur_jours": int(carence.get("carence_employeur_jours") or 0),
        "duree_par_taux_jours": duree_par_taux,
        "duree_maintien_legale_jours": 2 * duree_par_taux,
        "bareme": bareme.code,
        "bareme_detail": detail_du_bareme(bareme, _est_cadre(contexte), rejoue),
    }
    convention_ouverte = rejoue is not None and rejoue.tranche is not None
    if not convention_ouverte and not _anciennete_legale_atteinte(arret, contexte, date_debut_arret):
        return (
            {
                **commun,
                "maintien_applicable": False,
                "taux_maintien": 0.0,
                "maintien_cible": 0.0,
                "maintien_verse": 0.0,
                "nb_jours_maintien": 0,
                "complement_employeur": 0.0,
                "conflit_convention": False,
                "motif_non_maintien": motif_sans_droit(bareme, rejoue),
                "proratisation_temps_partiel": False,
                "regle_retenue": "convention",
                "paliers": [],
            },
            {},
        )
    inter_d, inter_f = _intersection_dates(
        date_debut_arret, date_fin_arret, date_debut_periode, date_fin_periode
    )
    jours: List[date] = (
        []
        if inter_d is None or inter_f is None
        else [inter_d + timedelta(days=k) for k in range(_compter_jours_calendaires(inter_d, inter_f))]
    )
    base = _base_des_jours(arret, contexte, date_debut_periode, date_fin_periode)
    options = dict(
        base=base, arret=arret, settings=settings, ijss=ijss,
        ijss_par_jour=ijss_par_jour, releve_du_mois=releve_du_mois,
    )
    convention = _option_au_bareme(
        {j: plan.taux_par_jour[j] for j in jours if j in plan.taux_par_jour}, **options
    )
    legal = _option_au_bareme(
        _taux_legaux_au_bareme(arret, qualification, contexte, anciennete_mois, date_debut_arret, jours),
        **options,
    )
    legal_retenu = legal["verse"] > convention["verse"] + 1e-9
    retenue = legal if legal_retenu else convention
    total_valeur = sum(p["valeur"] for p in retenue["paliers"])
    salaire_reel = float(arret.get("salaire_periode_reelle") or 0.0)
    return (
        {
            **commun,
            "maintien_applicable": True,
            "taux_maintien": (
                round(min(retenue["cible"] / total_valeur, 1.0), 4) if total_valeur else 0.0
            ),
            "maintien_cible": retenue["cible"],
            "maintien_verse": retenue["verse"],
            "nb_jours_maintien": sum(p["jours"] for p in retenue["paliers"]),
            "complement_employeur": round(retenue["verse"] - salaire_reel, 2),
            "conflit_convention": legal_retenu,
            "motif_non_maintien": None,
            "proratisation_temps_partiel": base.quotite != 1.0 and not base.mois_entier,
            "regle_retenue": "legal" if legal_retenu else "convention",
            "paliers": retenue["paliers"],
            "paliers_en_jours_ouvres": base.jours_ouvres,
            **retenue["deduction"],
        },
        retenue["taux_par_jour"],
    )
```

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — remplacer :

```python
    est_cadre = _statut_est_cadre(statut)

    jours_carence_payes = _jours_de_carence_payes_de_l_arret(
        arret,
        settings,
        date_entree=date_anciennete,
        date_debut_arret=date_debut_arret,
        date_fin_arret=date_fin_arret or date_debut_arret,
        arret_type=arret_type,
        est_cadre=est_cadre,
    )
    if jours_carence_payes:
```

par :

```python
    est_cadre = _statut_est_cadre(statut)

    # Barème de la convention (24/10/2026) : il remplace la carence payée et les
    # réglages manuels de taux, de durée et de carence. Sans barème : le calcul
    # d'avant, inchangé.
    bareme = None if qualification.get("est_maternite") else bareme_des_reglages(settings)
    plan_conv: Optional[PlanConventionnel] = None
    if bareme is not None:
        plan_conv = _plan_au_bareme(
            arret, contexte, bareme, arret_type, date_debut_arret,
            date_fin_arret or date_debut_arret,
        )
        carence = _carence_au_bareme(
            carence, plan_conv, bareme, date_debut_arret, date_fin_arret or date_debut_arret
        )
        jours_carence_payes: frozenset[date] = frozenset()
    else:
        jours_carence_payes = _jours_de_carence_payes_de_l_arret(
            arret,
            settings,
            date_entree=date_anciennete,
            date_debut_arret=date_debut_arret,
            date_fin_arret=date_fin_arret or date_debut_arret,
            arret_type=arret_type,
            est_cadre=est_cadre,
        )
    if jours_carence_payes:
```

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — remplacer :

```python
    maintien = _calculer_maintien_employeur(
        arret,
        qualification,
        carence,
        ijss,
        contexte,
        settings,
        date_debut_arret,
        anciennete_mois,
        date_debut_periode,
        date_fin_periode,
        jours_carence_payes=jours_carence_payes,
        ijss_par_jour=ijss_par_jour,
        releve_du_mois=releve_ijss_du_mois,
    )

    # Sans maintien de salaire sur la période
```

par :

```python
    taux_retenus: Dict[date, float] = {}

    def _maintien_de(arret_calcule: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal taux_retenus
        if plan_conv is not None and bareme is not None:
            resultat, taux_retenus = _calculer_maintien_au_bareme(
                arret_calcule,
                qualification,
                carence,
                ijss,
                contexte,
                settings,
                date_debut_arret,
                anciennete_mois,
                date_debut_periode,
                date_fin_periode,
                plan=plan_conv,
                bareme=bareme,
                ijss_par_jour=ijss_par_jour,
                releve_du_mois=releve_ijss_du_mois,
            )
            return resultat
        return _calculer_maintien_employeur(
            arret_calcule,
            qualification,
            carence,
            ijss,
            contexte,
            settings,
            date_debut_arret,
            anciennete_mois,
            date_debut_periode,
            date_fin_periode,
            jours_carence_payes=jours_carence_payes,
            ijss_par_jour=ijss_par_jour,
            releve_du_mois=releve_ijss_du_mois,
        )

    maintien = _maintien_de(arret)

    # Sans maintien de salaire sur la période
```

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — remplacer :

```python
        arret = {**arret, "subrogation_active": False}
        maintien = _calculer_maintien_employeur(
            arret,
            qualification,
            carence,
            ijss,
            contexte,
            settings,
            date_debut_arret,
            anciennete_mois,
            date_debut_periode,
            date_fin_periode,
            jours_carence_payes=jours_carence_payes,
            ijss_par_jour=ijss_par_jour,
            releve_du_mois=releve_ijss_du_mois,
        )
```

par :

```python
        arret = {**arret, "subrogation_active": False}
        maintien = _maintien_de(arret)
```

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — remplacer :

```python
    alertes: List[str] = []
    if not maintien.get("maintien_applicable", True):
        alertes.append(
            MOTIF_PARENTALITE_SANS_MAINTIEN
            if maintien.get("est_maternite")
            else "Ancienneté insuffisante pour le maintien légal"
        )
    duree_legale = int(maintien.get("duree_maintien_legale_jours") or 0)
    if duree_legale and nb_jours_arret_total > duree_legale:
        alertes.append(
            f"Durée maximale du maintien employeur atteinte ({duree_legale} jours "
            f"selon l'ancienneté). Vérifier l'activation de la prévoyance relais."
        )
```

par :

```python
    alertes: List[str] = []
    if plan_conv is not None and bareme is not None:
        alertes.extend(
            alertes_du_bareme(
                bareme,
                maintien,
                plan_conv,
                date_debut_arret,
                date_fin_arret or date_debut_arret,
                statut=statut,
                debut_periode=date_debut_periode,
                fin_periode=date_fin_periode,
            )
        )
    else:
        if not maintien.get("maintien_applicable", True):
            alertes.append(
                MOTIF_PARENTALITE_SANS_MAINTIEN
                if maintien.get("est_maternite")
                else "Ancienneté insuffisante pour le maintien légal"
            )
        duree_legale = int(maintien.get("duree_maintien_legale_jours") or 0)
        if duree_legale and nb_jours_arret_total > duree_legale:
            alertes.append(
                f"Durée maximale du maintien employeur atteinte ({duree_legale} jours "
                f"selon l'ancienneté). Vérifier l'activation de la prévoyance relais."
            )
```

- [ ] **Step 4 : les relancer, ils passent**

Run : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_maintien_paliers_bareme.py -q`
Expected : PASS — 15 passed

Puis, sans régression : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll tests/unit/maintenance_settings tests/integration/legacy/test_maintien_salaire_service.py -q` → tout vert.

- [ ] **Step 5 : commit**

```bash
git add backend/app/modules/payroll/domain/paliers_affiches.py backend/app/modules/payroll/engine/maintien_salaire_service.py backend/tests/unit/payroll/test_maintien_paliers_bareme.py
git commit -m "feat(paie): le maintien applique le barème de la plasturgie, plancher légal comparé sur le versé, IJSS déduites par palier" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 6 : Plusieurs arrêts du mois, prime d'ancienneté et prévoyance suivent le barème

**Files :**
- Modify : `backend/app/modules/payroll/engine/maintien_salaire_service.py` (`_calculer_prevoyance_complement`, `calculer_maintien`, `_calculer_maintien_des_arrets_du_mois`, `compute_jours_avec_maintien_mois`)
- Test : `backend/tests/unit/payroll/test_maintien_paliers_lecteurs.py`

**Interfaces :**
- Consumes (tâche 5) : `taux_retenus`, `plan_conv` dans `calculer_maintien` ; `bareme_des_reglages`.
- Produces :
  - `_calculer_prevoyance_complement(..., taux_maintien_par_jour: Optional[Dict[date, float]] = None)` ;
  - `_periode_couverte(segments, arret, date_debut_periode, date_fin_periode) -> bool`, qui pose `mois_entier_en_arret` sur chaque arrêt du mois sous le barème ;
  - la fusion de plusieurs arrêts réunit `paliers` et dit `regle_retenue` ;
  - `compute_jours_avec_maintien_mois` rend, sous le barème, les jours des paliers retenus.

- [ ] **Step 1 : les tests, qui échouent**

Créer `backend/tests/unit/payroll/test_maintien_paliers_lecteurs.py` :

```python
"""Sous le barème, les autres lecteurs du maintien suivent les paliers.

Plusieurs arrêts dans le mois, jours maintenus de la prime d'ancienneté,
complément de prévoyance (conception du 24/10/2026). Initiales seulement.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.maintien_salaire_service import (
    calculer_maintien,
    compute_jours_avec_maintien_mois,
)

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JUIN = (date(2026, 6, 1), date(2026, 6, 30))
SEPTEMBRE = (date(2026, 9, 1), date(2026, 9, 30))
BAREME = {
    "bareme_convention": "plasturgie_0292",
    "subrogation_mode": "never",
    "maintain_working_days": True,
    "deduire_ijss_sans_subrogation": True,
}
MANUELS = {"maintain_100_percent": True, "custom_duration_days": 57, "apply_legal_maintenance": True}
CHAINE = [("2026-05-04", "2026-05-31"), ("2026-06-01", "2026-06-30"),
          ("2026-07-01", "2026-07-31"), ("2026-08-01", "2026-08-31"),
          ("2026-09-01", "2026-09-30")]


def _sg():
    return build_test_contexte(
        salaire_base=1952.60, duree_hebdo=39.0, date_entree="2003-07-15",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )


def _arret(debut, fin, connus, **extra):
    return {
        "arret_type": "maladie_simple", "date_debut": debut, "date_fin": fin,
        "subrogation_active": False, "nombre_enfants": 0, "salaire_periode_reelle": 0.0,
        "arrets_connus": [{"debut": d, "fin": f, "type": "maladie_simple"} for d, f in connus],
        **extra,
    }


def test_deux_arrets_qui_couvrent_juin_valent_le_salaire_du_mois():
    connus = [CHAINE[0], ("2026-06-01", "2026-06-15"), ("2026-06-16", "2026-06-30")]
    arret = _arret("2026-06-01", "2026-06-30", connus, ijss_brut_override=1235.70, arrets_du_mois=[
        {"date_debut": "2026-06-01", "date_fin": "2026-06-15", "arret_type": "maladie_simple"},
        {"date_debut": "2026-06-16", "date_fin": "2026-06-30", "arret_type": "maladie_simple"},
    ])
    m = calculer_maintien(arret, _sg(), dict(BAREME), *JUIN)["maintien"]
    assert [(p["du"], p["au"], p["jours"], p["valeur"]) for p in m["paliers"]] == [
        ("2026-06-01", "2026-06-15", 11, 1115.74),
        ("2026-06-16", "2026-06-30", 11, 1115.74),
    ]
    assert (m["maintien_cible"], m["ijss_deduites"], m["maintien_verse"]) == (2231.48, 1235.70, 995.78)
    assert m["regle_retenue"] == "convention"


def test_la_prime_d_anciennete_suit_les_jours_de_la_regle_retenue():
    # IJ validées à 41,19 €/jour : le barème l'emporte sur le versé (218,96 contre 172,66).
    arret = _arret("2026-09-01", "2026-09-30", CHAINE, ijss_brut_override=1235.70)
    jours = compute_jours_avec_maintien_mois(arret, _sg(), {**BAREME, **MANUELS}, *SEPTEMBRE)
    assert jours == set(range(1, 16))  # 75 % jusqu'au 15/09 ; le légal n'est pas retenu


def test_la_prevoyance_lit_le_taux_de_chaque_jour_retenu():
    reglages = {**BAREME, **MANUELS, "provident_maintenance_rate": 0.8,
                "provident_cadre_only": False, "provident_relay_days": 1}
    arret = _arret("2026-09-01", "2026-09-30", CHAINE, ijss_brut_override=1235.70)
    r = calculer_maintien(arret, _sg(), reglages, *SEPTEMBRE)
    assert r["maintien"]["regle_retenue"] == "convention"
    # Du 16 au 30/09, plus de maintien : la prévoyance complète ; avant, 75 % suffit.
    assert r["prevoyance"]["nb_jours"] == 15
    assert r["prevoyance"]["montant"] > 0


def test_sans_bareme_la_prime_et_la_prevoyance_d_avant():
    sans = {k: v for k, v in {**BAREME, **MANUELS}.items() if k != "bareme_convention"}
    arret = _arret("2026-09-01", "2026-09-30", CHAINE)
    avant = compute_jours_avec_maintien_mois(arret, _sg(), sans, *SEPTEMBRE)
    assert compute_jours_avec_maintien_mois(arret, _sg(), {**sans, "bareme_convention": None}, *SEPTEMBRE) == avant
```

- [ ] **Step 2 : les lancer, ils échouent**

Run : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_maintien_paliers_lecteurs.py -q`
Expected : FAIL — 3 failed, 1 passed

- [ ] **Step 3 : le code**

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — remplacer :

```python
    date_fin_periode: date,
    jours_deja_en_arret: int = 0,
) -> Dict[str, Any]:
    """
    Complément de prévoyance (relais), paramétré par l'entreprise via les settings :
```

par :

```python
    date_fin_periode: date,
    jours_deja_en_arret: int = 0,
    taux_maintien_par_jour: Optional[Dict[date, float]] = None,
) -> Dict[str, Any]:
    """
    Complément de prévoyance (relais), paramétré par l'entreprise via les settings :
```

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — remplacer :

```python
                # Maintien employeur du jour (le plus favorable légal / conventionnel)
                jour_maintien = jour_arret - carence_emp
                m_leg = (
                    brut_journalier
                    * _taux_legal_pour_jour_maintien(jour_maintien, duree_par_taux)
                    if apply_legal
                    else 0.0
                )
                m_conv = (
                    brut_journalier * float(taux_conv)
                    if (taux_conv is not None and 1 <= jour_maintien <= cap_conv)
                    else 0.0
                )
                maintien_jour = max(m_leg, m_conv)
```

par :

```python
                # Maintien employeur du jour (le plus favorable légal / conventionnel).
                # Sous le barème : le taux du jour dans la règle retenue.
                if taux_maintien_par_jour is not None:
                    maintien_jour = brut_journalier * taux_maintien_par_jour.get(d, 0.0)
                else:
                    jour_maintien = jour_arret - carence_emp
                    m_leg = (
                        brut_journalier
                        * _taux_legal_pour_jour_maintien(jour_maintien, duree_par_taux)
                        if apply_legal
                        else 0.0
                    )
                    m_conv = (
                        brut_journalier * float(taux_conv)
                        if (taux_conv is not None and 1 <= jour_maintien <= cap_conv)
                        else 0.0
                    )
                    maintien_jour = max(m_leg, m_conv)
```

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — remplacer :

```python
        date_fin_periode=date_fin_periode,
        jours_deja_en_arret=jours_deja,
    )

    alertes: List[str] = []
```

par :

```python
        date_fin_periode=date_fin_periode,
        jours_deja_en_arret=jours_deja,
        taux_maintien_par_jour=taux_retenus if plan_conv is not None else None,
    )

    alertes: List[str] = []
```

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — insérer **avant** le bloc :

```python
def _calculer_maintien_des_arrets_du_mois(
```

le code :

```python
def _periode_couverte(
    segments: List[Dict[str, Any]],
    arret: Dict[str, Any],
    date_debut_periode: date,
    date_fin_periode: date,
) -> bool:
    """Tous les jours de la période sont-ils en arrêt, d'un arrêt ou d'un autre ?"""
    couverts: set = set()
    for segment in segments:
        sous = _arret_du_segment(arret, segment)
        debut = _parse_date(sous.get("date_debut"))
        fin = _parse_date(sous.get("date_fin")) or debut
        if debut is None or fin is None:
            continue
        jour = max(debut, date_debut_periode)
        while jour <= min(fin, date_fin_periode):
            couverts.add(jour)
            jour += timedelta(days=1)
    return len(couverts) == _compter_jours_calendaires(date_debut_periode, date_fin_periode)
```

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — remplacer :

```python
    resultats: List[Dict[str, Any]] = []
    for rang, segment in enumerate(segments):
        sous = _arret_du_segment(arret, segment)
        if override is not None:
```

par :

```python
    mois_entier: Optional[bool] = None
    if bareme_des_reglages(settings) is not None:
        mois_entier = _periode_couverte(segments, arret, date_debut_periode, date_fin_periode)
    resultats: List[Dict[str, Any]] = []
    for rang, segment in enumerate(segments):
        sous = _arret_du_segment(arret, segment)
        if mois_entier is not None:
            sous["mois_entier_en_arret"] = mois_entier
        if override is not None:
```

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — insérer **après** le bloc :

```python
    maintien["maintien_applicable"] = any(
        (r.get("maintien") or {}).get("maintien_applicable", True) for r in resultats
    )
```

le code :

```python
    if any("paliers" in (r.get("maintien") or {}) for r in resultats):
        maintien["paliers"] = [
            p for r in resultats for p in ((r.get("maintien") or {}).get("paliers") or [])
        ]
        legal = any((r.get("maintien") or {}).get("regle_retenue") == "legal" for r in resultats)
        maintien["regle_retenue"] = "legal" if legal else "convention"
        maintien["conflit_convention"] = legal
```

`backend/app/modules/payroll/engine/maintien_salaire_service.py` — remplacer :

```python
    date_debut_arret = _parse_date(arret.get("date_debut"))
    date_fin_arret = _parse_date(arret.get("date_fin")) or date_debut_arret
    if not date_debut_arret:
        return set()
    arret = _poser_la_chaine(arret, date_debut_arret, date_fin_arret, arret_type)
    jours_deja = _jours_deja_en_arret(arret)

    date_entree = _date_anciennete(contexte) or date(2000, 1, 1)
```

par :

```python
    date_debut_arret = _parse_date(arret.get("date_debut"))
    date_fin_arret = _parse_date(arret.get("date_fin")) or date_debut_arret
    if not date_debut_arret:
        return set()
    if not qualification.get("est_maternite") and bareme_des_reglages(settings) is not None:
        # Sous le barème : les jours des paliers de la règle retenue (barème ou légal).
        resultat = calculer_maintien(arret, contexte, settings, date_debut_periode, date_fin_periode)
        jours_bareme: set[int] = set()
        for palier in (resultat.get("maintien") or {}).get("paliers") or []:
            du, au = _parse_date(palier.get("du")), _parse_date(palier.get("au"))
            jour = du
            while du is not None and au is not None and jour <= au:
                jours_bareme.add(jour.day)
                jour += timedelta(days=1)
        return jours_bareme
    arret = _poser_la_chaine(arret, date_debut_arret, date_fin_arret, arret_type)
    jours_deja = _jours_deja_en_arret(arret)

    date_entree = _date_anciennete(contexte) or date(2000, 1, 1)
```

- [ ] **Step 4 : les relancer, ils passent**

Run : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_maintien_paliers_lecteurs.py -q`
Expected : PASS — 4 passed

Puis, sans régression : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll tests/unit/maintenance_settings tests/integration/legacy/test_maintien_salaire_service.py -q` → tout vert.

- [ ] **Step 5 : commit**

```bash
git add backend/app/modules/payroll/engine/maintien_salaire_service.py backend/tests/unit/payroll/test_maintien_paliers_lecteurs.py
git commit -m "feat(paie): sous le barème, plusieurs arrêts du mois, la prime d'ancienneté et la prévoyance suivent les paliers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 7 : La ligne de maintien dit ses paliers ; l'empreinte ne voit le barème que choisi

**Files :**
- Modify : `backend/app/modules/payroll/application/empreinte_entrees_service.py`, `backend/app/modules/payroll/domain/ijss_deduites.py`, `backend/app/modules/payroll/domain/paliers_affiches.py`, `backend/app/modules/payroll/domain/explications_lignes.py`
- Test : `backend/tests/unit/payroll/test_paliers_au_bulletin.py` (créé), `backend/tests/unit/payroll/test_empreinte_complementaire_service.py` (trois tests ajoutés)

**Interfaces :**
- Consumes : les clés du maintien de la tâche 5 ; `bareme_par_code`, `pourcent`, `libelle_tranche` (tâche 1).
- Produces : `ijss_deduites.suite_ijss_deduites(maintien) -> str` ; `paliers_affiches.explication_du_maintien_au_bareme(maintien) -> str | None` ; `_CLE_BAREME` dans l'empreinte, qui n'y entre que choisi.

- [ ] **Step 1 : les tests, qui échouent**

Créer `backend/tests/unit/payroll/test_paliers_au_bulletin.py` :

```python
"""Sous le barème, la ligne de maintien dit ses paliers, son garanti et ses IJSS
(conception du 24/10/2026)."""

from __future__ import annotations

import pytest

from app.modules.payroll.domain.explications_lignes import poser_explications

pytestmark = pytest.mark.unit

LIGNE = {"libelle": "Maintien de salaire employeur", "quantite": None, "taux": None,
         "gain": 445.23, "perte": None, "is_maintien_employeur": True}
JUILLET = {
    "maintien_cible": 1722.12, "maintien_verse": 445.23,
    "ijss_deduites": 1276.89, "ijss_deduites_source": "validees",
    "bareme": "plasturgie_0292", "regle_retenue": "convention",
    "bareme_detail": "Plasturgie (IDCC 0292), non-cadres, 5 ans et plus",
    "paliers_en_jours_ouvres": True,
    "paliers": [
        {"taux": 1.0, "du": "2026-07-01", "au": "2026-07-02", "jours": 2, "garanti": 194.04},
        {"taux": 0.75, "du": "2026-07-03", "au": "2026-07-31", "jours": 21, "garanti": 1528.08},
    ],
}


def _bulletin(maintien):
    return {
        "en_tete": {"annee": 2026, "mois": 7},
        "calcul_du_brut": [dict(LIGNE)],
        "bloc_maintien": {"maintien": maintien},
    }


def test_la_ligne_de_maintien_dit_les_paliers_le_garanti_et_les_ijss():
    b = poser_explications(_bulletin(JUILLET))
    assert b["calcul_du_brut"][0]["explication"] == (
        "Plasturgie (IDCC 0292), non-cadres, 5 ans et plus : 2 jours ouvrés à 100 % et "
        "21 jours ouvrés à 75 %, salaire garanti 1 722,12 € moins 1 276,89 € d'IJSS "
        "versées par la CPAM au salarié (montant validé dans le suivi IJSS)"
    )


def test_quand_le_legal_l_emporte_la_ligne_le_dit():
    legal = {**JUILLET, "regle_retenue": "legal", "maintien_cible": 1781.95,
             "ijss_deduites_source": "estimees", "paliers": [
                 {"taux": 0.9, "jours": 13}, {"taux": 0.6667, "jours": 10}]}
    texte = poser_explications(_bulletin(legal))["calcul_du_brut"][0]["explication"]
    assert texte.startswith(
        "Maintien légal, plus favorable ce mois-ci que le barème Plasturgie (IDCC 0292) : "
        "13 jours ouvrés à 90 % et 10 jours ouvrés à 66,67 %, salaire garanti 1 781,95 €"
    )


def test_avec_subrogation_pas_de_mention_d_ijss_versees_au_salarie():
    subroge = {k: v for k, v in JUILLET.items() if not k.startswith("ijss_deduites")}
    texte = poser_explications(_bulletin(subroge))["calcul_du_brut"][0]["explication"]
    assert texte.endswith("salaire garanti 1 722,12 €")


def test_sans_bareme_l_explication_d_avant():
    sans = {"maintien_cible": 665.68, "maintien_verse": 295.82,
            "ijss_deduites": 369.86, "ijss_deduites_source": "estimees"}
    assert poser_explications(_bulletin(sans))["calcul_du_brut"][0]["explication"].startswith(
        "Complément employeur : salaire garanti 665,68 €"
    )
```

`backend/tests/unit/payroll/test_empreinte_complementaire_service.py` — insérer **avant** le bloc :

```python
def test_la_jei_ne_compte_qu_activee():
```

le code :

```python
def test_le_bareme_nul_ne_change_pas_l_empreinte():
    avant = _du_mois(calendriers=_arret_en_mai())["reglages_societe"]
    nul = {**COMPLEMENTS.maintien, "bareme_convention": None}
    apres = _du_mois(replace(COMPLEMENTS, maintien=nul), calendriers=_arret_en_mai())
    assert empreinte_partie(apres["reglages_societe"]) == empreinte_partie(avant)


def test_choisir_le_bareme_un_mois_avec_arret_est_a_recalculer():
    choisi = {**COMPLEMENTS.maintien, "bareme_convention": "plasturgie_0292"}
    avant = _du_mois(calendriers=_arret_en_mai())["reglages_societe"]
    apres = _du_mois(replace(COMPLEMENTS, maintien=choisi), calendriers=_arret_en_mai())
    assert empreinte_partie(apres["reglages_societe"]) != empreinte_partie(avant)


def test_le_bareme_ne_touche_pas_un_mois_sans_arret():
    assert not _change("reglages_societe", maintien={**COMPLEMENTS.maintien, "bareme_convention": "plasturgie_0292"})
```

- [ ] **Step 2 : les lancer, ils échouent**

Run : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_paliers_au_bulletin.py tests/unit/payroll/test_empreinte_complementaire_service.py -q`
Expected : FAIL — 4 failed, 52 passed

- [ ] **Step 3 : le code**

`backend/app/modules/payroll/application/empreinte_entrees_service.py` — remplacer :

```python
_CLE_DEDUIRE_IJSS = "deduire_ijss_sans_subrogation"


def _maintien_pour_empreinte(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Le réglage du maintien que le moteur lit, la déduction des IJSS seulement allumée."""
    reglage = _sans(row, _COLONNES_HORS_CALCUL | {_CLE_DEDUIRE_IJSS})
    if reglage is not None and row.get(_CLE_DEDUIRE_IJSS) is True:
        reglage[_CLE_DEDUIRE_IJSS] = True
    return reglage
```

par :

```python
_CLE_DEDUIRE_IJSS = "deduire_ijss_sans_subrogation"
#: Réglage du 24/10/2026 : le barème de la convention n'y entre que choisi. La
#: migration ajoute la colonne, nulle partout ; sans ce filtre, tous les
#: bulletins avec un arrêt passeraient « À recalculer ».
_CLE_BAREME = "bareme_convention"


def _maintien_pour_empreinte(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Le réglage du maintien que le moteur lit : la déduction des IJSS seulement
    allumée, le barème seulement choisi."""
    reglage = _sans(row, _COLONNES_HORS_CALCUL | {_CLE_DEDUIRE_IJSS, _CLE_BAREME})
    if reglage is not None and row.get(_CLE_DEDUIRE_IJSS) is True:
        reglage[_CLE_DEDUIRE_IJSS] = True
    if reglage is not None and row.get(_CLE_BAREME):
        reglage[_CLE_BAREME] = row[_CLE_BAREME]
    return reglage
```

`backend/app/modules/payroll/domain/ijss_deduites.py` — insérer **avant** le bloc :

```python
def mention_ijss_deduites(
```

le code :

```python
def suite_ijss_deduites(maintien: Optional[Mapping[str, Any]]) -> str:
    """« moins 1 276,89 € d'IJSS versées par la CPAM au salarié (…) », ou rien."""
    deduites = montant_deduit(maintien)
    if deduites <= 0 or not isinstance(maintien, Mapping):
        return ""
    return (
        f" moins {_euros(deduites)} d'IJSS versées par la CPAM au salarié "
        f"({_SOURCE_LONGUE[_source(maintien)]})"
    )
```

`backend/app/modules/payroll/domain/paliers_affiches.py` — remplacer :

```python
from app.modules.payroll.domain.baremes_maintien import Bareme, libelle_tranche, pourcent
```

par :

```python
from app.modules.payroll.domain.baremes_maintien import (
    Bareme,
    bareme_par_code,
    libelle_tranche,
    pourcent,
)
from app.modules.payroll.domain.ijss_deduites import suite_ijss_deduites
```

`backend/app/modules/payroll/domain/paliers_affiches.py` — remplacer :

```python
__all__ = [
    "ALERTE_STATUT_ABSENT",
    "alertes_du_bareme",
```

par :

```python
def _euros(valeur: float) -> str:
    return f"{valeur:,.2f}".replace(",", " ").replace(".", ",") + " €"


def _jours_du_palier(n: int, ouvres: bool) -> str:
    if ouvres:
        return f"{n} jour ouvré" if n == 1 else f"{n} jours ouvrés"
    return _jours(n)


def explication_du_maintien_au_bareme(maintien: Optional[Mapping[str, Any]]) -> Optional[str]:
    """« D'où viennent ces lignes » : les paliers du mois, le garanti, les IJSS."""
    if not isinstance(maintien, Mapping) or not maintien.get("paliers"):
        return None
    ouvres = bool(maintien.get("paliers_en_jours_ouvres"))
    morceaux = [
        f"{_jours_du_palier(int(p.get('jours') or 0), ouvres)} à {pourcent(float(p.get('taux') or 0))}"
        for p in maintien["paliers"]
    ]
    garanti = round(float(maintien.get("maintien_cible") or 0.0), 2)
    if maintien.get("regle_retenue") == "legal":
        bareme = bareme_par_code(maintien.get("bareme"))
        nom = bareme.libelle if bareme else "de la convention"
        debut = f"Maintien légal, plus favorable ce mois-ci que le barème {nom}"
    else:
        debut = str(maintien.get("bareme_detail") or "Barème de la convention")
    return (
        f"{debut} : {' et '.join(morceaux)}, salaire garanti {_euros(garanti)}"
        f"{suite_ijss_deduites(maintien)}"
    )


__all__ = [
    "ALERTE_STATUT_ABSENT",
    "alertes_du_bareme",
    "explication_du_maintien_au_bareme",
```

`backend/app/modules/payroll/domain/explications_lignes.py` — remplacer :

```python
def _expliquer_ijss_deduites(bulletin: dict[str, Any]) -> None:
    """Sans subrogation, IJSS déduites : la ligne de maintien dit le calcul."""
    from app.modules.payroll.domain.ijss_deduites import explication_ijss_deduites

    bloc = bulletin.get("bloc_maintien")
    texte = explication_ijss_deduites(bloc.get("maintien") if isinstance(bloc, Mapping) else None)
```

par :

```python
def _expliquer_ijss_deduites(bulletin: dict[str, Any]) -> None:
    """La ligne de maintien dit le calcul : les paliers du barème quand il y en a
    un, sinon, sans subrogation, le garanti moins les IJSS déduites."""
    from app.modules.payroll.domain.ijss_deduites import explication_ijss_deduites
    from app.modules.payroll.domain.paliers_affiches import explication_du_maintien_au_bareme

    bloc = bulletin.get("bloc_maintien")
    maintien = bloc.get("maintien") if isinstance(bloc, Mapping) else None
    texte = explication_du_maintien_au_bareme(maintien) or explication_ijss_deduites(maintien)
```

- [ ] **Step 4 : les relancer, ils passent**

Run : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_paliers_au_bulletin.py tests/unit/payroll/test_empreinte_complementaire_service.py -q`
Expected : PASS — 56 passed

Puis, sans régression : `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll tests/unit/maintenance_settings tests/integration/legacy/test_maintien_salaire_service.py -q` → tout vert.

- [ ] **Step 5 : commit**

```bash
git add backend/app/modules/payroll/application/empreinte_entrees_service.py backend/app/modules/payroll/domain/explications_lignes.py backend/app/modules/payroll/domain/ijss_deduites.py backend/app/modules/payroll/domain/paliers_affiches.py backend/tests/unit/payroll/test_empreinte_complementaire_service.py backend/tests/unit/payroll/test_paliers_au_bulletin.py
git commit -m "feat(paie): la ligne de maintien dit ses paliers, et l'empreinte ne voit le barème que choisi" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 8 : La carte « Maintien de salaire » propose le barème et retire les deux champs morts

**Files :**
- Create : `frontend/src/features/company/components/baremeConvention.ts`
- Modify : `frontend/src/api/maintenanceSettings.ts`, `frontend/src/features/company/components/MaintenanceSettingsCard.tsx`
- Test : `frontend/src/test/baremeConvention.test.ts`

**Interfaces :**
- Consumes (tâche 3) : `bareme_convention` au GET/PUT, `GET /api/maintenance-settings/baremes`.
- Produces :
  - `api/maintenanceSettings.ts` : `type BaremeConvention = 'plasturgie_0292'`, `MaintenanceSettings.bareme_convention: BaremeConvention | null`, `interface BaremeLisible`, `getBaremesMaintien()` ; `seniority_extension_enabled` et `maintain_by_category` retirés du type ;
  - `baremeConvention.ts` : `AUCUN_BAREME`, `CHOIX_BAREME`, `AIDE_BAREME`, `TEXTE_LEGAL_SOUS_BAREME`, `TEXTE_STATUT_CADRE`, `CHAMPS_REMPLACES_PAR_LE_BAREME`, `texteRegleParLeBareme(libelle)`, `champVisible(cle, form)`, `choixBaremeDepuisReglage(code)`, `reglageDepuisChoixBareme(valeur)`, `baremeModifie(form, enregistre)`.

- [ ] **Step 1 : les tests, qui échouent**

Créer `frontend/src/test/baremeConvention.test.ts` :

```ts
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  AIDE_BAREME,
  CHAMPS_REMPLACES_PAR_LE_BAREME,
  CHOIX_BAREME,
  baremeModifie,
  champVisible,
  choixBaremeDepuisReglage,
  reglageDepuisChoixBareme,
  texteRegleParLeBareme,
} from "@/features/company/components/baremeConvention";

const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");

describe("Barème de la convention dans la carte « Maintien de salaire »", () => {
  it("propose « Aucun » et la plasturgie", () => {
    expect(CHOIX_BAREME.map((c) => [c.libelle, c.code])).toEqual([
      ["Aucun : les réglages ci-dessous", null],
      ["Plasturgie (IDCC 0292)", "plasturgie_0292"],
    ]);
    expect(AIDE_BAREME).toContain("Revenir à « Aucun » rend les réglages manuels");
    expect(texteRegleParLeBareme("Plasturgie (IDCC 0292)")).toBe(
      "Réglé par le barème Plasturgie (IDCC 0292).",
    );
  });

  it("le choix affiché suit le réglage, et l'inverse", () => {
    expect(choixBaremeDepuisReglage(null)).toBe("aucun");
    expect(choixBaremeDepuisReglage("plasturgie_0292")).toBe("plasturgie_0292");
    expect(reglageDepuisChoixBareme("aucun")).toBeNull();
    expect(reglageDepuisChoixBareme("plasturgie_0292")).toBe("plasturgie_0292");
    expect(reglageDepuisChoixBareme("autre")).toBeUndefined();
  });

  it("un barème choisi masque les champs qu'il remplace, et eux seuls", () => {
    const sous = { bareme_convention: "plasturgie_0292" as const };
    const sans = { bareme_convention: null };
    for (const cle of CHAMPS_REMPLACES_PAR_LE_BAREME) {
      expect(champVisible(cle, sous)).toBe(false);
      expect(champVisible(cle, sans)).toBe(true);
    }
    for (const cle of [
      "maintain_working_days",
      "maintain_parental_leave",
      "subrogation_mode",
      "deduire_ijss_sans_subrogation",
      "provident_maintenance_rate",
    ] as const) {
      expect(champVisible(cle, sous)).toBe(true);
    }
  });

  it("dit un choix pas encore enregistré", () => {
    const enregistre = { bareme_convention: null };
    expect(baremeModifie({ bareme_convention: "plasturgie_0292" }, enregistre)).toBe(true);
    expect(baremeModifie({ bareme_convention: null }, enregistre)).toBe(false);
    expect(baremeModifie({ bareme_convention: null }, undefined)).toBe(false);
  });

  it("la carte enregistre le barème, montre son tableau et n'a plus les deux champs morts", () => {
    const carte = lire("features/company/components/MaintenanceSettingsCard.tsx");
    expect(carte).toContain("bareme_convention: form.bareme_convention ?? null");
    expect(carte).toContain("CHOIX_BAREME.map");
    expect(carte).toContain("<TableauDuBareme bareme={baremeChoisi} />");
    expect(carte).toContain("{TEXTE_LEGAL_SOUS_BAREME}");
    expect(carte).toContain("baremeModifie(form, data)");
    expect(carte).toContain("Barème modifié, pas encore enregistré.");
    expect(carte).toContain(".filter(([key]) => visible(key))");
    expect(carte).not.toContain("Maintien par catégorie");
    expect(carte).not.toContain("Prolongation selon ancienneté");
    expect(carte).not.toContain("maintain_by_category");
    expect(carte).not.toContain("seniority_extension_enabled");
    const api = lire("api/maintenanceSettings.ts");
    expect(api).toContain("bareme_convention: BaremeConvention | null;");
    expect(api).toContain("'/api/maintenance-settings/baremes'");
    expect(api).not.toContain("maintain_by_category");
  });
});
```

- [ ] **Step 2 : les lancer, ils échouent**

Run : `cd frontend && npx vitest run src/test/baremeConvention.test.ts src/test/ijssSansSubrogation.test.ts src/test/ijssAffichage.test.ts`
Expected : FAIL — Error: Cannot find module '@/features/company/components/baremeConvention'

- [ ] **Step 3 : le code**

Créer `frontend/src/features/company/components/baremeConvention.ts` :

```ts
/**
 * Choix du barème de la convention dans la carte « Maintien de salaire »
 * (conception du 24/10/2026).
 *
 * « Aucun » : les réglages manuels, au centime comme avant. Un barème : ses
 * paliers s'appliquent, et les champs qu'il remplace disparaissent de l'écran.
 * Jamais un champ à l'écran que le moteur ignore.
 */
import type { BaremeConvention, MaintenanceSettings } from '@/api/maintenanceSettings';

export const AUCUN_BAREME = 'aucun';

export const CHOIX_BAREME: ReadonlyArray<{
  valeur: string;
  libelle: string;
  code: BaremeConvention | null;
}> = [
  { valeur: AUCUN_BAREME, libelle: 'Aucun : les réglages ci-dessous', code: null },
  { valeur: 'plasturgie_0292', libelle: 'Plasturgie (IDCC 0292)', code: 'plasturgie_0292' },
];

export const AIDE_BAREME =
  "Un barème tout fait applique les paliers de la convention : taux, durées selon le statut et l'ancienneté, carence et limites. Revenir à « Aucun » rend les réglages manuels, qui ne sont pas effacés.";

export const TEXTE_LEGAL_SOUS_BAREME =
  'Avec le barème, Martine compare chaque mois avec le maintien légal et verse le plus favorable.';

export const TEXTE_STATUT_CADRE =
  'Le statut cadre se lit sur la fiche du salarié ; une fiche sans statut est lue non-cadre.';

/** Champs que le barème remplace : ils disparaissent quand un barème est choisi. */
export const CHAMPS_REMPLACES_PAR_LE_BAREME: ReadonlyArray<keyof MaintenanceSettings> = [
  'apply_legal_maintenance',
  'min_seniority_months',
  'min_seniority_months_at_mp',
  'employer_waiting_days',
  'remove_employer_waiting',
  'annual_unique_waiting',
  'maintain_100_percent',
  'differentiated_at_illness',
  'no_seniority_condition',
  'paid_waiting_days_per_year',
  'paid_waiting_min_seniority_months',
  'custom_duration_days',
];

export function texteRegleParLeBareme(libelle: string): string {
  return `Réglé par le barème ${libelle}.`;
}

export function champVisible(
  cle: keyof MaintenanceSettings,
  form: Pick<MaintenanceSettings, 'bareme_convention'>,
): boolean {
  return !form.bareme_convention || !CHAMPS_REMPLACES_PAR_LE_BAREME.includes(cle);
}

export function choixBaremeDepuisReglage(code: BaremeConvention | null | undefined): string {
  return code ?? AUCUN_BAREME;
}

/** Le code à enregistrer ; undefined pour une valeur inconnue. */
export function reglageDepuisChoixBareme(valeur: string): BaremeConvention | null | undefined {
  const choix = CHOIX_BAREME.find((c) => c.valeur === valeur);
  return choix ? choix.code : undefined;
}

/** Le barème affiché n'est pas celui qui est enregistré. */
export function baremeModifie(
  form: Pick<MaintenanceSettings, 'bareme_convention'>,
  enregistre: Pick<MaintenanceSettings, 'bareme_convention'> | undefined,
): boolean {
  return Boolean(enregistre) && (form.bareme_convention ?? null) !== (enregistre?.bareme_convention ?? null);
}
```

`frontend/src/api/maintenanceSettings.ts` — insérer **après** le bloc :

```ts
export type SubrogationMode = 'when_maintien' | 'automatic' | 'at_mp_only' | 'per_case' | 'never';
```

le code :

```ts

/** Barème de la convention (conception du 24/10/2026). */
export type BaremeConvention = 'plasturgie_0292';
```

`frontend/src/api/maintenanceSettings.ts` — remplacer :

```ts
  employer_waiting_days: number;
  seniority_extension_enabled: boolean;
  remove_employer_waiting: boolean;
```

par :

```ts
  employer_waiting_days: number;
  remove_employer_waiting: boolean;
```

`frontend/src/api/maintenanceSettings.ts` — remplacer :

```ts
  differentiated_at_illness: boolean;
  maintain_by_category: boolean;
  no_seniority_condition: boolean;
```

par :

```ts
  differentiated_at_illness: boolean;
  no_seniority_condition: boolean;
```

`frontend/src/api/maintenanceSettings.ts` — remplacer :

```ts
  deduire_ijss_sans_subrogation: boolean;
  created_at: string | null;
```

par :

```ts
  deduire_ijss_sans_subrogation: boolean;
  /** Barème de la convention : null, les réglages manuels ; sinon les paliers du
   * barème, et les champs qu'il remplace disparaissent de l'écran. */
  bareme_convention: BaremeConvention | null;
  created_at: string | null;
```

`frontend/src/api/maintenanceSettings.ts` — insérer **avant** le bloc :

```ts
export async function saveMaintenanceSettings(
```

le code :

```ts
/** Un barème tel que l'écran le montre, construit par le serveur depuis le moteur. */
export interface BaremeLisible {
  code: BaremeConvention;
  libelle: string;
  sources: { titre: string; url: string }[];
  categories: {
    titre: string;
    lignes: { anciennete: string; paliers: string; limite: string }[];
    notes: string[];
  }[];
  regles: string[];
}

export async function getBaremesMaintien(): Promise<BaremeLisible[]> {
  const response = await apiClient.get<BaremeLisible[]>('/api/maintenance-settings/baremes');
  return response.data;
}
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — remplacer :

```tsx
import {
  getMaintenanceSettings,
  saveMaintenanceSettings,
  type MaintenanceSettings,
  type MaintenanceSettingsUpdate,
} from '@/api/maintenanceSettings';
```

par :

```tsx
import {
  getBaremesMaintien,
  getMaintenanceSettings,
  saveMaintenanceSettings,
  type BaremeLisible,
  type MaintenanceSettings,
  type MaintenanceSettingsUpdate,
} from '@/api/maintenanceSettings';
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — insérer **après** le bloc :

```tsx
} from './ijssSansSubrogation';
```

le code :

```tsx
import {
  AIDE_BAREME,
  CHOIX_BAREME,
  TEXTE_LEGAL_SOUS_BAREME,
  TEXTE_STATUT_CADRE,
  baremeModifie,
  champVisible,
  choixBaremeDepuisReglage,
  reglageDepuisChoixBareme,
  texteRegleParLeBareme,
} from './baremeConvention';

/** Le tableau du barème choisi, en lecture seule : ce que le moteur applique. */
function TableauDuBareme({ bareme }: { bareme: BaremeLisible }) {
  return (
    <div className="space-y-4 rounded-lg border p-4" data-testid="tableau-bareme">
      {bareme.categories.map((categorie) => (
        <div key={categorie.titre} className="space-y-2">
          <p className="font-medium">{categorie.titre}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="py-1 pr-4 font-normal">Ancienneté au début de l’arrêt</th>
                  <th className="py-1 pr-4 font-normal">Paliers</th>
                  <th className="py-1 font-normal">Limite par arrêt et par année civile</th>
                </tr>
              </thead>
              <tbody>
                {categorie.lignes.map((ligne) => (
                  <tr key={ligne.anciennete} className="border-t">
                    <td className="py-1 pr-4">{ligne.anciennete}</td>
                    <td className="py-1 pr-4">{ligne.paliers}</td>
                    <td className="py-1">{ligne.limite}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {categorie.notes.map((note) => (
            <p key={note} className="text-sm text-muted-foreground">
              {note}
            </p>
          ))}
        </div>
      ))}
      <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
        {bareme.regles.map((regle) => (
          <li key={regle}>{regle}</li>
        ))}
        <li>{TEXTE_STATUT_CADRE}</li>
      </ul>
      <p className="text-sm">
        Textes :{' '}
        {bareme.sources.map((source, i) => (
          <span key={source.url}>
            {i > 0 ? ' ; ' : null}
            <a className="underline" href={source.url} target="_blank" rel="noreferrer">
              {source.titre}
            </a>
          </span>
        ))}
      </p>
    </div>
  );
}
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — remplacer :

```tsx
    employer_waiting_days: form.employer_waiting_days,
    seniority_extension_enabled: form.seniority_extension_enabled,
    remove_employer_waiting: form.remove_employer_waiting,
```

par :

```tsx
    employer_waiting_days: form.employer_waiting_days,
    remove_employer_waiting: form.remove_employer_waiting,
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — remplacer :

```tsx
    differentiated_at_illness: form.differentiated_at_illness,
    maintain_by_category: form.maintain_by_category,
    no_seniority_condition: form.no_seniority_condition,
```

par :

```tsx
    differentiated_at_illness: form.differentiated_at_illness,
    no_seniority_condition: form.no_seniority_condition,
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — remplacer :

```tsx
    deduire_ijss_sans_subrogation: form.deduire_ijss_sans_subrogation,
  };
}
```

par :

```tsx
    deduire_ijss_sans_subrogation: form.deduire_ijss_sans_subrogation,
    bareme_convention: form.bareme_convention ?? null,
  };
}
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — insérer **avant** le bloc :

```tsx
  const [form, setForm] = useState<MaintenanceSettings | null>(null);
```

le code :

```tsx
  const { data: baremes } = useQuery({
    queryKey: ['maintenance-settings-baremes'],
    queryFn: getBaremesMaintien,
    enabled: Boolean(activeCompanyId),
    staleTime: Infinity,
  });
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — insérer **avant** le bloc :

```tsx
  const setNum = (key: keyof MaintenanceSettings, raw: string, optional = false) => {
```

le code :

```tsx
  const baremeChoisi = baremes?.find((b) => b.code === form.bareme_convention) ?? null;
  const libelleBareme =
    baremeChoisi?.libelle ??
    CHOIX_BAREME.find((c) => c.code === form.bareme_convention)?.libelle ??
    '';
  const visible = (cle: keyof MaintenanceSettings) => champVisible(cle, form);
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — remplacer :

```tsx
          <TabsContent value="legal" className="mt-4 space-y-6">
            <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
              <div>
                <Label htmlFor="apply_legal_maintenance">Appliquer le maintien légal</Label>
```

par :

```tsx
          <TabsContent value="legal" className="mt-4 space-y-6">
            {form.bareme_convention ? (
              <div className="rounded-lg border p-4 text-sm" role="note">
                <p className="font-medium">{texteRegleParLeBareme(libelleBareme)}</p>
                <p className="text-muted-foreground">{TEXTE_LEGAL_SOUS_BAREME}</p>
              </div>
            ) : null}
            {visible('apply_legal_maintenance') ? (
            <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
              <div>
                <Label htmlFor="apply_legal_maintenance">Appliquer le maintien légal</Label>
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — remplacer :

```tsx
                disabled={readOnly}
              />
            </div>
            <div className="grid gap-2 max-w-xs">
              <Label htmlFor="min_seniority_months">Ancienneté minimale maladie (mois)</Label>
```

par :

```tsx
                disabled={readOnly}
              />
            </div>
            ) : null}
            {visible('min_seniority_months') ? (
            <div className="grid gap-2 max-w-xs">
              <Label htmlFor="min_seniority_months">Ancienneté minimale maladie (mois)</Label>
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — remplacer :

```tsx
                onChange={(e) => setNum('min_seniority_months', e.target.value)}
                disabled={readOnly}
              />
            </div>
            <div className="grid gap-2 max-w-xs">
```

par :

```tsx
                onChange={(e) => setNum('min_seniority_months', e.target.value)}
                disabled={readOnly}
              />
            </div>
            ) : null}
            {visible('min_seniority_months_at_mp') ? (
            <div className="grid gap-2 max-w-xs">
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — remplacer :

```tsx
                onChange={(e) => setNum('min_seniority_months_at_mp', e.target.value)}
                disabled={readOnly}
              />
            </div>
            <div className="grid gap-2 max-w-xs">
```

par :

```tsx
                onChange={(e) => setNum('min_seniority_months_at_mp', e.target.value)}
                disabled={readOnly}
              />
            </div>
            ) : null}
            {visible('employer_waiting_days') ? (
            <div className="grid gap-2 max-w-xs">
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — remplacer :

```tsx
                disabled={readOnly || form.remove_employer_waiting}
              />
            </div>
            <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
              <div>
                <Label htmlFor="seniority_extension_enabled">Prolongation selon ancienneté</Label>
                <p className="text-sm text-muted-foreground">Allongement des droits lié à l’ancienneté.</p>
              </div>
              <Switch
                id="seniority_extension_enabled"
                checked={form.seniority_extension_enabled}
                onCheckedChange={(v) =>
                  setForm((p) => (p ? { ...p, seniority_extension_enabled: v } : p))
                }
                disabled={readOnly}
              />
            </div>
          </TabsContent>
```

par :

```tsx
                disabled={readOnly || form.remove_employer_waiting}
              />
            </div>
            ) : null}
          </TabsContent>
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — remplacer :

```tsx
          <TabsContent value="convention" className="mt-4 space-y-4">
            {[
              ['remove_employer_waiting', 'Supprimer la carence employeur'] as const,
              ['annual_unique_waiting', 'Carence annuelle unique'] as const,
              ['maintain_100_percent', 'Maintien à 100 %'] as const,
              ['differentiated_at_illness', 'Différenciation selon pathologie'] as const,
              ['maintain_by_category', 'Maintien par catégorie'] as const,
              ['no_seniority_condition', 'Sans condition d’ancienneté'] as const,
            ].map(([key, label]) => (
```

par :

```tsx
          <TabsContent value="convention" className="mt-4 space-y-4">
            <div className="grid gap-2 max-w-md">
              <Label id="bareme_convention">Barème de la convention</Label>
              <Select
                value={choixBaremeDepuisReglage(form.bareme_convention)}
                onValueChange={(v) => {
                  const code = reglageDepuisChoixBareme(v);
                  if (code === undefined) return;
                  setForm((p) => (p ? { ...p, bareme_convention: code } : p));
                }}
                disabled={readOnly}
              >
                <SelectTrigger aria-labelledby="bareme_convention">
                  <SelectValue placeholder="Choisir" />
                </SelectTrigger>
                <SelectContent>
                  {CHOIX_BAREME.map((choix) => (
                    <SelectItem key={choix.valeur} value={choix.valeur}>
                      {choix.libelle}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">{AIDE_BAREME}</p>
              {!readOnly && baremeModifie(form, data) ? (
                <div className="flex flex-wrap items-center gap-3" role="status">
                  <p className="text-sm font-medium text-amber-700 dark:text-amber-400">
                    Barème modifié, pas encore enregistré.
                  </p>
                  <Button
                    type="button"
                    size="sm"
                    onClick={handleSave}
                    disabled={mutation.isPending}
                  >
                    {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
                  </Button>
                </div>
              ) : null}
            </div>
            {form.bareme_convention ? (
              baremeChoisi ? (
                <TableauDuBareme bareme={baremeChoisi} />
              ) : (
                <p className="text-sm text-muted-foreground" role="status">
                  Chargement du barème…
                </p>
              )
            ) : null}
            {form.bareme_convention ? (
              <p className="text-sm font-medium">{texteRegleParLeBareme(libelleBareme)}</p>
            ) : null}
            {(
              [
                ['remove_employer_waiting', 'Supprimer la carence employeur'],
                ['annual_unique_waiting', 'Carence annuelle unique'],
                ['maintain_100_percent', 'Maintien à 100 %'],
                ['differentiated_at_illness', 'Différenciation selon pathologie'],
                ['no_seniority_condition', 'Sans condition d’ancienneté'],
              ] as const
            )
              .filter(([key]) => visible(key))
              .map(([key, label]) => (
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — insérer **avant** le bloc :

```tsx
            <div className="rounded-lg border p-4 space-y-3">
              <div>
                <Label htmlFor="paid_waiting_days_per_year">Carence payée par an (jours)</Label>
```

le code :

```tsx
            {visible('paid_waiting_days_per_year') ? (
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — insérer **après** le bloc :

```tsx
                    onChange={(e) => setNum('paid_waiting_min_seniority_months', e.target.value)}
                    disabled={readOnly}
                  />
                </div>
              </div>
            </div>
```

le code :

```tsx
            ) : null}
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — insérer **avant** le bloc :

```tsx
            <div className="grid gap-2 max-w-xs">
              <Label htmlFor="custom_duration_days">Durée personnalisée (jours, optionnel)</Label>
```

le code :

```tsx
            {visible('custom_duration_days') ? (
```

`frontend/src/features/company/components/MaintenanceSettingsCard.tsx` — remplacer :

```tsx
                onChange={(e) => setNum('custom_duration_days', e.target.value, true)}
                disabled={readOnly}
                placeholder="—"
              />
            </div>
          </TabsContent>
```

par :

```tsx
                onChange={(e) => setNum('custom_duration_days', e.target.value, true)}
                disabled={readOnly}
                placeholder="—"
              />
            </div>
            ) : null}
          </TabsContent>
```

- [ ] **Step 4 : les relancer, ils passent**

Run : `cd frontend && npx vitest run src/test/baremeConvention.test.ts src/test/ijssSansSubrogation.test.ts src/test/ijssAffichage.test.ts`
Expected : PASS — les trois fichiers passent (baremeConvention, ijssSansSubrogation, ijssAffichage)

Puis : `cd frontend && npm run typecheck && npx vitest run` → aucune erreur de type, tout vert.

- [ ] **Step 5 : commit**

```bash
git add frontend/src/api/maintenanceSettings.ts frontend/src/features/company/components/MaintenanceSettingsCard.tsx frontend/src/features/company/components/baremeConvention.ts frontend/src/test/baremeConvention.test.ts
git commit -m "feat(paie): la carte « Maintien de salaire » propose le barème de la plasturgie, masque ce qu'il remplace et retire les deux champs morts" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 9 : Le détail du maintien montre les paliers de la convention

**Files :**
- Create : `frontend/src/lib/paliersAffichage.ts`
- Modify : `frontend/src/api/absences.ts`, `frontend/src/components/payslip/MaintenanceDetailModal.tsx`, `frontend/src/components/absences/MaintenancePreviewBlock.tsx`
- Test : `frontend/src/test/paliersAffichage.test.ts`

**Interfaces :**
- Consumes (tâche 5) : `maintien.paliers`, `bareme_detail`, `regle_retenue`, `paliers_en_jours_ouvres`.
- Produces : `api/absences.ts` : `interface PalierDuMaintien`, champs optionnels du maintien ; `lib/paliersAffichage.ts` : `eurosFr`, `pourcentFr`, `ligneDuPalier(palier, enJoursOuvres)`, `titreDesPaliers(maintien)`, `lignesDesPaliers(maintien)`.

- [ ] **Step 1 : les tests, qui échouent**

Créer `frontend/src/test/paliersAffichage.test.ts` :

```ts
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import type { MaintenancePreview } from "@/api/absences";
import {
  eurosFr,
  ligneDuPalier,
  lignesDesPaliers,
  pourcentFr,
  titreDesPaliers,
} from "@/lib/paliersAffichage";

const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");

const JUILLET = {
  maintien_applicable: true,
  taux_maintien: 0.7425,
  maintien_cible: 1722.12,
  maintien_verse: 445.23,
  complement_employeur: 445.23,
  nb_jours_maintien: 23,
  conflit_convention: false,
  bareme: "plasturgie_0292",
  bareme_detail: "Plasturgie (IDCC 0292), non-cadres, 5 ans et plus",
  regle_retenue: "convention",
  paliers_en_jours_ouvres: true,
  paliers: [
    { taux: 1, du: "2026-07-01", au: "2026-07-02", jours: 2, garanti: 194.04, ijss_deduites: 82.38 },
    { taux: 0.75, du: "2026-07-03", au: "2026-07-31", jours: 21, garanti: 1528.08, ijss_deduites: 1194.51 },
  ],
} as MaintenancePreview["maintien"];

describe("Paliers de la convention au détail du maintien", () => {
  it("formate les montants et les taux comme le bulletin", () => {
    expect(eurosFr(1722.12)).toBe("1 722,12 €");
    expect(eurosFr(82.38)).toBe("82,38 €");
    expect([1, 0.75, 0.5, 0.9, 0.6667].map(pourcentFr)).toEqual([
      "100 %", "75 %", "50 %", "90 %", "66,67 %",
    ]);
  });

  it("une ligne par palier, avec ses IJSS déduites", () => {
    expect(lignesDesPaliers(JUILLET)).toEqual([
      "Du 01/07 au 02/07 : 2 jours ouvrés à 100 % — 194,04 € (IJSS déduites 82,38 €)",
      "Du 03/07 au 31/07 : 21 jours ouvrés à 75 % — 1 528,08 € (IJSS déduites 1 194,51 €)",
    ]);
    expect(
      ligneDuPalier({ taux: 1, du: "2026-05-04", au: "2026-05-04", jours: 1, garanti: 102.99 }, false),
    ).toBe("Du 04/05 au 04/05 : 1 jour à 100 % — 102,99 €");
  });

  it("le titre dit le barème, ou le légal quand il l'emporte, et rien sans barème", () => {
    expect(titreDesPaliers(JUILLET)).toBe("Plasturgie (IDCC 0292), non-cadres, 5 ans et plus");
    expect(titreDesPaliers({ ...JUILLET, regle_retenue: "legal" })).toBe(
      "Maintien légal, plus favorable ce mois-ci que le barème",
    );
    const { paliers: _p, bareme_detail: _d, ...sans } = JUILLET;
    expect(titreDesPaliers(sans as MaintenancePreview["maintien"])).toBeNull();
    expect(lignesDesPaliers(sans as MaintenancePreview["maintien"])).toEqual([]);
  });

  it("le détail du bulletin et l'aperçu de l'absence montrent la section", () => {
    const modal = lire("components/payslip/MaintenanceDetailModal.tsx");
    expect(modal).toContain("Paliers de la convention");
    expect(modal).toContain("lignesDesPaliers(m).map");
    const apercu = lire("components/absences/MaintenancePreviewBlock.tsx");
    expect(apercu).toContain("lignesDesPaliers(maintien).map");
  });
});
```

- [ ] **Step 2 : les lancer, ils échouent**

Run : `cd frontend && npx vitest run src/test/paliersAffichage.test.ts`
Expected : FAIL — Error: Cannot find module '@/lib/paliersAffichage'

- [ ] **Step 3 : le code**

Créer `frontend/src/lib/paliersAffichage.ts` :

```ts
/**
 * Les paliers du maintien sous le barème de la convention, tels que le détail
 * du bulletin et l'aperçu de l'absence les montrent (conception du 24/10/2026).
 *
 * Le calcul est fait par le serveur : ces textes disent seulement les paliers
 * qu'il a posés. Sans barème, il n'y en a pas, et rien ne s'affiche.
 */
import type { MaintenancePreview, PalierDuMaintien } from '@/api/absences';
import { pluriel } from '@/lib/pluriel';

export function eurosFr(n: number): string {
  const [entier, decimales] = Math.abs(n).toFixed(2).split('.');
  const groupes = entier.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return `${n < 0 ? '-' : ''}${groupes},${decimales} €`;
}

export function pourcentFr(taux: number): string {
  const valeur = Math.round(taux * 10000) / 100;
  return Number.isInteger(valeur) ? `${valeur} %` : `${valeur.toFixed(2).replace('.', ',')} %`;
}

function dateFr(iso: string): string {
  const [, mois, jour] = iso.split('-');
  return `${jour}/${mois}`;
}

function joursDuPalier(n: number, ouvres: boolean): string {
  return ouvres ? pluriel(n, 'jour ouvré', 'jours ouvrés') : pluriel(n, 'jour');
}

/** « Du 01/07 au 02/07 : 2 jours ouvrés à 100 % — 194,04 € (IJSS déduites 82,38 €) ». */
export function ligneDuPalier(palier: PalierDuMaintien, enJoursOuvres: boolean): string {
  const texte =
    `Du ${dateFr(palier.du)} au ${dateFr(palier.au)} : ` +
    `${joursDuPalier(palier.jours, enJoursOuvres)} à ${pourcentFr(palier.taux)} — ${eurosFr(palier.garanti)}`;
  return palier.ijss_deduites ? `${texte} (IJSS déduites ${eurosFr(palier.ijss_deduites)})` : texte;
}

/** Le titre de la section, ou null sans barème. */
export function titreDesPaliers(maintien: MaintenancePreview['maintien']): string | null {
  if (!maintien.paliers || !maintien.bareme_detail) return null;
  return maintien.regle_retenue === 'legal'
    ? 'Maintien légal, plus favorable ce mois-ci que le barème'
    : maintien.bareme_detail;
}

export function lignesDesPaliers(maintien: MaintenancePreview['maintien']): string[] {
  return (maintien.paliers ?? []).map((p) => ligneDuPalier(p, Boolean(maintien.paliers_en_jours_ouvres)));
}
```

`frontend/src/api/absences.ts` — insérer **avant** le bloc :

```ts
export interface MaintenancePreview {
  qualification: {
```

le code :

```ts
/** Un palier du mois sous le barème de la convention (conception du 24/10/2026). */
export interface PalierDuMaintien {
  taux: number;
  du: string;
  au: string;
  jours: number;
  jours_calendaires?: number;
  valeur?: number;
  garanti: number;
  ijss_deduites?: number;
}
```

`frontend/src/api/absences.ts` — remplacer :

```ts
    duree_par_taux_jours?: number;
    duree_maintien_legale_jours?: number;
  };
  prevoyance: {
```

par :

```ts
    duree_par_taux_jours?: number;
    duree_maintien_legale_jours?: number;
    /** Sous un barème seulement. */
    bareme?: string;
    bareme_detail?: string;
    regle_retenue?: 'convention' | 'legal';
    paliers?: PalierDuMaintien[];
    paliers_en_jours_ouvres?: boolean;
  };
  prevoyance: {
```

`frontend/src/components/payslip/MaintenanceDetailModal.tsx` — insérer **après** le bloc :

```tsx
import { libelleIjssDuDetail } from '@/lib/ijssAffichage';
```

le code :

```tsx
import { lignesDesPaliers, titreDesPaliers } from '@/lib/paliersAffichage';
```

`frontend/src/components/payslip/MaintenanceDetailModal.tsx` — remplacer :

```tsx
  const m = maintien.maintien;

  return (
```

par :

```tsx
  const m = maintien.maintien;
  const titrePaliers = titreDesPaliers(m);

  return (
```

`frontend/src/components/payslip/MaintenanceDetailModal.tsx` — insérer **avant** le bloc :

```tsx
          {maintien.prevoyance &&
          (maintien.prevoyance.prevoyance_declenchee ||
```

le code :

```tsx
          {titrePaliers ? (
            <section className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Paliers de la convention
              </h3>
              <p className="font-medium">{titrePaliers}</p>
              <ul className="space-y-1">
                {lignesDesPaliers(m).map((ligne) => (
                  <li key={ligne}>{ligne}</li>
                ))}
              </ul>
            </section>
          ) : null}
```

`frontend/src/components/absences/MaintenancePreviewBlock.tsx` — insérer **après** le bloc :

```tsx
import { libelleIjssDuDetail, texteDeductionDuPliant } from '@/lib/ijssAffichage';
```

le code :

```tsx
import { lignesDesPaliers, titreDesPaliers } from '@/lib/paliersAffichage';
```

`frontend/src/components/absences/MaintenancePreviewBlock.tsx` — insérer **après** le bloc :

```tsx
  const maintien = data.maintien;
```

le code :

```tsx
  const titrePaliers = titreDesPaliers(maintien);
```

`frontend/src/components/absences/MaintenancePreviewBlock.tsx` — remplacer :

```tsx
            <p>
              Complément employeur :{" "}
              {eur(maintien.complement_employeur ?? 0)}
            </p>
          </>
        )}
      </section>
```

par :

```tsx
            <p>
              Complément employeur :{" "}
              {eur(maintien.complement_employeur ?? 0)}
            </p>
            {titrePaliers ? (
              <div className="space-y-1">
                <p className="font-medium">{titrePaliers}</p>
                <ul className="space-y-1">
                  {lignesDesPaliers(maintien).map((ligne) => (
                    <li key={ligne}>{ligne}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        )}
      </section>
```

- [ ] **Step 4 : les relancer, ils passent**

Run : `cd frontend && npx vitest run src/test/paliersAffichage.test.ts`
Expected : PASS — 4 passed

Puis : `cd frontend && npm run typecheck && npx vitest run` → aucune erreur de type, tout vert.

- [ ] **Step 5 : commit**

```bash
git add frontend/src/api/absences.ts frontend/src/components/absences/MaintenancePreviewBlock.tsx frontend/src/components/payslip/MaintenanceDetailModal.tsx frontend/src/lib/paliersAffichage.ts frontend/src/test/paliersAffichage.test.ts
git commit -m "feat(paie): le détail du maintien et l'aperçu de l'absence montrent les paliers de la convention" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

## Vérifications finales (sans commit)

Rien de ce qui suit n'écrit dans le dépôt, en base ni sur le site.

- [ ] **1. Les suites complètes**

```bash
cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit -q
cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/integration/legacy -q
cd frontend && npm run typecheck && npx vitest run
cd frontend && npx eslint src/features/company/components/MaintenanceSettingsCard.tsx src/features/company/components/baremeConvention.ts src/lib/paliersAffichage.ts src/components/payslip/MaintenanceDetailModal.tsx src/components/absences/MaintenancePreviewBlock.tsx src/test/baremeConvention.test.ts src/test/paliersAffichage.test.ts
cd backend && /Users/alex/dev/EYWAI/backend/.venv/bin/ruff check --no-cache --select F app/modules/payroll/domain/baremes_maintien.py app/modules/payroll/domain/paliers_affiches.py app/modules/payroll/engine/paliers_convention.py app/modules/payroll/engine/maintien_salaire_service.py app/modules/maintenance_settings tests/unit/payroll/test_baremes_maintien.py tests/unit/payroll/test_paliers_convention.py tests/unit/payroll/test_maintien_paliers_valeur.py tests/unit/payroll/test_maintien_paliers_bareme.py tests/unit/payroll/test_maintien_paliers_lecteurs.py tests/unit/payroll/test_paliers_au_bulletin.py tests/unit/maintenance_settings/test_bareme_convention.py
```

Expected :
- `tests/unit` : tout vert ;
- `tests/integration/legacy` : les 24 échecs de référence, pas un de plus ;
- front : typecheck propre, vitest tout vert, eslint muet ;
- ruff : « All checks passed! ».

- [ ] **2. Le filet au centime** (`~/dev/eywai-filet`, lecture seule, piège à écritures)

Avant et après, le même jour : la vraie paie bouge sur la base de test.

```bash
~/dev/eywai-filet/lancer.sh ~/dev/eywai-filet/paliers-avant 531773b8
~/dev/eywai-filet/lancer.sh ~/dev/eywai-filet/paliers-apres "$(git rev-parse --short HEAD)"
cd ~/dev/eywai-filet && /Users/alex/dev/EYWAI/backend/.venv/bin/python comparer5.py "paliers-avant/apres_*.json" "paliers-apres/apres_*.json"
```

Expected : « Bulletins avec écart : 0 », « Cumuls avec écart : 0 », et les mêmes erreurs connues des deux côtés. Aucune société n'a de barème : rien ne doit bouger. Un écart arrête le chantier ; on l'explique avant toute autre chose.

- [ ] **3. Le bac à sable de Comitech, barème posé en mémoire**

Créer `~/dev/eywai-filet/paliers_comitech.py`, hors dépôt :

```python
"""Bac à sable, lecture seule : Comitech avec le barème de la plasturgie posé en mémoire.

Usage, depuis backend/ du worktree, après la tâche 9 :
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/alex/dev/EYWAI/backend/.venv/bin/python -B \
    ~/dev/eywai-filet/paliers_comitech.py ~/dev/eywai-filet/paliers-comitech.json

Aucune écriture : piège posé avant l'import de l'application, puis interception
du filet (toute requête qui n'est pas une lecture est refusée). Le barème est
posé dans la mémoire du processus, jamais en base. Sortie en initiales.
"""
import json
import sys

from dotenv import load_dotenv

load_dotenv("/Users/alex/dev/EYWAI/backend/.env")
from scripts.verification_rgdu import piege  # noqa: E402

piege.poser_le_piege()
from scripts import filet_paie as f  # noqa: E402

SORTIE = sys.argv[1]
CO = "12cd8c71-da13-43f9-9151-475c4d5e8812"  # Comitech
ENTREES = {"2003-07-15": "S.G.", "2003-09-01": "D.S.", "2026-05-04": "T.L.", "2025-05-28": "D.J."}
GROUPES = {
    "S.G.": [[5], [6], [7], [8], [9, 10]],
    "D.S.": [[4], [5], [6], [7], [8]],
    "T.L.": [[6], [7], [8], [9, 10]],
    "D.J.": [[5]],
}
REGLAGES = {"bareme_convention": "plasturgie_0292", "deduire_ijss_sans_subrogation": True}
#: Maintien de Quadra par mois d'arrêt (relevé du 24/10, rappels compris).
QUADRA = {"S.G. 05": 1030.09, "S.G. 06": 995.78, "S.G. 07": 715.94, "S.G. 08": 0.0,
          "S.G. 09": 0.0, "D.S. 04": 668.77, "D.S. 05": 2549.28, "D.J. 05": 0.0}

with f.Interception("photo"):
    import app.modules.maintenance_settings.application.queries as q
    from app.core.database import supabase

    origine = q.get_maintenance_settings

    def simule(company_id):
        s = origine(company_id)
        return s.model_copy(update=REGLAGES) if str(company_id) == CO else s

    q.get_maintenance_settings = simule
    emps = supabase.table("employees").select("id,hire_date").eq("company_id", CO).execute().data
    ids = {ENTREES[str(e["hire_date"])]: e["id"] for e in emps if str(e.get("hire_date")) in ENTREES}
    out = {}
    for ini, groupes in GROUPES.items():
        for groupe in groupes:
            r = f._calculer([{"employee_id": ids[ini], "year": 2026, "month": m} for m in groupe])
            for m in groupe:
                v = r.get(f"{ids[ini]}/2026-{m:02d}", {})
                bloc = (v.get("payslip_data") or {}).get("bloc_maintien") or {}
                mt = bloc.get("maintien") or {}
                out[f"{ini} {m:02d}"] = {"erreur": v["erreur"][:300]} if v.get("erreur") else {
                    "verse": mt.get("maintien_verse"),
                    "cible": mt.get("maintien_cible"),
                    "ijss_deduites": mt.get("ijss_deduites"),
                    "regle": mt.get("regle_retenue"),
                    "paliers": [(p["taux"], p["du"], p["au"], p["jours"]) for p in mt.get("paliers") or []],
                    "alertes": bloc.get("alertes"),
                }

json.dump({"reglages": REGLAGES, "ecritures_piegees": piege.ECRITURES, "resultats": out},
          open(SORTIE, "w"), ensure_ascii=False, indent=1, default=str)
for cle, v in sorted(out.items()):
    print(f"{cle} : Martine {v.get('verse')} / Quadra {QUADRA.get(cle, 'n/a')} "
          f"({v.get('regle')}) {v.get('paliers') or v.get('erreur', '')}")
print("écritures piégées :", piege.ECRITURES)
```

Run, depuis `backend/` du worktree :

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/alex/dev/EYWAI/backend/.venv/bin/python -B ~/dev/eywai-filet/paliers_comitech.py ~/dev/eywai-filet/paliers-comitech.json
```

**Attendu.** Les IJ sont celles qu'estime Martine (41,9547 €/jour), tant qu'aucun montant n'est validé au suivi IJSS. Quadra en a relevé 41,19 pour S.G. et 41,95 pour D.S. L'écart avec la conception tient donc aux seules IJ.

| Mois | Martine attendu | Règle | Quadra |
|---|---|---|---|
| S.G. 05 | ≈ 1 010,97 | barème, 100 % | 1 030,09 |
| S.G. 06 | ≈ 972,84 | barème, salaire du mois | 995,78 |
| S.G. 07 | ≈ 481,35 | légal (90 % jusqu'au 19/07, puis 66,67 %) | 715,94 |
| S.G. 08 | ≈ 373,01 | barème, 75 % | 0 |
| S.G. 09 | ≈ 207,49, alerte « limite de 135 jours atteinte le 15/09/2026 » | barème | 0 |
| S.G. 10 | 0 | limite atteinte | — |
| D.S. 04 | 668,77 | barème, cadres, 10 ans et plus | 668,77 |
| D.S. 05 | ≈ 2 549,13 | barème, salaire du mois | 2 549,28 |
| D.S. 06 et 07 | ≈ 2 591,09 et ≈ 2 107,43 | barème | 1 919,99 + 1 652,41 + 510,85 |
| T.L. | 0, « un an d'ancienneté requis » | — | 0 |
| D.J. 05 | un maintien d'accident du travail, sans condition d'ancienneté | barème | 0 |

Les seules écritures piégées admises sont `update employee_cp_seniority_grants`, déjà vues le 24/10 et refusées par le piège. Un écart qui ne vient pas des IJ s'explique avant la suite. Les initiales seules sortent du script ; le fichier JSON reste dans `~/dev/eywai-filet`.

- [ ] **4. S'arrêter et rendre compte à Alexandre**

Rendre :
- le résultat du filet ;
- le tableau du bac à sable ;
- les questions du §7 de la conception, pour la personne qui fait la paie Comitech.

Pas de push, pas de migration, pas de déploiement.

## Après le plan (hors exécution, sur accord d'Alexandre)

- Pousser la branche, attendre la CI.
- Appliquer la migration `20261024120000_bareme_convention_maintien.sql` sur la base de test **avant** le code (option `migration` du workflow). Puis déployer : `gh workflow run deploy-test-env.yml --ref feat/maintien-paliers-convention`.
- Sur le site de test, vérifier la carte :
  - le choix du barème et son tableau ;
  - les champs masqués ;
  - l'enregistrement et le rappel « Barème modifié, pas encore enregistré » ;
  - le détail des paliers sur un personnage de MAJI, puis tout ranger.
- Choisir le barème chez Comitech à l'écran, avec Alexandre, après les réponses aux questions du §7. Jamais chez Colorplast sans la réponse de Gaëlle.
