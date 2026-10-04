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


# --- Cascade : le mois d'avant recalculé après le calcul de ce bulletin -------
#
# Mai a été calculé sur les cumuls d'avril (CALENDRIERS[(2026, 4)]). Gaëlle
# corrige avril et le régénère : ses cumuls changent, mai porte encore les
# anciens. Le calendrier, les absences et les saisies de mai n'ont pas bougé.


def _cumuls_d_avril_corriges():
    return {
        cle: {**row, "cumuls": {"brut_total": 10_400}} if cle == (2026, 4) else row
        for cle, row in CALENDRIERS.items()
    }


def _ligne_de_mai(**surcharges):
    from app.modules.payroll.domain.empreinte_entrees import empreinte_cumuls

    ligne = {
        "year": 2026,
        "month": 5,
        "origine": "calcule",
        "empreinte_entrees": empreinte_des_lectures(**_kwargs()),
        "empreinte_cumuls_precedents": empreinte_cumuls(CALENDRIERS[(2026, 4)]["cumuls"]),
    }
    ligne.update(surcharges)
    return ligne


def _annoter(lectures, ligne):
    with patch(
        "app.modules.payroll.application.empreinte_entrees_service.lire_lectures_salarie",
        return_value=lectures,
    ):
        return annoter_a_recalculer("e1", [ligne])[0]


def test_le_mois_d_avant_recalcule_met_ce_bulletin_a_recalculer():
    ligne = _annoter(_lectures(calendriers=_cumuls_d_avril_corriges()), _ligne_de_mai())
    assert ligne["a_recalculer"] is True
    assert "empreinte_cumuls_precedents" not in ligne


def test_le_mois_d_avant_inchange_laisse_le_bulletin_a_jour():
    assert _annoter(_lectures(), _ligne_de_mai())["a_recalculer"] is False


def test_un_bulletin_sans_empreinte_des_cumuls_suit_la_seule_empreinte_d_entree():
    ligne = _ligne_de_mai(empreinte_cumuls_precedents=None)
    assert _annoter(_lectures(calendriers=_cumuls_d_avril_corriges()), ligne)["a_recalculer"] is False


def test_au_premier_mois_du_contrat_les_cumuls_d_avant_ne_comptent_pas():
    """Le bulletin repart de zéro (contrats successifs) : il ne dépend pas du mois d'avant."""
    nouveau_contrat = {**EMPLOYEE, "hire_date": "2026-05-01"}
    ligne = _ligne_de_mai(
        empreinte_entrees=empreinte_des_lectures(**_kwargs(employee=nouveau_contrat))
    )
    lectures = _lectures(employee=nouveau_contrat, calendriers=_cumuls_d_avril_corriges())
    assert _annoter(lectures, ligne)["a_recalculer"] is False


def test_janvier_suit_les_cumuls_de_decembre():
    from app.modules.payroll.domain.empreinte_entrees import empreinte_cumuls

    decembre = {"cumuls": {"brut_total": 30_000}}
    calendriers = {(2025, 12): {"cumuls": decembre}, (2026, 1): {}, (2026, 2): {}}
    lectures = _lectures(calendriers=calendriers, saisies_par_mois={})
    entrees = empreinte_des_lectures(
        **_kwargs(year=2026, month=1, calendriers=calendriers, saisies=[])
    )
    ligne = {
        "year": 2026, "month": 1, "origine": "calcule",
        "empreinte_entrees": entrees,
        "empreinte_cumuls_precedents": empreinte_cumuls(decembre),
    }
    assert _annoter(lectures, dict(ligne))["a_recalculer"] is False
    corrige = {**calendriers, (2025, 12): {"cumuls": {"brut_total": 30_500}}}
    assert _annoter(_lectures(calendriers=corrige, saisies_par_mois={}), dict(ligne))["a_recalculer"] is True


# --- La cascade, de proche en proche ------------------------------------------
#
# Bulletins de mars à juin, chacun calculé sur les cumuls du mois d'avant.
# Corriger février (ou mars) périme mars ; avril, calculé sur les cumuls de
# mars que le recalcul de mars changera, l'est aussi, et ainsi de suite.

_MOIS = (3, 4, 5, 6)


def _calendriers_de_la_chaine(**cumuls_changes):
    calendriers = {}
    for mois in range(2, 8):
        cumuls = {"cumuls": {"brut_total": 1000.0 * mois}}
        if mois in cumuls_changes.get("mois", ()):
            cumuls = {"cumuls": {"brut_total": 1000.0 * mois + 400}}
        calendriers[(2026, mois)] = {
            "planned_calendar": {"calendrier_prevu": []},
            "actual_hours": {"calendrier_reel": []},
            "cumuls": cumuls,
        }
    return calendriers


def _bulletins_de_la_chaine(calendriers, *, sauf=(), repris=()):
    from app.modules.payroll.domain.empreinte_entrees import empreinte_cumuls

    return [
        {
            "year": 2026,
            "month": mois,
            "origine": "importe" if mois in repris else "calcule",
            "empreinte_entrees": empreinte_des_lectures(
                **_kwargs(month=mois, calendriers=calendriers, saisies=[])
            ),
            "empreinte_cumuls_precedents": empreinte_cumuls(calendriers[(2026, mois - 1)]["cumuls"]),
        }
        for mois in _MOIS
        if mois not in sauf
    ]


def _etats(lignes, calendriers_actuels):
    lectures = _lectures(calendriers=calendriers_actuels, saisies_par_mois={})
    return {
        int(l["month"]): l["a_recalculer"] for l in _annoter_toutes(lectures, lignes)
    }


