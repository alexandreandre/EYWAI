"""Congés payés : une absence non assimilée à du travail effectif n'acquiert rien.

Code du travail (lus sur code.travail.gouv.fr le 10/11/2026) :
- L3141-3 : « deux jours et demi ouvrables par mois de travail effectif » ;
- L3141-4 : « Sont assimilées à un mois de travail effectif [...] les périodes
  équivalentes à quatre semaines ou vingt-quatre jours de travail » ;
- L3141-5 : liste limitative des périodes comptées comme travail effectif
  (congés payés, maternité, AT/MP, arrêt maladie...). L'absence injustifiée et
  le congé sans solde n'y sont pas.

Un mois où le salarié a travaillé au moins quatre semaines (20 jours ouvrés
pour une semaine de cinq jours) compte entier ; en deçà, au prorata des jours
travaillés sur 20. Un mois entier d'absence injustifiée n'acquiert rien.

Retour de la réunion du 10/11/2026 (Colorplast, X.P.) : entré le 23/09, absent
tout octobre, sorti le 29/10 : 4,16 jours acquis (2,08 + 2,08) au lieu du
solde repris du cabinet au 30/09 seul.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.modules.absences.domain.cp_absences_non_assimilees import (
    jours_non_assimiles_des_demandes,
    mois_perdus_par_absences,
)
from app.modules.absences.domain.leave_policy import (
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
)
from app.modules.absences.domain.rules import (
    calculate_acquired_cp,
    calculate_acquired_cp_for_period,
    compute_cp_balances_for_bulletin,
)

pytestmark = pytest.mark.unit

OUVRES = LeavePolicySettings(
    cp_acquisition_days_per_month=25 / 12, cp_counting_unit="ouvre"
)
OUVRABLES = LeavePolicySettings()


def _jours_ouvres(debut: date, fin: date) -> frozenset[date]:
    jours = set()
    jour = debut
    while jour <= fin:
        if jour.weekday() < 5:
            jours.add(jour)
        jour += timedelta(days=1)
    return frozenset(jours)


OCTOBRE_ABSENT = _jours_ouvres(date(2026, 10, 1), date(2026, 10, 31))


class TestMoisPerdus:
    def test_mois_entier_absent_perd_le_mois(self):
        assert mois_perdus_par_absences(
            OCTOBRE_ABSENT, debut=date(2026, 6, 1), fin=date(2026, 10, 31)
        ) == pytest.approx(1.0)

    def test_une_journee_d_absence_garde_le_mois_entier(self):
        # 22 jours ouvrés en octobre 2026, 21 travaillés >= 20 : quatre semaines.
        perte = mois_perdus_par_absences(
            {date(2026, 10, 14)}, debut=date(2026, 6, 1), fin=date(2026, 10, 31)
        )
        assert perte == 0.0

    def test_trois_jours_d_absence_perdent_un_vingtieme(self):
        # 22 ouvrés − 3 = 19 travaillés, 19/20 du mois.
        perte = mois_perdus_par_absences(
            {date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14)},
            debut=date(2026, 6, 1),
            fin=date(2026, 10, 31),
        )
        assert perte == pytest.approx(0.05)

    def test_absence_jusqu_a_la_reprise_ne_retire_rien(self):
        assert (
            mois_perdus_par_absences(
                OCTOBRE_ABSENT,
                debut=date(2026, 6, 1),
                fin=date(2026, 10, 31),
                reprise_au=date(2026, 10, 31),
            )
            == 0.0
        )

    def test_absence_apres_la_fin_ne_compte_pas(self):
        assert (
            mois_perdus_par_absences(
                OCTOBRE_ABSENT, debut=date(2026, 6, 1), fin=date(2026, 9, 30)
            )
            == 0.0
        )

    def test_mois_de_sortie_perd_sa_part_creditee(self):
        # Sorti le 29/10 sans avoir travaillé : la part du mois créditée
        # (21 ouvrés au 29/10, 20 au moins : le mois entier) est perdue.
        perte = mois_perdus_par_absences(
            OCTOBRE_ABSENT,
            debut=date(2026, 6, 1),
            fin=date(2026, 10, 29),
            fraction_du_mois={(2026, 10): 1.0},
        )
        assert perte == pytest.approx(1.0)

    def test_samedi_et_dimanche_ignores(self):
        perte = mois_perdus_par_absences(
            {date(2026, 10, 3), date(2026, 10, 4)},
            debut=date(2026, 6, 1),
            fin=date(2026, 10, 31),
        )
        assert perte == 0.0


class TestDemandes:
    def test_conge_sans_solde_valide_est_non_assimile(self):
        jours = jours_non_assimiles_des_demandes(
            [
                {"type": "sans_solde", "status": "validated", "selected_days": ["2026-10-05"]},
                {"type": "conge_paye", "status": "validated", "selected_days": ["2026-10-06"]},
                {"type": "sans_solde", "status": "pending", "selected_days": ["2026-10-07"]},
            ]
        )
        assert jours == frozenset({date(2026, 10, 5)})


class TestAcquis:
    def test_mois_absent_n_acquiert_rien(self):
        avant = calculate_acquired_cp(
            date(2026, 6, 1), date(2026, 10, 31), policy=OUVRES
        )
        apres = calculate_acquired_cp(
            date(2026, 6, 1),
            date(2026, 10, 31),
            policy=OUVRES,
            jours_non_assimiles=OCTOBRE_ABSENT,
        )
        assert avant == pytest.approx(10.41)
        assert apres == pytest.approx(8.33)

    def test_periode_close_aussi(self):
        acquis = calculate_acquired_cp_for_period(
            date(2025, 1, 1),
            date(2026, 6, 1),
            date(2027, 5, 31),
            policy=OUVRES,
            jours_non_assimiles=OCTOBRE_ABSENT,
        )
        # 11 mois × 2,083 = 22,91 → arrondi supérieur à la clôture : 23.
        assert acquis == 23.0

    def test_cas_du_10_11_reprise_au_30_09_puis_octobre_absent_et_sortie_le_29(self):
        # Reprise Quadra au 30/09 : 0,55 j au compteur N (entré le 23/09).
        reprise = EmployeeLeaveAdjustment(
            cp_n_opening_balance=-1.53,
            cp_opening_reference_date=date(2026, 9, 30),
        )
        sans_absence = compute_cp_balances_for_bulletin(
            date(2026, 9, 23),
            [],
            date(2026, 10, 29),
            policy=OUVRES,
            adjustment=reprise,
            date_de_sortie=date(2026, 10, 29),
        )
        avec_absence = compute_cp_balances_for_bulletin(
            date(2026, 9, 23),
            [],
            date(2026, 10, 29),
            policy=OUVRES,
            adjustment=reprise,
            date_de_sortie=date(2026, 10, 29),
            jours_non_assimiles=_jours_ouvres(date(2026, 10, 1), date(2026, 10, 29)),
        )
        assert sans_absence["periode_courante"]["solde"] == pytest.approx(2.63)
        assert avec_absence["periode_courante"]["acquis"] == pytest.approx(2.08)
        assert avec_absence["periode_courante"]["solde"] == pytest.approx(0.55)

    def test_sans_solde_des_demandes_compte_sans_planning(self):
        demandes = [
            {
                "type": "sans_solde",
                "status": "validated",
                "selected_days": [j.isoformat() for j in sorted(OCTOBRE_ABSENT)],
            }
        ]
        lignes = compute_cp_balances_for_bulletin(
            date(2026, 6, 1), demandes, date(2026, 10, 31), policy=OUVRES
        )
        assert lignes["periode_courante"]["acquis"] == pytest.approx(8.33)

    def test_ouvrables_meme_regle(self):
        acquis = calculate_acquired_cp(
            date(2026, 6, 1),
            date(2026, 10, 31),
            policy=OUVRABLES,
            jours_non_assimiles=OCTOBRE_ABSENT,
        )
        # 4 mois × 2,5 = 10 (arrondi supérieur en ouvrables).
        assert acquis == 10.0
