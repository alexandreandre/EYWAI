"""Un arrêt saisi qui recouvre un arrêt déjà enregistré est refusé (retour du 26/11).

Cas réel : arrêt maladie importé de la DSN du 24/09/2025 au 30/06/2026,
ressaisi du 01/05 au 27/11/2026. Sans refus, mai et juin portaient deux arrêts.
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from app.modules.absences.application import commands
from app.modules.absences.domain.chevauchement_arret import refus_chevauchement_arret
from app.modules.absences.schemas.requests import AbsenceRequestCreate


def _jours(debut: date, fin: date) -> list[str]:
    return [(debut + timedelta(days=i)).isoformat() for i in range((fin - debut).days + 1)]


ARRET_IMPORTE = {
    "type": "arret_maladie",
    "status": "validated",
    "selected_days": _jours(date(2025, 9, 24), date(2026, 6, 30)),
}


def test_une_prolongation_qui_recouvre_est_refusee_et_dit_ou_commencer():
    refus = refus_chevauchement_arret(
        "arret_maladie", _jours(date(2026, 5, 1), date(2026, 11, 27)), [ARRET_IMPORTE]
    )
    assert refus is not None
    assert "du 24/09/2025 au 30/06/2026" in refus
    assert "à partir du 01/07/2026" in refus


def test_la_prolongation_au_lendemain_passe():
    assert (
        refus_chevauchement_arret(
            "arret_maladie", _jours(date(2026, 7, 1), date(2026, 11, 27)), [ARRET_IMPORTE]
        )
        is None
    )


def test_une_periode_contenue_dans_l_arret_existant_dit_d_annuler():
    refus = refus_chevauchement_arret(
        "arret_at", _jours(date(2026, 3, 1), date(2026, 3, 10)), [ARRET_IMPORTE]
    )
    assert refus is not None and "annulez-le" in refus


@pytest.mark.parametrize("statut", ["cancelled", "rejected", "pending"])
def test_un_arret_annule_ou_refuse_ne_compte_pas(statut):
    assert (
        refus_chevauchement_arret(
            "arret_maladie",
            _jours(date(2026, 5, 1), date(2026, 5, 31)),
            [{**ARRET_IMPORTE, "status": statut}],
        )
        is None
    )


def test_un_arret_importe_en_morceaux_se_lit_comme_un_seul():
    morceaux = [
        {"type": "arret_maladie", "status": "validated",
         "selected_days": _jours(date(2026, 6, 1), date(2026, 6, 30))},
        {"type": "arret_maladie", "status": "validated",
         "selected_days": _jours(date(2025, 9, 24), date(2026, 5, 31))},
    ]
    refus = refus_chevauchement_arret(
        "arret_maladie", _jours(date(2026, 5, 1), date(2026, 11, 27)), morceaux
    )
    assert "du 24/09/2025 au 30/06/2026" in refus
    assert "à partir du 01/07/2026" in refus


def test_une_periode_qui_englobe_l_arret_ne_propose_pas_de_prolongation():
    refus = refus_chevauchement_arret(
        "arret_maladie", _jours(date(2027, 1, 1), date(2027, 2, 15)),
        [{"type": "arret_maladie_pro", "status": "validated",
          "selected_days": _jours(date(2027, 1, 10), date(2027, 1, 31))}],
    )
    assert "prolongation" not in refus and "annulez-le" in refus
    assert "un arrêt enregistré" in refus and "(Maladie professionnelle)" in refus


def test_une_periode_qui_finit_dans_l_arret_dit_jusqu_ou_saisir():
    refus = refus_chevauchement_arret(
        "arret_maladie", _jours(date(2025, 9, 1), date(2025, 10, 5)), [ARRET_IMPORTE]
    )
    assert "jusqu'au 23/09/2025" in refus


def test_un_conge_n_est_pas_un_arret():
    conge = {"type": "conge_paye", "status": "validated", "selected_days": ["2026-05-04"]}
    assert refus_chevauchement_arret("arret_maladie", ["2026-05-04"], [conge]) is None
    assert refus_chevauchement_arret("conge_paye", ["2026-05-04"], [ARRET_IMPORTE]) is None


def test_l_enregistrement_est_refuse_avant_toute_ecriture():
    demande = AbsenceRequestCreate(
        employee_id="emp-1",
        type="arret_maladie",
        arret_type="maladie_simple",
        date_debut=date(2026, 5, 1),
        date_fin=date(2026, 11, 27),
    )
    with patch(
        "app.modules.absences.application.commands.get_employee_company_id",
        return_value="comp-1",
    ), patch("app.modules.absences.application.commands.absence_repository") as repo:
        repo.list_by_employee_id.return_value = [ARRET_IMPORTE]
        with pytest.raises(ValueError) as refus:
            commands.create_absence_request(demande)
    assert "à partir du 01/07/2026" in str(refus.value)
    repo.create.assert_not_called()
