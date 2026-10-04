"""Ce que l'empreinte complémentaire voit, et ce qu'elle ne voit volontairement pas.

Seul compte ce que le moteur lit pour le mois du bulletin : les formules de
mutuelle de la fiche, les ajustements de congés jusqu'à l'année du bulletin et
les réglages de congés, le départ rattaché au mois, l'historique de salaire
jusqu'à la fin du mois, et les réglages société que le moteur lit sans que
l'empreinte d'entrée les suive.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

import pytest

from app.modules.payroll.application.empreinte_entrees_service import (
    annoter_a_recalculer,
    complements_du_mois,
    empreinte_des_lectures,
    poser_empreinte_complementaire_depuis_lectures,
)
from app.modules.payroll.domain.empreinte_entrees import (
    empreinte_complementaire_stockee,
    empreinte_partie,
)
from app.modules.payroll.infrastructure.empreinte_entrees_queries import (
    Complements,
    LecturesEmpreinte,
)

pytestmark = pytest.mark.unit

SERVICE = "app.modules.payroll.application.empreinte_entrees_service"

EMPLOYEE = {
    "id": "e1",
    "company_id": "c1",
    "salaire_de_base": {"valeur": 2000},
    "duree_hebdomadaire": 35,
    "statut": "Non-Cadre",
    "is_forfait_jour": False,
    "hire_date": "2024-01-15",
    "specificites_paie": {"mutuelle": {"adhesion": True, "mutuelle_type_ids": ["m1"]}},
}
COMPANY = {"id": "c1", "idcc": "292", "settings": {"dsn_import": {"le": "2026-09-01"}}}
CALENDRIERS = {
    (2026, 4): {"planned_calendar": {"calendrier_prevu": []}, "actual_hours": {"calendrier_reel": []}},
    (2026, 5): {
        "planned_calendar": {"calendrier_prevu": [{"jour": 12, "type": "travail", "heures": 7}]},
        "actual_hours": {"calendrier_reel": [{"jour": 12, "type": "travail", "heures": 7}]},
    },
    (2026, 6): {"planned_calendar": {"calendrier_prevu": []}, "actual_hours": {"calendrier_reel": []}},
}
FENETRE = {"debut": "2026-04-27", "fin": "2026-05-24"}

MUTUELLE_M1 = {
    "id": "m1",
    "company_id": "c1",
    "libelle": "Mutuelle Base",
    "montant_salarial": 30.0,
    "montant_patronal": 30.0,
    "part_patronale_soumise_a_csg": True,
    "part_salariale_deductible_impot": True,
    "part_salariale_obligatoire": True,
    "is_active": True,
    "updated_at": "2026-09-01T10:00:00",
    "code_organisme_dsn": "P0942",
}
MUTUELLE_M2 = {**MUTUELLE_M1, "id": "m2", "libelle": "Mutuelle Famille", "montant_salarial": 80.0}

COMPLEMENTS = Complements(
    mutuelles=[MUTUELLE_M1, MUTUELLE_M2],
    sorties=[],
    ajustements_conges=[
        {"id": "a1", "employee_id": "e1", "year": 2026, "cp_n1_opening_balance": 12.0,
         "cp_n_opening_balance": 3.0, "note": None, "updated_at": "2026-09-01"},
    ],
    reglages_conges={"id": "l1", "company_id": "c1", "cp_acquisition_days_per_month": 2.5,
                     "rtt_year_end_reminder_enabled": False, "updated_at": "2026-09-12"},
    conges_anciennete=None,
    historique_salaire=[
        {"effective_date": "2025-01-01", "ancien_salaire": {"valeur": 1900},
         "nouveau_salaire": {"valeur": 2000}},
    ],
    maintien={"id": "x", "company_id": "c1", "employer_waiting_days": 3,
              "paid_waiting_days_per_year": 3, "updated_at": "2026-09-28"},
    jei=None,
)


def _du_mois(complements=COMPLEMENTS, *, employee=EMPLOYEE, company=COMPANY,
             calendriers=CALENDRIERS, year=2026, month=5):
    return complements_du_mois(
        complements,
        year=year,
        month=month,
        employee=employee,
        company=company,
        calendriers=calendriers,
        fenetre=FENETRE,
    )


def _change(partie, **surcharges):
    """La partie a-t-elle changé entre COMPLEMENTS et COMPLEMENTS surchargé ?"""
    avant = _du_mois()[partie]
    apres = _du_mois(replace(COMPLEMENTS, **surcharges))[partie]
    return empreinte_partie(avant) != empreinte_partie(apres)


# --- Mutuelle -------------------------------------------------------------------


def test_le_montant_d_une_formule_de_mutuelle_du_salarie_change_la_partie_mutuelle():
    assert _change("mutuelle", mutuelles=[{**MUTUELLE_M1, "montant_salarial": 32.5}, MUTUELLE_M2])
    assert _change("mutuelle", mutuelles=[{**MUTUELLE_M1, "is_active": False}, MUTUELLE_M2])


def test_une_formule_que_le_salarie_n_a_pas_ne_compte_pas():
    assert not _change("mutuelle", mutuelles=[MUTUELLE_M1, {**MUTUELLE_M2, "montant_salarial": 99}])


def test_les_codes_dsn_et_horodatages_d_une_formule_ne_comptent_pas():
    assert not _change(
        "mutuelle",
        mutuelles=[{**MUTUELLE_M1, "updated_at": "2026-10-04", "code_organisme_dsn": "X"}, MUTUELLE_M2],
    )


def test_la_formule_surchargee_pour_le_mois_est_celle_qui_compte():
    employe = {
        **EMPLOYEE,
        "specificites_paie": {
            "mutuelle": {"adhesion": True, "mutuelle_type_ids": ["m1"]},
            "overrides_mensuels": {"2026-05": {"mutuelle": {"mutuelle_type_ids": ["m2"]}}},
        },
    }
    avant = _du_mois(employee=employe)["mutuelle"]
    apres = _du_mois(
        replace(COMPLEMENTS, mutuelles=[MUTUELLE_M1, {**MUTUELLE_M2, "montant_salarial": 99}]),
        employee=employe,
    )["mutuelle"]
    assert empreinte_partie(avant) != empreinte_partie(apres)


# --- Congés ---------------------------------------------------------------------


def test_un_ajustement_de_conges_jusqu_a_l_annee_du_bulletin_compte():
    ligne = COMPLEMENTS.ajustements_conges[0]
    assert _change("conges_ajustements", ajustements_conges=[{**ligne, "cp_n1_opening_balance": 14.0}])
    precedente = {**ligne, "id": "a0", "year": 2025, "cp_n_opening_balance": 20.0}
    assert _change("conges_ajustements", ajustements_conges=[ligne, precedente])


def test_un_ajustement_d_une_annee_suivante_ne_compte_pas():
    suivante = {**COMPLEMENTS.ajustements_conges[0], "id": "a2", "year": 2027}
    assert not _change("conges_ajustements", ajustements_conges=[*COMPLEMENTS.ajustements_conges, suivante])


def test_les_reglages_de_conges_comptent_pas_leurs_horodatages_ni_les_rappels():
    reglages = COMPLEMENTS.reglages_conges
    assert _change("conges_reglages", reglages_conges={**reglages, "cp_acquisition_days_per_month": 2.08})
    assert _change("conges_reglages", conges_anciennete={"enabled": True, "rules": []})
    assert not _change(
        "conges_reglages",
        reglages_conges={**reglages, "updated_at": "2026-10-04", "rtt_year_end_reminder_enabled": True},
    )


# --- Départ ---------------------------------------------------------------------

DEPART = {
    "exit_type": "demission",
    "status": "validated",
    "last_working_day": "2026-05-20",
    "calculated_indemnities": {
        "indemnite_preavis": {"montant": 0},
        "total_gross_indemnities": 500.0,
        "calculation_date": "2026-05-02T10:00:00",
        "exit_id": "x1",
    },
}


def test_le_depart_du_mois_compte_son_type_et_ses_indemnites():
    base = replace(COMPLEMENTS, sorties=[DEPART])
    assert empreinte_partie(_du_mois(base)["depart"]) != empreinte_partie(_du_mois()["depart"])
    autre_type = {**DEPART, "exit_type": "licenciement"}
    assert empreinte_partie(_du_mois(replace(base, sorties=[autre_type]))["depart"]) != (
        empreinte_partie(_du_mois(base)["depart"])
    )
    indemnites = {**DEPART, "calculated_indemnities": {**DEPART["calculated_indemnities"],
                                                       "total_gross_indemnities": 650.0}}
    assert empreinte_partie(_du_mois(replace(base, sorties=[indemnites]))["depart"]) != (
        empreinte_partie(_du_mois(base)["depart"])
    )


def test_la_date_du_calcul_des_indemnites_ne_compte_pas():
    base = replace(COMPLEMENTS, sorties=[DEPART])
    recalcule = {**DEPART, "calculated_indemnities": {**DEPART["calculated_indemnities"],
                                                      "calculation_date": "2026-10-04T08:00:00"}}
    assert empreinte_partie(_du_mois(replace(base, sorties=[recalcule]))["depart"]) == (
        empreinte_partie(_du_mois(base)["depart"])
    )


def test_un_depart_d_un_autre_mois_ou_annule_ne_compte_pas():
    plus_tard = {**DEPART, "last_working_day": "2026-07-31"}
    annule = {**DEPART, "status": "cancelled"}
    assert not _change("depart", sorties=[plus_tard])
    assert not _change("depart", sorties=[annule])


# --- Historique de salaire -----------------------------------------------------


def test_un_salaire_date_jusqu_a_la_fin_du_mois_compte():
    hausse = {"effective_date": "2026-05-10", "ancien_salaire": {"valeur": 2000},
              "nouveau_salaire": {"valeur": 2100}}
    assert _change("salaire", historique_salaire=[*COMPLEMENTS.historique_salaire, hausse])
    retroactive = {"effective_date": "2026-02-01", "ancien_salaire": {"valeur": 2000},
                   "nouveau_salaire": {"valeur": 2050}}
    assert _change("salaire", historique_salaire=[*COMPLEMENTS.historique_salaire, retroactive])


def test_une_hausse_posterieure_au_mois_ne_compte_pas():
    future = {"effective_date": "2026-10-01", "ancien_salaire": {"valeur": 2000},
              "nouveau_salaire": {"valeur": 2200}}
    assert not _change("salaire", historique_salaire=[*COMPLEMENTS.historique_salaire, future])


def test_sans_salaire_applicable_le_premier_suivant_donne_l_ancien_salaire():
    """`salaire_actif_a_date` lit alors l'ancien salaire de la première entrée future."""
    futur = {"effective_date": "2026-10-01", "ancien_salaire": {"valeur": 1950},
             "nouveau_salaire": {"valeur": 2200}}
    avant = _du_mois(replace(COMPLEMENTS, historique_salaire=[futur]))["salaire"]
    apres = _du_mois(replace(COMPLEMENTS, historique_salaire=[
        {**futur, "ancien_salaire": {"valeur": 1980}}]))["salaire"]
    assert empreinte_partie(avant) != empreinte_partie(apres)