def _annoter_toutes(lectures, lignes):
    with patch(
        "app.modules.payroll.application.empreinte_entrees_service.lire_lectures_salarie",
        return_value=lectures,
    ):
        return annoter_a_recalculer("e1", [dict(l) for l in lignes])


def test_mars_recalcule_perime_avril_puis_mai_et_juin_de_proche_en_proche():
    lignes = _bulletins_de_la_chaine(_calendriers_de_la_chaine())
    assert _etats(lignes, _calendriers_de_la_chaine()) == {3: False, 4: False, 5: False, 6: False}
    apres = _calendriers_de_la_chaine(mois=(3,))
    assert _etats(lignes, apres) == {3: False, 4: True, 5: True, 6: True}


def test_un_bulletin_repris_ou_un_mois_sans_bulletin_arrete_la_cascade():
    apres = _calendriers_de_la_chaine(mois=(3,))
    repris = _bulletins_de_la_chaine(_calendriers_de_la_chaine(), repris=(5,))
    assert _etats(repris, apres) == {3: False, 4: True, 5: None, 6: False}
    trou = _bulletins_de_la_chaine(_calendriers_de_la_chaine(), sauf=(5,))
    assert _etats(trou, apres) == {3: False, 4: True, 6: False}


def test_le_premier_mois_d_un_contrat_arrete_la_cascade():
    nouveau_contrat = {**EMPLOYEE, "hire_date": "2026-05-01"}
    calendriers = _calendriers_de_la_chaine()
    lignes = [
        {**l, "empreinte_entrees": empreinte_des_lectures(
            **_kwargs(month=l["month"], calendriers=calendriers, saisies=[], employee=nouveau_contrat)
        )}
        for l in _bulletins_de_la_chaine(calendriers)
    ]
    lectures = _lectures(
        employee=nouveau_contrat, calendriers=_calendriers_de_la_chaine(mois=(3,)), saisies_par_mois={}
    )
    etats = {int(l["month"]): l["a_recalculer"] for l in _annoter_toutes(lectures, lignes)}
    # Mars et avril appartiennent au contrat d'avant : ils ne se recalculent
    # plus, rien n'est dit pour eux. Mai repart de zéro : la cascade s'arrête.
    assert etats == {3: None, 4: None, 5: False, 6: False}


def test_des_entrees_changees_ne_se_propagent_pas_au_dela_de_la_fenetre():
    """Une fiche ou un calendrier changés périment les bulletins qui les lisent,
    pas toute la suite : seul un recalcul change les cumuls."""
    calendriers = _calendriers_de_la_chaine()
    lignes = _bulletins_de_la_chaine(calendriers)
    apres = dict(calendriers)
    apres[(2026, 4)] = {
        **calendriers[(2026, 4)],
        "actual_hours": {"calendrier_reel": [{"jour": 2, "type": "travail", "heures": 9}]},
    }
    assert _etats(lignes, apres) == {3: True, 4: True, 5: True, 6: False}


def test_etat_dans_la_chaine_nomme_le_mois_a_recalculer_d_abord():
    from app.modules.payroll.application import empreinte_entrees_service as service

    lignes = _bulletins_de_la_chaine(_calendriers_de_la_chaine())
    with (
        patch.object(service, "lire_empreintes_des_bulletins", return_value=lignes),
        patch.object(
            service,
            "lire_lectures_salarie",
            return_value=_lectures(calendriers=_calendriers_de_la_chaine(mois=(3,)), saisies_par_mois={}),
        ) as lire,
    ):
        juin = service.etat_dans_la_chaine("e1", 2026, 6)
        avril = service.etat_dans_la_chaine("e1", 2026, 4)
    assert lire.call_args_list[0].args == ("e1", [(2026, 3), (2026, 4), (2026, 5), (2026, 6)])
    assert juin.a_recalculer is True
    assert juin.cascade_depuis == (2026, 4)
    assert juin.cumuls_precedents_changes is False
    assert juin.entrees_changees is False
    assert (avril.cascade_depuis, avril.cumuls_precedents_changes) == ((2026, 4), True)


def test_etat_dans_la_chaine_inconnu_sans_bulletin_ou_sans_lecture():
    from app.modules.payroll.application import empreinte_entrees_service as service

    lignes = _bulletins_de_la_chaine(_calendriers_de_la_chaine())
    with (
        patch.object(service, "lire_empreintes_des_bulletins", return_value=lignes),
        patch.object(service, "lire_lectures_salarie", return_value=None),
    ):
        assert service.etat_dans_la_chaine("e1", 2026, 6) is None
    with patch.object(service, "lire_empreintes_des_bulletins", return_value=lignes):
        assert service.etat_dans_la_chaine("e1", 2026, 9) is None


def test_la_lecture_groupee_relit_les_cumuls_des_calendriers():
    from app.modules.payroll.infrastructure import empreinte_entrees_queries as q

    vues: list[str] = []

    class _Requete:
        def __init__(self, table):
            self.table = table

        def select(self, colonnes, *_a, **_k):
            if self.table == "employee_schedules":
                vues.append(colonnes)
            return self

        def __getattr__(self, _nom):
            return lambda *_a, **_k: self

        def execute(self):
            from types import SimpleNamespace

            if self.table == "employees":
                return SimpleNamespace(data={"id": "e1", "company_id": None})
            return SimpleNamespace(data=[])

    class _Base:
        def table(self, nom):
            return _Requete(nom)

    with patch.object(q, "supabase", _Base()):
        q.lire_lectures_salarie("e1", [(2026, 5)])
    assert vues and "cumuls" in vues[0]
