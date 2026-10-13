"""Les textes des départs accordent le nombre : « 1 jour », « 2 jours » (relevé H, 12/10/2026).

Le dossier d'une fin de période d'essai disait « après 1 jours de présence »,
« 0 jours jusqu'au dernier jour travaillé », « Délai non respecté de 1 jours »,
« / 30 × 1 jours », « Congés acquis […] : 0,08 jours ». Le singulier vaut pour
0 et 1 (et 0,08), le pluriel dès 2 (app/shared/domain/pluriel.py).

La garde lit les textes des départs (dossier, préavis, reçu, attestation,
certificat) : aucun nombre n'y est suivi de « jours » ou « ans » écrit en dur.
Les journaux ne sont pas montrés ; l'âge d'un départ à la retraite (60 ans et
plus) est toujours pluriel.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from app.modules.payroll.engine.calcul_indemnites_sortie import (
    calculer_indemnite_depart_retraite,
    calculer_indemnites_sortie,
)
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

APP = Path(__file__).resolve().parents[3] / "app"

FICHIERS = [
    "modules/payroll/engine/calcul_indemnites_sortie.py",
    "modules/employee_exits/domain/notice_period.py",
    "modules/employee_exits/application/commands.py",
    "modules/payroll/solde_de_tout_compte/common/socle_commun.py",
    "modules/payroll/solde_de_tout_compte/document_generator.py",
    "modules/payroll/solde_de_tout_compte/cases/licenciement.py",
    "modules/payroll/solde_de_tout_compte/cases/retraite.py",
    "modules/payroll/solde_de_tout_compte/cases/rupture_conventionnelle.py",
    "modules/payroll/documents/attestation_employeur_generator.py",
]

MOT_EN_DUR = re.compile(r"^ (jours|ans)\b")


def _textes_avec_nombre_en_dur(fichier: str) -> list[str]:
    arbre = ast.parse((APP / fichier).read_text(encoding="utf-8"))
    parents = {enfant: noeud for noeud in ast.walk(arbre) for enfant in ast.iter_child_nodes(noeud)}
    fautes = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.JoinedStr):
            continue
        parent = parents.get(noeud)
        while parent is not None and not isinstance(parent, ast.Call):
            parent = parents.get(parent)
        if parent is not None and "log" in ast.unparse(parent.func):
            continue
        for valeur, suite in zip(noeud.values, noeud.values[1:]):
            if not (isinstance(valeur, ast.FormattedValue) and isinstance(suite, ast.Constant)):
                continue
            expression = ast.unparse(valeur.value)
            if expression.lower().startswith("age"):
                continue
            if MOT_EN_DUR.match(str(suite.value)):
                fautes.append(f"{fichier}:{noeud.lineno} : {{{expression}}}{suite.value[:30]}")
    return fautes


def test_aucun_nombre_suivi_de_jours_ou_ans_ecrit_en_dur():
    fautes = [faute for fichier in FICHIERS for faute in _textes_avec_nombre_en_dur(fichier)]
    assert fautes == []


_ICCP = "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"


@patch(_ICCP, return_value={"montant": 0.0, "description": "ICCP", "details": {}})
def test_le_delai_de_prevenance_d_un_jour_s_ecrit_au_singulier(_iccp):
    salarie = {
        "id": "emp-1",
        "hire_date": "2026-10-12",
        "contract_type": "CDI",
        "salaire_de_base": {"valeur": 2000.0},
        "duree_hebdomadaire": 35,
        "baremes": {"pss": {"annuel": 48060.0}},
    }
    depart = {
        "id": "exit-1",
        "exit_type": "fin_periode_essai",
        "exit_request_date": "2026-10-12",
        "last_working_day": "2026-10-12",
        "notice_period_days": 0,
        "notice_indemnity_type": "not_applicable",
        "exit_notes": {"probation_ended_by": "employer"},
    }
    calcul = calculer_indemnites_sortie(salarie, depart, BaseEnMemoire({}))["indemnite_delai_prevenance"]["calcul"]

    assert "après 1 jour de présence" in calcul
    assert "0 jour jusqu'au dernier jour travaillé" in calcul
    assert "Délai non respecté de 1 jour :" in calcul
    assert "/ 30 × 1 jour = 66,67 €" in calcul
    assert re.search(r"temps non exécuté : 0,\d+ jour,", calcul)
    assert "jours" not in calcul.replace("jours civils", "")


def test_l_anciennete_d_un_an_s_ecrit_au_singulier():
    assert calculer_indemnite_depart_retraite(12, 2000.0)["calcul"].startswith("Ancienneté de 1 an :")
    assert calculer_indemnite_depart_retraite(30, 2000.0)["calcul"].startswith("Ancienneté de 2 ans :")
