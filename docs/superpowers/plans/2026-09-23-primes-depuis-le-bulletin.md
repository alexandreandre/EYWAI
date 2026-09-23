# Primes saisies depuis le bulletin — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** une prime ajoutée, corrigée ou retirée dans l'écran « Modifier le bulletin » devient une variable du mois (`monthly_inputs`), puis le moteur recalcule tout le bulletin — bases, cotisations, net, cumuls.

**Architecture:** le moteur marque chaque ligne de prime issue d'une saisie avec `saisie_id`. À l'enregistrement, une fonction pure compare les primes d'avant et d'après ; la commande vérifie l'appartenance des saisies avant d'enregistrer, écrit les variables du mois après, puis régénère **une seule fois** (heures sup comprises). Côté écran, « Ajouter une ligne » devient « Ajouter une prime » et réutilise le sélecteur de l'onglet Primes (`SaisieModal`).

**Tech Stack:** Python 3.12 / FastAPI / pytest (interpréteur `backend/.venv/bin/python`, linter `backend/.venv/bin/ruff`) ; React / TypeScript / vitest (`npm run typecheck`, `npx vitest run`).

## Global Constraints

- Spec : `docs/superpowers/specs/2026-09-23-primes-depuis-le-bulletin-design.md`.
- Les variables du mois sont la seule vérité pour les primes ; le bulletin n'en est qu'une porte d'entrée.
- Une ligne sans `saisie_id` ni `nouvelle_saisie` n'est **pas** une prime saisie : elle garde le comportement actuel (ne bouge que le brut).
- Refus d'une saisie qui n'appartient pas au salarié, à la société et au mois du bulletin : `PayslipBadRequestError` (erreur existante, HTTP 400), **avant** tout enregistrement.
- Une seule régénération par enregistrement, options identiques aux heures sup : `force_calendrier_incomplet=True`, `regenerer_bulletin_valide=True`.
- Échec du moteur : les saisies restent écrites, la réponse porte `recalcul_erreur` (champ à **déclarer** dans `PayslipEditResponse`, sinon FastAPI le retire).
- Un bulletin importé reste refusé (`_refuser_si_importe`, inchangé).
- Commentaires, docstrings, libellés et messages en français.
- **Ne jamais commiter sans accord explicite d'Alexandre** : les étapes « Commit » sont des propositions.
- Tests backend depuis `backend/` avec `APP_ENV=test`.

---

### Task 1 : le moteur relie chaque ligne de prime à sa saisie

**Files:**
- Create: `backend/app/modules/payroll/engine/lien_saisie.py`
- Modify: `backend/app/modules/payroll/documents/payslip_generator.py` (construction de `prime_entry`, vers la ligne 792)
- Modify: `backend/app/modules/payroll/documents/payslip_generator_forfait.py` (construction de `prime_entry`, vers la ligne 277)
- Modify: `backend/app/modules/payroll/documents/payslip_run_heures.py` (`prime_calculee`, vers la ligne 654)
- Modify: `backend/app/modules/payroll/documents/payslip_run_forfait.py` (`prime_calculee`, vers la ligne 304)
- Modify: `backend/app/modules/payroll/engine/calcul_brut.py` (lignes de primes, vers la ligne 1607)
- Modify: `backend/app/modules/payroll/engine/calcul_brut_forfait.py` (lignes de primes, vers la ligne 506)
- Test: `backend/tests/unit/payroll/test_lien_saisie.py`

**Interfaces:**
- Produces: `lier_a_la_saisie(cible: dict, source: Mapping[str, Any]) -> dict` — rend `cible` enrichie de `saisie_id` si `source` en porte un, inchangée sinon. Toute ligne de prime issue d'une saisie porte `"saisie_id": "<id monthly_inputs>"`, dans `calcul_du_brut` comme dans `primes_non_soumises`.

- [ ] **Step 1 : écrire les tests qui échouent**

`backend/tests/unit/payroll/test_lien_saisie.py` :

```python
"""Une ligne de prime garde l'identifiant de la saisie qui l'a produite.

Sans ce lien, corriger ou retirer une prime depuis le bulletin ne saurait pas
quelle variable du mois modifier (spec 2026-09-23).
"""

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.lien_saisie import lier_a_la_saisie
from tests.unit.payroll.helpers import _weekday_calendrier, build_test_contexte

pytestmark = pytest.mark.unit


def test_le_lien_est_recopie_quand_la_source_en_porte_un():
    assert lier_a_la_saisie({"libelle": "Prime"}, {"saisie_id": "s-1"}) == {
        "libelle": "Prime",
        "saisie_id": "s-1",
    }


def test_sans_lien_la_ligne_est_inchangee():
    assert lier_a_la_saisie({"libelle": "Prime"}, {"libelle": "Prime"}) == {
        "libelle": "Prime"
    }


def test_une_prime_saisie_imprime_son_lien_dans_le_brut():
    contexte = build_test_contexte()
    contexte.year = 2026

    resultat = calculer_salaire_brut(
        contexte,
        calendrier_saisie=_weekday_calendrier(2026, 4),
        date_debut_periode=date(2026, 4, 1),
        date_fin_periode=date(2026, 4, 30),
        primes_saisies=[
            {"libelle": "Prime exceptionnelle", "montant": 100.0, "prime_id": "x", "saisie_id": "s-1"},
            {"libelle": "Prime sans saisie", "montant": 50.0, "prime_id": "y"},
        ],
    )

    lignes = {l["libelle"]: l for l in resultat["lignes_composants_brut"]}
    assert lignes["Prime exceptionnelle"]["saisie_id"] == "s-1"
    assert "saisie_id" not in lignes["Prime sans saisie"]
```

- [ ] **Step 2 : vérifier l'échec**

Run: `cd backend && APP_ENV=test .venv/bin/python -m pytest tests/unit/payroll/test_lien_saisie.py -v`
Expected: ÉCHEC — `ModuleNotFoundError: No module named 'app.modules.payroll.engine.lien_saisie'`.

- [ ] **Step 3 : écrire l'aide**

`backend/app/modules/payroll/engine/lien_saisie.py` :

```python
"""Le lien entre une ligne de prime du bulletin et la saisie qui l'a produite.

Une prime saisie comme variable du mois (`monthly_inputs`) traverse le
générateur, la répartition soumise / non soumise, puis le calcul du brut. Son
identifiant doit arriver jusqu'à la ligne imprimée : c'est lui qui permet de
corriger ou de retirer cette prime depuis l'écran de modification du bulletin
(spec 2026-09-23). Les primes calculées par le moteur n'en portent pas.
"""

from __future__ import annotations

from typing import Any, Mapping


def lier_a_la_saisie(cible: dict[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
    """`cible` enrichie du `saisie_id` de `source`, s'il existe."""
    saisie_id = source.get("saisie_id")
    if saisie_id:
        cible["saisie_id"] = str(saisie_id)
    return cible
```

