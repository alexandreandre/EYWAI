"""Congés payés acquis pendant un arrêt maladie ordinaire.

Code du travail L3141-5 7° et L3141-5-1 (loi n° 2024-364 du 22/04/2024, en
vigueur le 24/04/2024) : un arrêt pour maladie ou accident non professionnel
acquiert 2 jours ouvrables par mois, au lieu de 2,5, dans la limite de 24 jours
par période de référence. Accident du travail, maladie professionnelle, trajet,
maternité, paternité, adoption : travail effectif, taux plein (L3141-5 2° et 5°).
Service-public F37482 (lu le 05/11/2026) : 2 mois d'arrêt du 01/08 au 30/09/2024
sur la période 2024-25 donnent 5 + 4 + 20 = 29 jours.

Martine créditait 2,5 jours (2,08 ouvrés) par mois d'arrêt, comme un mois
travaillé. Chaque mois perd désormais 20 % de la part de ses jours calendaires
passée en arrêt maladie ordinaire.

Une reprise de soldes suit le cabinet : un arrêt antérieur à sa date ne change
pas le solde repris ; seul l'acquis calculé par Martine après elle change.

Convention de la métallurgie (IDCC 3248), art. 84, plus favorable : l'arrêt pour
maladie ou accident compte comme travail effectif dans la limite de 2 mois
(1 an d'ancienneté), 4 (5 ans), 6 (10 ans), 8 (20 ans) par période de référence,
un an pour les groupes d'emplois F à I, l'ancienneté s'appréciant à l'ouverture
de la période.
"""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta

import pytest

from app.modules.absences.domain.cp_arret_maladie import (
    METALLURGIE_3248_ART_84,
    assimilation_maladie_de_la_convention,
    est_arret_maladie_ordinaire,
    mois_d_arret,
)
from app.modules.absences.domain.cp_seniority import EmployeeCpSeniorityContext
from app.modules.absences.domain.leave_policy import (
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
)
from app.modules.absences.domain.rules import (
    calculate_acquired_cp,
    compute_absence_balances,
    compute_cp_period_balances,
)

pytestmark = pytest.mark.unit

OUVRABLES = LeavePolicySettings()
OUVRES = LeavePolicySettings(
    cp_acquisition_days_per_month=25 / 12, cp_counting_unit="ouvre"
)
METALLURGIE = dataclasses.replace(
    OUVRABLES, cp_maladie_assimilation=METALLURGIE_3248_ART_84
)
ANCIEN = date(2015, 3, 1)


def _arret(
    debut: date,
    fin: date,
    *,
    nature="arret_maladie",
    type_arret="maladie_simple",
    statut="validated",
):
    jours = [
        (debut + timedelta(days=n)).isoformat() for n in range((fin - debut).days + 1)
    ]
    return {
        "type": nature,
        "arret_type": type_arret,
        "status": statut,
        "selected_days": jours,
    }


# --- Qualification de l'arrêt -------------------------------------------------


@pytest.mark.parametrize(
    "type_arret", ["maladie_simple", "ald", "arret_exceptionnel", None]
)
def test_un_arret_maladie_non_professionnel_acquiert_au_taux_reduit(type_arret):
    assert est_arret_maladie_ordinaire(
        _arret(date(2026, 10, 1), date(2026, 10, 2), type_arret=type_arret)
    )


@pytest.mark.parametrize(
    "nature, type_arret",
    [
        ("arret_at", "accident_travail"),
        ("arret_at", "accident_trajet"),
        ("arret_at", "rechute_at"),
        ("arret_maladie_pro", "maladie_professionnelle"),
        ("arret_maternite", "maternite"),
        ("arret_paternite", "paternite"),
        ("arret_maternite", "adoption"),
        # Le salarié travaille à temps partiel : son contrat n'est pas suspendu.
        ("arret_maladie", "mi_temps_therapeutique"),
        # Combinaisons refusées à la saisie, mais présentes dans d'anciennes
        # données : le type d'arrêt professionnel l'emporte.
        ("arret_maladie", "accident_travail"),
        ("conge_paye", None),
        ("sans_solde", None),
    ],
)
def test_ces_absences_comptent_comme_du_travail_effectif(nature, type_arret):
    assert not est_arret_maladie_ordinaire(
        _arret(
            date(2026, 10, 1), date(2026, 10, 2), nature=nature, type_arret=type_arret
        )
    )


def test_un_arret_annule_ne_compte_pas():
    assert not est_arret_maladie_ordinaire(
        _arret(date(2026, 10, 1), date(2026, 10, 2), statut="cancelled")
    )


