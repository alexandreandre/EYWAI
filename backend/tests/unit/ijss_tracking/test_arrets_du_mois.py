"""Écran « Arrêts et IJ » (retour d'Elsa du 16/11) : règles et geste « IJ reçues »."""

from __future__ import annotations

import pytest

import app.modules.ijss_tracking.application.arrets as mod
from app.modules.ijss_tracking.domain.arrets_du_mois import (
    bornes_arret,
    bulletin_calcule_avant,
    chiffres_du_bulletin,
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


# --- Ligne de suivi figée sur un bulletin d'avant l'arrêt (MAJI, 17/11) ---


def test_le_montant_saisi_n_est_pas_une_estimation():
    pdata = {
        "bloc_maintien": {"ijss": {"ijss_theorique": 500.0, "ijss_brut_override": True}}
    }
    assert ij_estimees_du_bulletin(pdata) is None
    assert "ijss_theorique" not in chiffres_du_bulletin(pdata)
    pdata["bloc_maintien"]["ijss"]["ijss_brut_override"] = None
    assert chiffres_du_bulletin(pdata)["ijss_theorique"] == 500.0


def test_chiffres_du_bulletin_sans_arret():
    chiffres = chiffres_du_bulletin({"bloc_maintien": {}, "synthese_net": {}})
    assert chiffres["nb_jours_indemnises"] == 0
    assert "ijss_theorique" not in chiffres


def test_bulletin_calcule_avant():
    bulletin = {"generated_at": "2026-11-10T14:20:00+00:00"}
    assert bulletin_calcule_avant(bulletin, "2026-11-17T08:52:56.123456+00:00")
    assert not bulletin_calcule_avant(bulletin, "2026-11-01T00:00:00Z")
    assert not bulletin_calcule_avant(None, "2026-11-17T08:52:56+00:00")
    assert not bulletin_calcule_avant(bulletin, None)
    # Même seconde, fractions de longueurs différentes.
    assert bulletin_calcule_avant(
        {"updated_at": "2026-11-17T08:55:29+00:00"}, "2026-11-17T08:55:29.5+00:00"
    )


def test_la_ligne_figee_reprend_le_bulletin_recalcule(monkeypatch):
    """Cas réel MAJI : la ligne a été réécrite (updated_at) après le calcul du
    bulletin, mais n'a jamais lu ce calcul : elle se rafraîchit quand même."""
    from app.modules.ijss_tracking.application import service as service_mod

    ligne = {
        "id": "l-1",
        "absence_request_id": "a-1",
        "updated_at": "2026-11-17T08:55:29.30+00:00",
        "nb_jours_indemnises": 0,
        "calculation_snapshot": {"bloc_maintien": {}},
    }
    bulletin = {
        "id": "ps-1",
        "generated_at": "2026-11-17T08:55:28.61+00:00",
        "payslip_data": {
            "bloc_maintien": {"ijss": {"nb_jours_indemnises": 1, "ijss_theorique": 42.97}}
        },
    }
    ecrits: dict = {}
    monkeypatch.setattr(service_mod, "_bulletins_du_mois", lambda cid, y, m: {"e-1": bulletin})
    monkeypatch.setattr(mod.repo, "list_expected_lines", lambda pid: [ligne])
    monkeypatch.setattr(
        mod.repo, "update_expected_line", lambda lid, f: ecrits.update(f) or {**ligne, **f}
    )
    arret = {"id": "a-1", "employee_id": "e-1"}

    rendue = mod._ligne_attendue_de_l_arret("c-1", arret, {"id": "p-1"}, 2026, 10)
    assert rendue["nb_jours_indemnises"] == 1 and ecrits["ijss_theorique"] == 42.97
    assert ecrits["calculation_snapshot"]["bulletin_genere_le"] == bulletin["generated_at"]

    # Ligne qui a déjà lu ce calcul : rendue telle quelle, quel que soit updated_at.
    ecrits.clear()
    ligne["calculation_snapshot"] = {"bulletin_genere_le": bulletin["generated_at"]}
    ligne["updated_at"] = "2026-11-17T07:00:00+00:00"
    assert mod._ligne_attendue_de_l_arret("c-1", arret, {"id": "p-1"}, 2026, 10) is ligne
    assert ecrits == {}


def test_arret_enregistre_apres_le_bulletin_le_dit():
    bulletin = {
        "generated_at": "2026-11-10T14:20:00+00:00",
        "payslip_data": {"bloc_maintien": {}},
    }
    assert bulletin_calcule_avant(bulletin, "2026-11-17T08:52:56+00:00")


def _liste_avec(monkeypatch, *, payslip_data, ijss_theorique):
    import app.modules.ijss_tracking.application.service as service

    arret = {
        "id": "a1",
        "employee_id": "e1",
        "type": "arret_maladie",
        "selected_days": ["2026-10-20", "2026-10-21"],
        "created_at": "2026-10-01T00:00:00+00:00",
    }
    monkeypatch.setattr(mod, "_arrets_valides", lambda _c: [arret])
    monkeypatch.setattr(service, "_fetch_employees", lambda _c: [{"id": "e1"}])
    monkeypatch.setattr(
        service,
        "_bulletins_du_mois",
        lambda *_a: {
            "e1": {
                "id": "b1",
                "payslip_data": payslip_data,
                "generated_at": "2026-11-05T00:00:00+00:00",
            }
        },
    )
    monkeypatch.setattr(mod, "_saisies_ij_du_mois", lambda *_a: {})
    monkeypatch.setattr(mod.repo, "get_or_create_period", lambda *_a: {"id": "p1"})
    monkeypatch.setattr(
        mod.repo,
        "list_expected_lines",
        lambda _p: [{"absence_request_id": "a1", "ijss_theorique": ijss_theorique}],
    )
    monkeypatch.setattr(mod, "_justificatifs", lambda _ids: {})
    monkeypatch.setattr(mod, "_urls_signees", lambda _u: {})
    return mod.lister_arrets_du_mois("co", 2026, 10)["arrets"][0]


def test_le_zero_de_creation_n_est_pas_une_estimation(monkeypatch):
    """Ligne créée quand le bulletin portait déjà le montant saisi : son 0 par
    défaut ne s'affiche pas « Martine les estime à 0,00 € »."""
    saisi = {"bloc_maintien": {"ijss": {"ijss_brut_override": 500.0}}}
    ligne = _liste_avec(monkeypatch, payslip_data=saisi, ijss_theorique=0.0)
    assert ligne["ij_estimees"] is None


def test_l_estimation_d_avant_la_saisie_reste(monkeypatch):
    saisi = {"bloc_maintien": {"ijss": {"ijss_brut_override": 500.0}}}
    ligne = _liste_avec(monkeypatch, payslip_data=saisi, ijss_theorique=43.12)
    assert ligne["ij_estimees"] == 43.12


def test_un_montant_saisi_a_zero_est_une_saisie():
    """0 € saisi par la RH (arrêt en carence) : pas « estimées » à la place."""
    pdata = {"bloc_maintien": {"ijss": {"ijss_brut_override": 0.0, "ijss_theorique": 43.1}}}
    assert ij_estimees_du_bulletin(pdata) is None