# --- Réglages société hors des champs suivis -----------------------------------


def test_la_prime_d_anciennete_de_la_societe_compte():
    societe = {**COMPANY, "settings": {"parametres_paie": {"prime_anciennete": {"valeur_point_override": 5.1}}}}
    assert empreinte_partie(_du_mois(company=societe)["reglages_societe"]) != (
        empreinte_partie(_du_mois()["reglages_societe"])
    )


def test_les_jours_ouvres_du_forfait_ne_comptent_que_pour_un_forfait():
    societe = {**COMPANY, "settings": {"forfait_jours_ouvres_mois": 21}}
    assert empreinte_partie(_du_mois(company=societe)["reglages_societe"]) == (
        empreinte_partie(_du_mois()["reglages_societe"])
    )
    forfait = {**EMPLOYEE, "statut": "Cadre", "is_forfait_jour": True}
    assert empreinte_partie(_du_mois(employee=forfait, company=societe)["reglages_societe"]) != (
        empreinte_partie(_du_mois(employee=forfait)["reglages_societe"])
    )


def test_le_maintien_de_salaire_ne_compte_qu_un_mois_avec_un_arret():
    maintien = {**COMPLEMENTS.maintien, "employer_waiting_days": 7}
    assert not _change("reglages_societe", maintien=maintien)
    arret = {
        **CALENDRIERS,
        (2026, 5): {
            "planned_calendar": {"calendrier_prevu": [
                {"jour": 12, "type": "arret_maladie", "heures": 0, "arret_type": "maladie"}]},
            "actual_hours": {"calendrier_reel": []},
        },
    }
    avant = _du_mois(calendriers=arret)["reglages_societe"]
    apres = _du_mois(replace(COMPLEMENTS, maintien=maintien), calendriers=arret)["reglages_societe"]
    assert empreinte_partie(avant) != empreinte_partie(apres)


