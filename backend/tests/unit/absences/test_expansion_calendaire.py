"""Expansion calendaire des arrêts : helper partagé, schéma API, commande.

Spec : docs/superpowers/specs/2026-09-01-arrets-jours-calendaires-design.md
"""

from datetime import date

from app.shared.domain.absence_calendar import daterange_days


def test_daterange_days_couvre_week_ends_et_bornes():
    # vendredi 14/08/2026 → lundi 17/08/2026 : le week-end est inclus
    jours = daterange_days(date(2026, 8, 14), date(2026, 8, 17))
    assert jours == [
        date(2026, 8, 14),
        date(2026, 8, 15),
        date(2026, 8, 16),
        date(2026, 8, 17),
    ]


def test_daterange_days_fin_avant_debut_renvoie_le_debut():
    assert daterange_days(date(2026, 8, 17), date(2026, 8, 14)) == [date(2026, 8, 17)]


def test_import_dsn_reexporte_le_helper_partage():
    from app.modules.dsn_import.domain import dsn_absence_exit_mapping

    assert dsn_absence_exit_mapping.daterange_days is daterange_days


# ----- Schéma AbsenceRequestCreate : saisie par période -----

import pytest
from pydantic import ValidationError

from app.modules.absences.schemas.requests import AbsenceRequestCreate


def _payload_arret(**overrides):
    payload = {
        "employee_id": "emp-1",
        "type": "arret_maladie",
        "arret_type": "maladie_simple",
    }
    payload.update(overrides)
    return payload


def test_schema_etend_une_periode_d_arret_en_jours_calendaires():
    # L'expansion vit dans le schéma (frontière d'entrée) : la commande ne
    # consomme qu'un seul contrat, selected_days.
    req = AbsenceRequestCreate(
        **_payload_arret(date_debut=date(2026, 8, 14), date_fin=date(2026, 8, 17))
    )
    assert req.selected_days == [
        date(2026, 8, 14),
        date(2026, 8, 15),
        date(2026, 8, 16),
        date(2026, 8, 17),
    ]


def test_schema_refuse_une_periode_aberrante():
    with pytest.raises(ValidationError, match="3 ans"):
        AbsenceRequestCreate(
            **_payload_arret(date_debut=date(2026, 8, 17), date_fin=date(2062, 9, 18))
        )


def test_schema_refuse_une_periode_incomplete():
    with pytest.raises(ValidationError, match="début ET une date de fin"):
        AbsenceRequestCreate(**_payload_arret(date_debut=date(2026, 8, 17)))


def test_schema_refuse_fin_avant_debut():
    with pytest.raises(ValidationError, match="antérieure"):
        AbsenceRequestCreate(
            **_payload_arret(date_debut=date(2026, 9, 18), date_fin=date(2026, 8, 17))
        )


def test_schema_refuse_periode_et_jours_melanges():
    with pytest.raises(ValidationError, match="pas les deux"):
        AbsenceRequestCreate(
            **_payload_arret(
                date_debut=date(2026, 8, 17),
                date_fin=date(2026, 8, 21),
                selected_days=[date(2026, 8, 17)],
            )
        )


def test_schema_refuse_periode_pour_un_conge_paye():
    with pytest.raises(ValidationError, match="réservée aux arrêts"):
        AbsenceRequestCreate(
            employee_id="emp-1",
            type="conge_paye",
            date_debut=date(2026, 8, 17),
            date_fin=date(2026, 8, 21),
        )


def test_schema_refuse_periode_pour_mi_temps_therapeutique():
    with pytest.raises(ValidationError, match="jour par jour"):
        AbsenceRequestCreate(
            **_payload_arret(
                arret_type="mi_temps_therapeutique",
                date_debut=date(2026, 8, 17),
                date_fin=date(2026, 8, 21),
            )
        )


def test_schema_sans_jours_ni_periode_delegue_a_la_commande():
    # Le refus « au moins un jour » reste dans la commande (ValueError → 400,
    # contrat d'API historique), pas dans le schéma (422).
    req = AbsenceRequestCreate(**_payload_arret())
    assert req.selected_days == []
    assert req.date_debut is None and req.date_fin is None


def test_schema_jours_seuls_comportement_inchange():
    req = AbsenceRequestCreate(**_payload_arret(selected_days=[date(2026, 8, 17)]))
    assert req.selected_days == [date(2026, 8, 17)]
    assert req.date_debut is None


# ----- Commande create_absence_request : bout en bout depuis le schéma -----

from unittest.mock import patch

from app.modules.absences.application import commands


def test_creation_par_periode_stocke_tous_les_jours_calendaires():
    # Le schéma étend la période ; la commande stocke selected_days tel quel.
    request_data = AbsenceRequestCreate(
        **_payload_arret(date_debut=date(2026, 8, 14), date_fin=date(2026, 8, 17))
    )
    with patch(
        "app.modules.absences.application.commands.get_employee_company_id",
        return_value="comp-1",
    ):
        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.create.return_value = {"id": "req-1"}
            commands.create_absence_request(request_data)

    call_data = repo.create.call_args[0][0]
    assert call_data["selected_days"] == [
        "2026-08-14",
        "2026-08-15",
        "2026-08-16",
        "2026-08-17",
    ]
