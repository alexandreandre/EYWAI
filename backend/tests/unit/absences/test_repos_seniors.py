"""Repos seniors de la plasturgie — accord du 18 avril 2025, articles 3 et 4.

Texte : data/_sources/plasturgie/accord-18-04-2025-repos-seniors-lu-23-11-2026.txt
"""

from datetime import date, timedelta

import pytest

from app.modules.absences.application.balance_display import balances_to_api_list
from app.modules.absences.domain.cp_seniority import EmployeeCpSeniorityContext
from app.modules.absences.domain.leave_policy import LeavePolicySettings
from app.modules.absences.domain.repos_seniors import (
    ALERTE_DATE_NAISSANCE,
    absent_toute_la_periode,
    age_au,
    droit_repos_seniors,
    premier_juin_de_rattachement,
    refus_pose_repos_seniors,
    solde_repos_seniors,
)
from app.modules.absences.domain.rules import compute_absence_balances

JUIN_2026 = date(2026, 6, 1)


def _naissance_pour_age(age: int, au: date = JUIN_2026) -> date:
    """Date de naissance qui donne `age` ans révolus au 1er juin (né le 15 janvier)."""
    return date(au.year - age, 1, 15)


def _jours(debut: date, fin: date) -> list[str]:
    out = []
    jour = debut
    while jour <= fin:
        out.append(jour.isoformat())
        jour += timedelta(days=1)
    return out


def _absence(type_: str, jours: list[str], **extra) -> dict:
    return {"type": type_, "status": "validated", "selected_days": jours, **extra}


def _repos(*jours: str) -> dict:
    return _absence("repos_senior", list(jours))


ARRET_TOUTE_LA_PERIODE = _absence(
    "arret_maladie", _jours(date(2025, 6, 1), date(2026, 5, 31))
)


class TestAge:
    @pytest.mark.parametrize(
        ("age", "jours"),
        [(57, 0), (58, 1), (59, 1), (60, 2), (64, 2)],
    )
    def test_jours_selon_l_age_au_1er_juin(self, age, jours):
        droit = droit_repos_seniors(_naissance_pour_age(age), JUIN_2026, [])
        assert droit.age == age
        assert droit.jours == jours
        assert droit.alerte is None

    def test_l_anniversaire_du_1er_juin_compte(self):
        assert age_au(date(1968, 6, 1), JUIN_2026) == 58
        assert droit_repos_seniors(date(1968, 6, 1), JUIN_2026, []).jours == 1

    def test_l_anniversaire_du_2_juin_ne_compte_pas_encore(self):
        assert droit_repos_seniors(date(1968, 6, 2), JUIN_2026, []).jours == 0

    def test_rien_avant_le_1er_juin_2025(self):
        droit = droit_repos_seniors(_naissance_pour_age(62, date(2024, 6, 1)), date(2024, 6, 1), [])
        assert droit.jours == 0
        assert "1er juin 2025" in droit.motif

    def test_premiere_attribution_au_1er_juin_2025(self):
        droit = droit_repos_seniors(
            _naissance_pour_age(61, date(2025, 6, 1)), date(2025, 6, 1), []
        )
        assert droit.jours == 2
        assert droit.fin_de_prise == date(2026, 5, 31)

    def test_l_attribution_se_fait_le_1er_juin(self):
        with pytest.raises(ValueError):
            droit_repos_seniors(_naissance_pour_age(60), date(2026, 7, 1), [])


