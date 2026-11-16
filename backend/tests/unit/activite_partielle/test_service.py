"""Activité partielle : la pose des heures chômées du mois (base en mémoire)."""

from __future__ import annotations

import pytest

import app.modules.activite_partielle.application.service as svc


class _Requete:
    def __init__(self, base, table):
        self.base, self.table, self.filtres, self.op, self.donnees = (
            base,
            table,
            [],
            "select",
            None,
        )

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self.filtres.append(lambda r: str(r.get(col)) == str(val))
        return self

    def in_(self, col, vals):
        vals = {str(v) for v in vals}
        self.filtres.append(lambda r: str(r.get(col)) in vals)
        return self

    def insert(self, rows):
        self.op, self.donnees = "insert", rows if isinstance(rows, list) else [rows]
        return self

    def upsert(self, row, on_conflict=None):
        self.op, self.donnees = "upsert", row
        return self

    def delete(self):
        self.op = "delete"
        return self

    def execute(self):
        rows = self.base.setdefault(self.table, [])
        ok = [r for r in rows if all(f(r) for f in self.filtres)]
        if self.op == "insert":
            for r in self.donnees:
                rows.append({**r, "id": f"{self.table}-{len(rows)}"})
            return type("R", (), {"data": self.donnees})
        if self.op == "upsert":
            rows[:] = [
                r for r in rows if r.get("company_id") != self.donnees["company_id"]
            ]
            rows.append(dict(self.donnees))
            return type("R", (), {"data": [self.donnees]})
        if self.op == "delete":
            rows[:] = [r for r in rows if r not in ok]
            return type("R", (), {"data": ok})
        return type("R", (), {"data": [dict(r) for r in ok]})


class _Base:
    def __init__(self):
        self.tables: dict[str, list] = {}

    def table(self, nom):
        return _Requete(self.tables, nom)


@pytest.fixture
def base(monkeypatch):
    b = _Base()
    b.tables["employees"] = [
        {
            "id": "e1",
            "company_id": "co",
            "first_name": "A",
            "last_name": "B",
            "salaire_de_base": {"type": "mensuel", "valeur": 2166.67},
            "duree_hebdomadaire": "35.00",
            "hire_date": "2020-01-01",
            "employment_status": "actif",
        }
    ]
    b.tables["company_activite_partielle"] = [
        {
            "company_id": "co",
            "active": True,
            "date_debut": "2026-06-01",
            "date_fin": None,
            "taux_indemnite": "60",
            "plancher_horaire": "9.74",
            "plafond_horaire": "33.24",
            "heures_par_jour": None,
        }
    ]
    monkeypatch.setattr(svc, "_db", lambda: b)
    monkeypatch.setattr(svc, "_bulletin_remis", lambda eid, y, m: False)
    import app.modules.monthly_inputs.application.queries as q

    monkeypatch.setattr(q, "bulletins_a_recalculer", lambda cid, cibles: [])
    return b


def test_pose_les_deux_lignes_et_les_remplace(base):
    res = svc.poser_heures_du_mois(
        "co", 2026, 11, [{"employee_id": "e1", "heures": 56}], "u"
    )
    (r,) = res["resultats"]
    assert r["statut"] == "pose"
    assert r["indemnite"] == 545.44
    lignes = base.tables["monthly_inputs"]
    assert {ligne["name"] for ligne in lignes} == {
        "Heures chômées (act. part.)",
        "Indemnité activité partielle",
    }
    retenue = next(ligne for ligne in lignes if ligne["amount"] < 0)
    assert retenue["payroll_quantity"] == 56
    assert retenue["amount"] == pytest.approx(-800.0, abs=0.01)

    svc.poser_heures_du_mois("co", 2026, 11, [{"employee_id": "e1", "heures": 7}], "u")
    assert len(base.tables["monthly_inputs"]) == 2
    vue = svc.lister_mois("co", 2026, 11)
    assert vue["salaries"][0]["deja"]["heures"] == 7
    assert vue["refus"] is None


def test_zero_heure_retire(base):
    svc.poser_heures_du_mois("co", 2026, 11, [{"employee_id": "e1", "heures": 7}], "u")
    res = svc.poser_heures_du_mois(
        "co", 2026, 11, [{"employee_id": "e1", "heures": 0}], "u"
    )
    assert res["resultats"][0]["statut"] == "retire"
    assert base.tables["monthly_inputs"] == []


def test_hors_periode_refuse(base):
    with pytest.raises(ValueError, match="avant le début"):
        svc.poser_heures_du_mois(
            "co", 2026, 5, [{"employee_id": "e1", "heures": 7}], "u"
        )


def test_bulletin_remis_intouche(base, monkeypatch):
    monkeypatch.setattr(svc, "_bulletin_remis", lambda eid, y, m: True)
    res = svc.poser_heures_du_mois(
        "co", 2026, 11, [{"employee_id": "e1", "heures": 7}], "u"
    )
    assert res["resultats"][0]["statut"] == "bulletin_remis"
    assert "monthly_inputs" not in base.tables or base.tables["monthly_inputs"] == []