# --- Part du mois passée en arrêt ----------------------------------------------


def test_un_mois_entier_d_arret_vaut_un_mois_quelle_que_soit_sa_longueur():
    fevrier = {date(2026, 2, 1) + timedelta(days=n) for n in range(28)}
    octobre = {date(2026, 10, 1) + timedelta(days=n) for n in range(31)}
    assert mois_d_arret(fevrier, date(2026, 2, 1), date(2026, 2, 28)) == 1.0
    assert mois_d_arret(octobre, date(2026, 10, 1), date(2026, 10, 31)) == 1.0


def test_la_part_du_mois_se_compte_en_jours_calendaires():
    quinze = {date(2026, 9, 1) + timedelta(days=n) for n in range(15)}
    assert mois_d_arret(quinze, date(2026, 6, 1), date(2026, 9, 30)) == pytest.approx(
        0.5
    )


def test_les_jours_hors_de_la_fenetre_ne_comptent_pas():
    octobre = {date(2026, 10, 1) + timedelta(days=n) for n in range(31)}
    assert mois_d_arret(octobre, date(2026, 6, 1), date(2026, 9, 30)) == 0.0


# --- Acquis de la période ------------------------------------------------------


def test_exemple_de_service_public_deux_mois_d_arret_donnent_29_jours():
    arret = _arret(date(2024, 8, 1), date(2024, 9, 30))
    soldes = compute_cp_period_balances(
        ANCIEN, [arret], date(2025, 5, 31), policy=OUVRABLES
    )
    assert soldes["periode_courante"]["acquis"] == 29.0


def test_sans_arret_rien_ne_change():
    soldes = compute_cp_period_balances(ANCIEN, [], date(2025, 5, 31), policy=OUVRABLES)
    assert soldes["periode_courante"]["acquis"] == 30.0


def test_un_mois_d_arret_en_jours_ouvres_acquiert_un_virgule_67():
    # Juin à octobre 2026, octobre en arrêt : 4 × 2,0833 + 1,6667 = 10,00
    # au lieu de 10,41.
    arret = _arret(date(2026, 10, 1), date(2026, 10, 31))
    avec = compute_cp_period_balances(
        ANCIEN, [arret], date(2026, 10, 31), policy=OUVRES
    )
    sans = compute_cp_period_balances(ANCIEN, [], date(2026, 10, 31), policy=OUVRES)
    assert sans["periode_courante"]["acquis"] == 10.41
    assert avec["periode_courante"]["acquis"] == 10.0


def test_un_mois_d_arret_seul_acquiert_quatre_cinquiemes_en_ouvres():
    # 0,8 × 25/12 = 1,6667, tronqué au centième en cours de période.
    arret = _arret(date(2026, 6, 1), date(2026, 6, 30))
    assert (
        calculate_acquired_cp(
            ANCIEN, date(2026, 6, 30), policy=OUVRES, mois_d_arret_maladie=1.0
        )
        == 1.66
    )
    soldes = compute_cp_period_balances(
        ANCIEN, [arret], date(2026, 6, 30), policy=OUVRES
    )
    assert soldes["periode_courante"]["acquis"] == 1.66


def test_une_periode_entiere_d_arret_acquiert_24_jours_ouvrables():
    arret = _arret(date(2025, 6, 1), date(2026, 5, 31))
    soldes = compute_cp_period_balances(
        ANCIEN, [arret], date(2026, 5, 31), policy=OUVRABLES
    )
    assert soldes["periode_courante"]["acquis"] == 24.0


@pytest.mark.parametrize(
    "nature, type_arret",
    [
        ("arret_at", "accident_travail"),
        ("arret_at", "accident_trajet"),
        ("arret_maladie_pro", "maladie_professionnelle"),
        ("arret_maternite", "maternite"),
        ("arret_paternite", "paternite"),
        ("arret_maladie", "mi_temps_therapeutique"),
    ],
)
def test_ces_arrets_gardent_le_taux_plein(nature, type_arret):
    arret = _arret(
        date(2024, 8, 1), date(2024, 9, 30), nature=nature, type_arret=type_arret
    )
    soldes = compute_cp_period_balances(
        ANCIEN, [arret], date(2025, 5, 31), policy=OUVRABLES
    )
    assert soldes["periode_courante"]["acquis"] == 30.0


def test_deux_demandes_sur_les_memes_jours_ne_comptent_qu_une_fois():
    arret = _arret(date(2024, 8, 1), date(2024, 9, 30))
    soldes = compute_cp_period_balances(
        ANCIEN, [arret, dict(arret)], date(2025, 5, 31), policy=OUVRABLES
    )
    assert soldes["periode_courante"]["acquis"] == 29.0


