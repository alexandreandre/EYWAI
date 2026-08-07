# Export « provision congés payés » — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer un 24ᵉ type d'export, `provision_cp`, qui valorise en euros la dette de
congés payés d'une société à une date d'arrêté, au format de l'état Cegid qu'Elsa a
envoyé le 27/07/2026.

**Architecture:** Un module de domaine pur (aucun accès base) porte les quatre formules
et le choix de la période de référence ; un module d'infrastructure lit les soldes,
les bulletins et les salariés puis appelle le domaine ; le câblage suit à l'identique
celui des 23 exports existants (six points backend, trois points frontend). Aucune
migration, aucun changement du contrat d'API.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Supabase (postgrest-py), openpyxl,
pytest, React + TypeScript.

## Constat vérifié (à ne pas re-débattre)

Spec complète : [2026-08-07-provision-cp-design.md](../specs/2026-08-07-provision-cp-design.md).

1. Le fichier modèle est `data/_inbox/whatsapp-elsa/00000595-PROVISION CP.pdf` (identique
   à `00000604`), envoyé par Elsa le 27/07/2026 avec « doc provision CP à mettre en
   export » (`data/_inbox/whatsapp-elsa/_chat.txt:8963-8964`). CARTOL, 71 salariés,
   total 394 121,22 €.
2. Les quatre formules sont vérifiées sur **71/71 lignes** :
   `solde jours = N-1 + N` · `provision = solde jours × salaire_ref ÷ 22` ·
   `charges = provision × taux ÷ 100` · `total = provision + charges`.
   Diviseur médian mesuré : 22,0000.
3. Le taux de charges est `cotisations patronales ÷ brut` par salarié. Recalculé sur nos
   bulletins il tombe à 0,1–0,25 pt du modèle pour les paies stables (De Carvalho 32,14 /
   32,12 · Vignaud 38,38 / 38,50 · Veillat 24,70 / 24,57).
4. Le salaire de référence est le brut mensuel moyen sur la période d'acquisition. Il ne
   sera **pas** reproductible au centime avant juin 2027 : EYWAI n'a pas de paie avant
   janvier 2026, et tous les écarts constatés sont des cas d'absence longue en 2025.
   → Aucun test n'asserte l'égalité avec le PDF. On mesure et on consigne.
