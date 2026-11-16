"""Écran « Arrêts et IJ » (retour d'Elsa du 16/11) : règles et geste « IJ reçues »."""

from __future__ import annotations

import pytest

import app.modules.ijss_tracking.application.arrets as mod
from app.modules.ijss_tracking.domain.arrets_du_mois import (
    bornes_arret,
    etat_du_maintien,
    ij_estimees_du_bulletin,
    jours_dans_le_mois,
    refus_montant_ij,
)
from app.modules.payslips.application.dto import PayslipBadRequestError

# --- Règles pures ---


def test_bornes_et_jours_du_mois():
    jours = [
        "2026-10-28",
        "2026-10-29",
        "2026-10-30",
        "2026-10-31",
        "2026-11-01",
        "2026-11-02",
    ]
    debut, fin = bornes_arret(jours)
    assert (debut.isoformat(), fin.isoformat()) == ("2026-10-28", "2026-11-02")
    assert jours_dans_le_mois(jours, 2026, 10) == 4
    assert jours_dans_le_mois(jours, 2026, 11) == 2
    assert jours_dans_le_mois(jours, 2026, 12) == 0
    assert bornes_arret([]) == (None, None)


def test_maintien_sans_bulletin():
    assert etat_du_maintien(None)["etat"] == "bulletin_a_faire"


def test_maintien_en_attente_des_ij():
    pdata = {
        "bloc_maintien": {
            "maintien": {
                "en_attente_des_ij": True,
                "maintien_en_attente": 312.456,
                "motif_non_maintien": "En attente des IJ",
            }
        }
    }
    etat = etat_du_maintien(pdata)
    assert etat["etat"] == "en_attente_des_ij"
    assert etat["montant_en_attente"] == 312.46


def test_maintien_verse_ou_non():
    assert (
        etat_du_maintien({"bloc_maintien": {"maintien": {"maintien_verse": 120.0}}})[
            "etat"
        ]
        == "verse"
    )
    sans = etat_du_maintien(
        {"bloc_maintien": {"maintien": {"motif_non_maintien": "Ancienneté < 1 an"}}}
    )
    assert sans["etat"] == "sans_maintien"
    assert sans["motif"] == "Ancienneté < 1 an"


def test_ij_estimees():
    assert (
        ij_estimees_du_bulletin({"bloc_maintien": {"ijss": {"ijss_theorique": 401.2}}})
        == 401.2
    )
    assert ij_estimees_du_bulletin({"synthese_net": {"ijss_subrogees": 88}}) == 88.0
    assert ij_estimees_du_bulletin(None) is None


@pytest.mark.parametrize(
    "montant,refuse",
    [(0, False), (412.5, False), (-1, True), ("abc", True), (200_000, True)],
)
def test_refus_montant(montant, refuse):
    assert (refus_montant_ij(montant) is not None) is refuse


# --- Geste « IJ reçues » ---

ARRET = {
    "id": "abs-1",
    "employee_id": "emp-1",
    "company_id": "co-1",
    "type": "arret_maladie",
    "status": "validated",
    "selected_days": ["2026-10-20", "2026-10-21", "2026-10-22"],
    "subrogation_active": False,
}
PERIODE = {"id": "per-1", "period_year": 2026, "period_month": 10, "status": "open"}


@pytest.fixture
def scene(monkeypatch):
    """Repo en mémoire, arrêt fixe, bulletin réglable ; trace ce qui est écrit."""
    lignes: dict[str, dict] = {}
    trace: dict = {"saisies": [], "appliquees": [], "bulletin": None, "remis": False}

    monkeypatch.setattr(mod, "_arret_de_la_societe", lambda cid, aid: dict(ARRET))
    monkeypatch.setattr(
        mod.repo, "get_or_create_period", lambda cid, y, m: dict(PERIODE)
    )
    monkeypatch.setattr(
        mod.repo, "list_expected_lines", lambda pid: [dict(l) for l in lignes.values()]
    )

    def upsert(record):
        lid = f"exp-{len(lignes) + 1}"
        lignes[lid] = {**record, "id": lid}
        return dict(lignes[lid])

    def update(lid, fields):
        lignes[lid].update(fields)
        return dict(lignes[lid])

    monkeypatch.setattr(mod.repo, "upsert_expected_line", upsert)
    monkeypatch.setattr(mod.repo, "update_expected_line", update)

    import app.modules.ijss_tracking.application.apply_to_payslip as apply_mod
    import app.modules.ijss_tracking.application.service as service_mod
    import app.modules.payslips.application.commands as payslip_cmds

    monkeypatch.setattr(service_mod, "_bulletins_du_mois", lambda cid, y, m: {})

    def valider(cid, lid, uid, amount, source):
        lignes[lid].update({"ijss_brut_validated": amount, "validation_source": source})
        return dict(lignes[lid])

    monkeypatch.setattr(apply_mod, "validate_expected_line_brut", valider)
    monkeypatch.setattr(
        apply_mod,
        "_ecrire_saisie_ijss",
        lambda eid, cid, y, m, brut, lid: trace["saisies"].append((eid, y, m, brut)),
    )

    def appliquer(cid, lid, uid):
        trace["appliquees"].append((lid, lignes[lid]["ijss_brut_validated"]))
        return {}

    monkeypatch.setattr(apply_mod, "apply_validated_ijss_to_payslip", appliquer)
    monkeypatch.setattr(
        payslip_cmds, "_fetch_existing_payslip", lambda eid, y, m: trace["bulletin"]
    )

    def remis(existant, y, m):
        if trace["remis"]:
            raise PayslipBadRequestError("Ce bulletin a été remis au salarié.")

    monkeypatch.setattr(payslip_cmds, "refuser_si_remis", remis)
    return lignes, trace


