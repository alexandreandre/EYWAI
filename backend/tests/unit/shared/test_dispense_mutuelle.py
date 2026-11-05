"""Alerte « mutuelle » de la DSN, dispense comprise (spec du 05/11/2026)."""

import pytest

from app.shared.domain.dispense_mutuelle import MOTIFS_DISPENSE, alerte_mutuelle

pytestmark = pytest.mark.unit


def _dispense(**champs):
    base = {"motif": "couverture_collective", "demande_recue_le": "2026-08-01"}
    base.update(champs)
    return {"adhesion": False, "dispense": base}


def test_les_sept_motifs_de_la_loi():
    assert set(MOTIFS_DISPENSE) == {
        "couverture_collective",
        "css",
        "assurance_individuelle",
        "cdd_moins_12_mois",
        "cdd_12_mois_et_plus",
        "temps_partiel_10_pourcent",
        "anterieur_decision_unilaterale",
    }


def test_adherent_rien_a_dire():
    assert alerte_mutuelle({"adhesion": True}, "CDI", 2026, 9) is None


@pytest.mark.parametrize("contrat", ["Apprentissage", "Stage", None])
def test_contrat_hors_perimetre_rien_a_dire(contrat):
    assert alerte_mutuelle({}, contrat, 2026, 9) is None


@pytest.mark.parametrize(
    "mutuelle", [None, {}, {"adhesion": False}, {"dispense": None}]
)
def test_ni_formule_ni_dispense_dit_quoi_faire(mutuelle):
    alerte = alerte_mutuelle(mutuelle, "CDI", 2026, 9)
    assert alerte.startswith("mutuelle absente")
    assert "Modifier la fiche" in alerte
    assert "dispense" in alerte


def test_dispense_valable_rien_a_dire():
    assert (
        alerte_mutuelle(_dispense(justificatif_recu_le="2026-08-01"), "CDI", 2026, 9)
        is None
    )


@pytest.mark.parametrize(
    "champs",
    [
        {"motif": None},
        {"motif": "inconnu"},
        {"demande_recue_le": None},
        {"demande_recue_le": "pas une date"},
    ],
)
def test_dispense_sans_motif_ou_sans_demande_est_incomplete(champs):
    alerte = alerte_mutuelle(_dispense(**champs), "CDI", 2026, 9)
    assert alerte.startswith("dispense de mutuelle incomplète")
    assert "demande signée" in alerte


@pytest.mark.parametrize("motif", ["css", "assurance_individuelle"])
def test_motif_a_echeance_sans_date_de_fin_est_incomplet(motif):
    alerte = alerte_mutuelle(_dispense(motif=motif), "CDI", 2026, 9)
    assert alerte.startswith("dispense de mutuelle incomplète")
    assert "date de fin" in alerte


def test_dispense_finie_avant_le_mois():
    alerte = alerte_mutuelle(
        _dispense(motif="css", fin_le="2026-08-31"), "CDI", 2026, 9
    )
    assert alerte.startswith("dispense de mutuelle finie le 31/08/2026")


def test_dispense_qui_finit_dans_le_mois_vaut_encore():
    assert (
        alerte_mutuelle(_dispense(motif="css", fin_le="2026-09-15"), "CDI", 2026, 9)
        is None
    )


def test_justificatif_annuel_a_redemander_au_bout_d_un_an():
    mutuelle = _dispense(
        demande_recue_le="2025-09-01", justificatif_recu_le="2025-09-01"
    )
    alerte = alerte_mutuelle(mutuelle, "CDI", 2026, 9)
    assert alerte.startswith("justificatif de sa mutuelle collective à redemander")
    assert "01/09/2025" in alerte


def test_justificatif_de_moins_d_un_an_vaut_encore():
    mutuelle = _dispense(
        demande_recue_le="2025-10-01", justificatif_recu_le="2025-10-01"
    )
    assert alerte_mutuelle(mutuelle, "CDI", 2026, 9) is None


def test_sans_date_de_justificatif_la_demande_en_tient_lieu():
    mutuelle = _dispense(demande_recue_le="2025-09-01")
    assert alerte_mutuelle(mutuelle, "CDI", 2026, 9).startswith("justificatif")


def test_justificatif_du_29_fevrier():
    mutuelle = _dispense(
        demande_recue_le="2024-02-29", justificatif_recu_le="2024-02-29"
    )
    assert alerte_mutuelle(mutuelle, "CDI", 2025, 1) is None
    assert alerte_mutuelle(mutuelle, "CDI", 2025, 2).startswith("justificatif")


def test_le_justificatif_annuel_ne_vaut_que_pour_la_couverture_collective():
    mutuelle = _dispense(motif="cdd_moins_12_mois", demande_recue_le="2020-01-01")
    assert alerte_mutuelle(mutuelle, "CDD", 2026, 9) is None


@pytest.mark.parametrize("motif", ["cdd_moins_12_mois", "cdd_12_mois_et_plus"])
def test_motif_cdd_sur_un_cdi(motif):
    alerte = alerte_mutuelle(_dispense(motif=motif), "CDI", 2026, 9)
    assert alerte.startswith("dispense « CDD » sur un CDI")


def test_dispense_ecrite_le_25_10_au_motif_en_toutes_lettres():
    # Format des dispenses posées le 25/10/2026 (CDD de Colorplast et Comitech) :
    # le motif est reconnu, seule manque la date de la demande signée.
    ancienne = {
        "adhesion": False,
        "dispense": {
            "motif": "CDD de moins de douze mois",
            "depuis": "2026-09-14",
            "fondement": "Code de la sécurité sociale, art. R242-1-6, 2° b",
            "decidee_le": "2026-10-25",
        },
    }
    alerte = alerte_mutuelle(ancienne, "CDD", 2026, 10)
    assert alerte.startswith("dispense de mutuelle incomplète")
    assert "motif" not in alerte
    assert "demande signée" in alerte
    ancienne["dispense"]["demande_recue_le"] = "2026-09-14"
    assert alerte_mutuelle(ancienne, "CDD", 2026, 10) is None
