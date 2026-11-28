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


# L20 (capture du 27/11) : un arrêt maladie déjà enregistré du 01/09 au 29/11,
# ressaisi en maladie professionnelle sur la même période.
ARRET_MALADIE_AUTOMNE = {
    "type": "arret_maladie",
    "status": "validated",
    "selected_days": _jours(date(2026, 9, 1), date(2026, 11, 29)),
}


def test_requalifier_en_maladie_professionnelle_dit_le_chemin():
    refus = refus_chevauchement_arret(
        "arret_maladie_pro", _jours(date(2026, 9, 1), date(2026, 11, 29)), [ARRET_MALADIE_AUTOMNE]
    )
    assert refus is not None
    assert "du 01/09/2026 au 29/11/2026 (Arrêt maladie)" in refus
    assert "Pour le requalifier en « Maladie professionnelle »" in refus
    assert "Arrêts & IJ" in refus and "« Annuler cet arrêt »" in refus
    assert "bulletins déjà faits" in refus


def test_meme_nature_sur_la_meme_periode_dit_seulement_de_remplacer():
    refus = refus_chevauchement_arret(
        "arret_maladie", _jours(date(2026, 9, 1), date(2026, 11, 29)), [ARRET_MALADIE_AUTOMNE]
    )
    assert "requalifier" not in refus and "annulez-le" in refus


def _demande_maladie_pro(**autres):
    # Ce que la fenêtre envoie : nature et type de la maladie professionnelle,
    # période du … au …, date de première constatation vide, subrogation
    # « règle de la société » (absente).
    return AbsenceRequestCreate(
        employee_id="emp-1",
        type="arret_maladie_pro",
        arret_type="maladie_professionnelle",
        date_debut=date(2026, 9, 1),
        date_fin=date(2026, 11, 29),
        **autres,
    )


def test_la_maladie_professionnelle_de_la_fenetre_est_acceptee():
    with patch(
        "app.modules.absences.application.commands.get_employee_company_id",
        return_value="comp-1",
    ), patch("app.modules.absences.application.commands.absence_repository") as repo:
        repo.list_by_employee_id.return_value = []
        repo.create.side_effect = lambda d: d
        cree = commands.create_absence_request(_demande_maladie_pro())
    assert cree["type"] == "arret_maladie_pro"
    assert cree["arret_type"] == "maladie_professionnelle"
    assert len(cree["selected_days"]) == 90
    assert "demi_journees" not in cree


def test_la_maladie_professionnelle_sur_un_arret_maladie_existant_dit_de_le_requalifier():
    with patch(
        "app.modules.absences.application.commands.get_employee_company_id",
        return_value="comp-1",
    ), patch("app.modules.absences.application.commands.absence_repository") as repo:
        repo.list_by_employee_id.return_value = [ARRET_MALADIE_AUTOMNE]
        with pytest.raises(ValueError) as refus:
            commands.create_absence_request(_demande_maladie_pro(date_accident=date(2026, 8, 20)))
    assert "Pour le requalifier en « Maladie professionnelle »" in str(refus.value)
    assert "ne correspond pas à la nature" not in str(refus.value)
    repo.create.assert_not_called()


# Relecture de L20 : une nature différente dit toujours la requalification,
# même quand la période déborde après ou avant l'arrêt existant.
def test_maladie_pro_qui_deborde_apres_ne_propose_pas_une_prolongation():
    refus = refus_chevauchement_arret(
        "arret_maladie_pro", _jours(date(2026, 9, 1), date(2026, 12, 15)), [ARRET_MALADIE_AUTOMNE]
    )
    assert "prolongation" not in refus
    assert "Pour le requalifier en « Maladie professionnelle »" in refus


def test_maladie_pro_qui_commence_avant_ne_propose_pas_les_jours_d_avant():
    refus = refus_chevauchement_arret(
        "arret_maladie_pro", _jours(date(2026, 8, 20), date(2026, 11, 29)), [ARRET_MALADIE_AUTOMNE]
    )
    assert "jours d'avant" not in refus
    assert "Pour le requalifier en « Maladie professionnelle »" in refus


ARRET_EN_DEUX_LIGNES = [
    {"type": "arret_maladie", "status": "validated",
     "selected_days": _jours(date(2026, 10, 1), date(2026, 11, 29))},
    {"type": "arret_maladie", "status": "validated",
     "selected_days": _jours(date(2026, 9, 1), date(2026, 9, 30))},
]


def test_requalifier_un_arret_en_deux_lignes_dit_les_deux_a_annuler():
    refus = refus_chevauchement_arret(
        "arret_maladie_pro", _jours(date(2026, 9, 1), date(2026, 11, 29)), ARRET_EN_DEUX_LIGNES
    )
    assert "annulez-le" not in refus
    assert (
        "annulez les 2 arrêts concernés (du 01/09/2026 au 30/09/2026, "
        "du 01/10/2026 au 29/11/2026)"
    ) in refus


def test_remplacer_un_arret_en_deux_lignes_dit_les_deux_a_annuler():
    refus = refus_chevauchement_arret(
        "arret_maladie", _jours(date(2026, 9, 10), date(2026, 10, 10)), ARRET_EN_DEUX_LIGNES
    )
    assert "annulez-le" not in refus
    assert (
        "Pour le remplacer, annulez les 2 arrêts concernés (du 01/09/2026 au "
        "30/09/2026, du 01/10/2026 au 29/11/2026), puis saisissez la bonne période."
    ) in refus
