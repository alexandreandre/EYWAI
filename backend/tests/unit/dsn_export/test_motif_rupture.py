"""Motif de rupture (S21.G00.62.002) : proposé, choisi, refusé (R-449).

Cahier technique DSN 2026.1, S21.G00.62.002, CCH-11 : motifs permis selon la
nature du contrat (S21.G00.40.007).
"""
from datetime import date

import pytest

from app.modules.dsn_export.domain.evenements import bloc_fin_contrat
from app.modules.dsn_export.domain.motif_rupture import (
    motif_propose,
    motif_refuse,
    motifs_possibles,
)

CDI = {"contract_type": "CDI"}
CDD = {"contract_type": "CDD", "contract_end_date": "2026-09-30"}
OCTOBRE = (date(2026, 9, 1), date(2026, 9, 30))


def _sortie(exit_type, **extra):
    return {
        "exit_type": exit_type,
        "last_working_day": "2026-09-15",
        "exit_request_date": "2026-09-01",
        **extra,
    }


def _bloc(salarie, sortie):
    return bloc_fin_contrat({**salarie, "sortie_dsn": sortie}, *OCTOBRE)


def test_le_motif_choisi_au_dossier_part_en_dsn():
    sortie = _sortie("licenciement", exit_notes={"motif_dsn": "014"})
    bloc, _ = _bloc(CDI, sortie)
    assert bloc["S21.G00.62.002"] == "014"


def test_licenciement_pour_inaptitude_garde_son_motif_propose():
    sortie = _sortie("licenciement", exit_notes={"inaptitude_origine": "non_professionnelle"})
    assert _bloc(CDI, sortie)[0]["S21.G00.62.002"] == "091"


def test_rupture_anticipee_de_cdd_sans_motif_ne_sort_plus_en_031():
    bloc, avertissements = _bloc(CDD, _sortie("fin_cdd"))
    assert bloc is None
    assert any("dossier de sortie" in a and "motif" in a.lower() for a in avertissements)


def test_rupture_anticipee_de_cdd_avec_motif_choisi():
    sortie = _sortie("fin_cdd", exit_notes={"motif_dsn": "037"})
    bloc, _ = _bloc(CDD, sortie)
    assert bloc["S21.G00.62.002"] == "037"
    assert bloc["S21.G00.62.003"] == "01092026"  # CCH-12 de 62.003


def test_cdd_a_son_terme_reste_en_031():
    sortie = _sortie("fin_cdd", last_working_day="2026-09-30")
    assert _bloc(CDD, sortie)[0]["S21.G00.62.002"] == "031"


@pytest.mark.parametrize(
    ("exit_type", "attendu"),
    [("demission", "037"), ("licenciement", "036"), ("rupture_conventionnelle", "084")],
)
def test_un_cdd_ne_prend_pas_un_motif_de_cdi(exit_type, attendu):
    """CCH-11 : 059, 020 et 043 ne sont pas autorisés pour la nature 02."""
    assert _bloc(CDD, _sortie(exit_type))[0]["S21.G00.62.002"] == attendu


def test_faute_grave_sur_cdd():
    sortie = _sortie("licenciement", is_gross_misconduct=True)
    assert _bloc(CDD, sortie)[0]["S21.G00.62.002"] == "095"


def test_motif_choisi_devenu_incompatible_n_est_pas_emis():
    sortie = _sortie("licenciement", exit_notes={"motif_dsn": "020"})
    bloc, avertissements = _bloc(CDD, sortie)
    assert bloc is None
    assert any("020" in a for a in avertissements)


def test_refus_dit_quoi_faire():
    message = motif_refuse("031", _sortie("fin_cdd"), {"contract_type": "CDI"})
    assert message and "Choisissez" in message
    assert motif_refuse("037", _sortie("fin_cdd"), CDD) is None


def test_refus_si_le_motif_ne_va_pas_avec_le_type_de_sortie():
    assert motif_refuse("059", _sortie("licenciement"), CDI)


def test_inaptitude_impose_son_motif():
    """CCH-29 : l'indemnité 032 d'une inaptitude professionnelle exige 033, 091 ou 092."""
    sortie = _sortie("licenciement", exit_notes={"inaptitude_origine": "professionnelle"})
    assert motif_refuse("020", sortie, CDI)
    assert motif_refuse("092", sortie, CDI) is None
    assert motif_refuse("091", _sortie("licenciement"), CDI)


def test_faute_grave_impose_087_ou_088():
    sortie = _sortie("licenciement", is_gross_misconduct=True)
    assert motif_refuse("020", sortie, CDI)
    assert motif_refuse("088", sortie, CDI) is None
    assert motif_refuse("087", _sortie("licenciement"), CDI)


def test_rupture_anticipee_cdi_en_alternance():
    """CCH-11 : 036, 037 et 084 sur un CDI seulement avec le dispositif 61, 64 ou 65."""
    salarie = {"contract_type": "CDI", "classification_conventionnelle": {"dispositif_politique_publique": "64"}}
    assert "037" in motifs_possibles(_sortie("fin_cdd"), salarie)
    assert "037" not in motifs_possibles(_sortie("fin_cdd"), CDI)


def test_proposition_du_dossier():
    assert motif_propose(_sortie("fin_cdd", last_working_day="2026-09-30"), CDD) == ("031", None)
    code, raison = motif_propose(_sortie("fin_cdd"), CDD)
    assert code == "" and "terme" in raison


def test_autre_motif_sans_choix_n_invente_rien():
    code, raison = motif_propose(_sortie("autre_motif"), CDI)
    assert code == "" and raison


def test_un_transfert_n_a_pas_de_motif_a_choisir():
    assert motifs_possibles(_sortie("transfert"), CDI) == []