- [ ] **Step 4 : poser le lien à la source (générateurs)**

Dans `payslip_generator.py`, juste après la construction de `prime_entry` (le bloc `prime_entry = {"prime_id": prime_id, "libelle": row["name"], ...}`), ajouter :

```python
            if row.get("id"):
                prime_entry["saisie_id"] = str(row["id"])
```

Même ajout dans `payslip_generator_forfait.py`, juste après son `prime_entry = {...}`.

- [ ] **Step 5 : le propager (répartition puis lignes)**

Dans `payslip_run_heures.py` et `payslip_run_forfait.py`, remplacer :

```python
            prime_calculee = {
                "libelle": libelle,
                "montant": montant,
                "prime_id": prime_id,
            }
```

par :

```python
            prime_calculee = lier_a_la_saisie(
                {
                    "libelle": libelle,
                    "montant": montant,
                    "prime_id": prime_id,
                },
                saisie,
            )
```

avec, en tête de chaque fichier : `from app.modules.payroll.engine.lien_saisie import lier_a_la_saisie`.

Dans `calcul_brut.py` et `calcul_brut_forfait.py`, remplacer dans la boucle `for prime in primes_saisies:` :

```python
            lignes_composants_brut.append(
                {
                    "libelle": prime.get("libelle", "Prime"),
                    "quantite": None,
                    "taux": None,
                    "gain": prime.get("montant", 0.0),
                    "perte": None,
                }
            )
```

par :

```python
            lignes_composants_brut.append(
                lier_a_la_saisie(
                    {
                        "libelle": prime.get("libelle", "Prime"),
                        "quantite": None,
                        "taux": None,
                        "gain": prime.get("montant", 0.0),
                        "perte": None,
                    },
                    prime,
                )
            )
```

avec le même import en tête. Les primes non soumises sont imprimées telles que `prime_calculee` les porte : le lien y est donc déjà.

- [ ] **Step 6 : vérifier**

Run: `cd backend && APP_ENV=test .venv/bin/python -m pytest tests/unit/payroll -q && .venv/bin/ruff check app/modules/payroll tests/unit/payroll/test_lien_saisie.py`
Expected: suite verte (les trois nouveaux tests compris), `All checks passed!`.

- [ ] **Step 7 : proposer le commit**

```bash
git add backend/app/modules/payroll/engine/lien_saisie.py backend/app/modules/payroll/documents/payslip_generator.py backend/app/modules/payroll/documents/payslip_generator_forfait.py backend/app/modules/payroll/documents/payslip_run_heures.py backend/app/modules/payroll/documents/payslip_run_forfait.py backend/app/modules/payroll/engine/calcul_brut.py backend/app/modules/payroll/engine/calcul_brut_forfait.py backend/tests/unit/payroll/test_lien_saisie.py
git commit -m "feat(paie): chaque ligne de prime garde le lien vers sa saisie"
```

---

### Task 2 : le calcul pur des primes éditées

**Files:**
- Create: `backend/app/modules/payslips/domain/primes_editees.py`
- Test: `backend/tests/unit/payslips/test_primes_editees.py`

**Interfaces:**
- Consumes: le champ `saisie_id` des lignes (tâche 1) ; le bloc `nouvelle_saisie` posé par l'écran (tâche 4) : `{"name": str, "amount": float, "is_socially_taxed": bool, "is_taxable": bool, "catalog_prime_id": str | None}`.
- Produces:
  - `DiffPrimes(ajoutees: tuple[dict, ...], modifiees: tuple[tuple[str, float], ...], retirees: tuple[str, ...])`, dataclass figée, propriété `vide -> bool`, propriété `ids_touches -> set[str]` (modifiées ∪ retirées).
  - `diff_primes(avant: dict | None, apres: dict | None) -> DiffPrimes`.

- [ ] **Step 1 : écrire les tests qui échouent**

`backend/tests/unit/payslips/test_primes_editees.py` :

```python
"""Ce qui a changé dans les primes saisies entre deux versions d'un bulletin."""

import pytest

from app.modules.payslips.domain.primes_editees import diff_primes

pytestmark = pytest.mark.unit

BASE = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 14.28, "gain": 2165.85}


def _prime(saisie_id, gain, libelle="Prime exceptionnelle"):
    return {"libelle": libelle, "quantite": None, "taux": None, "gain": gain, "saisie_id": saisie_id}


def _bulletin(*lignes, non_soumises=()):
    return {"calcul_du_brut": [BASE, *lignes], "primes_non_soumises": list(non_soumises)}


NOUVELLE = {
    "libelle": "Prime de fin de chantier",
    "gain": 100.0,
    "nouvelle_saisie": {
        "name": "Prime de fin de chantier",
        "amount": 100.0,
        "is_socially_taxed": True,
        "is_taxable": True,
        "catalog_prime_id": None,
    },
}


def test_rien_ne_change_diff_vide():
    avant = _bulletin(_prime("s-1", 100.0))
    assert diff_primes(avant, _bulletin(_prime("s-1", 100.0))).vide


def test_une_prime_ajoutee_depuis_le_bulletin():
    diff = diff_primes(_bulletin(), _bulletin(NOUVELLE))

    assert diff.ajoutees == (
        {
            "name": "Prime de fin de chantier",
            "amount": 100.0,
            "is_socially_taxed": True,
            "is_taxable": True,
            "catalog_prime_id": None,
        },
    )
    assert not diff.modifiees and not diff.retirees


def test_le_montant_retouche_apres_ajout_fait_foi():
    retouchee = {**NOUVELLE, "gain": 120.0}
    assert diff_primes(_bulletin(), _bulletin(retouchee)).ajoutees[0]["amount"] == 120.0


def test_un_montant_corrige():
    diff = diff_primes(_bulletin(_prime("s-1", 100.0)), _bulletin(_prime("s-1", 150.0)))
    assert diff.modifiees == (("s-1", 150.0),)


def test_une_prime_retiree():
    diff = diff_primes(_bulletin(_prime("s-1", 100.0)), _bulletin())
    assert diff.retirees == ("s-1",)
    assert diff.ids_touches == {"s-1"}


def test_une_prime_non_soumise_se_lit_sur_son_montant():
    avant = _bulletin(non_soumises=[{"libelle": "Panier", "montant": 7.5, "saisie_id": "s-2"}])
    apres = _bulletin(non_soumises=[{"libelle": "Panier", "montant": 15.0, "saisie_id": "s-2"}])
    assert diff_primes(avant, apres).modifiees == (("s-2", 15.0),)


def test_une_ligne_calculee_retouchee_n_est_pas_une_prime():
    retouchee = {**BASE, "gain": 2000.0}
    assert diff_primes(_bulletin(), {"calcul_du_brut": [retouchee]}).vide


def test_un_lien_inconnu_du_bulletin_d_origine_est_ignore():
    """Un saisie_id absent d'avant n'a rien à corriger : on ne l'invente pas."""
    assert diff_primes(_bulletin(), _bulletin(_prime("s-9", 100.0))).vide


def test_ajout_et_retrait_dans_le_meme_enregistrement():
    diff = diff_primes(_bulletin(_prime("s-1", 100.0)), _bulletin(NOUVELLE))
    assert diff.retirees == ("s-1",)
    assert len(diff.ajoutees) == 1
```

