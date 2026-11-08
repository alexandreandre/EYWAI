"""Deux salariés d'une même formule avec des montants différents (Cartol, 07/11).

Le libellé du catalogue est unique par société et ne porte pas de montant : le second
montant se heurtait au premier libellé, et le salarié restait sans formule à l'écran.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.dsn_import.application import psc_catalog

pytestmark = pytest.mark.unit


class _Requete:
    def __init__(self, base, table):
        self.base, self.table, self.filtres, self.op, self.donnees = base, table, [], "select", None

    def select(self, *_):
        return self

    def eq(self, cle, valeur):
        self.filtres.append((cle, valeur))
        return self

    def limit(self, *_):
        return self

    def insert(self, ligne):
        self.op, self.donnees = "insert", ligne
        return self

    def delete(self):
        self.op = "delete"
        return self

    def update(self, ligne):
        self.op, self.donnees = "update", ligne
        return self

    def upsert(self, ligne, **_):
        self.op, self.donnees = "upsert", ligne
        return self

    def execute(self):
        lignes = self.base.setdefault(self.table, [])
        garde = [l for l in lignes if all(str(l.get(c)) == str(v) for c, v in self.filtres)]
        if self.op == "insert":
            if self.table == "company_mutuelle_types" and any(
                l["company_id"] == self.donnees["company_id"] and l["libelle"] == self.donnees["libelle"]
                for l in lignes
            ):
                raise RuntimeError("duplicate key value violates unique constraint")
            ligne = {**self.donnees, "id": f"t{len(lignes) + 1}"}
            lignes.append(ligne)
            return type("R", (), {"data": [ligne]})
        if self.op == "delete":
            self.base[self.table] = [l for l in lignes if l not in garde]
            return type("R", (), {"data": garde})
        if self.op == "update":
            for l in garde:
                l.update(self.donnees)
            return type("R", (), {"data": garde})
        if self.op == "upsert":
            lignes.append(dict(self.donnees))
            return type("R", (), {"data": [self.donnees]})
        return type("R", (), {"data": garde})


class _Client:
    def __init__(self):
        self.base = {}

    def table(self, nom):
        return _Requete(self.base, nom)


def _payload(montant):
    return {
        "statut": "Non-Cadre",
        "specificites_paie": {
            "mutuelle": {
                "adhesion": True,
                "pack_couverture": "autre",
                "lignes_specifiques": [{"montant_salarial": montant, "montant_patronal": 0}],
            }
        },
        "_psc_meta": {"statut_categoriel": "non_cadre"},
    }


def test_deux_montants_de_la_meme_formule_ont_chacun_leur_ligne_de_catalogue():
    client = _Client()
    with patch.object(psc_catalog, "get_supabase_admin_client", return_value=client):
        psc_catalog.sync_employee_psc_catalog("societe", "e1", _payload(47.42))
        psc_catalog.sync_employee_psc_catalog("societe", "e2", _payload(59.27))
        psc_catalog.sync_employee_psc_catalog("societe", "e3", _payload(59.27))

    types = client.base["company_mutuelle_types"]
    affectations = {a["employee_id"]: a["mutuelle_type_id"] for a in client.base["employee_mutuelle_types"]}
    assert len(types) == 2
    assert set(affectations) == {"e1", "e2", "e3"}
    assert affectations["e2"] == affectations["e3"] != affectations["e1"]
