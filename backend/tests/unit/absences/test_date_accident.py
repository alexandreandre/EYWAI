"""Date de l'accident ou de la première constatation d'un arrêt (R-451).

Sans colonne : rangée sous une clé réservée de `demi_journees`, jamais utilisée
par les arrêts, dont les clés de jour ne risquent pas de la rencontrer.
"""
from datetime import date

import pytest
from pydantic import ValidationError

from app.modules.absences.domain.date_accident import avec_date_accident, date_accident_de
from app.modules.absences.domain.rules import quotite_demi_journees
from app.modules.absences.schemas.requests import AbsenceRequestCreate
from app.modules.dsn_export.domain.evenements import periodes_d_arret
from app.modules.dsn_export.domain.signalements import signalements_a_faire


def _demande(**extra):
    return {
        "employee_id": "e1",
        "type": "arret_maladie_pro",
        "date_debut": date(2026, 10, 5),
        "date_fin": date(2026, 10, 9),
        "arret_type": "maladie_professionnelle",
        **extra,
    }


def test_la_date_se_relit():
    absence = {"demi_journees": avec_date_accident(None, date(2026, 9, 10))}
    assert date_accident_de(absence) == date(2026, 9, 10)


def test_une_absence_sans_date_ne_lit_rien():
    assert date_accident_de({"demi_journees": {"2026-09-14": "matin"}}) is None
    assert date_accident_de({"demi_journees": None}) is None


def test_la_cle_reservee_ne_pese_sur_aucune_journee():
    demi = avec_date_accident(None, date(2026, 9, 10))
    assert quotite_demi_journees([date(2026, 10, 5), date(2026, 10, 6)], demi) == 2.0


def test_la_date_est_acceptee_sur_un_arret_accident():
    demande = AbsenceRequestCreate(**_demande(date_accident=date(2026, 9, 10)))
    assert demande.date_accident == date(2026, 9, 10)


def test_la_date_est_refusee_apres_le_premier_jour_d_arret():
    with pytest.raises(ValidationError, match="premier jour d.arrêt"):
        AbsenceRequestCreate(**_demande(date_accident=date(2026, 10, 6)))


def test_la_date_est_refusee_sur_une_maladie_ordinaire():
    with pytest.raises(ValidationError, match="accident"):
        AbsenceRequestCreate(
            **_demande(type="arret_maladie", arret_type="maladie_simple", date_accident=date(2026, 9, 10))
        )


def _arret(demi=None):
    return {
        "id": "a1",
        "employee_id": "e1",
        "type": "arret_maladie_pro",
        "selected_days": ["2026-10-05", "2026-10-06"],
        "created_at": "2026-10-05T10:00:00+00:00",
        "demi_journees": demi,
    }


def test_la_periode_porte_la_date_et_l_arret():
    periode = periodes_d_arret([_arret({"date_accident": "2026-09-10"})])[0]
    assert periode.date_accident == date(2026, 9, 10)
    assert periode.absence_id == "a1"


def test_le_signalement_porte_la_date():
    s = signalements_a_faire({"e1": [_arret({"date_accident": "2026-09-10"})]}, [], depuis=None, effectif=10)[0]
    assert s.date_accident == date(2026, 9, 10)
    assert s.absence_id == "a1"
    assert s.a_verifier is None


def test_sans_date_le_signalement_le_dit():
    s = signalements_a_faire({"e1": [_arret()]}, [], depuis=None, effectif=10)[0]
    assert s.date_accident is None
    assert "accident" in s.a_verifier


def test_une_maladie_ordinaire_n_a_rien_a_verifier():
    arret = {**_arret(), "type": "arret_maladie"}
    s = signalements_a_faire({"e1": [arret]}, [], depuis=None, effectif=10)[0]
    assert s.a_verifier is None


def test_definir_la_date_sur_un_arret_deja_saisi():
    from unittest.mock import patch

    from app.modules.absences.application import commands

    ligne = {**_arret(), "company_id": "c1"}
    with patch("app.modules.absences.application.commands.absence_repository") as repo:
        repo.get_by_id.return_value = ligne
        repo.update.return_value = ligne
        commands.definir_date_accident("a1", "c1", date(2026, 9, 10))
        repo.update.assert_called_once_with("a1", {"demi_journees": {"date_accident": "2026-09-10"}})


def test_definir_la_date_refuse_ce_qui_ne_va_pas():
    from unittest.mock import patch

    from app.modules.absences.application import commands

    with patch("app.modules.absences.application.commands.absence_repository") as repo:
        repo.get_by_id.return_value = {**_arret(), "company_id": "c1"}
        with pytest.raises(ValueError, match="premier jour"):
            commands.definir_date_accident("a1", "c1", date(2026, 10, 9))
        repo.update.assert_not_called()


def test_definir_la_date_d_une_autre_societe_est_refuse():
    from unittest.mock import patch

    from app.modules.absences.application import commands

    with patch("app.modules.absences.application.commands.absence_repository") as repo:
        repo.get_by_id.return_value = {**_arret(), "company_id": "c2"}
        with pytest.raises(LookupError):
            commands.definir_date_accident("a1", "c1", date(2026, 9, 10))