- [ ] **Step 2 : vérifier l'échec**

Run: `cd backend && APP_ENV=test .venv/bin/python -m pytest tests/unit/payslips/test_primes_editees.py -v`
Expected: ÉCHEC — `ModuleNotFoundError: No module named 'app.modules.payslips.domain.primes_editees'`.

- [ ] **Step 3 : écrire le domaine**

`backend/app/modules/payslips/domain/primes_editees.py` :

```python
"""Les primes saisies qui ont changé entre deux versions d'un bulletin.

Pourquoi ce module : l'écran « Modifier le bulletin » laissait ajouter une
ligne de prime qui ne bougeait que le brut — ni bases, ni cotisations, ni
cumuls (retour de Gaëlle du 23/09/2026). Désormais une prime ajoutée, corrigée
ou retirée depuis le bulletin devient une variable du mois, et le moteur refait
tout (spec 2026-09-23).

On ne regarde que deux sortes de lignes, dans le brut et dans les primes non
soumises :

- celles qui portent `saisie_id` — imprimées par le moteur depuis une saisie ;
- celles qui portent `nouvelle_saisie` — ajoutées depuis le bulletin avec le
  sélecteur de primes.

Toute autre ligne (salaire de base, absence, prime d'ancienneté calculée) n'est
pas une prime saisie et reste hors du calcul.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

_SECTIONS = ("calcul_du_brut", "primes_non_soumises")
_TOLERANCE = 0.005


@dataclass(frozen=True)
class DiffPrimes:
    ajoutees: tuple[dict[str, Any], ...] = ()
    modifiees: tuple[tuple[str, float], ...] = ()
    retirees: tuple[str, ...] = ()

    @property
    def vide(self) -> bool:
        return not (self.ajoutees or self.modifiees or self.retirees)

    @property
    def ids_touches(self) -> set[str]:
        return {sid for sid, _ in self.modifiees} | set(self.retirees)


def _lignes(payslip_data: dict[str, Any] | None) -> Iterator[dict[str, Any]]:
    for section in _SECTIONS:
        for ligne in (payslip_data or {}).get(section) or []:
            if isinstance(ligne, dict) and not ligne.get("is_sous_total"):
                yield ligne


def _montant(ligne: dict[str, Any]) -> float:
    """Le brut porte `gain`, les primes non soumises `montant`."""
    for cle in ("gain", "montant"):
        valeur = ligne.get(cle)
        if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
            return round(float(valeur), 2)
    return 0.0


def _par_saisie(payslip_data: dict[str, Any] | None) -> dict[str, float]:
    return {
        str(ligne["saisie_id"]): _montant(ligne)
        for ligne in _lignes(payslip_data)
        if ligne.get("saisie_id")
    }


def diff_primes(avant: dict[str, Any] | None, apres: dict[str, Any] | None) -> DiffPrimes:
    """Ajoutées, montants corrigés et retirées, d'`avant` à `apres`."""
    ids_avant = _par_saisie(avant)
    ids_apres = _par_saisie(apres)

    ajoutees = tuple(
        {**ligne["nouvelle_saisie"], "amount": _montant(ligne)}
        for ligne in _lignes(apres)
        if isinstance(ligne.get("nouvelle_saisie"), dict)
    )
    modifiees = tuple(
        (sid, montant)
        for sid, montant in ids_apres.items()
        if sid in ids_avant and abs(montant - ids_avant[sid]) > _TOLERANCE
    )
    retirees = tuple(sid for sid in ids_avant if sid not in ids_apres)
    return DiffPrimes(ajoutees, modifiees, retirees)
```

- [ ] **Step 4 : vérifier**

Run: `cd backend && APP_ENV=test .venv/bin/python -m pytest tests/unit/payslips/test_primes_editees.py -v && .venv/bin/ruff check app/modules/payslips/domain/primes_editees.py tests/unit/payslips/test_primes_editees.py`
Expected: 9 tests verts, `All checks passed!`.

- [ ] **Step 5 : proposer le commit**

```bash
git add backend/app/modules/payslips/domain/primes_editees.py backend/tests/unit/payslips/test_primes_editees.py
git commit -m "feat(paie): savoir quelles primes ont change sur un bulletin edite"
```

---

### Task 3 : la commande écrit les variables du mois et régénère une fois

**Files:**
- Create: `backend/app/modules/payslips/application/primes_editees.py`
- Modify: `backend/app/modules/payslips/application/commands.py` (`_recalculer_apres_correction_heures_sup` et `edit_payslip`, vers les lignes 547-648)
- Modify: `backend/app/modules/payslips/schemas/responses.py` (`PayslipEditResponse`, ligne 150)
- Test: `backend/tests/unit/payslips/test_primes_depuis_le_bulletin.py`
- Test existant à garder vert : `backend/tests/unit/payslips/test_recalcul_heures_sup.py`

**Interfaces:**
- Consumes: `diff_primes`, `DiffPrimes` (tâche 2).
- Produces:
  - `verifier_appartenance(ids: set[str], *, employee_id: str, company_id: str, year: int, month: int) -> None` — lève `PayslipBadRequestError` si un id n'est pas une saisie de ce salarié, de cette société et de ce mois.
  - `appliquer_primes_editees(diff: DiffPrimes, *, employee_id: str, company_id: str, year: int, month: int) -> None` — insère, met à jour, supprime dans `monthly_inputs`.
  - `edit_payslip` rend le résultat de l'éditeur, enrichi de `recalcul_erreur: str` si la régénération a échoué.
  - `PayslipEditResponse.recalcul_erreur: Optional[str] = None`.

- [ ] **Step 1 : écrire les tests qui échouent**

`backend/tests/unit/payslips/test_primes_depuis_le_bulletin.py` :