def test_la_periode_precedente_porte_aussi_l_arret():
    arret = _arret(date(2025, 8, 1), date(2025, 9, 30))
    soldes = compute_cp_period_balances(
        ANCIEN, [arret], date(2026, 10, 31), policy=OUVRABLES
    )
    assert soldes["periode_precedente"]["acquis"] == 29.0
    assert soldes["n1_remaining"] == 29.0


def test_le_mois_d_entree_au_prorata_perd_aussi_sa_part_d_arret():
    # Entrée le 14/09 : 17/30 de mois ; arrêt du 14 au 30/09 (17 jours sur 30).
    arret = _arret(date(2026, 9, 14), date(2026, 9, 30))
    soldes = compute_cp_period_balances(
        date(2026, 9, 14), [arret], date(2026, 9, 30), policy=OUVRES
    )
    # (17/30 − 0,2 × 17/30) × 25/12 = 0,9444
    assert soldes["periode_courante"]["acquis"] == 0.94


def test_les_soldes_affiches_suivent_l_acquis_reduit():
    arret = _arret(date(2024, 8, 1), date(2024, 9, 30))
    soldes = compute_absence_balances(
        ANCIEN, [arret], date(2025, 5, 31), policy=OUVRABLES
    )
    assert soldes["conges_payes_n"]["acquis"] == 29.0


# --- Reprise de soldes ---------------------------------------------------------

#: Reprise au 30/09/2026 : 1,5 jour de plus que le théorique en N.
REPRISE = EmployeeLeaveAdjustment(
    cp_n_opening_balance=1.5, cp_opening_reference_date=date(2026, 9, 30)
)


def test_un_arret_avant_la_reprise_ne_change_pas_le_solde_repris():
    arret = _arret(date(2026, 8, 1), date(2026, 8, 31))
    avec = compute_cp_period_balances(
        ANCIEN, [arret], date(2026, 10, 31), policy=OUVRES, adjustment=REPRISE
    )
    sans = compute_cp_period_balances(
        ANCIEN, [], date(2026, 10, 31), policy=OUVRES, adjustment=REPRISE
    )
    assert avec == sans


def test_un_arret_apres_la_reprise_reduit_l_acquis_de_martine():
    arret = _arret(date(2026, 10, 1), date(2026, 10, 31))
    avec = compute_cp_period_balances(
        ANCIEN, [arret], date(2026, 10, 31), policy=OUVRES, adjustment=REPRISE
    )
    sans = compute_cp_period_balances(
        ANCIEN, [], date(2026, 10, 31), policy=OUVRES, adjustment=REPRISE
    )
    # 0,2 × 25/12 = 0,4167 de moins (10,41 → 10,00).
    assert sans["periode_courante"]["solde"] == 11.91
    assert avec["periode_courante"]["solde"] == 11.5


def test_le_solde_a_la_date_de_reprise_reste_celui_du_cabinet():
    # L'arrêt couvre la date de reprise : seuls les jours après elle comptent.
    arret = _arret(date(2026, 9, 1), date(2026, 10, 31))
    a_la_reprise = compute_cp_period_balances(
        ANCIEN, [arret], date(2026, 9, 30), policy=OUVRES, adjustment=REPRISE
    )
    sans = compute_cp_period_balances(
        ANCIEN, [], date(2026, 9, 30), policy=OUVRES, adjustment=REPRISE
    )
    assert a_la_reprise == sans


def test_une_reprise_fidele_au_bulletin_ne_bouge_pas():
    reprise = EmployeeLeaveAdjustment(
        cp_n1_opening_balance=2.0,
        cp_n_opening_balance=-3.0,
        cp_opening_reference_date=date(2026, 5, 31),
        note="Import CP bulletin mai 2026",
    )
    arret = _arret(date(2026, 3, 1), date(2026, 5, 31))
    avec = compute_absence_balances(
        ANCIEN, [arret], date(2026, 5, 31), policy=OUVRABLES, adjustment=reprise
    )
    sans = compute_absence_balances(
        ANCIEN, [], date(2026, 5, 31), policy=OUVRABLES, adjustment=reprise
    )
    assert avec["conges_payes"] == sans["conges_payes"]


