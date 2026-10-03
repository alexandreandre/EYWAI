"""Service d'empreinte : même hash que le générateur, trois états à la liste."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payroll.application.empreinte_entrees_service import (
    annoter_a_recalculer,
    entrees_depuis_lectures,
    empreinte_actuelle,
    empreinte_des_lectures,
    poser_empreinte_depuis_lectures,
)
from app.modules.payroll.domain.empreinte_entrees import CLE_EMPREINTE, empreinte_stockee
from app.modules.payroll.infrastructure.empreinte_entrees_queries import LecturesEmpreinte

EMPLOYEE = {
    "salaire_de_base": {"montant": 2000},
    "duree_hebdomadaire": 35,
    "statut": "Non-Cadre",
    "is_forfait_jour": False,
}
COMPANY = {"idcc": "292", "taux_at_mp": 1.2, "settings": {}}
CALENDRIERS = {
    (2026, 4): {
        "planned_calendar": {"calendrier_prevu": [{"jour": 30, "type": "travail", "heures": 7}]},
        "actual_hours": {"calendrier_reel": [{"jour": 30, "type": "travail", "heures": 7}]},
        "cumuls": {"brut_total": 10_000},
        "payroll_events": {"ignore": True},
    },
    (2026, 5): {
        "planned_calendar": {"calendrier_prevu": [{"jour": 12, "type": "travail", "heures": 7}]},
        "actual_hours": {"calendrier_reel": [{"jour": 12, "type": "travail", "heures": 8}]},
        "cumuls": {"brut_total": 12_000},
    },
    (2026, 6): {
        "planned_calendar": {"calendrier_prevu": []},
        "actual_hours": {"calendrier_reel": []},
    },
}


def _kwargs(**surcharges):
    base = dict(
        year=2026,
        month=5,
        calendriers=CALENDRIERS,
        absences=[],
        saisies=[{"name": "Prime", "amount": 50, "created_at": "hier"}],
        employee=EMPLOYEE,
        company=COMPANY,
        notes_de_frais=[],
    )
    base.update(surcharges)
    return base


def test_les_heures_d_un_jour_changent_l_empreinte_des_lectures():
    avant = empreinte_des_lectures(**_kwargs())
    calendriers = {
        cle: {
            **row,
            "actual_hours": {"calendrier_reel": [{"jour": 12, "type": "travail", "heures": 9}]}
            if cle == (2026, 5)
            else row,
        }
        for cle, row in CALENDRIERS.items()
    }
    assert empreinte_des_lectures(**_kwargs(calendriers=calendriers)) != avant


def test_les_cumuls_et_evenements_de_paie_ne_changent_pas_l_empreinte():
    avant = empreinte_des_lectures(**_kwargs())
    calendriers = {
        cle: {**row, "cumuls": {"brut_total": 99_999}, "payroll_events": {"autre": 1}}
        for cle, row in CALENDRIERS.items()
    }
    assert empreinte_des_lectures(**_kwargs(calendriers=calendriers)) == avant


def test_une_absence_qui_touche_la_fenetre_change_l_empreinte():
    avant = empreinte_des_lectures(**_kwargs())
    absences = [{"type": "conge_paye", "selected_days": ["2026-05-04"]}]
    assert empreinte_des_lectures(**_kwargs(absences=absences)) != avant


def test_poser_l_empreinte_ne_touche_pas_les_montants():
    bulletin = {"salaire_brut": 1800.0, "parametres": {"smic_horaire": 11.88}}
    pose = poser_empreinte_depuis_lectures(bulletin, **_kwargs())
    assert pose["salaire_brut"] == 1800.0
    assert pose["parametres"]["smic_horaire"] == 11.88
    assert empreinte_stockee(pose) == empreinte_des_lectures(**_kwargs())
    assert bulletin["parametres"].get(CLE_EMPREINTE) is None


def _lectures(**surcharges) -> LecturesEmpreinte:
    valeurs = dict(
        employee=EMPLOYEE,
        company=COMPANY,
        calendriers=CALENDRIERS,
        absences=[],
        saisies_par_mois={(2026, 5): [{"name": "Prime", "amount": 50}]},
        notes_de_frais=[],
    )
    valeurs.update(surcharges)
    return LecturesEmpreinte(**valeurs)


def test_annoter_sans_empreinte_reste_inconnu():
    with patch(
        "app.modules.payroll.application.empreinte_entrees_service.lire_lectures_salarie",
        return_value=_lectures(),
    ) as lire:
        lignes = annoter_a_recalculer(
            "e1",
            [{"year": 2026, "month": 5, "origine": "calcule", "net_a_payer": 1}],
        )
    lire.assert_called_once_with("e1", [(2026, 5)])
    assert lignes[0]["a_recalculer"] is None
    assert "empreinte_entrees" not in lignes[0]


def test_annoter_empreinte_identique_n_est_pas_a_recalculer():
    hash_ok = empreinte_des_lectures(**_kwargs())
    with patch(
        "app.modules.payroll.application.empreinte_entrees_service.lire_lectures_salarie",
        return_value=_lectures(),
    ):
        lignes = annoter_a_recalculer(
            "e1",
            [{"year": 2026, "month": 5, "origine": "calcule", "empreinte_entrees": hash_ok}],
        )
    assert lignes[0]["a_recalculer"] is False


def test_annoter_heures_changees_est_a_recalculer():
    hash_old = empreinte_des_lectures(**_kwargs())
    calendriers = {
        cle: {
            **row,
            "actual_hours": {"calendrier_reel": [{"jour": 12, "type": "travail", "heures": 9}]}
            if cle == (2026, 5)
            else row,
        }
        for cle, row in CALENDRIERS.items()
    }
    with patch(
        "app.modules.payroll.application.empreinte_entrees_service.lire_lectures_salarie",
        return_value=_lectures(calendriers=calendriers),
    ):
        lignes = annoter_a_recalculer(
            "e1",
            [{"year": 2026, "month": 5, "origine": "calcule", "empreinte_entrees": hash_old}],
        )
    assert lignes[0]["a_recalculer"] is True


def test_un_bulletin_importe_n_est_jamais_marque():
    hash_old = "0" * 64
    with patch(
        "app.modules.payroll.application.empreinte_entrees_service.lire_lectures_salarie",
        return_value=_lectures(),
    ):
        lignes = annoter_a_recalculer(
            "e1",
            [{"year": 2026, "month": 5, "origine": "importe", "empreinte_entrees": hash_old}],
        )
    assert lignes[0]["a_recalculer"] is None


def test_une_seule_lecture_pour_plusieurs_mois():
    with patch(
        "app.modules.payroll.application.empreinte_entrees_service.lire_lectures_salarie",
        return_value=_lectures(),
    ) as lire:
        annoter_a_recalculer(
            "e1",
            [
                {"year": 2026, "month": 5, "origine": "calcule"},
                {"year": 2026, "month": 6, "origine": "calcule"},
            ],
        )
    lire.assert_called_once_with("e1", [(2026, 5), (2026, 6)])


def test_empreinte_actuelle_sans_salarie_est_inconnue():
    with patch(
        "app.modules.payroll.application.empreinte_entrees_service.lire_lectures_salarie",
        return_value=None,
    ):
        assert empreinte_actuelle("inconnu", 2026, 5) is None


def test_absence_validee_sans_jour_cp_aligne_generation_et_liste():
    """Maladie / RTT / arrêt dans la fenêtre, sans jour CP au prévu."""
    maladie = [{"type": "arret_maladie", "selected_days": ["2026-05-10"]}]
    generation = empreinte_des_lectures(**_kwargs(absences=maladie))
    liste = empreinte_des_lectures(**_kwargs(absences=maladie))
    assert generation == liste
    assert empreinte_des_lectures(**_kwargs(absences=[])) != generation
    changee = empreinte_des_lectures(
        **_kwargs(absences=[{"type": "arret_maladie", "selected_days": ["2026-05-11"]}])
    )
    assert changee != generation


def test_changer_end_date_de_la_fenetre_change_l_empreinte():
    a = empreinte_des_lectures(
        **_kwargs(fenetre_variables={"debut": "2026-04-27", "fin": "2026-05-24"})
    )
    b = empreinte_des_lectures(
        **_kwargs(fenetre_variables={"debut": "2026-04-27", "fin": "2026-05-31"})
    )
    assert a != b
    assert empreinte_des_lectures(**_kwargs()) != a


def test_une_surcharge_variable_periods_change_l_empreinte():
    from datetime import date

    a = empreinte_des_lectures(
        **_kwargs(surcharges_fenetre={(2026, 5): date(2026, 5, 24)})
    )
    b = empreinte_des_lectures(
        **_kwargs(surcharges_fenetre={(2026, 5): date(2026, 5, 31)})
    )
    assert a != b


def test_changer_la_date_de_sortie_change_l_empreinte():
    avant = empreinte_des_lectures(
        **_kwargs(employee={**EMPLOYEE, "contract_end_date": "2026-12-31"})
    )
    apres = empreinte_des_lectures(
        **_kwargs(
            employee={
                **EMPLOYEE,
                "contract_end_date": "2026-12-31",
                "exit_last_working_day": "2026-05-15",
            }
        )
    )
    assert apres != avant
    autre = empreinte_des_lectures(
        **_kwargs(
            employee={
                **EMPLOYEE,
                "contract_end_date": "2026-12-31",
                "exit_last_working_day": "2026-05-20",
            }
        )
    )
    assert autre != apres


def test_entrees_depuis_lectures_ignore_les_horodatages_de_saisie():
    a = entrees_depuis_lectures(**_kwargs(saisies=[{"name": "Prime", "amount": 50, "created_at": "a"}]))
    b = entrees_depuis_lectures(**_kwargs(saisies=[{"name": "Prime", "amount": 50, "created_at": "b"}]))
    assert a == b


@pytest.mark.parametrize(
    ("avant", "apres"),
    [
        ({"effectif": 19}, {"effectif": 21}),
        ({"settings": {}}, {"settings": {"taux_assurance_chomage": 2.95}}),
        (
            {"settings": {"taux_assurance_chomage": 2.95}},
            {"settings": {"taux_assurance_chomage": 4.2}},
        ),
        ({"settings": {}}, {"settings": {"date_paiement": "dernier_jour_du_mois"}}),
        ({"settings": {}}, {"settings": {"jour_solidarite": "2026-05-25"}}),
    ],
)
def test_un_reglage_de_l_ecran_parametres_de_paie_fait_passer_a_recalculer(avant, apres):
    """Effectif, chômage, date de paiement, journée de solidarité : réglés à
    l'écran « Paramètres de paie », ils changent le calcul — les bulletins déjà
    calculés doivent passer « À recalculer »."""
    assert empreinte_des_lectures(
        **_kwargs(company={**COMPANY, **avant})
    ) != empreinte_des_lectures(**_kwargs(company={**COMPANY, **apres}))