5. Les soldes existent déjà :
   [rules.py:609](backend/app/modules/absences/domain/rules.py#L609)
   `compute_cp_balances_for_bulletin(...)` renvoie `{"periode_courante": {...},
   "periode_precedente": {...}}`, chaque entrée portant une clé `solde` en jours
   **ouvrables**. La conversion en ouvrés est
   [fractionnement.py:30](backend/app/modules/absences/domain/fractionnement.py#L30)
   `ouvrables_to_ouvres(ouvrables, ratio)`.
6. Les données de paie sont dans `payslips.payslip_data` :
   `salaire_brut` (float) et `cotisations_officielles` (liste d'objets portant
   `total_patronal` et `total_salarial`).
7. Le câblage d'un export se fait en six points, identiques pour les 23 existants :
   `domain/value_objects.py` (2 frozensets) · `schemas/requests.py` (le `Literal`) ·
   `application/queries.py` (branche preview) · `application/service.py` (branche
   generate + fonction `_generate_*`) · `infrastructure/providers.py` (2 ré-exports) ·
   `infrastructure/export_*.py` (le module).

## Global Constraints

- Français dans tout le code visible (libellés de colonnes, messages d'anomalie).
- **Aucune exception avalée.** Le défaut corrigé sur les exports CSE (#12) venait d'un
  `try/except` silencieux. Interdit ici.
- Aucun salarié exclu silencieusement : une donnée manquante produit une ligne avec la
  colonne « Anomalie » remplie, jamais une disparition.
- Montants arrondis au centime (`round(x, 2)`), jours arrondis au centième.
- Aucune migration de base, aucun réglage nouveau : le diviseur (22) et la fenêtre
  (12 mois) sont des constantes du domaine, passées en arguments par défaut.
- Le module `domain/provision_cp.py` ne doit importer ni `supabase`, ni FastAPI, ni
  aucun module `infrastructure`. C'est ce qui rend les tests exacts possibles.
- Tests : `pytestmark = pytest.mark.unit`, dans `backend/tests/unit/exports/`.
- Lancement des tests depuis `backend/` avec `./venv/bin/python -m pytest`.

---

### Task 1 : les quatre formules, dans un domaine pur

**Files:**
- Create: `backend/app/modules/exports/domain/provision_cp.py`
- Test: `backend/tests/unit/exports/test_provision_cp_domain.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `DIVISEUR_MENSUALISATION: float = 22.0`
  - `FENETRE_REFERENCE_MOIS: int = 12`
  - `@dataclass(frozen=True) LigneProvision` avec les champs
    `matricule: str`, `nom: str`, `date_entree: str`, `solde_n1: float`,
    `solde_n: float`, `solde_jours: float`, `salaire_reference: float`,
    `taux_charges: float`, `montant_charges: float`, `provision: float`,
    `total: float`, `mois_retenus: str`, `anomalie: str`
  - `calculer_ligne(matricule, nom, date_entree, solde_n1, solde_n, salaire_reference, taux_charges, mois_retenus, anomalie="", diviseur=DIVISEUR_MENSUALISATION) -> LigneProvision`
  - `calculer_totaux(lignes: list[LigneProvision]) -> dict[str, float]`

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/exports/test_provision_cp_domain.py`. Les trois premiers cas
sont des lignes réelles du PDF Cegid, reprises au centime.

```python
"""Tests des formules de provision CP — valeurs réelles de l'état Cegid CARTOL du 21/07/2026."""

import pytest

from app.modules.exports.domain import provision_cp as module

pytestmark = pytest.mark.unit


class TestCalculerLigne:
    def test_bertaud_ligne_reelle_du_modele_cegid(self):
        ligne = module.calculer_ligne(
            matricule="BERTAUD",
            nom="SYLVAIN BERTAUD",
            date_entree="2010-03-01",
            solde_n1=28.00,
            solde_n=4.16,
            salaire_reference=2640.86,
            taux_charges=25.74,
            mois_retenus="12/12",
        )
        assert ligne.solde_jours == 32.16
        assert ligne.provision == 3860.46
        assert ligne.montant_charges == 993.68
        assert ligne.total == 4854.14

    def test_blin_ligne_reelle_du_modele_cegid(self):
        ligne = module.calculer_ligne(
            matricule="BLIN",
            nom="Fabien BLIN",
            date_entree="2022-09-05",
            solde_n1=3.00,
            solde_n=4.16,
            salaire_reference=2978.39,
            taux_charges=36.33,
            mois_retenus="12/12",
        )
        assert ligne.solde_jours == 7.16
        assert ligne.provision == 969.33
        assert ligne.montant_charges == 352.16
        assert ligne.total == 1321.49

    def test_faucher_ligne_reelle_du_modele_cegid(self):
        ligne = module.calculer_ligne(
            matricule="FAUCHER",
            nom="DAMIEN FAUCHER",
            date_entree="2015-01-05",
            solde_n1=27.00,
            solde_n=4.16,
            salaire_reference=12797.15,
            taux_charges=48.92,
            mois_retenus="12/12",
        )
        assert ligne.solde_jours == 31.16
        assert ligne.provision == 18125.42
        assert ligne.montant_charges == 8866.96
        assert ligne.total == 26992.38

    def test_diviseur_non_standard(self):
        ligne = module.calculer_ligne(
            matricule="X",
            nom="X",
            date_entree="2020-01-01",
            solde_n1=20.0,
            solde_n=0.0,
            salaire_reference=2200.0,
            taux_charges=0.0,
            mois_retenus="12/12",
            diviseur=21.67,
        )
        assert ligne.provision == round(20.0 * 2200.0 / 21.67, 2)

    def test_solde_negatif_donne_une_provision_negative(self):
        ligne = module.calculer_ligne(
            matricule="X",
            nom="X",
            date_entree="2026-01-01",
            solde_n1=0.0,
            solde_n=-2.08,
            salaire_reference=2200.0,
            taux_charges=30.0,
            mois_retenus="6/12",
        )
        assert ligne.solde_jours == -2.08
        assert ligne.provision < 0
        assert ligne.total < 0

    def test_anomalie_conservee_telle_quelle(self):
        ligne = module.calculer_ligne(
            matricule="X",
            nom="X",
            date_entree="2026-05-01",
            solde_n1=0.0,
            solde_n=2.08,
            salaire_reference=1800.0,
            taux_charges=30.0,
            mois_retenus="0/12",
            anomalie="aucun bulletin",
        )
        assert ligne.anomalie == "aucun bulletin"


class TestCalculerTotaux:
    def test_totaux_et_taux_moyen_pondere(self):
        lignes = [
            module.calculer_ligne("A", "A", "2020-01-01", 10.0, 2.0, 2000.0, 20.0, "12/12"),
            module.calculer_ligne("B", "B", "2020-01-01", 20.0, 2.0, 3000.0, 40.0, "12/12"),
        ]
        totaux = module.calculer_totaux(lignes)

        assert totaux["solde_n1"] == 30.0
        assert totaux["solde_n"] == 4.0
        assert totaux["solde_jours"] == 34.0
        assert totaux["provision"] == round(sum(l.provision for l in lignes), 2)
        assert totaux["montant_charges"] == round(sum(l.montant_charges for l in lignes), 2)
        assert totaux["total"] == round(totaux["provision"] + totaux["montant_charges"], 2)
        # taux moyen = charges totales / provision totale, jamais la moyenne des taux
        assert totaux["taux_charges"] == round(
            totaux["montant_charges"] / totaux["provision"] * 100, 2
        )

    def test_totaux_sur_liste_vide(self):
        totaux = module.calculer_totaux([])
        assert totaux["provision"] == 0.0
        assert totaux["taux_charges"] == 0.0
```

- [ ] **Step 2 : lancer le test, vérifier qu'il échoue**

```bash
cd backend && ./venv/bin/python -m pytest tests/unit/exports/test_provision_cp_domain.py -v
```

Attendu : `ModuleNotFoundError: No module named 'app.modules.exports.domain.provision_cp'`.

- [ ] **Step 3 : écrire le domaine**

Créer `backend/app/modules/exports/domain/provision_cp.py` :

```python
# Formules de l'état de provision des congés payés.
# Domaine pur : aucun accès base, aucune dépendance FastAPI.
# Les quatre formules reproduisent l'état Cegid « État de provision des congés payés »,
# vérifiées sur les 71 lignes du modèle CARTOL du 21/07/2026.
from __future__ import annotations

from dataclasses import dataclass

# Jours ouvrés moyens d'un mois, convention du cabinet. Ce n'est pas une règle légale :
# la règle légale est le maximum entre maintien de salaire et 1/10e de la rémunération
# de la période de référence. On reproduit le modèle demandé.
DIVISEUR_MENSUALISATION: float = 22.0

# Fenêtre du salaire de référence et du taux de charges.
FENETRE_REFERENCE_MOIS: int = 12


@dataclass(frozen=True)
class LigneProvision:
    matricule: str
    nom: str
    date_entree: str
    solde_n1: float
    solde_n: float
    solde_jours: float
    salaire_reference: float
    taux_charges: float
    montant_charges: float
    provision: float
    total: float
    mois_retenus: str
    anomalie: str


def calculer_ligne(
    matricule: str,
    nom: str,
    date_entree: str,
    solde_n1: float,
    solde_n: float,
    salaire_reference: float,
    taux_charges: float,
    mois_retenus: str,
    anomalie: str = "",
    diviseur: float = DIVISEUR_MENSUALISATION,
) -> LigneProvision:
    """Une ligne de l'état, à partir de données déjà résolues.

    solde_n1 / solde_n sont en jours ouvrés. taux_charges est en pourcentage (25.74),
    pas en fraction.
    """
    if diviseur <= 0:
        raise ValueError(f"Diviseur de mensualisation invalide : {diviseur}")

    solde_jours = round(solde_n1 + solde_n, 2)
    provision = round(solde_jours * salaire_reference / diviseur, 2)
    montant_charges = round(provision * taux_charges / 100, 2)
    total = round(provision + montant_charges, 2)

    return LigneProvision(
        matricule=matricule,
        nom=nom,
        date_entree=date_entree,
        solde_n1=round(solde_n1, 2),
        solde_n=round(solde_n, 2),
        solde_jours=solde_jours,
        salaire_reference=round(salaire_reference, 2),
        taux_charges=round(taux_charges, 2),
        montant_charges=montant_charges,
        provision=provision,
        total=total,
        mois_retenus=mois_retenus,
        anomalie=anomalie,
    )


def calculer_totaux(lignes: list[LigneProvision]) -> dict[str, float]:
    """Ligne « Total » de l'état. Le taux est pondéré, jamais une moyenne de taux."""
    provision = round(sum(l.provision for l in lignes), 2)
    montant_charges = round(sum(l.montant_charges for l in lignes), 2)
    return {
        "solde_n1": round(sum(l.solde_n1 for l in lignes), 2),
        "solde_n": round(sum(l.solde_n for l in lignes), 2),
        "solde_jours": round(sum(l.solde_jours for l in lignes), 2),
        "salaire_reference": round(sum(l.salaire_reference for l in lignes), 2),
        "taux_charges": round(montant_charges / provision * 100, 2) if provision else 0.0,
        "montant_charges": montant_charges,
        "provision": provision,
        "total": round(provision + montant_charges, 2),
    }
```

- [ ] **Step 4 : lancer les tests, vérifier qu'ils passent**

```bash
cd backend && ./venv/bin/python -m pytest tests/unit/exports/test_provision_cp_domain.py -v
```

Attendu : 8 passed. Si `test_faucher_ligne_reelle_du_modele_cegid` échoue au centime,
**ne pas ajuster la tolérance** : le diviseur ou l'ordre des arrondis est faux.

- [ ] **Step 5 : commit**

```bash
git add backend/app/modules/exports/domain/provision_cp.py backend/tests/unit/exports/test_provision_cp_domain.py
git commit -m "feat(exports): formules de provision congés payés, vérifiées sur le modèle Cegid"
```

---

### Task 2 : période de référence, salaire moyen et taux de charges

**Files:**
- Modify: `backend/app/modules/exports/domain/provision_cp.py`
- Modify: `backend/tests/unit/exports/test_provision_cp_domain.py`

**Interfaces:**
- Consumes: Task 1 (`FENETRE_REFERENCE_MOIS`).
- Produces:
  - `mois_de_reference(annee: int, mois: int, fenetre: int = FENETRE_REFERENCE_MOIS) -> list[tuple[int, int]]`
    — les `fenetre` couples `(année, mois)` se terminant au mois donné inclus, du plus
    ancien au plus récent.
  - `@dataclass(frozen=True) Reference` avec `salaire_reference: float`,
    `taux_charges: float`, `mois_retenus: str`, `anomalie: str`
  - `resoudre_reference(bulletins: dict[tuple[int, int], tuple[float, float]], mois_cibles: list[tuple[int, int]], salaire_contractuel: float | None, taux_societe: float | None) -> Reference`
    — `bulletins` associe `(année, mois)` à `(brut, cotisations patronales)`.

- [ ] **Step 1 : écrire le test qui échoue**

Ajouter à `backend/tests/unit/exports/test_provision_cp_domain.py` :

```python
class TestMoisDeReference:
    def test_douze_mois_a_cheval_sur_deux_annees(self):
        mois = module.mois_de_reference(2026, 7)
        assert len(mois) == 12
        assert mois[0] == (2025, 8)
        assert mois[-1] == (2026, 7)

    def test_fenetre_reduite(self):
        assert module.mois_de_reference(2026, 3, fenetre=4) == [
            (2025, 12),
            (2026, 1),
            (2026, 2),
            (2026, 3),
        ]


class TestResoudreReference:
    def test_moyenne_sur_les_mois_presents(self):
        bulletins = {(2026, m): (2000.0 + m, 600.0) for m in range(1, 7)}
        ref = module.resoudre_reference(
            bulletins=bulletins,
            mois_cibles=module.mois_de_reference(2026, 6),
            salaire_contractuel=1900.0,
            taux_societe=35.0,
        )
        attendu = sum(2000.0 + m for m in range(1, 7)) / 6
        assert ref.salaire_reference == round(attendu, 2)
        assert ref.taux_charges == round(600.0 * 6 / (attendu * 6) * 100, 2)
        assert ref.mois_retenus == "6/12"
        assert ref.anomalie == ""

    def test_mois_a_brut_nul_ignore(self):
        bulletins = {(2026, 1): (2000.0, 600.0), (2026, 2): (0.0, 0.0)}
        ref = module.resoudre_reference(
            bulletins=bulletins,
            mois_cibles=module.mois_de_reference(2026, 2),
            salaire_contractuel=1900.0,
            taux_societe=35.0,
        )
        assert ref.salaire_reference == 2000.0
        assert ref.mois_retenus == "1/12"

    def test_aucun_bulletin_repli_sur_le_contractuel(self):
        ref = module.resoudre_reference(
            bulletins={},
            mois_cibles=module.mois_de_reference(2026, 6),
            salaire_contractuel=1900.0,
            taux_societe=35.0,
        )
        assert ref.salaire_reference == 1900.0
        assert ref.taux_charges == 35.0
        assert ref.mois_retenus == "0/12"
        assert ref.anomalie == "aucun bulletin : salaire contractuel et taux société utilisés"

    def test_aucun_bulletin_et_aucun_contractuel(self):
        ref = module.resoudre_reference(
            bulletins={},
            mois_cibles=module.mois_de_reference(2026, 6),
            salaire_contractuel=None,
            taux_societe=None,
        )
        assert ref.salaire_reference == 0.0
        assert ref.taux_charges == 0.0
        assert ref.anomalie == "aucun bulletin et aucun salaire contractuel"

    def test_bulletin_hors_fenetre_ignore(self):
        bulletins = {(2024, 3): (9999.0, 9999.0), (2026, 6): (2000.0, 600.0)}
        ref = module.resoudre_reference(
            bulletins=bulletins,
            mois_cibles=module.mois_de_reference(2026, 6),
            salaire_contractuel=None,
            taux_societe=None,
        )
        assert ref.salaire_reference == 2000.0
        assert ref.mois_retenus == "1/12"
```

- [ ] **Step 2 : lancer le test, vérifier qu'il échoue**

```bash
cd backend && ./venv/bin/python -m pytest tests/unit/exports/test_provision_cp_domain.py -v -k "Reference"
```

Attendu : `AttributeError: module ... has no attribute 'mois_de_reference'`.

- [ ] **Step 3 : compléter le domaine**

Ajouter à `backend/app/modules/exports/domain/provision_cp.py`, après `calculer_totaux` :

```python
def mois_de_reference(
    annee: int, mois: int, fenetre: int = FENETRE_REFERENCE_MOIS
) -> list[tuple[int, int]]:
    """Les `fenetre` couples (année, mois) qui se terminent au mois donné, inclus."""
    couples: list[tuple[int, int]] = []
    a, m = annee, mois
    for _ in range(fenetre):
        couples.append((a, m))
        m -= 1
        if m == 0:
            a, m = a - 1, 12
    return list(reversed(couples))


@dataclass(frozen=True)
class Reference:
    salaire_reference: float
    taux_charges: float
    mois_retenus: str
    anomalie: str


def resoudre_reference(
    bulletins: dict[tuple[int, int], tuple[float, float]],
    mois_cibles: list[tuple[int, int]],
    salaire_contractuel: float | None,
    taux_societe: float | None,
) -> Reference:
    """Salaire moyen et taux de charges sur la fenêtre de référence.

    `bulletins` associe (année, mois) à (brut, cotisations patronales). Un mois sans
    bulletin ou à brut nul n'est pas retenu : il ne doit pas tirer la moyenne vers le bas.
    """
    retenus = [
        bulletins[cle]
        for cle in mois_cibles
        if cle in bulletins and bulletins[cle][0] > 0
    ]
    total_mois = len(mois_cibles)

    if not retenus:
        if salaire_contractuel:
            return Reference(
                salaire_reference=round(float(salaire_contractuel), 2),
                taux_charges=round(float(taux_societe or 0.0), 2),
                mois_retenus=f"0/{total_mois}",
                anomalie="aucun bulletin : salaire contractuel et taux société utilisés",
            )
        return Reference(
            salaire_reference=0.0,
            taux_charges=0.0,
            mois_retenus=f"0/{total_mois}",
            anomalie="aucun bulletin et aucun salaire contractuel",
        )

    somme_brut = sum(b for b, _ in retenus)
    somme_patronal = sum(p for _, p in retenus)
    return Reference(
        salaire_reference=round(somme_brut / len(retenus), 2),
        taux_charges=round(somme_patronal / somme_brut * 100, 2),
        mois_retenus=f"{len(retenus)}/{total_mois}",
        anomalie="",
    )
```

- [ ] **Step 4 : lancer les tests, vérifier qu'ils passent**

```bash
cd backend && ./venv/bin/python -m pytest tests/unit/exports/test_provision_cp_domain.py -v
```

Attendu : 15 passed.

- [ ] **Step 5 : commit**

```bash
git add backend/app/modules/exports/domain/provision_cp.py backend/tests/unit/exports/test_provision_cp_domain.py
git commit -m "feat(exports): période de référence, salaire moyen et taux de charges de la provision CP"
```

---

### Task 3 : lecture des données et construction des lignes

**Files:**
- Create: `backend/app/modules/exports/infrastructure/export_provision_cp.py`
- Test: `backend/tests/unit/exports/test_export_provision_cp.py`

**Interfaces:**
- Consumes: Task 1 et 2 (`calculer_ligne`, `calculer_totaux`, `mois_de_reference`,
  `resoudre_reference`, `LigneProvision`).
- Produces:
  - `EXPORT_HEADERS: list[str]`
  - `collecter_lignes(company_id: str, period: str, employee_ids: list[str] | None = None) -> tuple[list[LigneProvision], list[str]]`
    — renvoie les lignes et la liste des avertissements d'en-tête.
  - `preview_provision_cp(company_id: str, period: str, employee_ids: list[str] | None = None) -> dict`
  - `generate_provision_cp_export(company_id: str, period: str, employee_ids: list[str] | None = None, file_format: str = "xlsx") -> bytes`

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/exports/test_export_provision_cp.py`. On mocke les trois
fonctions d'accès aux données, jamais `supabase` directement.

```python
"""Tests de l'export provision congés payés (infrastructure)."""

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_provision_cp as module

pytestmark = pytest.mark.unit

SALARIES = [
    {
        "id": "emp-1",
        "matricule": "BERTAUD",
        "first_name": "Sylvain",
        "last_name": "BERTAUD",
        "hire_date": "2010-03-01",
        "employment_status": "actif",
        "salaire_de_base": {"montant": 2600.0},
    },
    {
        "id": "emp-2",
        "matricule": "NEUF",
        "first_name": "Maëlle",
        "last_name": "SEGUIN",
        "hire_date": "2026-05-01",
        "employment_status": "actif",
        "salaire_de_base": {"montant": 1900.0},
    },
]

BULLETINS = {
    "emp-1": {(2026, m): (2640.86, 679.76) for m in range(1, 8)},
    "emp-2": {},
}

SOLDES = {
    "emp-1": (28.00, 4.16),
    "emp-2": (0.00, 2.08),
}


def _patch_all():
    return (
        patch.object(module, "_lire_salaries", return_value=SALARIES),
        patch.object(module, "_lire_bulletins", return_value=BULLETINS),
        patch.object(module, "_lire_soldes_ouvres", side_effect=lambda eid, *a, **k: SOLDES[eid]),
    )


class TestCollecterLignes:
    def test_les_deux_salaries_sont_presents(self):
        p1, p2, p3 = _patch_all()
        with p1, p2, p3:
            lignes, avertissements = module.collecter_lignes("company-1", "2026-07")

        assert [l.matricule for l in lignes] == ["BERTAUD", "NEUF"]

    def test_salarie_avec_bulletins_calcule_sur_ses_bulletins(self):
        p1, p2, p3 = _patch_all()
        with p1, p2, p3:
            lignes, _ = module.collecter_lignes("company-1", "2026-07")

        bertaud = lignes[0]
        assert bertaud.solde_jours == 32.16
        assert bertaud.salaire_reference == 2640.86
        assert bertaud.mois_retenus == "7/12"
        assert bertaud.anomalie == ""
        assert bertaud.provision == 3860.46

    def test_salarie_sans_bulletin_replie_et_signale(self):
        p1, p2, p3 = _patch_all()
        with p1, p2, p3:
            lignes, _ = module.collecter_lignes("company-1", "2026-07")

        neuf = lignes[1]
        assert neuf.salaire_reference == 1900.0
        assert neuf.mois_retenus == "0/12"
        assert "aucun bulletin" in neuf.anomalie

    def test_avertissement_quand_l_historique_est_incomplet(self):
        p1, p2, p3 = _patch_all()
        with p1, p2, p3:
            _, avertissements = module.collecter_lignes("company-1", "2026-07")

        assert any("sur 12" in a for a in avertissements)

    def test_solde_nul_hors_perimetre(self):
        with patch.object(module, "_lire_salaries", return_value=SALARIES), \
             patch.object(module, "_lire_bulletins", return_value=BULLETINS), \
             patch.object(module, "_lire_soldes_ouvres",
                          side_effect=lambda eid, *a, **k: (0.0, 0.0) if eid == "emp-2" else SOLDES[eid]):
            lignes, _ = module.collecter_lignes("company-1", "2026-07")

        assert [l.matricule for l in lignes] == ["BERTAUD"]

    def test_salarie_sans_date_d_embauche_exclu_et_signale(self):
        sans_date = [dict(SALARIES[0]), {**SALARIES[1], "hire_date": None}]
        with patch.object(module, "_lire_salaries", return_value=sans_date), \
             patch.object(module, "_lire_bulletins", return_value=BULLETINS), \
             patch.object(module, "_lire_soldes_ouvres", side_effect=lambda eid, *a, **k: SOLDES[eid]):
            lignes, avertissements = module.collecter_lignes("company-1", "2026-07")

        assert [l.matricule for l in lignes] == ["BERTAUD"]
        assert any("date d'entrée" in a for a in avertissements)


class TestPreview:
    def test_preview_expose_le_contrat_commun(self):
        p1, p2, p3 = _patch_all()
        with p1, p2, p3:
            preview = module.preview_provision_cp("company-1", "2026-07")

        assert preview["employees_count"] == 2
        assert preview["can_generate"] is True
        assert preview["totals"]["total_amount"] == preview["details"]["total"]
        assert preview["anomalies"] == [] or all(
            a["severity"] != "blocking" for a in preview["anomalies"]
        )

    def test_preview_bloquant_quand_aucune_ligne(self):
        with patch.object(module, "_lire_salaries", return_value=[]), \
             patch.object(module, "_lire_bulletins", return_value={}), \
             patch.object(module, "_lire_soldes_ouvres", return_value=(0.0, 0.0)):
            preview = module.preview_provision_cp("company-1", "2026-07")

        assert preview["can_generate"] is False
        assert any(a["severity"] == "blocking" for a in preview["anomalies"])


class TestGenerate:
    def test_xlsx_commence_par_l_entete_zip(self):
        p1, p2, p3 = _patch_all()
        with p1, p2, p3:
            contenu = module.generate_provision_cp_export("company-1", "2026-07")

        assert contenu[:2] == b"PK"

    def test_csv_contient_la_ligne_total(self):
        p1, p2, p3 = _patch_all()
        with p1, p2, p3:
            contenu = module.generate_provision_cp_export(
                "company-1", "2026-07", file_format="csv"
            )

        texte = contenu.decode("utf-8-sig")
        assert "Total" in texte
        assert "BERTAUD" in texte
```

- [ ] **Step 2 : lancer le test, vérifier qu'il échoue**

```bash
cd backend && ./venv/bin/python -m pytest tests/unit/exports/test_export_provision_cp.py -v
```

Attendu : `ModuleNotFoundError: No module named 'app.modules.exports.infrastructure.export_provision_cp'`.

- [ ] **Step 3 : écrire l'infrastructure**

Créer `backend/app/modules/exports/infrastructure/export_provision_cp.py` :

```python
# Export « État de provision des congés payés » — valorisation en euros de la dette de CP.
# Modèle : état Cegid transmis par Elsa le 27/07/2026 (CARTOL, 71 salariés, 394 121,22 €).
from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase
from app.modules.absences.application.queries import _leave_context, _parse_hire_date
from app.modules.absences.domain.fractionnement import ouvrables_to_ouvres
from app.modules.absences.domain.rules import compute_cp_balances_for_bulletin
from app.modules.absences.infrastructure import fractionnement_repository as frac_repo
from app.modules.absences.infrastructure.repository import absence_repository
from app.modules.exports.domain.provision_cp import (
    FENETRE_REFERENCE_MOIS,
    LigneProvision,
    calculer_ligne,
    calculer_totaux,
    mois_de_reference,
    resoudre_reference,
)
from app.shared.utils.export import generate_csv, generate_xlsx

EXPORT_HEADERS = [
    "Matricule",
    "Nom de l'employé",
    "Date d'entrée",
    "Solde jrs N-1",
    "Solde jrs N",
    "Solde jours",
    "Salaire de référence",
    "Taux Ch. soc.",
    "Montant charges sociales",
    "Provision",
    "Total",
    "Mois retenus",
    "Anomalie",
]


def _fin_de_mois(period: str) -> date:
    annee, mois = map(int, period.split("-"))
    return date(annee, mois, calendar.monthrange(annee, mois)[1])


def _montant_contractuel(salarie: Dict[str, Any]) -> Optional[float]:
    brut = salarie.get("salaire_de_base")
    if isinstance(brut, dict):
        for cle in ("montant", "value", "brut_mensuel", "amount"):
            valeur = brut.get(cle)
            if isinstance(valeur, (int, float)):
                return float(valeur)
        return None
    return float(brut) if isinstance(brut, (int, float)) else None


def _lire_salaries(
    company_id: str, employee_ids: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    requete = (
        supabase.table("employees")
        .select(
            "id, matricule, first_name, last_name, hire_date, "
            "employment_status, salaire_de_base"
        )
        .eq("company_id", company_id)
        .eq("employment_status", "actif")
    )
    if employee_ids:
        requete = requete.in_("id", employee_ids)
    lignes = requete.execute().data or []
    return sorted(lignes, key=lambda e: (e.get("last_name") or "", e.get("first_name") or ""))


def _lire_bulletins(
    company_id: str, mois_cibles: List[Tuple[int, int]]
) -> Dict[str, Dict[Tuple[int, int], Tuple[float, float]]]:
    """Brut et cotisations patronales par salarié et par mois, sur la fenêtre demandée."""
    annees = sorted({a for a, _ in mois_cibles})
    reponse = (
        supabase.table("payslips")
        .select("employee_id, year, month, payslip_data")
        .eq("company_id", company_id)
        .in_("year", annees)
        .execute()
    )
    attendus = set(mois_cibles)
    resultat: Dict[str, Dict[Tuple[int, int], Tuple[float, float]]] = {}
    for ligne in reponse.data or []:
        cle = (ligne["year"], ligne["month"])
        if cle not in attendus:
            continue
        donnees = ligne.get("payslip_data") or {}
        brut = float(donnees.get("salaire_brut") or 0)
        patronal = sum(
            float(c.get("total_patronal") or 0)
            for c in (donnees.get("cotisations_officielles") or [])
        )
        resultat.setdefault(ligne["employee_id"], {})[cle] = (brut, patronal)
    return resultat


def _lire_soldes_ouvres(
    employee_id: str, company_id: str, ref_date: date
) -> Tuple[float, float]:
    """Soldes CP période précédente et période en cours, en jours ouvrés."""
    hire_date = _parse_hire_date(employee_id)
    if not hire_date:
        return (0.0, 0.0)
    policy, adjustment, _, cp_seniority = _leave_context(
        employee_id, ref_date.year, company_id
    )
    from app.modules.absences.application.fractionnement_prefill import (
        build_employee_cp_seniority_context_from_db,
    )

    contexte = build_employee_cp_seniority_context_from_db(employee_id)
    validees = absence_repository.list_validated_for_employees([employee_id])
    soldes = compute_cp_balances_for_bulletin(
        hire_date,
        validees,
        ref_date,
        policy=policy,
        adjustment=adjustment,
        cp_seniority=cp_seniority,
        employee_ctx=contexte,
    )
    reglages = frac_repo.get_fractionnement_settings_row(company_id) or {}
    ratio = float(reglages.get("ouvres_to_ouvrables_ratio") or 1.2)
    n1 = ouvrables_to_ouvres(float(soldes["periode_precedente"].get("solde") or 0), ratio)
    n = ouvrables_to_ouvres(float(soldes["periode_courante"].get("solde") or 0), ratio)
    return (n1, n)


def collecter_lignes(
    company_id: str, period: str, employee_ids: Optional[List[str]] = None
) -> Tuple[List[LigneProvision], List[str]]:
    ref_date = _fin_de_mois(period)
    mois_cibles = mois_de_reference(ref_date.year, ref_date.month)
    salaries = _lire_salaries(company_id, employee_ids)
    bulletins = _lire_bulletins(company_id, mois_cibles)

    lignes: List[LigneProvision] = []
    sans_date = 0
    mois_max = 0

    for salarie in salaries:
        if not salarie.get("hire_date"):
            sans_date += 1
            continue
        n1, n = _lire_soldes_ouvres(salarie["id"], company_id, ref_date)
        if round(n1 + n, 2) == 0:
            continue
        reference = resoudre_reference(
            bulletins=bulletins.get(salarie["id"], {}),
            mois_cibles=mois_cibles,
            salaire_contractuel=_montant_contractuel(salarie),
            taux_societe=None,
        )
        mois_max = max(mois_max, int(reference.mois_retenus.split("/")[0]))
        anomalie = reference.anomalie
        if round(n1 + n, 2) < 0:
            anomalie = "; ".join(filter(None, [anomalie, "solde négatif : congés pris d'avance"]))
        lignes.append(
            calculer_ligne(
                matricule=salarie.get("matricule") or "",
                nom=f"{salarie.get('first_name') or ''} {salarie.get('last_name') or ''}".strip(),
                date_entree=str(salarie["hire_date"])[:10],
                solde_n1=n1,
                solde_n=n,
                salaire_reference=reference.salaire_reference,
                taux_charges=reference.taux_charges,
                mois_retenus=reference.mois_retenus,
                anomalie=anomalie,
            )
        )

    avertissements: List[str] = []
    if lignes and mois_max < FENETRE_REFERENCE_MOIS:
        avertissements.append(
            f"Salaire de référence calculé sur {mois_max} mois sur "
            f"{FENETRE_REFERENCE_MOIS} — EYWAI ne contient de la paie que depuis "
            "janvier 2026."
        )
    if sans_date:
        avertissements.append(
            f"{sans_date} salarié(s) exclu(s) : aucune date d'entrée renseignée."
        )
    return lignes, avertissements


def preview_provision_cp(
    company_id: str, period: str, employee_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    lignes, avertissements = collecter_lignes(company_id, period, employee_ids)
    totaux = calculer_totaux(lignes)

    anomalies: List[Dict[str, Any]] = []
    if not lignes:
        anomalies.append(
            {
                "type": "error",
                "message": "Aucun salarié avec un solde de congés à cette date",
                "severity": "blocking",
            }
        )
    nb_anomalies = sum(1 for l in lignes if l.anomalie)
    if nb_anomalies:
        anomalies.append(
            {
                "type": "warning",
                "message": f"{nb_anomalies} ligne(s) signalée(s) dans la colonne Anomalie",
                "severity": "warning",
            }
        )

    return {
        "employees_count": len(lignes),
        "totals": {
            "employees_count": len(lignes),
            "total_amount": totaux["total"],
        },
        "anomalies": anomalies,
        "warnings": avertissements,
        "can_generate": all(a.get("severity") != "blocking" for a in anomalies),
        "details": {
            "provision": totaux["provision"],
            "montant_charges": totaux["montant_charges"],
            "total": totaux["total"],
            "solde_jours": totaux["solde_jours"],
            "taux_charges_moyen": totaux["taux_charges"],
        },
    }


def _lignes_export(lignes: List[LigneProvision]) -> List[Dict[str, Any]]:
    donnees = [
        {
            "Matricule": l.matricule,
            "Nom de l'employé": l.nom,
            "Date d'entrée": l.date_entree,
            "Solde jrs N-1": l.solde_n1,
            "Solde jrs N": l.solde_n,
            "Solde jours": l.solde_jours,
            "Salaire de référence": l.salaire_reference,
            "Taux Ch. soc.": l.taux_charges,
            "Montant charges sociales": l.montant_charges,
            "Provision": l.provision,
            "Total": l.total,
            "Mois retenus": l.mois_retenus,
            "Anomalie": l.anomalie,
        }
        for l in lignes
    ]
    totaux = calculer_totaux(lignes)
    donnees.append(
        {
            "Matricule": "",
            "Nom de l'employé": "Total",
            "Date d'entrée": "",
            "Solde jrs N-1": totaux["solde_n1"],
            "Solde jrs N": totaux["solde_n"],
            "Solde jours": totaux["solde_jours"],
            "Salaire de référence": totaux["salaire_reference"],
            "Taux Ch. soc.": totaux["taux_charges"],
            "Montant charges sociales": totaux["montant_charges"],
            "Provision": totaux["provision"],
            "Total": totaux["total"],
            "Mois retenus": "",
            "Anomalie": "",
        }
    )
    return donnees


def generate_provision_cp_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    file_format: str = "xlsx",
) -> bytes:
    lignes, _ = collecter_lignes(company_id, period, employee_ids)
    donnees = _lignes_export(lignes)
    if file_format == "xlsx":
        return generate_xlsx(donnees, EXPORT_HEADERS, f"Provision CP {period}")
    return generate_csv(donnees, EXPORT_HEADERS)
```

- [ ] **Step 4 : lancer les tests, vérifier qu'ils passent**

```bash
cd backend && ./venv/bin/python -m pytest tests/unit/exports/test_export_provision_cp.py -v
```

Attendu : 10 passed.

- [ ] **Step 5 : commit**

```bash
git add backend/app/modules/exports/infrastructure/export_provision_cp.py backend/tests/unit/exports/test_export_provision_cp.py
git commit -m "feat(exports): lecture des soldes et bulletins pour la provision CP"
```

---

### Task 4 : câblage backend du type d'export

**Files:**
- Modify: `backend/app/modules/exports/domain/value_objects.py:5-54`
- Modify: `backend/app/modules/exports/schemas/requests.py:7-28`
- Modify: `backend/app/modules/exports/infrastructure/providers.py`
- Modify: `backend/app/modules/exports/application/queries.py:297`
- Modify: `backend/app/modules/exports/application/service.py:147`
- Test: `backend/tests/unit/exports/test_export_provision_cp.py`

**Interfaces:**
- Consumes: Task 3 (`preview_provision_cp`, `generate_provision_cp_export`).
- Produces: le type `provision_cp` accepté par `/exports/preview` et `/exports/generate`.

- [ ] **Step 1 : écrire le test qui échoue**

Ajouter à `backend/tests/unit/exports/test_export_provision_cp.py` :

```python
class TestCablage:
    def test_type_declare_en_preview_et_en_generation(self):
        from app.modules.exports.domain.value_objects import (
            EXPORT_TYPES_GENERATE,
            EXPORT_TYPES_PREVIEW,
        )

        assert "provision_cp" in EXPORT_TYPES_PREVIEW
        assert "provision_cp" in EXPORT_TYPES_GENERATE

    def test_type_accepte_par_le_schema_de_requete(self):
        from app.modules.exports.schemas.requests import ExportPreviewRequest

        requete = ExportPreviewRequest(export_type="provision_cp", period="2026-07")
        assert requete.export_type == "provision_cp"

    def test_providers_expose_les_deux_fonctions(self):
        from app.modules.exports.infrastructure import providers

        assert callable(providers.preview_provision_cp)
        assert callable(providers.generate_provision_cp_export)
```

- [ ] **Step 2 : lancer le test, vérifier qu'il échoue**

```bash
cd backend && ./venv/bin/python -m pytest tests/unit/exports/test_export_provision_cp.py -v -k Cablage
```

Attendu : 3 failed — `assert 'provision_cp' in EXPORT_TYPES_PREVIEW` puis
`ValidationError` puis `AttributeError`.

- [ ] **Step 3 : câbler les cinq fichiers**

**3a.** Dans `backend/app/modules/exports/domain/value_objects.py`, ajouter
`"provision_cp",` juste après `"conges_absences",` dans **les deux** frozensets
`EXPORT_TYPES_PREVIEW` et `EXPORT_TYPES_GENERATE`.

**3b.** Dans `backend/app/modules/exports/schemas/requests.py`, ajouter
`    "provision_cp",` juste après `    "conges_absences",` dans le `Literal ExportType`.

**3c.** Dans `backend/app/modules/exports/infrastructure/providers.py`, ajouter l'import
à la suite du bloc `from .export_conges_absences import (...)` :

```python
from .export_provision_cp import (
    generate_provision_cp_export as _generate_provision_cp_export,
    preview_provision_cp as _preview_provision_cp,
)
```

puis, à la suite de `generate_conges_absences_export` (vers la ligne 360), les deux
délégations :

```python
def preview_provision_cp(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return _preview_provision_cp(company_id, period, employee_ids)


def generate_provision_cp_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    file_format: str,
) -> bytes:
    return _generate_provision_cp_export(company_id, period, employee_ids, file_format)
```

**3d.** Dans `backend/app/modules/exports/application/queries.py`, ajouter une branche
juste après le bloc `elif request.export_type == "conges_absences":` (il se termine par
le `return ExportPreviewResponse(...)` vers la ligne 310) :

```python
    elif request.export_type == "provision_cp":
        preview = providers.preview_provision_cp(
            company_id,
            request.period,
            request.employee_ids,
        )
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=preview["employees_count"],
            totals=ExportTotals(**preview["totals"]),
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
            details=preview.get("details"),
        )
```

**3e.** Dans `backend/app/modules/exports/application/service.py`, ajouter la branche
juste après `elif request.export_type == "conges_absences":` (ligne 147-148) :

```python
    elif request.export_type == "provision_cp":
        return _generate_provision_cp(company_id, user_id, user_name, request)
```

puis, juste après la fonction `_generate_conges_absences` (elle commence ligne 409),
la fonction jumelle. Elle reprend la même mécanique de dépôt de fichier et
d'enregistrement d'historique ; recopier le corps de `_generate_conges_absences` en
remplaçant les quatre appels et le nom de fichier :

```python
def _generate_provision_cp(
    company_id: str,
    user_id: str,
    user_name: str,
    request: ExportGenerateRequest,
) -> ExportGenerateResponse:
    preview = providers.preview_provision_cp(
        company_id,
        request.period,
        request.employee_ids,
    )
    if not preview["can_generate"]:
        raise ValueError("Impossible de générer l'export. Vérifiez les anomalies bloquantes.")

    file_content = providers.generate_provision_cp_export(
        company_id,
        request.period,
        request.employee_ids,
        request.format,
    )
    period_formatted = request.period.replace("-", "_")
    extension = request.format
    filename = f"provision_cp_{period_formatted}.{extension}"
    storage_path = f"exports/{company_id}/{request.export_type}/{filename}"
    final_storage_path = upload_export_file(
        BUCKET, storage_path, file_content, _content_type(extension)
    )
    signed_url = create_signed_url(final_storage_path, 3600)

    parameters = {
        "employee_ids": request.employee_ids,
        "filters": request.filters,
    }
    totals = preview["totals"]
    export_record: ExportRecordForInsert = {
        "company_id": company_id,
        "export_type": request.export_type,
        "period": request.period,
        "parameters": parameters,
        "file_paths": [final_storage_path],
        "report": {
            "employees_count": preview.get("employees_count", 0),
            "totals": totals,
            "anomalies": preview.get("anomalies", []),
            "warnings": preview.get("warnings", []),
        },
        "status": "generated",
        "generated_by": user_id,
    }
    export_id = commands.record_export_history(export_record)

    return ExportGenerateResponse(
        export_id=export_id,
        export_type=request.export_type,
        period=request.period,
        status="generated",
        files=[
            ExportFileInfo(
                filename=filename,
                path=final_storage_path,
                size=len(file_content),
                format=request.format,
            )
        ],
        report=ExportReport(
            export_type=request.export_type,
            period=request.period,
            generated_at=datetime.now(),
            generated_by=user_name,
            employees_count=preview.get("employees_count", 0),
            totals=ExportTotals(**totals),
            anomalies=[ExportAnomaly(**a) for a in preview.get("anomalies", [])],
            warnings=preview.get("warnings", []),
            parameters=parameters,
        ),
        download_urls={filename: signed_url},
    )
```

> Il n'y a pas de fonction de factorisation dans `service.py` : les 23 exports répètent
> ce bloc. Ne pas en inventer une dans cette tâche.

- [ ] **Step 4 : lancer toute la suite exports, vérifier qu'elle passe**

```bash
cd backend && ./venv/bin/python -m pytest tests/unit/exports/ -v
```

Attendu : toute la suite au vert, dont les 3 tests `TestCablage`. `test_export_coverage.py`
vérifie possiblement que chaque type déclaré a un générateur : s'il échoue, c'est qu'un
des cinq points de câblage manque, pas que le test est à corriger.

- [ ] **Step 5 : commit**

```bash
git add backend/app/modules/exports/
git add backend/tests/unit/exports/test_export_provision_cp.py
git commit -m "feat(exports): câbler le type provision_cp sur preview et generate"
```

---

### Task 5 : câblage frontend

**Files:**
- Modify: `frontend/src/api/exports.ts:6-27`
- Modify: `frontend/src/components/exports/ExportCommonModel.tsx:63-120`
- Modify: `frontend/src/components/exports/ExportHistory.tsx:39-42`
- Modify: `frontend/src/components/exports/ExportsRhTab.tsx:17-41`
- Modify: `frontend/src/lib/exportEmptyState.ts:13`

**Interfaces:**
- Consumes: Task 4 (le type `provision_cp` accepté par l'API).
- Produces: une carte « Provision congés payés » dans l'onglet Exports RH.

- [ ] **Step 1 : ajouter le type à l'union TypeScript**

Dans `frontend/src/api/exports.ts`, ajouter au `type ExportType` (ligne 6-27), après
la ligne `| "conges_absences"` :

```typescript
  | "provision_cp"
```

- [ ] **Step 2 : déclarer le libellé et le mapping**

Dans `frontend/src/components/exports/ExportCommonModel.tsx`, ajouter au
`EXPORT_TYPE_MAP` (après `"conges-absences": "conges_absences",`) :

```typescript
  provision_cp: "provision_cp",
  "provision-cp": "provision_cp",
  "Provision congés payés": "provision_cp",
```

et ajouter `"provision_cp",` au `FILE_FORMAT_EXPORT_TYPES` (l'export propose xlsx et csv).

Dans `frontend/src/components/exports/ExportHistory.tsx`, ajouter à la table des
libellés (près de `conges_absences: "Congés payés / Absences",`) :

```typescript
  provision_cp: "Provision congés payés",
```

Dans `frontend/src/lib/exportEmptyState.ts`, ajouter :

```typescript
  provision_cp: "solde de congés à provisionner",
```

- [ ] **Step 3 : ajouter la carte dans l'onglet Exports RH**

Dans `frontend/src/components/exports/ExportsRhTab.tsx`, ajouter au
`exportTypeMapping` :

```typescript
    "provision-cp": "provision_cp",
```

et à la liste `exports`, après l'entrée `conges-absences` :

```typescript
    {
      id: "provision-cp",
      name: "Provision congés payés",
      description:
        "Valorisation en euros de la dette de congés payés à la fin du mois choisi, salarié par salarié",
      icon: Calendar,
    },
```

- [ ] **Step 4 : vérifier la compilation**

```bash
cd frontend && npm run build
```

Attendu : build réussi, aucune erreur TypeScript. Une erreur
`Type '"provision_cp"' is not assignable` signifie que le Step 1 n'a pas été fait.

- [ ] **Step 5 : commit**

```bash
git add frontend/src/api/exports.ts frontend/src/components/exports/ frontend/src/lib/exportEmptyState.ts
git commit -m "feat(exports): carte Provision congés payés dans l'onglet Exports RH"
```

---

### Task 6 : mesure de l'écart contre le modèle Cegid

**Files:**
- Create: `backend/scripts/provision_cp_comparer_modele.py`

**Interfaces:**
- Consumes: Task 3 (`collecter_lignes`).
- Produces: un rapport d'écart à l'écran. **Aucune écriture en base.**

Ce script n'est pas un test : il ne peut rien asserter tant que la paie 2025 manque
(constat 4). Il sert à mesurer l'écart, à le consigner, et à le refaire tourner en 2027
quand l'historique sera complet.

- [ ] **Step 1 : écrire le script**

Créer `backend/scripts/provision_cp_comparer_modele.py` :

```python
"""Compare l'export provision CP au modèle Cegid transmis par Elsa.

Lecture seule, aucune écriture. À relancer quand EYWAI aura douze mois d'historique
de paie (juin 2027) : c'est à ce moment-là seulement que l'égalité au centime a un sens.

Usage :
    ./venv/bin/python scripts/provision_cp_comparer_modele.py \\
        --societe "Cartol Industrie" --periode 2026-07 \\
        --modele "../data/_inbox/whatsapp-elsa/00000595-PROVISION CP.pdf"
"""

from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.exports.infrastructure.export_provision_cp import (  # noqa: E402
    collecter_lignes,
)


def _cle(texte: str) -> str:
    sans_accent = (
        unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode()
    )
    return re.sub(r"[^A-Z]", "", sans_accent.upper())


def lire_modele(chemin: str) -> list[dict]:
    texte = subprocess.run(
        ["pdftotext", "-layout", chemin, "-"], capture_output=True, text=True, check=True
    ).stdout
    lignes = []
    for ligne in texte.splitlines():
        nombres = re.findall(r"-?[\d ]+\.\d\d", ligne)
        if len(nombres) != 8:
            continue
        valeurs = [float(n.replace(" ", "")) for n in nombres]
        libelle = re.sub(r"\s+", " ", ligne.strip())
        libelle = libelle[: libelle.find(nombres[0].strip()[:4])].strip()
        if libelle.lower().startswith("total"):
            continue
        mots = libelle.split()
        lignes.append(
            {
                "cle": {_cle(m) for m in mots[1:] if _cle(m)},
                "libelle": " ".join(mots[1:]),
                "solde_jours": valeurs[2],
                "salaire_reference": valeurs[3],
                "taux_charges": valeurs[4],
                "provision": valeurs[6],
                "total": valeurs[7],
            }
        )
    return lignes


def main() -> int:
    parseur = argparse.ArgumentParser()
    parseur.add_argument("--societe", required=True)
    parseur.add_argument("--periode", required=True)
    parseur.add_argument("--modele", required=True)
    args = parseur.parse_args()

    societes = supabase.table("companies").select("id, company_name").execute().data or []
    trouvees = [s for s in societes if _cle(args.societe) in _cle(s["company_name"])]
    if len(trouvees) != 1:
        print(f"Société introuvable ou ambiguë : {args.societe}")
        return 1
    company_id = trouvees[0]["id"]

    modele = lire_modele(args.modele)
    nos_lignes, avertissements = collecter_lignes(company_id, args.periode)
    print(f"Modèle : {len(modele)} lignes | EYWAI : {len(nos_lignes)} lignes")
    for a in avertissements:
        print(f"  avertissement : {a}")

    index = {frozenset({_cle(m) for m in l.nom.split() if _cle(m)}): l for l in nos_lignes}
    apparies, orphelins = [], []
    for ligne_modele in modele:
        correspondances = [
            nl for cles, nl in index.items() if ligne_modele["cle"] and ligne_modele["cle"] <= cles
        ]
        if len(correspondances) == 1:
            apparies.append((ligne_modele, correspondances[0]))
        else:
            orphelins.append(ligne_modele["libelle"])

    print(f"\nAppariés : {len(apparies)} | non rapprochés : {len(orphelins)}")
    for nom in orphelins:
        print(f"  non rapproché : {nom}")

    if not apparies:
        return 0

    for champ in ("solde_jours", "salaire_reference", "taux_charges", "provision", "total"):
        ecarts = [abs(getattr(n, champ) - m[champ]) for m, n in apparies]
        exacts = sum(1 for e in ecarts if e < 0.01)
        print(
            f"\n{champ:20s} : {exacts}/{len(ecarts)} exacts | "
            f"écart médian {statistics.median(ecarts):10.2f} | max {max(ecarts):10.2f}"
        )

    total_modele = sum(m["total"] for m, _ in apparies)
    total_eywai = sum(n.total for _, n in apparies)
    print(
        f"\nTotal modèle {total_modele:12.2f} EUR | total EYWAI {total_eywai:12.2f} EUR | "
        f"écart {total_eywai - total_modele:+12.2f} EUR "
        f"({(total_eywai - total_modele) / total_modele * 100:+.1f} %)"
    )
    print("\nRappel : l'écart sur le salaire de référence est attendu tant qu'EYWAI n'a")
    print("pas la paie 2025. Ne pas corriger le moteur sur cette base.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2 : lancer le script sur Cartol**

```bash
cd backend && ./venv/bin/python scripts/provision_cp_comparer_modele.py \
  --societe "Cartol Industrie" --periode 2026-07 \
  --modele "../data/_inbox/whatsapp-elsa/00000595-PROVISION CP.pdf"
```

Attendu : au moins 60 salariés appariés, `solde_jours` et `taux_charges` proches,
`salaire_reference` avec un écart médian visible. Ce résultat est le livrable de l'étape :
le consigner tel quel.

- [ ] **Step 3 : consigner le résultat dans la spec**

Ajouter à la fin de `docs/superpowers/specs/2026-08-07-provision-cp-design.md` une
section « Mesure du 07/08/2026 » reprenant les chiffres imprimés : nombre d'appariés,
écart médian par champ, écart total en euros et en pourcentage.

- [ ] **Step 4 : commit**

```bash
git add backend/scripts/provision_cp_comparer_modele.py docs/superpowers/specs/2026-08-07-provision-cp-design.md
git commit -m "chore(exports): script de comparaison de la provision CP au modèle du cabinet"
```

---

### Task 7 : recette sur l'environnement de test

**Files:**
- Modify: `docs/afaire.md` (compte rendu du point #23)

**Interfaces:**
- Consumes: toutes les tâches précédentes.
- Produces: le compte rendu du point #23.

- [ ] **Step 1 : lancer toute la suite de tests**

```bash
cd backend && ./venv/bin/python -m pytest tests/unit/exports/ tests/unit/absences/ -v
```

Attendu : au vert. Une régression dans `tests/unit/absences/` signifie qu'un import de
Task 3 a modifié un comportement partagé — corriger avant de continuer.

- [ ] **Step 2 : déployer sur l'environnement de test et générer l'export**

Sur le frontend de test, société Cartol : Exports > Exports RH > « Provision congés
payés », période 2026-07, format xlsx. Télécharger.

Vérifier dans le fichier :
- la ligne « Total » est présente et sa colonne Total vaut bien provision + charges ;
- une ligne au moins porte « x/12 » en Mois retenus, avec x < 12 ;
- aucune cellule de date au format machine (le défaut corrigé sur les exports CSE) ;
- le nombre de lignes est supérieur aux 71 du modèle Cegid, puisque nous n'excluons pas
  les embauches récentes.

- [ ] **Step 3 : générer aussi sur une société sans réglage de congés**

Même manipulation sur Zone 404 ou MAJI. Attendu : soit un export cohérent, soit
l'anomalie bloquante « Aucun salarié avec un solde de congés à cette date ». Dans les
deux cas, **jamais une erreur 500**.

- [ ] **Step 4 : rédiger le compte rendu dans `docs/afaire.md`**

Sous la ligne `#23. Pouvoir faire un export de calcul de provision des congés payés...`,
en langage courant, sans jargon, dans le style des points MOI : le fichier exemple était
déjà là depuis le 21/07 ; ce que fait l'export ; les chiffres réels mesurés à l'étape 6 ;
ce qui reste (la preuve au centime en juin 2027, la question du périmètre à poser à
Elsa).

- [ ] **Step 5 : commit**

```bash
git add docs/afaire.md
git commit -m "docs(afaire): compte rendu du point #23, provision congés payés"
```

---

## Questions ouvertes à poser à Elsa (hors de ce plan)

Une seule, à envoyer telle quelle une fois l'export vu à l'écran :

> Ton état de provision CP du 27/07 sort 71 salariés pour Cartol, alors que 86 ont été
> payés en juin. Les absents sont tous des embauches récentes (Lucas RENAUD, Pierre-Jean
> SICAUD, Annaëlle BREMENT, Maëlle SEGUIN, Lucas ALVES, Florence LEGRIP…). Est-ce que le
> cabinet les exclut volontairement de la provision, ou est-ce que l'état est arrêté à
> une date antérieure à leur arrivée ? De notre côté on les inclut, puisqu'ils ont des
> droits acquis donc une dette.