def test_ij_recues_sans_bulletin_ecrit_la_saisie(scene):
    lignes, trace = scene
    res = mod.enregistrer_ij_recues("co-1", "abs-1", 2026, 10, 254.1, "u-1")
    assert res["statut"] == "en_attente_du_bulletin"
    assert trace["saisies"] == [("emp-1", 2026, 10, 254.1)]
    assert trace["appliquees"] == []
    (ligne,) = lignes.values()
    assert ligne["absence_request_id"] == "abs-1"
    assert ligne["ijss_brut_validated"] == 254.1
    assert ligne["validation_source"] == "manual"


def test_ij_recues_bulletin_en_cours_recalcule(scene):
    _lignes, trace = scene
    trace["bulletin"] = {"id": "ps-1"}
    res = mod.enregistrer_ij_recues("co-1", "abs-1", 2026, 10, 254.1, "u-1")
    assert res["statut"] == "bulletin_recalcule"
    assert trace["appliquees"] == [("exp-1", 254.1)]


def test_ij_recues_bulletin_remis_ne_touche_pas_le_bulletin(scene):
    lignes, trace = scene
    trace["bulletin"] = {"id": "ps-1"}
    trace["remis"] = True
    res = mod.enregistrer_ij_recues("co-1", "abs-1", 2026, 10, 254.1, "u-1")
    assert res["statut"] == "bulletin_remis"
    assert "Rappel de maintien de salaire" in res["message"]
    assert trace["appliquees"] == []
    assert trace["saisies"] == []
    assert lignes["exp-1"]["ijss_brut_validated"] == 254.1


def test_deux_arrets_le_meme_mois_la_saisie_porte_la_somme(scene):
    lignes, trace = scene
    lignes["exp-0"] = {
        "id": "exp-0",
        "employee_id": "emp-1",
        "absence_request_id": "abs-0",
        "ijss_brut_validated": 100.0,
    }
    trace["bulletin"] = {"id": "ps-1"}
    mod.enregistrer_ij_recues("co-1", "abs-1", 2026, 10, 254.1, "u-1")
    ((lid, applique),) = trace["appliquees"]
    assert applique == 354.1
    # La ligne de l'arrêt garde son propre montant.
    assert lignes[lid]["ijss_brut_validated"] == 254.1


def test_ij_recues_hors_du_mois_refuse(scene):
    with pytest.raises(ValueError, match="ne touche pas ce mois"):
        mod.enregistrer_ij_recues("co-1", "abs-1", 2026, 11, 10.0, "u-1")


def test_ij_recues_montant_negatif_refuse(scene):
    with pytest.raises(ValueError, match="négatif"):
        mod.enregistrer_ij_recues("co-1", "abs-1", 2026, 10, -5, "u-1")


def test_justificatif_chemin_d_un_autre_utilisateur_refuse(monkeypatch):
    monkeypatch.setattr(mod, "_arret_de_la_societe", lambda cid, aid: dict(ARRET))
    with pytest.raises(ValueError, match="Fichier introuvable"):
        mod.ajouter_justificatif(
            "co-1", "abs-1", "virement_cpam", "autre-user/x.pdf", "x.pdf", "u-1"
        )
    with pytest.raises(ValueError, match="Type"):
        mod.ajouter_justificatif(
            "co-1", "abs-1", "facture", "u-1/x.pdf", "x.pdf", "u-1"
        )