def test_le_roulement_de_periode_ne_compte_pas_l_arret_deux_fois():
    # Reprise au 31/07/2026, arrêt d'octobre à décembre 2026 : le N fermé au 31/05/2027
    # devient le N-1 du 30/06/2027, au centième.
    reprise = EmployeeLeaveAdjustment(
        cp_n_opening_balance=1.5, cp_opening_reference_date=date(2026, 7, 31)
    )
    arret = _arret(date(2026, 10, 1), date(2026, 12, 31))
    politique = dataclasses.replace(OUVRES, cp_carryover_enabled=True)
    cloture = compute_cp_period_balances(
        ANCIEN, [arret], date(2027, 5, 31), policy=politique, adjustment=reprise
    )
    suivant = compute_cp_period_balances(
        ANCIEN, [arret], date(2027, 6, 30), policy=politique, adjustment=reprise
    )
    assert cloture["n_remaining"] == 25.5  # 11,4 × 25/12 = 23,75 → 24, + 1,5
    assert suivant["n1_remaining"] == cloture["n_remaining"]


def test_l_ecart_d_une_reprise_en_cours_ignore_les_arrets_d_avant():
    arret = _arret(date(2026, 8, 1), date(2026, 8, 31))
    avec = compute_cp_period_balances(
        ANCIEN, [arret], date(2026, 9, 30), policy=OUVRES, reprise_au=date(2026, 9, 30)
    )
    sans = compute_cp_period_balances(ANCIEN, [], date(2026, 9, 30), policy=OUVRES)
    assert avec == sans


# --- Convention de la métallurgie (IDCC 3248), art. 84 -------------------------


def test_la_metallurgie_assimile_l_arret_dans_son_plafond():
    # 9 ans d'ancienneté au 01/06/2024 : 4 mois assimilés, l'arrêt en fait 2.
    arret = _arret(date(2024, 8, 1), date(2024, 9, 30))
    soldes = compute_cp_period_balances(
        ANCIEN, [arret], date(2025, 5, 31), policy=METALLURGIE
    )
    assert soldes["periode_courante"]["acquis"] == 30.0


def test_au_dela_du_plafond_la_metallurgie_revient_au_taux_legal():
    # 1 an d'ancienneté : 2 mois assimilés sur 3 ; le troisième à 2 jours.
    entree = date(2023, 6, 1)
    arret = _arret(date(2024, 8, 1), date(2024, 10, 31))
    soldes = compute_cp_period_balances(
        entree, [arret], date(2025, 5, 31), policy=METALLURGIE
    )
    assert soldes["periode_courante"]["acquis"] == 30.0  # 29,5 arrondi à 30
    arret_long = _arret(date(2024, 8, 1), date(2024, 12, 31))
    soldes = compute_cp_period_balances(
        entree, [arret_long], date(2025, 5, 31), policy=METALLURGIE
    )
    # 5 mois d'arrêt, 2 assimilés : 30 − 3 × 0,5 = 28,5 → 29.
    assert soldes["periode_courante"]["acquis"] == 29.0


def test_moins_d_un_an_d_anciennete_a_l_ouverture_de_la_periode_taux_legal():
    entree = date(2023, 6, 2)  # 11 mois et 30 jours au 01/06/2024
    arret = _arret(date(2024, 8, 1), date(2024, 9, 30))
    soldes = compute_cp_period_balances(
        entree, [arret], date(2025, 5, 31), policy=METALLURGIE
    )
    assert soldes["periode_courante"]["acquis"] == 29.0


def test_un_an_jour_pour_jour_a_l_ouverture_suffit():
    entree = date(2023, 6, 1)
    arret = _arret(date(2024, 8, 1), date(2024, 9, 30))
    soldes = compute_cp_period_balances(
        entree, [arret], date(2025, 5, 31), policy=METALLURGIE
    )
    assert soldes["periode_courante"]["acquis"] == 30.0


@pytest.mark.parametrize(
    "annees, mois",
    [
        (0, 0.0),
        (1, 2.0),
        (4, 2.0),
        (5, 4.0),
        (9, 4.0),
        (10, 6.0),
        (19, 6.0),
        (20, 8.0),
        (35, 8.0),
    ],
)
def test_bareme_de_l_article_84(annees, mois):
    assert (
        METALLURGIE_3248_ART_84.mois_assimiles(anciennete_annees=annees, groupe=None)
        == mois
    )


@pytest.mark.parametrize("groupe", ["F", "G", "H", "I"])
def test_les_groupes_f_a_i_ont_un_an_quelle_que_soit_l_anciennete(groupe):
    assert (
        METALLURGIE_3248_ART_84.mois_assimiles(anciennete_annees=0, groupe=groupe)
        == 12.0
    )


def test_un_cadre_du_groupe_f_garde_le_taux_plein_sur_six_mois_d_arret():
    entree = date(2024, 3, 1)
    ctx = EmployeeCpSeniorityContext(hire_date=entree, groupe_emploi="F")
    arret = _arret(date(2024, 8, 1), date(2025, 1, 31))
    soldes = compute_cp_period_balances(
        entree, [arret], date(2025, 5, 31), policy=METALLURGIE, employee_ctx=ctx
    )
    assert soldes["periode_courante"]["acquis"] == 30.0