class TestAbsence:
    def test_absence_continue_sur_les_12_mois_aucun_jour(self):
        droit = droit_repos_seniors(
            _naissance_pour_age(60), JUIN_2026, [ARRET_TOUTE_LA_PERIODE]
        )
        assert droit.jours == 0
        assert "sans interruption" in droit.motif

    def test_absences_de_motifs_differents_bout_a_bout(self):
        """« quelle qu'en soit le motif » : un arrêt puis un congé sans solde
        qui se suivent forment une absence continue."""
        absences = [
            _absence("arret_maladie", _jours(date(2025, 6, 1), date(2025, 12, 31))),
            _absence("sans_solde", _jours(date(2026, 1, 1), date(2026, 5, 31))),
        ]
        assert droit_repos_seniors(_naissance_pour_age(60), JUIN_2026, absences).jours == 0

    def test_absence_partielle_ne_fait_rien_perdre(self):
        """Un seul jour ouvré travaillé dans les 12 mois rompt la continuité."""
        jours = [j for j in ARRET_TOUTE_LA_PERIODE["selected_days"] if j != "2026-03-11"]
        droit = droit_repos_seniors(
            _naissance_pour_age(60), JUIN_2026, [_absence("arret_maladie", jours)]
        )
        assert droit.jours == 2

    def test_absence_de_onze_mois_ne_fait_rien_perdre(self):
        arret = _absence("arret_maladie", _jours(date(2025, 7, 1), date(2026, 5, 31)))
        assert droit_repos_seniors(_naissance_pour_age(59), JUIN_2026, [arret]).jours == 1

    def test_les_week_ends_et_feries_ne_rompent_pas_la_continuite(self):
        """Des congés posés en jours ouvrés seulement couvrent la période."""
        ouvres = [
            j
            for j in ARRET_TOUTE_LA_PERIODE["selected_days"]
            if date.fromisoformat(j).weekday() < 5
        ]
        assert absent_toute_la_periode(
            [_absence("conge_paye", ouvres)], date(2025, 6, 1), date(2026, 5, 31)
        )

    def test_une_demi_journee_est_une_absence_partielle(self):
        absence = _absence(
            "conge_paye",
            ARRET_TOUTE_LA_PERIODE["selected_days"],
            demi_journees={"2026-02-10": "matin"},
        )
        assert droit_repos_seniors(_naissance_pour_age(60), JUIN_2026, [absence]).jours == 2

    def test_une_absence_non_validee_ne_compte_pas(self):
        en_attente = {**ARRET_TOUTE_LA_PERIODE, "status": "pending"}
        assert droit_repos_seniors(_naissance_pour_age(60), JUIN_2026, [en_attente]).jours == 2

    def test_entre_apres_le_1er_juin_rien_pour_cette_periode(self):
        droit = droit_repos_seniors(
            _naissance_pour_age(60), JUIN_2026, [], date_embauche=date(2026, 6, 2)
        )
        assert droit.jours == 0
        assert "1er juin 2027" in droit.motif


class TestDateDeNaissanceAbsente:
    def test_zero_jour_et_une_alerte(self):
        droit = droit_repos_seniors(None, JUIN_2026, [])
        assert droit.jours == 0
        assert droit.alerte == ALERTE_DATE_NAISSANCE
        assert "date de naissance" in droit.alerte

    def test_le_compteur_porte_l_alerte(self):
        solde = solde_repos_seniors([], date(2026, 9, 1), enabled=True, date_naissance=None)
        assert solde["acquis"] == 0
        assert solde["alerte"] == ALERTE_DATE_NAISSANCE

    def test_l_ecran_montre_l_alerte_sous_la_ligne(self):
        soldes = compute_absence_balances(
            date(2010, 1, 1),
            [],
            date(2026, 9, 1),
            policy=LeavePolicySettings(repos_seniors_enabled=True),
            employee_ctx=EmployeeCpSeniorityContext(hire_date=date(2010, 1, 1)),
        )
        lignes = balances_to_api_list(
            soldes, policy=LeavePolicySettings(repos_seniors_enabled=True)
        )
        ligne = next(b for b in lignes if b["type"] == "Repos seniors")
        assert ligne["alerte"] == ALERTE_DATE_NAISSANCE


