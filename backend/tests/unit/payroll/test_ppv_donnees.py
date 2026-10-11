"""Ce que le générateur lit pour ranger une PPV. [G3]

Les PPV déjà versées dans l'année (variables des mois d'avant, par leur nature),
la rémunération moyenne des 12 mois qui précèdent le versement (bulletins
enregistrés) et l'accord d'intéressement de la société. Rien n'est lu quand le
mois n'a pas de PPV.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.payroll.documents import ppv_donnees

pytestmark = pytest.mark.unit


class _Requete:
    def __init__(self, nom: str, base: "_Base"):
        self._nom = nom
        self._base = base
        self._lignes = list(base.tables.get(nom, []))

    def select(self, *_a, **_k):
        return self

    def eq(self, colonne, valeur):
        self._lignes = [l for l in self._lignes if l.get(colonne) == valeur]
        return self

    def in_(self, colonne, valeurs):
        self._lignes = [l for l in self._lignes if l.get(colonne) in valeurs]
        return self

    def lt(self, colonne, valeur):
        self._lignes = [l for l in self._lignes if l.get(colonne) < valeur]
        return self

    def execute(self):
        self._base.lues.append(self._nom)
        return type("R", (), {"data": self._lignes})()


class _Base:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]):
        self.tables = tables
        self.lues: list[str] = []

    def table(self, nom):
        return _Requete(nom, self)


def _variable(mois: int, nom: str, montant: float, **extra) -> dict[str, Any]:
    return {"employee_id": "e1", "year": 2026, "month": mois, "name": nom, "amount": montant, **extra}


def _bulletin(annee: int, mois: int, brut: float) -> dict[str, Any]:
    return {"employee_id": "e1", "year": annee, "month": mois, "salaire_brut": brut}


PPV_DU_MOIS = [_variable(9, "Prime de partage de la valeur", 100.0, catalog_prime_id="prime_partage_valeur")]


def test_les_ppv_de_l_annee_et_la_remuneration_des_12_mois():
    base = _Base(
        {
            "monthly_inputs": [
                _variable(3, "Prime exceptionnelle", 500.0),
                _variable(7, "PPV juillet", 100.0),
                _variable(9, "Prime de partage de la valeur", 100.0),  # le mois même : pas « déjà versée »
            ],
            "payslips": [
                _bulletin(2025, 8, 9999.0),  # hors des 12 mois (sept. 2025 à août 2026)
                _bulletin(2025, 9, 2000.0),
                _bulletin(2026, 8, 3000.0),
            ],
        }
    )
    donnees = ppv_donnees.donnees_ppv_du_mois(
        base, "e1", 2026, 9, {"settings": {"ppv_accord_interessement": True}}, PPV_DU_MOIS
    )

    assert donnees["deja_versees"] == [100.0]
    assert donnees["remuneration_mensuelle_moyenne"] == pytest.approx(2500.0)
    assert donnees["accord_interessement"] is True


def test_sans_ppv_dans_le_mois_rien_n_est_lu():
    base = _Base({})
    assert (
        ppv_donnees.donnees_ppv_du_mois(
            base, "e1", 2026, 9, {}, [_variable(9, "Prime exceptionnelle", 100.0)]
        )
        is None
    )
    assert base.lues == []


def test_sans_bulletin_avant_la_remuneration_reste_inconnue():
    base = _Base({"monthly_inputs": [], "payslips": []})
    donnees = ppv_donnees.donnees_ppv_du_mois(base, "e1", 2026, 9, {}, PPV_DU_MOIS)

    assert donnees["remuneration_mensuelle_moyenne"] is None
    assert donnees["accord_interessement"] is False