```python
"""Une prime ajoutée, corrigée ou retirée sur le bulletin repasse par le moteur.

Retour de Gaëlle du 23/09/2026 : une prime ajoutée dans « Modifier le
bulletin » changeait le brut, mais ni le cumul brut ni les bases de
cotisations. Désormais elle devient une variable du mois et le bulletin est
recalculé (spec 2026-09-23).
"""

from unittest.mock import patch

import pytest

from app.modules.payslips.application.commands import edit_payslip
from app.modules.payslips.application.dto import EditPayslipInput, PayslipBadRequestError

pytestmark = pytest.mark.unit

BASE = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 14.28, "gain": 2165.85}
PRIME = {"libelle": "Prime exceptionnelle", "gain": 100.0, "saisie_id": "s-1"}
NOUVELLE = {
    "libelle": "Prime de fin de chantier",
    "gain": 100.0,
    "nouvelle_saisie": {
        "name": "Prime de fin de chantier",
        "amount": 100.0,
        "is_socially_taxed": True,
        "is_taxable": True,
        "catalog_prime_id": None,
    },
}
AVANT = {
    "id": "ps-1",
    "employee_id": "emp-1",
    "company_id": "comp-1",
    "year": 2026,
    "month": 8,
    "payslip_data": {"calcul_du_brut": [BASE, PRIME]},
}
MODULE = "app.modules.payslips.application.commands"


def _commande(*lignes):
    return EditPayslipInput(
        payslip_id="ps-1",
        payslip_data={"calcul_du_brut": [BASE, *lignes]},
        changes_summary="Prime",
        current_user_id="user-gaelle",
        current_user_name="Gaëlle",
    )


@pytest.fixture(autouse=True)
def _contexte():
    with patch(f"{MODULE}._fetch_payslip_status", return_value={"id": "ps-1", "status": "brouillon"}), patch(
        f"{MODULE}._fetch_payslip_for_recalc", return_value=AVANT
    ), patch(f"{MODULE}.payslip_editor_provider") as editeur:
        editeur.save_edited.return_value = {"status": "success", "message": "ok"}
        yield editeur


def test_ajouter_une_prime_ecrit_la_saisie_et_regenere_une_fois():
    with patch(f"{MODULE}.verifier_appartenance"), patch(
        f"{MODULE}.appliquer_primes_editees"
    ) as appliquer, patch(f"{MODULE}.generate_payslip") as regenerer:
        edit_payslip(_commande(PRIME, NOUVELLE))

    diff = appliquer.call_args.args[0]
    assert diff.ajoutees[0]["name"] == "Prime de fin de chantier"
    assert appliquer.call_args.kwargs == {
        "employee_id": "emp-1", "company_id": "comp-1", "year": 2026, "month": 8,
    }
    regenerer.assert_called_once()
    entree = regenerer.call_args.args[0]
    assert (entree.employee_id, entree.year, entree.month) == ("emp-1", 2026, 8)
    assert entree.force_calendrier_incomplet and entree.regenerer_bulletin_valide


def test_retirer_une_prime_retire_sa_saisie():
    with patch(f"{MODULE}.verifier_appartenance") as verifier, patch(
        f"{MODULE}.appliquer_primes_editees"
    ) as appliquer, patch(f"{MODULE}.generate_payslip"):
        edit_payslip(_commande())

    assert verifier.call_args.args[0] == {"s-1"}
    assert appliquer.call_args.args[0].retirees == ("s-1",)


def test_une_saisie_etrangere_est_refusee_avant_tout_enregistrement(_contexte):
    with patch(
        f"{MODULE}.verifier_appartenance", side_effect=PayslipBadRequestError("saisie inconnue")
    ), patch(f"{MODULE}.appliquer_primes_editees") as appliquer, patch(
        f"{MODULE}.generate_payslip"
    ) as regenerer:
        with pytest.raises(PayslipBadRequestError):
            edit_payslip(_commande())

    _contexte.save_edited.assert_not_called()
    appliquer.assert_not_called()
    regenerer.assert_not_called()


def test_retoucher_une_ligne_calculee_ne_recalcule_rien():
    retouchee = {**BASE, "gain": 2000.0}
    with patch(f"{MODULE}.appliquer_primes_editees") as appliquer, patch(
        f"{MODULE}.generate_payslip"
    ) as regenerer:
        edit_payslip(_commande(retouchee, PRIME))

    appliquer.assert_not_called()
    regenerer.assert_not_called()


def test_heures_sup_et_prime_ensemble_une_seule_regeneration():
    hs = {"libelle": "Heures suppl. majorées à 25%", "quantite": 4.0, "taux": 17.85, "gain": 71.4}
    with patch(f"{MODULE}.verifier_appartenance"), patch(f"{MODULE}.appliquer_primes_editees"), patch(
        f"{MODULE}._remplacer_heures_sup_declarees"
    ) as declarer, patch(f"{MODULE}.generate_payslip") as regenerer:
        edit_payslip(_commande(PRIME, NOUVELLE, hs))

    declarer.assert_called_once()
    regenerer.assert_called_once()


def test_un_echec_du_moteur_est_rendu_sans_perdre_la_saisie():
    with patch(f"{MODULE}.verifier_appartenance"), patch(
        f"{MODULE}.appliquer_primes_editees"
    ) as appliquer, patch(f"{MODULE}.generate_payslip", side_effect=RuntimeError("moteur KO")):
        resultat = edit_payslip(_commande(PRIME, NOUVELLE))

    appliquer.assert_called_once()
    assert "moteur KO" in resultat["recalcul_erreur"]
```

- [ ] **Step 2 : vérifier l'échec**

Run: `cd backend && APP_ENV=test .venv/bin/python -m pytest tests/unit/payslips/test_primes_depuis_le_bulletin.py -v`
Expected: ÉCHEC — `AttributeError: <module ...commands> does not have the attribute 'verifier_appartenance'`.

- [ ] **Step 3 : écrire l'application**

`backend/app/modules/payslips/application/primes_editees.py` :