class TestPeriodeDePrise:
    NAISSANCE = date(1965, 1, 15)  # 61 ans au 1er juin 2026

    def test_rattachement_au_1er_juin(self):
        assert premier_juin_de_rattachement(date(2026, 5, 31)) == date(2025, 6, 1)
        assert premier_juin_de_rattachement(date(2026, 6, 1)) == date(2026, 6, 1)

    def test_solde_dans_la_periode(self):
        absences = [_repos("2026-10-05")]
        solde = solde_repos_seniors(
            absences, date(2026, 12, 1), enabled=True, date_naissance=self.NAISSANCE
        )
        assert solde == {"acquis": 2.0, "pris": 1.0, "solde": 1.0}

    def test_jours_perdus_apres_le_31_mai_n_plus_1(self):
        """Le 31 mai 2027 il reste 1 jour ; le 1er juin 2027 il est perdu,
        et le droit de la nouvelle période s'ouvre sans report."""
        absences = [_repos("2026-10-05")]
        veille = solde_repos_seniors(
            absences, date(2027, 5, 31), enabled=True, date_naissance=self.NAISSANCE
        )
        assert veille["solde"] == 1.0
        lendemain = solde_repos_seniors(
            absences, date(2027, 6, 1), enabled=True, date_naissance=self.NAISSANCE
        )
        assert lendemain == {"acquis": 2.0, "pris": 0.0, "solde": 2.0}

    def test_pas_de_prorata_pour_une_entree_avant_le_1er_juin(self):
        solde = solde_repos_seniors(
            [],
            date(2026, 9, 1),
            enabled=True,
            date_naissance=self.NAISSANCE,
            date_embauche=date(2026, 5, 4),
        )
        assert solde["acquis"] == 2.0


class TestCaseEteinte:
    def test_eteinte_par_defaut(self):
        assert LeavePolicySettings().repos_seniors_enabled is False

    def test_compteur_a_zero_sans_alerte(self):
        solde = solde_repos_seniors(
            [_repos("2026-10-05")], date(2026, 12, 1), enabled=False, date_naissance=None
        )
        assert solde == {"acquis": 0.0, "pris": 0.0, "solde": 0.0}

    def test_aucune_ligne_a_l_ecran(self):
        soldes = compute_absence_balances(
            date(2010, 1, 1),
            [],
            date(2026, 9, 1),
            employee_ctx=EmployeeCpSeniorityContext(
                hire_date=date(2010, 1, 1), birth_date=date(1960, 1, 1)
            ),
        )
        assert soldes["repos_seniors"]["acquis"] == 0
        lignes = balances_to_api_list(soldes, policy=LeavePolicySettings())
        assert all(b["type"] != "Repos seniors" for b in lignes)

    def test_allumee_la_ligne_apparait(self):
        policy = LeavePolicySettings(repos_seniors_enabled=True)
        soldes = compute_absence_balances(
            date(2010, 1, 1),
            [_repos("2026-10-05")],
            date(2026, 12, 1),
            policy=policy,
            employee_ctx=EmployeeCpSeniorityContext(
                hire_date=date(2010, 1, 1), birth_date=date(1960, 1, 1)
            ),
        )
        ligne = next(
            b for b in balances_to_api_list(soldes, policy=policy) if b["type"] == "Repos seniors"
        )
        assert (ligne["acquired"], ligne["taken"], ligne["remaining"]) == (2.0, 1.0, 1.0)
        assert "alerte" not in ligne