def test_la_jei_ne_compte_qu_activee():
    assert not _change("reglages_societe", jei={"jei_enabled": False, "taux_exoneration": 50})
    assert _change("reglages_societe", jei={"jei_enabled": True, "taux_exoneration": 50})


def test_un_reglage_societe_sans_effet_sur_la_paie_ne_compte_pas():
    societe = {**COMPANY, "settings": {"dsn_import": {"le": "2026-10-04"}, "medical_follow_up_enabled": True}}
    assert empreinte_partie(_du_mois(company=societe)["reglages_societe"]) == (
        empreinte_partie(_du_mois()["reglages_societe"])
    )


# --- De la génération à la liste -----------------------------------------------


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


def _lectures(complements=COMPLEMENTS, **surcharges) -> LecturesEmpreinte:
    valeurs = dict(
        employee=EMPLOYEE,
        company=COMPANY,
        calendriers=CALENDRIERS,
        absences=[],
        saisies_par_mois={(2026, 5): [{"name": "Prime", "amount": 50}]},
        notes_de_frais=[],
        complements=complements,
    )
    valeurs.update(surcharges)
    return LecturesEmpreinte(**valeurs)


def _genere(complements=COMPLEMENTS, **surcharges):
    """Le bulletin de mai tel que la génération le pose (empreintes comprises)."""
    with patch(f"{SERVICE}.lire_complements", return_value=complements) as lire:
        data = poser_empreinte_complementaire_depuis_lectures({}, **_kwargs(**surcharges))
    lire.assert_called_once_with(EMPLOYEE, COMPANY)
    return {
        "year": 2026,
        "month": 5,
        "origine": "calcule",
        "status": "brouillon",
        "empreinte_entrees": empreinte_des_lectures(**_kwargs(**surcharges)),
        "empreinte_complementaire": empreinte_complementaire_stockee(data),
    }