```python
"""Écrire dans les variables du mois les primes éditées sur un bulletin.

Le calcul de ce qui a changé est pur (`domain.primes_editees`) ; ce module fait
les écritures dans `monthly_inputs`. La vérification d'appartenance est
séparée pour être faite **avant** d'enregistrer le bulletin : un identifiant
d'une autre fiche ne doit laisser aucune trace.
"""

from __future__ import annotations

import logging

from app.core.database import supabase
from app.modules.payslips.application.dto import PayslipBadRequestError
from app.modules.payslips.domain.primes_editees import DiffPrimes

logger = logging.getLogger(__name__)

MESSAGE_SAISIE_INCONNUE = (
    "Cette prime ne correspond à aucune variable du mois de ce bulletin : "
    "rechargez le bulletin avant de la modifier."
)


def verifier_appartenance(
    ids: set[str], *, employee_id: str, company_id: str, year: int, month: int
) -> None:
    """Chaque id doit être une saisie de ce salarié, de cette société, de ce mois."""
    if not ids:
        return
    r = (
        supabase.table("monthly_inputs")
        .select("id")
        .in_("id", sorted(ids))
        .match(
            {
                "employee_id": employee_id,
                "company_id": str(company_id),
                "year": year,
                "month": month,
            }
        )
        .execute()
    )
    connus = {str(row["id"]) for row in r.data or []}
    if ids - connus:
        raise PayslipBadRequestError(MESSAGE_SAISIE_INCONNUE)


def appliquer_primes_editees(
    diff: DiffPrimes, *, employee_id: str, company_id: str, year: int, month: int
) -> None:
    """Insère les primes ajoutées, corrige les montants, retire les primes supprimées."""
    base = {
        "employee_id": employee_id,
        "company_id": str(company_id),
        "year": year,
        "month": month,
    }
    if diff.ajoutees:
        supabase.table("monthly_inputs").insert([{**base, **p} for p in diff.ajoutees]).execute()
    for saisie_id, montant in diff.modifiees:
        supabase.table("monthly_inputs").update({"amount": montant}).eq("id", saisie_id).execute()
    for saisie_id in diff.retirees:
        supabase.table("monthly_inputs").delete().eq("id", saisie_id).execute()
    logger.info(
        "[edition] Primes du bulletin %s/%s de %s : %d ajoutée(s), %d corrigée(s), %d retirée(s).",
        month,
        year,
        employee_id,
        len(diff.ajoutees),
        len(diff.modifiees),
        len(diff.retirees),
    )
```

- [ ] **Step 4 : découper la déclaration des heures sup de la régénération**

Dans `commands.py`, renommer `_recalculer_apres_correction_heures_sup` en `_declarer_heures_sup_corrigees`, garder sa docstring et ses deux gardes, mais **retirer l'appel à `generate_payslip`** et le `logger.info` final ; la fonction rend `True` quand elle a écrit la déclaration :

```python
def _declarer_heures_sup_corrigees(cmd: EditPayslipInput, avant: dict[str, Any]) -> bool:
    """Redéclare au moteur les heures supplémentaires corrigées sur le bulletin.

    (docstring existante conservée, dernière phrase remplacée par :)
    Rend True si une déclaration a été écrite ; la régénération est faite une
    seule fois par `edit_payslip`, primes comprises.
    """
    heures_avant = quantites_heures_sup_conjoncturelles(avant.get("payslip_data"))
    heures_apres = quantites_heures_sup_conjoncturelles(cmd.payslip_data)
    if heures_apres == (0.0, 0.0):
        return False
    if abs(sum(heures_apres) - sum(heures_avant)) <= 0.001:
        return False
    _remplacer_heures_sup_declarees(
        employee_id=avant["employee_id"],
        company_id=avant["company_id"],
        year=avant["year"],
        month=avant["month"],
        heures_25=heures_apres[0],
        heures_50=heures_apres[1],
    )
    logger.info(
        "[edition] Heures supplémentaires corrigées au bulletin %s : %s -> %s.",
        cmd.payslip_id,
        heures_avant,
        heures_apres,
    )
    return True


def _regenerer(cmd: EditPayslipInput, avant: dict[str, Any]) -> str | None:
    """Recalcule le bulletin par le moteur ; rend le message d'erreur s'il échoue.

    Les variables du mois sont déjà écrites : elles sont la vérité. Un échec
    du moteur ne les défait pas, il est rendu pour que l'écran propose
    « Régénérer ».
    """
    try:
        generate_payslip(
            GeneratePayslipInput(
                employee_id=avant["employee_id"],
                year=avant["year"],
                month=avant["month"],
                # Le bulletin existe déjà : ces deux gardes ont été franchies à sa
                # première génération. Les réopposer bloquerait une correction.
                force_calendrier_incomplet=True,
                regenerer_bulletin_valide=True,
                requested_by=cmd.current_user_id,
                requested_by_name=cmd.current_user_name,
            )
        )
    except Exception as exc:  # noqa: BLE001 — l'erreur est rendue à l'écran
        logger.exception("[edition] Recalcul du bulletin %s impossible", cmd.payslip_id)
        return str(exc)
    return None
```

- [ ] **Step 5 : réécrire `edit_payslip`**

Ajouter aux imports de `commands.py` :

```python
from app.modules.payslips.application.primes_editees import (
    appliquer_primes_editees,
    verifier_appartenance,
)
from app.modules.payslips.domain.primes_editees import diff_primes
```

puis remplacer le corps d'`edit_payslip` par :

```python
    _refuser_si_importe(cmd.payslip_id)
    etait_valide = _etait_valide(cmd.payslip_id)
    avant = _fetch_payslip_for_recalc(cmd.payslip_id)
    diff = diff_primes(avant.get("payslip_data") if avant else None, cmd.payslip_data)
    periode = (
        {
            "employee_id": avant["employee_id"],
            "company_id": avant["company_id"],
            "year": avant["year"],
            "month": avant["month"],
        }
        if avant
        else None
    )
    # Avant d'enregistrer : une saisie d'une autre fiche ne doit laisser aucune trace.
    if periode and not diff.vide:
        verifier_appartenance(diff.ids_touches, **periode)

    result = payslip_editor_provider.save_edited(
        payslip_id=cmd.payslip_id,
        new_payslip_data=cmd.payslip_data,
        changes_summary=cmd.changes_summary,
        current_user_id=cmd.current_user_id,
        current_user_name=cmd.current_user_name,
        pdf_notes=cmd.pdf_notes,
        internal_note=cmd.internal_note,
    )
    if etait_valide:
        _set_payslip_status_brouillon(cmd.payslip_id)
        logger.warning(
            "[edition] Bulletin validé %s modifié par %s : repassé en brouillon.",
            cmd.payslip_id,
            cmd.current_user_id,
        )
    if not avant:
        return result
    # Après l'enregistrement : l'historique garde ainsi trace de la saisie
    # avant que le moteur ne réécrive le bulletin. Une seule régénération,
    # heures sup et primes comprises.
    a_recalculer = _declarer_heures_sup_corrigees(cmd, avant)
    if not diff.vide:
        appliquer_primes_editees(diff, **periode)
        a_recalculer = True
    if a_recalculer:
        erreur = _regenerer(cmd, avant)
        if erreur:
            result = {**result, "recalcul_erreur": erreur}
    return result
```

Compléter la docstring d'`edit_payslip` : « Ajouter, corriger ou retirer une prime saisie déclenche aussi un recalcul complet (spec 2026-09-23). »

- [ ] **Step 6 : déclarer le champ de réponse**

Dans `backend/app/modules/payslips/schemas/responses.py`, classe `PayslipEditResponse`, ajouter après `new_pdf_url: str` :