class TestRefusDePose:
    DROIT_2026 = droit_repos_seniors(date(1967, 1, 15), JUIN_2026, [])  # 59 ans : 1 jour

    def _refus(self, jours, *, enabled=True, demi=False, deja=0.0):
        return refus_pose_repos_seniors(
            enabled=enabled,
            jours_demandes=jours,
            demi_journees=demi,
            droit_par_periode={JUIN_2026: self.DROIT_2026},
            deja_poses_par_periode={JUIN_2026: deja},
        )

    def test_case_eteinte_refusee(self):
        assert "pas activés" in self._refus([date(2026, 10, 5)], enabled=False)

    def test_demi_journee_refusee(self):
        assert "à la journée" in self._refus([date(2026, 10, 5)], demi=True)

    def test_dans_le_droit_acceptee(self):
        assert self._refus([date(2026, 10, 5)]) is None

    def test_au_dela_du_droit_refusee(self):
        refus = self._refus([date(2026, 10, 5), date(2026, 10, 6)])
        assert refus == (
            "Repos seniors insuffisants : 1 jour restant sur la période du "
            "1er juin 2026 au 31 mai 2027, pour 2 jours demandés."
        )

    def test_deja_pris_refusee(self):
        assert "0 jour restant" in self._refus([date(2026, 10, 5)], deja=1.0)

    def test_date_de_naissance_absente_refusee(self):
        refus = refus_pose_repos_seniors(
            enabled=True,
            jours_demandes=[date(2026, 10, 5)],
            demi_journees=False,
            droit_par_periode={JUIN_2026: droit_repos_seniors(None, JUIN_2026, [])},
            deja_poses_par_periode={},
        )
        assert refus == ALERTE_DATE_NAISSANCE


class TestBranchements:
    def test_type_d_absence_connu(self):
        from typing import get_args

        from app.modules.absences.domain.enums import AbsenceType
        from app.modules.absences.schemas.requests import AbsenceType as AbsenceTypeApi

        assert "repos_senior" in get_args(AbsenceType)
        assert "repos_senior" in get_args(AbsenceTypeApi)

    def test_n_ecrit_jamais_le_calendrier(self):
        """Comme le JTC : le jour reste travaillé, la paie ne retire rien."""
        from app.modules.absences.domain.enums import type_calendrier_projete
        from app.modules.schedules.domain.ecart_rules import (
            validated_absence_days_in_month,
        )

        assert type_calendrier_projete("repos_senior") is None
        assert validated_absence_days_in_month([_repos("2026-10-05")], 2026, 10) == set()

    def test_reglage_lu_et_ecrit(self):
        from app.modules.absences.application.leave_settings_commands import (
            _WRITABLE_POLICY_KEYS,
        )
        from app.modules.absences.infrastructure.leave_settings_repository import (
            _row_to_policy,
        )

        assert "repos_seniors_enabled" in _WRITABLE_POLICY_KEYS
        assert _row_to_policy({"repos_seniors_enabled": True}).repos_seniors_enabled is True
        assert _row_to_policy({}).repos_seniors_enabled is False

    def test_se_modifie_comme_un_conge(self):
        from app.modules.absences.application.modification import TYPES_MODIFIABLES

        assert "repos_senior" in TYPES_MODIFIABLES

    def test_colonne_du_bulletin_seulement_si_alimentee(self):
        from app.modules.payroll.documents.bulletin_view import construire_compteurs

        def colonnes(solde):
            bulletin = {"pied_de_page": {"solde_conges": {"conges_payes": {}, **solde}}}
            return [c["titre"] for c in construire_compteurs(bulletin)["colonnes"]]

        assert "Repos seniors" not in colonnes({})
        assert "Repos seniors" in colonnes(
            {"repos_seniors": {"acquis": 2.0, "pris": 0.0, "solde": 2.0}}
        )

    def test_depart_jours_perdus_sans_indemnite(self):
        from app.modules.payroll.engine.bulletin import alertes_des_compteurs_de_conges

        alertes = alertes_des_compteurs_de_conges(
            {"repos_seniors": {"acquis": 2.0, "pris": 1.0, "solde": 1.0}},
            bulletin_de_sortie=True,
        )
        alerte = next(a for a in alertes if a["code"] == "repos_seniors_perdus_au_depart")
        assert alerte["message"] == (
            "Départ : 1 j de repos seniors non pris, perdus sans indemnité "
            "(accord plasturgie du 18 avril 2025, art. 4)."
        )
        assert alertes_des_compteurs_de_conges(
            {"repos_seniors": {"acquis": 2.0, "pris": 1.0, "solde": 1.0}}
        ) == []