def _annoter(lectures, ligne):
    with patch(f"{SERVICE}.lire_lectures_salarie", return_value=lectures):
        return annoter_a_recalculer("e1", [dict(ligne)])[0]


def test_un_bulletin_genere_puis_relu_sans_changement_est_a_jour():
    ligne = _annoter(_lectures(), _genere())
    assert ligne["a_recalculer"] is False
    assert "empreinte_complementaire" not in ligne


def test_une_mutuelle_modifiee_apres_le_calcul_le_met_a_recalculer():
    modifiee = replace(COMPLEMENTS, mutuelles=[{**MUTUELLE_M1, "montant_patronal": 35.0}, MUTUELLE_M2])
    assert _annoter(_lectures(modifiee), _genere())["a_recalculer"] is True


def test_un_compteur_de_conges_ajuste_apres_le_calcul_le_met_a_recalculer():
    ajuste = replace(COMPLEMENTS, ajustements_conges=[
        {**COMPLEMENTS.ajustements_conges[0], "cp_n1_opening_balance": 15.0}])
    assert _annoter(_lectures(ajuste), _genere())["a_recalculer"] is True


def test_un_bulletin_d_avant_le_deploiement_ne_passe_pas_a_recalculer():
    """Sans empreinte complémentaire, seule l'empreinte d'entrée décide : une
    mutuelle changée depuis ne le périme pas — rien à comparer."""
    ligne = {**_genere(), "empreinte_complementaire": None}
    modifiee = replace(COMPLEMENTS, mutuelles=[{**MUTUELLE_M1, "montant_patronal": 35.0}, MUTUELLE_M2])
    assert _annoter(_lectures(modifiee), ligne)["a_recalculer"] is False


def test_des_complements_illisibles_a_la_generation_laissent_les_parties_d_entree():
    with patch(f"{SERVICE}.lire_complements", side_effect=RuntimeError("réseau")):
        data = poser_empreinte_complementaire_depuis_lectures({"parametres": {}}, **_kwargs())
    parties = empreinte_complementaire_stockee(data)
    assert parties and "fiche" in parties and "mutuelle" not in parties


def test_des_complements_illisibles_a_la_lecture_ne_perimant_rien():
    assert _annoter(_lectures(complements=None), _genere())["a_recalculer"] is False