```python
    #: Présent si le moteur n'a pas pu recalculer après une prime ou des heures
    #: sup éditées : les variables du mois sont écrites, le bulletin reste la
    #: version saisie. Sans cette déclaration, FastAPI retirerait le champ.
    recalcul_erreur: Optional[str] = None
```

(vérifier que `Optional` est importé en tête du fichier ; sinon l'ajouter à l'import `typing`).

- [ ] **Step 7 : vérifier**

Run: `cd backend && APP_ENV=test .venv/bin/python -m pytest tests/unit/payslips -q && .venv/bin/ruff check app/modules/payslips tests/unit/payslips`
Expected: suite verte — les six nouveaux tests **et** `test_recalcul_heures_sup.py` inchangé (il patche `_remplacer_heures_sup_declarees` et `generate_payslip`, toujours appelés une fois) ; `All checks passed!`.

- [ ] **Step 8 : proposer le commit**

```bash
git add backend/app/modules/payslips/application/primes_editees.py backend/app/modules/payslips/application/commands.py backend/app/modules/payslips/schemas/responses.py backend/tests/unit/payslips/test_primes_depuis_le_bulletin.py
git commit -m "fix(paie): une prime editee sur le bulletin devient une variable du mois et recalcule"
```

---

### Task 4 : l'écran — « Ajouter une prime », bannière, avertissement

**Files:**
- Create: `frontend/src/components/payslip-edit/AjouterPrimeBouton.tsx`
- Create: `frontend/src/features/payroll/utils/primesEditees.ts`
- Create: `frontend/src/features/payroll/utils/primesEditees.test.ts`
- Modify: `frontend/src/components/payslip-edit/CalculBrutSection.tsx`
- Modify: `frontend/src/components/payslip-edit/PrimesNonSoumisesSection.tsx`
- Modify: `frontend/src/pages/rh/PayslipEdit.tsx`
- Modify: `frontend/src/api/payslips.ts` (`PayslipEditResponse`)

**Interfaces:**
- Consumes: `SaisieModal` (`components/SaisieModal.tsx`, `onSave(data: MonthlyInputCreate[])`), le contrat `nouvelle_saisie` de la tâche 2, `recalcul_erreur` de la tâche 3.
- Produces:
  - `ligneDepuisSaisie(saisie: MonthlyInputCreate): LignePrime` — ligne du brut avec `nouvelle_saisie`.
  - `primesEditees(avant: unknown, apres: unknown): boolean` — vrai si une prime saisie a été ajoutée, corrigée ou retirée (même règle que le serveur).
  - `<AjouterPrimeBouton employee year month onAjout />`.

- [ ] **Step 1 : écrire les tests qui échouent**

`frontend/src/features/payroll/utils/primesEditees.test.ts` :

```ts
import { describe, expect, it } from 'vitest';
import { ligneDepuisSaisie, primesEditees } from './primesEditees';

const base = { libelle: 'Salaire de base', quantite: 151.67, taux: 14.28, gain: 2165.85 };
const prime = { libelle: 'Prime exceptionnelle', gain: 100, saisie_id: 's-1' };

describe('ligneDepuisSaisie', () => {
  it('porte la saisie à créer et son montant', () => {
    const ligne = ligneDepuisSaisie({
      employee_id: 'emp-1',
      year: 2026,
      month: 8,
      name: 'Prime de fin de chantier',
      amount: 100,
      is_socially_taxed: true,
      is_taxable: true,
    });
    expect(ligne.libelle).toBe('Prime de fin de chantier');
    expect(ligne.gain).toBe(100);
    expect(ligne.nouvelle_saisie).toEqual({
      name: 'Prime de fin de chantier',
      amount: 100,
      is_socially_taxed: true,
      is_taxable: true,
      catalog_prime_id: null,
    });
  });
});

describe('primesEditees', () => {
  it('rien ne change', () => {
    expect(primesEditees({ calcul_du_brut: [base, prime] }, { calcul_du_brut: [base, prime] })).toBe(false);
  });
  it('un montant corrigé', () => {
    expect(
      primesEditees({ calcul_du_brut: [base, prime] }, { calcul_du_brut: [base, { ...prime, gain: 150 }] })
    ).toBe(true);
  });
  it('une prime retirée', () => {
    expect(primesEditees({ calcul_du_brut: [base, prime] }, { calcul_du_brut: [base] })).toBe(true);
  });
  it('une prime ajoutée', () => {
    const nouvelle = { libelle: 'X', gain: 10, nouvelle_saisie: { name: 'X', amount: 10 } };
    expect(primesEditees({ calcul_du_brut: [base] }, { calcul_du_brut: [base, nouvelle] })).toBe(true);
  });
  it('une ligne calculée retouchée n’en est pas une', () => {
    expect(
      primesEditees({ calcul_du_brut: [base] }, { calcul_du_brut: [{ ...base, gain: 2000 }] })
    ).toBe(false);
  });
});
```

- [ ] **Step 2 : vérifier l'échec**

Run: `cd frontend && npx vitest run src/features/payroll/utils/primesEditees.test.ts`
Expected: ÉCHEC — `Failed to resolve import "./primesEditees"`.

- [ ] **Step 3 : écrire l'utilitaire**

`frontend/src/features/payroll/utils/primesEditees.ts` :

```ts
/**
 * Primes saisies éditées depuis le bulletin (spec 2026-09-23).
 *
 * Une prime ajoutée, corrigée ou retirée sur le bulletin devient une variable
 * du mois et le serveur fait recalculer tout le bulletin. Seules comptent les
 * lignes qui portent `saisie_id` (imprimées depuis une saisie) ou
 * `nouvelle_saisie` (ajoutées ici) — même règle que
 * `backend/app/modules/payslips/domain/primes_editees.py`, avec laquelle
 * cette fonction doit rester d'accord.
 */
import type { MonthlyInputCreate } from '@/api/saisies';

const SECTIONS = ['calcul_du_brut', 'primes_non_soumises'] as const;

export interface NouvelleSaisie {
  name: string;
  amount: number;
  is_socially_taxed: boolean;
  is_taxable: boolean;
  catalog_prime_id: string | null;
}

export interface LignePrime {
  libelle: string;
  quantite: null;
  taux: null;
  gain: number;
  perte: null;
  is_sous_total: false;
  nouvelle_saisie: NouvelleSaisie;
}

export function ligneDepuisSaisie(saisie: MonthlyInputCreate): LignePrime {
  const montant = Number(saisie.amount) || 0;
  return {
    libelle: saisie.name,
    quantite: null,
    taux: null,
    gain: montant,
    perte: null,
    is_sous_total: false,
    nouvelle_saisie: {
      name: saisie.name,
      amount: montant,
      is_socially_taxed: saisie.is_socially_taxed ?? true,
      is_taxable: saisie.is_taxable ?? true,
      catalog_prime_id: saisie.catalog_prime_id ?? null,
    },
  };
}

type Ligne = Record<string, unknown>;

function lignes(data: unknown): Ligne[] {
  const d = (data ?? {}) as Record<string, unknown>;
  return SECTIONS.flatMap((s) => (Array.isArray(d[s]) ? (d[s] as Ligne[]) : [])).filter(
    (l) => l && typeof l === 'object' && !l.is_sous_total
  );
}

function montant(l: Ligne): number {
  const v = typeof l.gain === 'number' ? l.gain : l.montant;
  return typeof v === 'number' ? Math.round(v * 100) / 100 : 0;
}

function parSaisie(data: unknown): Map<string, number> {
  return new Map(
    lignes(data)
      .filter((l) => l.saisie_id)
      .map((l) => [String(l.saisie_id), montant(l)])
  );
}

export function primesEditees(avant: unknown, apres: unknown): boolean {
  if (lignes(apres).some((l) => l.nouvelle_saisie && typeof l.nouvelle_saisie === 'object')) return true;
  const a = parSaisie(avant);
  const b = parSaisie(apres);
  for (const [id, m] of a) {
    if (!b.has(id) || Math.abs((b.get(id) ?? 0) - m) > 0.005) return true;
  }
  return false;
}
```

