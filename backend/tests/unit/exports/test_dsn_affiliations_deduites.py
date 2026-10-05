"""L'assemblage des données DSN déduit les affiliations d'un salarié qui n'en a pas.

C'est le chemin de l'export à l'écran et des scripts : la déduction s'y fait
au moment de l'export, sans rien écrire en base.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_dsn

pytestmark = pytest.mark.unit

PREVOYANCE_NC = {"id_contrat": "1", "option": "OPT1", "population": "02"}
SANTE = {"id_contrat": "2", "option": "ISO", "population": "00"}


def _salarie(identifiant: str, *, adherent: bool, affiliations=None, **autres) -> Dict[str, Any]:
    specificites: Dict[str, Any] = {"mutuelle": {"adhesion": adherent}}
    if affiliations is not None:
        specificites["affiliations_psc"] = affiliations
    return {
        "id": identifiant,
        "company_id": "c1",
        "first_name": "Prénom",
        "last_name": f"Fictif{identifiant}",
        "statut": "Non-Cadre",
        "contract_type": "CDI",
        "specificites_paie": specificites,
        **autres,
    }


ANCIEN_ADHERENT = _salarie(
    "a1",
    adherent=True,
    affiliations=[
        {**PREVOYANCE_NC, "id_affiliation": "1"},
        {**SANTE, "id_affiliation": "2"},
    ],
)
ANCIEN_DISPENSE = _salarie(
    "a2", adherent=False, affiliations=[{**PREVOYANCE_NC, "id_affiliation": "1"}]
)


class _Requete:
    def __init__(self, lignes: List[Dict[str, Any]]):
        self._lignes = lignes

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, colonne, valeur):
        return _Requete([l for l in self._lignes if l.get(colonne, valeur) == valeur])

    def in_(self, colonne, valeurs):
        return _Requete([l for l in self._lignes if l.get(colonne) in valeurs])

    def execute(self):
        return type("Reponse", (), {"data": copy.deepcopy(self._lignes)})()


class _Base:
    """Lecture seule : aucune méthode d'écriture n'existe."""

    def __init__(self, tables: Dict[str, List[Dict[str, Any]]]):
        self._tables = tables

    def table(self, nom):
        return _Requete(self._tables.get(nom, []))


def _assembler(salaries, employee_ids=None, period="2026-10"):
    annee, mois = map(int, period.split("-"))
    bulletins = [
        {
            "id": f"p-{s['id']}",
            "employee_id": s["id"],
            "company_id": "c1",
            "year": annee,
            "month": mois,
            "payslip_data": {"salaire_brut": 2000.0, "synthese_net": {}},
        }
        for s in salaries
    ]
    base = _Base({"employees": salaries, "payslips": bulletins})
    with patch.object(export_dsn, "supabase", base), patch.object(
        export_dsn, "_evenements_dsn", lambda *a, **k: {}
    ), patch.object(export_dsn.oeth_queries, "get_boeth_code_for_employee", lambda *a: None):
        donnees, _ = export_dsn.get_dsn_employees_data("c1", period, employee_ids)
    return {d["employee"]["id"]: d["employee"] for d in donnees}


def test_un_embauche_adherent_recoit_les_affiliations_de_ses_collegues():
    nouveau = _salarie("n1", adherent=True)
    fiches = _assembler([ANCIEN_ADHERENT, ANCIEN_DISPENSE, nouveau])
    assert fiches["n1"]["affiliations_psc"] == [
        {"id_affiliation": "1", "id_contrat": "1", "option": "OPT1", "population": "02"},
        {"id_affiliation": "2", "id_contrat": "2", "option": "ISO", "population": "00"},
    ]
    assert fiches["n1"]["affiliations_psc_deduites"] is True
    # Rien n'est posé dans la fiche elle-même.
    assert "affiliations_psc" not in fiches["n1"]["specificites_paie"]


def test_un_embauche_dispense_ne_recoit_que_la_prevoyance():
    nouveau = _salarie("n1", adherent=False)
    fiches = _assembler([ANCIEN_ADHERENT, ANCIEN_DISPENSE, nouveau])
    assert fiches["n1"]["affiliations_psc"] == [
        {"id_affiliation": "1", "id_contrat": "1", "option": "OPT1", "population": "02"},
    ]


def test_l_adhesion_du_mois_suit_la_surcharge_mensuelle():
    nouveau = _salarie("n1", adherent=False)
    nouveau["specificites_paie"]["overrides_mensuels"] = {
        "2026-10": {"mutuelle": {"adhesion": True}}
    }
    fiches = _assembler([ANCIEN_ADHERENT, ANCIEN_DISPENSE, nouveau])
    assert len(fiches["n1"]["affiliations_psc"]) == 2


def test_un_export_restreint_au_salarie_lit_quand_meme_ses_collegues():
    nouveau = _salarie("n1", adherent=True)
    fiches = _assembler([ANCIEN_ADHERENT, ANCIEN_DISPENSE, nouveau], employee_ids=["n1"])
    assert list(fiches) == ["n1"]
    assert len(fiches["n1"]["affiliations_psc"]) == 2


def test_un_salarie_repris_garde_ses_affiliations():
    fiches = _assembler([ANCIEN_ADHERENT, ANCIEN_DISPENSE, _salarie("n1", adherent=True)])
    assert "affiliations_psc" not in fiches["a1"]
    assert "affiliations_psc_deduites" not in fiches["a1"]


def test_sans_collegue_comparable_rien_n_est_deduit():
    cadre = _salarie("n1", adherent=True, statut="Cadre")
    fiches = _assembler([ANCIEN_ADHERENT, ANCIEN_DISPENSE, cadre])
    assert "affiliations_psc" not in fiches["n1"]
    assert "affiliations_psc_deduites" not in fiches["n1"]