def test_l_anciennete_se_lit_sur_la_date_d_anciennete_de_la_fiche():
    entree = date(2024, 3, 1)
    ctx = EmployeeCpSeniorityContext(
        hire_date=entree, seniority_reference_date=date(2010, 1, 1)
    )
    arret = _arret(date(2024, 8, 1), date(2024, 11, 30))
    soldes = compute_cp_period_balances(
        entree, [arret], date(2025, 5, 31), policy=METALLURGIE, employee_ctx=ctx
    )
    # 14 ans à l'ouverture : 6 mois assimilés, les 4 mois d'arrêt aussi.
    assert soldes["periode_courante"]["acquis"] == 30.0


def test_le_plafond_conventionnel_compte_les_arrets_d_avant_la_reprise():
    # 1 an d'ancienneté, 2 mois assimilés. Juillet (avant la reprise du 31/07)
    # en use un ; septembre et octobre (après) : un assimilé, un à 2 jours.
    entree = date(2025, 6, 1)
    reprise = EmployeeLeaveAdjustment(cp_opening_reference_date=date(2026, 7, 31))
    arrets = [
        _arret(date(2026, 7, 1), date(2026, 7, 31)),
        _arret(date(2026, 9, 1), date(2026, 10, 31)),
    ]
    soldes = compute_cp_period_balances(
        entree, arrets, date(2026, 10, 31), policy=METALLURGIE, adjustment=reprise
    )
    # 5 mois à 2,5 − 0,5 = 12 jours.
    assert soldes["periode_courante"]["acquis"] == 12.0


def test_seule_la_metallurgie_a_une_regle_conventionnelle():
    assert assimilation_maladie_de_la_convention("3248") is METALLURGIE_3248_ART_84
    assert assimilation_maladie_de_la_convention(" 3248 ") is METALLURGIE_3248_ART_84
    assert assimilation_maladie_de_la_convention("0292") is None
    assert assimilation_maladie_de_la_convention("292") is None
    assert assimilation_maladie_de_la_convention(None) is None
    assert assimilation_maladie_de_la_convention("") is None


# --- Réglage de la société : la convention de son IDCC -------------------------


class _Reponse:
    def __init__(self, data):
        self.data = data


class _Requete:
    def __init__(self, base, table):
        self._base, self._table = base, table

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        return _Reponse(self._base[self._table])


class _Base:
    def __init__(self, **tables):
        self.tables = tables

    def table(self, nom):
        return _Requete(self.tables, nom)


def _politique_de(monkeypatch, idcc):
    from app.modules.absences.infrastructure import leave_settings_repository as repo

    monkeypatch.setattr(
        repo,
        "supabase",
        _Base(company_leave_settings=[], companies=[{"idcc": idcc}]),
    )
    repo.oublier_les_conventions()
    return repo.get_leave_policy("societe")


def test_une_societe_de_la_metallurgie_suit_l_article_84(monkeypatch):
    assert (
        _politique_de(monkeypatch, "3248").cp_maladie_assimilation
        is METALLURGIE_3248_ART_84
    )


@pytest.mark.parametrize("idcc", ["0292", None])
def test_les_autres_societes_suivent_la_loi(monkeypatch, idcc):
    assert _politique_de(monkeypatch, idcc).cp_maladie_assimilation is None


def test_le_groupe_d_emplois_se_lit_sur_la_classification():
    from app.modules.absences.application.cp_seniority_queries import (
        build_employee_cp_seniority_context,
    )

    ctx = build_employee_cp_seniority_context(
        {
            "hire_date": "2020-01-01",
            "classification_conventionnelle": {"groupe_emploi": "F"},
        }
    )
    assert ctx.groupe_emploi == "F"
    sans = build_employee_cp_seniority_context({"hire_date": "2020-01-01"})
    assert sans.groupe_emploi is None


def test_l_ecart_d_une_reprise_importee_ignore_les_arrets_d_avant():
    from app.modules.absences.application.leave_settings_commands import (
        _soldes_a_la_reprise,
    )

    arret = _arret(date(2026, 8, 1), date(2026, 8, 31))
    assert _soldes_a_la_reprise(
        ANCIEN, [arret], date(2026, 9, 30), OUVRES, 0.0, 1.5
    ) == _soldes_a_la_reprise(ANCIEN, [], date(2026, 9, 30), OUVRES, 0.0, 1.5)