(Si `MonthlyInputCreate` n'est pas exporté par `@/api/saisies`, l'exporter depuis ce fichier : c'est le type déjà utilisé par `SaisieModal`.)

- [ ] **Step 4 : vérifier**

Run: `cd frontend && npx vitest run src/features/payroll/utils/primesEditees.test.ts`
Expected: 6 tests verts.

- [ ] **Step 5 : le bouton**

`frontend/src/components/payslip-edit/AjouterPrimeBouton.tsx` :

```tsx
import { useState } from 'react';
import { PlusCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SaisieModal } from '@/components/SaisieModal';
import type { MonthlyInputCreate } from '@/api/saisies';
import { ligneDepuisSaisie, type LignePrime } from '@/features/payroll/utils/primesEditees';

interface Props {
  employee: { id: string; first_name: string; last_name: string; job_title: string };
  year: number;
  month: number;
  onAjout: (lignes: LignePrime[]) => void;
}

/** Même sélecteur que l'onglet Primes : catalogue ou prime libre avec ses cases. */
export default function AjouterPrimeBouton({ employee, year, month, onAjout }: Props) {
  const [ouvert, setOuvert] = useState(false);
  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOuvert(true)} data-testid="ajouter-prime">
        <PlusCircle className="h-4 w-4 mr-2" />
        Ajouter une prime
      </Button>
      <SaisieModal
        isOpen={ouvert}
        onClose={() => setOuvert(false)}
        onSave={(saisies: MonthlyInputCreate[]) => {
          onAjout(saisies.map(ligneDepuisSaisie));
          setOuvert(false);
        }}
        employees={[employee]}
        employeeScopeId={employee.id}
        year={year}
        month={month}
      />
    </>
  );
}
```

- [ ] **Step 6 : brancher la section du brut**

Dans `CalculBrutSection.tsx` :

1. Ajouter aux props `employee`, `year`, `month` (même forme que `AjouterPrimeBouton`) et `primesModifiees: boolean`.
2. Remplacer le bouton qui appelle `handleAddLine` par :

```tsx
<AjouterPrimeBouton
  employee={employee}
  year={year}
  month={month}
  onAjout={(nouvelles) => {
    const newData = [...data, ...nouvelles];
    onChange(newData, recalculateBrut(newData));
  }}
/>
```

et supprimer `handleAddLine`.
3. Dans `marquerRetouche`, ne pas marquer `autreLigneRetouchee` pour une ligne qui porte `saisie_id` : passer la ligne entière et tester `ligne?.saisie_id` avant le test des heures sup.
4. Ajouter, à côté de l'alerte `info-recalcul-heures-sup`, une alerte d'information quand `primesModifiees` :

```tsx
{primesModifiees && (
  <Alert data-testid="info-recalcul-primes">
    <RefreshCw className="h-4 w-4" />
    <AlertTitle>Le bulletin sera recalculé</AlertTitle>
    <AlertDescription>
      À l’enregistrement, la prime devient une variable du mois : bases, cotisations,
      net et cumuls suivront. Elle apparaîtra aussi dans l’onglet Primes.
    </AlertDescription>
  </Alert>
)}
```

5. Compléter l'avertissement rouge existant : « Les cotisations, le net imposable, le net à payer **et les cumuls** restent ceux du calcul d’origine » ; et, quand `primesModifiees && autreLigneRetouchee`, ajouter la phrase : « Cette retouche sera remplacée par le recalcul déclenché par la prime : enregistrez-la séparément. »

- [ ] **Step 7 : la section des primes non soumises**

Dans `PrimesNonSoumisesSection.tsx`, supprimer le bouton d'ajout libre (« Nouvelle prime non soumise ») et le remplacer par la phrase : « Pour ajouter une prime non soumise, utilisez « Ajouter une prime » dans le calcul du brut et décochez *soumise à cotisations* : le moteur la rangera ici. » La correction du montant et la suppression d'une ligne restent possibles.

- [ ] **Step 8 : la page**

Dans `PayslipEdit.tsx` :

1. Passer à `CalculBrutSection` : `employee` (depuis `payslip` : `{ id: payslip.employee_id, first_name: payslip.employee_first_name ?? '', last_name: payslip.employee_last_name ?? '', job_title: '' }` — utiliser les champs réellement présents sur `PayslipDetail`), `year={payslip.year}`, `month={payslip.month}`, `primesModifiees={primesEditees(payslip.payslip_data, editedData)}`.
2. Dans `handleSave`, après `const response = await editPayslip(...)` :

```ts
if (response.recalcul_erreur) {
  toast({
    title: 'Primes enregistrées, recalcul impossible',
    description: `Les variables du mois sont à jour mais le bulletin n’a pas pu être recalculé (${response.recalcul_erreur}). Utilisez « Régénérer ».`,
    variant: 'destructive',
  });
}
```

3. Dans `frontend/src/api/payslips.ts`, ajouter à `PayslipEditResponse` : `recalcul_erreur?: string | null;`.

- [ ] **Step 9 : vérifier**

Run: `cd frontend && npm run typecheck && npx vitest run && npx eslint src/components/payslip-edit src/features/payroll/utils/primesEditees.ts src/pages/rh/PayslipEdit.tsx`
Expected: aucune **nouvelle** erreur de type par rapport à la ligne de base (`npm run typecheck` avant les changements en a 113 : noter le compte avant et après, il ne doit pas augmenter) ; vitest vert ; eslint propre sur les fichiers touchés.

- [ ] **Step 10 : proposer le commit**

```bash
git add frontend/src/components/payslip-edit frontend/src/features/payroll/utils/primesEditees.ts frontend/src/features/payroll/utils/primesEditees.test.ts frontend/src/pages/rh/PayslipEdit.tsx frontend/src/api/payslips.ts
git commit -m "feat(frontend): ajouter une prime depuis le bulletin avec le selecteur de l'onglet Primes"
```

---

### Task 5 : le critère de réussite, sur le test

**Files:**
- Create: `backend/scripts/verif_prime_depuis_le_bulletin.py`

**Interfaces:**
- Consumes: tout ce qui précède, déployé sur le test (`gh workflow run deploy-test-env.yml --ref fix/payslip-edit-state`, avec l'accord d'Alexandre).

- [ ] **Step 1 : écrire le contrôle**

`backend/scripts/verif_prime_depuis_le_bulletin.py` — sur un bulletin d'août Colorplast en **brouillon** (Cotte), le script :

1. sauvegarde `payslip_data` et les `monthly_inputs` d'août du salarié ;
2. **chemin A** : insère une saisie « Prime contrôle » de 100 € soumise et imposable, régénère par `generate_payslip`, relève brut, bases (`structure_cotisations`), total des cotisations, net à payer, `cumuls` ;
3. restaure ;
4. **chemin B** : appelle `edit_payslip` avec le bulletin courant plus une ligne `ligneDepuisSaisie` équivalente (même `nouvelle_saisie`), relève les mêmes valeurs ;
5. restaure (bulletin et saisies), relit pour vérifier la restauration ;
6. imprime les deux relevés côte à côte et sort en erreur si un seul champ diffère de plus d'un centime.

```python
"""Critère de la spec 2026-09-23 : une prime ajoutée depuis le bulletin donne,
au centime, le même bulletin que la même prime saisie dans l'onglet Primes.

Sur le TEST, un bulletin d'août Colorplast en brouillon ; tout est restauré.
Usage : python -m scripts.verif_prime_depuis_le_bulletin [--salarie COTTE]
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SOCIETE = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
ANNEE, MOIS = 2026, 8
PRIME = {
    "name": "Prime contrôle",
    "amount": 100.0,
    "is_socially_taxed": True,
    "is_taxable": True,
    "catalog_prime_id": None,
}


def _releve(ps: dict) -> dict:
    d = ps["payslip_data"]
    cumuls = ((d.get("cumuls") or {}).get("cumuls") or {})
    return {
        "brut": round(float(d.get("salaire_brut") or 0), 2),
        "net_a_payer": round(float(d.get("net_a_payer") or 0), 2),
        "cotis_sal": round(sum(float(l.get("montant_salarial") or 0)
                               for l in (d.get("structure_cotisations") or {}).get("lignes") or []), 2),
        "cumul_brut": round(float(cumuls.get("brut_total") or cumuls.get("salaire_brut") or 0), 2),
    }


def main() -> int:
    from app.core.database import supabase
    from app.modules.payslips.application.commands import edit_payslip, generate_payslip
    from app.modules.payslips.application.dto import EditPayslipInput, GeneratePayslipInput

    nom = sys.argv[sys.argv.index("--salarie") + 1] if "--salarie" in sys.argv else "COTTE"
    emp = next(e for e in supabase.table("employees").select("id, last_name")
               .eq("company_id", SOCIETE).execute().data if e["last_name"] == nom)
    eid = str(emp["id"])

    def bulletin() -> dict:
        return (supabase.table("payslips").select("*").eq("employee_id", eid)
                .eq("year", ANNEE).eq("month", MOIS).single().execute().data)

    def saisies() -> list:
        return (supabase.table("monthly_inputs").select("*").eq("employee_id", eid)
                .eq("year", ANNEE).eq("month", MOIS).execute().data or [])

    origine = bulletin()
    if origine.get("status") != "brouillon":
        print(f"!! bulletin {nom} {MOIS:02d}/{ANNEE} non brouillon — rien n'est fait")
        return 1
    saisies_origine = saisies()

    def restaurer() -> None:
        actuelles = {s["id"] for s in saisies()}
        for sid in actuelles - {s["id"] for s in saisies_origine}:
            supabase.table("monthly_inputs").delete().eq("id", sid).execute()
        supabase.table("payslips").update({"payslip_data": origine["payslip_data"]}).eq("id", origine["id"]).execute()

    regen = GeneratePayslipInput(employee_id=eid, year=ANNEE, month=MOIS,
                                 force_calendrier_incomplet=True, regenerer_bulletin_valide=True)
    try:
        supabase.table("monthly_inputs").insert(
            {**PRIME, "employee_id": eid, "company_id": SOCIETE, "year": ANNEE, "month": MOIS}).execute()
        generate_payslip(regen)
        a = _releve(bulletin())
        restaurer()

        data = copy.deepcopy(origine["payslip_data"])
        data.setdefault("calcul_du_brut", []).append({
            "libelle": PRIME["name"], "quantite": None, "taux": None, "gain": PRIME["amount"],
            "perte": None, "is_sous_total": False, "nouvelle_saisie": dict(PRIME)})
        edit_payslip(EditPayslipInput(payslip_id=origine["id"], payslip_data=data,
                                      changes_summary="contrôle", current_user_id="script",
                                      current_user_name="script"))
        b = _releve(bulletin())
    finally:
        restaurer()

    ecarts = {k: (a[k], b[k]) for k in a if abs(a[k] - b[k]) > 0.01}
    for k in a:
        print(f"  {k:12s} onglet Primes {a[k]:>10.2f}   depuis le bulletin {b[k]:>10.2f}")
    print("IDENTIQUES au centime" if not ecarts else f"!! ÉCARTS : {ecarts}")
    return 1 if ecarts else 0


if __name__ == "__main__":
    sys.exit(main())
```

Remarque : vérifier sur un vrai bulletin les clés exactes du cumul brut et des lignes de cotisations (`structure_cotisations`, `cumuls.cumuls`) avant de lancer, et ajuster `_releve` si les noms diffèrent — le script doit comparer des champs réellement remplis, pas deux zéros.

- [ ] **Step 2 : lancer en arrière-plan**

Run: `cd backend && APP_ENV=test .venv/bin/python -m scripts.verif_prime_depuis_le_bulletin` (arrière-plan)
Expected: `IDENTIQUES au centime`, et un bulletin de Cotte restauré à l'identique.

- [ ] **Step 3 : proposer le commit**

```bash
git add backend/scripts/verif_prime_depuis_le_bulletin.py
git commit -m "chore(paie): controle prime depuis le bulletin contre onglet Primes"
```