def test_la_lecture_groupee_lit_les_complements():
    from types import SimpleNamespace

    from app.modules.payroll.infrastructure import empreinte_entrees_queries as q

    lues: list[str] = []

    class _Requete:
        def __init__(self, table):
            self.table = table
            lues.append(table)

        def __getattr__(self, _nom):
            return lambda *_a, **_k: self

        def execute(self):
            if self.table == "employees":
                return SimpleNamespace(data={**EMPLOYEE, "current_exit_id": None})
            if self.table == "company_mutuelle_types":
                return SimpleNamespace(data=[MUTUELLE_M1])
            if self.table == "companies":
                return SimpleNamespace(data=COMPANY)
            return SimpleNamespace(data=[])

    class _Base:
        def table(self, nom):
            return _Requete(nom)

    with patch.object(q, "supabase", _Base()):
        lectures = q.lire_lectures_salarie("e1", [(2026, 5)])
    assert lectures.complements is not None
    assert lectures.complements.mutuelles == [MUTUELLE_M1]
    for table in (
        "company_mutuelle_types", "employee_exits", "employee_leave_adjustments",
        "company_leave_settings", "company_cp_seniority_settings", "salary_history",
        "company_maintenance_settings", "company_jei_settings",
    ):
        assert table in lues


# --- Une fiche modifiée : seulement les brouillons du contrat en cours ----------
#
# La fiche est celle d'aujourd'hui, pas celle du mois : une augmentation saisie
# en octobre n'a pas à périmer un bulletin validé, et recalculer un mois d'un
# ancien contrat est impossible (la fiche porte le nouveau).

FICHE_AUGMENTEE = {**EMPLOYEE, "salaire_de_base": {"valeur": 2100}}


def test_une_fiche_modifiee_signale_un_brouillon_du_contrat_en_cours():
    ligne = _annoter(_lectures(employee=FICHE_AUGMENTEE), _genere())
    assert ligne["a_recalculer"] is True


def test_une_fiche_modifiee_ne_signale_pas_un_bulletin_valide():
    valide = {**_genere(), "status": "valide"}
    assert _annoter(_lectures(employee=FICHE_AUGMENTEE), valide)["a_recalculer"] is False


def test_un_bulletin_valide_reste_signale_quand_sa_mutuelle_change():
    valide = {**_genere(), "status": "valide"}
    modifiee = replace(COMPLEMENTS, mutuelles=[{**MUTUELLE_M1, "montant_patronal": 35.0}, MUTUELLE_M2])
    assert _annoter(_lectures(modifiee), valide)["a_recalculer"] is True


def test_un_bulletin_d_un_ancien_contrat_n_est_jamais_signale():
    """Réembauche en juillet : mai appartient au contrat d'avant, il ne se recalcule plus."""
    reembauche = {**EMPLOYEE, "hire_date": "2026-07-01"}
    calendriers = {
        **CALENDRIERS,
        (2026, 5): {
            "planned_calendar": {"calendrier_prevu": [{"jour": 12, "type": "travail", "heures": 7}]},
            "actual_hours": {"calendrier_reel": [{"jour": 12, "type": "travail", "heures": 9}]},
        },
    }
    ligne = _annoter(_lectures(employee=reembauche, calendriers=calendriers), _genere())
    assert ligne["a_recalculer"] is None


def test_un_bulletin_valide_d_avant_l_empreinte_complementaire_n_est_plus_signale():
    """Sans parties, on ne sait pas si c'est la fiche : un bulletin validé reste tel quel."""
    ancien = {**_genere(), "empreinte_complementaire": None, "status": "valide"}
    assert _annoter(_lectures(employee=FICHE_AUGMENTEE), ancien)["a_recalculer"] is None


def test_un_brouillon_d_avant_l_empreinte_complementaire_reste_signale_comme_avant():
    ancien = {**_genere(), "empreinte_complementaire": None}
    assert _annoter(_lectures(employee=FICHE_AUGMENTEE), ancien)["a_recalculer"] is True


def test_le_contrat_en_cours_commence_au_mois_de_son_debut():
    from app.shared.domain.employment_rules import mois_du_contrat_en_cours

    fiche = {"hire_date": "2026-01-10", "date_debut_execution": "2026-07-01"}
    assert not mois_du_contrat_en_cours(fiche, 2026, 6)
    assert mois_du_contrat_en_cours(fiche, 2026, 7)
    assert mois_du_contrat_en_cours(fiche, 2027, 1)
    assert mois_du_contrat_en_cours({}, 2020, 1)


def test_les_lectures_des_bulletins_rendent_leur_statut():
    from app.modules.payroll.infrastructure import empreinte_entrees_queries as q

    assert "status" in q._EMPREINTES_DES_BULLETINS
