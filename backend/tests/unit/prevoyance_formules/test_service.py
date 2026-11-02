"""Service des formules de prévoyance : dépôt simulé, fiches simulées."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.modules.prevoyance_formules.application import service
from app.modules.prevoyance_formules.schemas import FormuleCreate, FormuleUpdate

pytestmark = pytest.mark.unit

SOCIETE = "c1"
LIGNE = {"libelle": "Prévoyance TA", "salarial": 0.005, "patronal": 0.007, "forfait_social": 0.08}
LIGNE_TB = {**LIGNE, "libelle": "Prévoyance TB", "base": "tranche_2"}


class DepotSimule:
    def __init__(self):
        self.formules = {"f1": {"id": "f1", "company_id": SOCIETE, "libelle": "Cadres",
                                "statut_categoriel": "cadre", "lignes": [LIGNE], "is_active": True}}
        self.fiches = []

    def lister(self, company_id):
        return [f for f in self.formules.values() if f["company_id"] == company_id]

    def lire(self, formule_id, company_id):
        f = self.formules.get(formule_id)
        return f if f and f["company_id"] == company_id else None

    def creer(self, row):
        row = {**row, "id": f"f{len(self.formules) + 1}", "is_active": True}
        self.formules[row["id"]] = row
        return row

    def modifier(self, formule_id, company_id, patch):
        self.formules[formule_id] = {**self.formules[formule_id], **patch}
        return self.formules[formule_id]

    def fiches_de_la_societe(self, company_id):
        return self.fiches


@pytest.fixture
def depot(monkeypatch):
    d = DepotSimule()
    ecrites = []
    monkeypatch.setattr(service, "_depot", lambda: d)
    monkeypatch.setattr(service, "_ecrire_prevoyance", lambda eid, prev: ecrites.append((eid, prev)))
    d.ecrites = ecrites
    return d


def _fiche(eid, formule_id, lignes):
    return {"id": eid, "specificites_paie": {"prevoyance": {"adhesion": True, "formule_id": formule_id,
                                                            "lignes_specifiques": lignes}}}


def test_creer_une_formule(depot):
    f = service.creer_formule(SOCIETE, "u1", FormuleCreate(libelle="Non-cadres", statut_categoriel="non_cadre",
                                                           lignes=[LIGNE_TB]))
    assert f["company_id"] == SOCIETE
    assert f["lignes"][0]["base"] == "tranche_2"


def test_une_ligne_sans_libelle_est_refusee():
    with pytest.raises(ValueError):
        FormuleCreate(libelle="X", lignes=[{"libelle": " ", "salarial": 0.01}])


def test_modifier_compte_les_fiches_qui_ont_encore_les_anciennes_lignes(depot):
    depot.fiches = [_fiche("e1", "f1", [LIGNE]), _fiche("e2", "f1", [LIGNE]), _fiche("e3", "f2", [LIGNE])]
    retour = service.modifier_formule("f1", SOCIETE, FormuleUpdate(lignes=[LIGNE, LIGNE_TB]))
    assert retour["fiches_a_mettre_a_jour"] == 2
    assert len(retour["formule"]["lignes"]) == 2


def test_appliquer_ne_reecrit_que_les_fiches_qui_divergent(depot):
    depot.formules["f1"]["lignes"] = [LIGNE, LIGNE_TB]
    depot.fiches = [_fiche("e1", "f1", [LIGNE]), _fiche("e2", "f1", [LIGNE, LIGNE_TB]), _fiche("e3", None, [LIGNE])]
    assert service.appliquer_formule_aux_fiches("f1", SOCIETE) == 1
    (eid, prevoyance), = depot.ecrites
    assert eid == "e1"
    assert prevoyance["formule_id"] == "f1"
    assert [l["libelle"] for l in prevoyance["lignes_specifiques"]] == ["Prévoyance TA", "Prévoyance TB"]


def test_une_formule_d_une_autre_societe_est_introuvable(depot):
    with pytest.raises(service.FormuleErreur) as e:
        service.modifier_formule("f1", "autre", FormuleUpdate(libelle="Autre"))
    assert e.value.status_code == 404


def test_retirer_desactive_sans_toucher_aux_fiches(depot):
    depot.fiches = [_fiche("e1", "f1", [LIGNE])]
    assert service.retirer_formule("f1", SOCIETE)["is_active"] is False
    assert depot.ecrites == []


def test_les_routes_sont_inscrites():
    from app.main import app

    chemins = set(app.openapi()["paths"])
    assert "/api/prevoyance-formules" in chemins
    assert "/api/prevoyance-formules/{formule_id}/appliquer" in chemins


def test_ecrire_reserve_aux_rh():
    from types import SimpleNamespace

    from app.modules.prevoyance_formules.api.router import _societe_rh

    salarie = SimpleNamespace(active_company_id=SOCIETE, has_rh_access_in_company=lambda c: False)
    with pytest.raises(HTTPException) as e:
        _societe_rh(salarie)
    assert e.value.status_code == 403
