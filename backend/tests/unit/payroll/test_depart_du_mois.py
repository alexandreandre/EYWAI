"""Départ autre qu'une fin de CDD : la génération pose les compteurs de congés.

Sans eux, le bulletin d'une démission ou d'un licenciement reprenait
l'estimation du dossier de départ (mois sans bulletin complétés au salaire du
contrat) au lieu de la règle légale par période (revue du 02/10/2026).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from app.modules.payroll.documents import payslip_run_heures as run


class _Contexte:
    is_cdd = False
    is_interim = False
    cumuls: dict = {}

    def est_dernier_mois_cdd(self, *_):
        return False

    def est_dernier_mois_mission(self, *_):
        return False


COMPTEURS = {"cp": "compteurs"}
PERIODES = {"periode_en_cours": {"droits": 25.0, "restants": 20.0}}


def _poser(sortie):
    ctx = _Contexte()
    with patch.object(run, "resolve_exit_state_for_payslip", return_value=sortie), patch(
        "app.modules.absences.application.queries.get_absence_balances_for_payslip",
        return_value=COMPTEURS,
    ) as compteurs, patch.object(run, "periodes_depuis_compteurs", return_value=PERIODES), patch.object(
        run, "_brut_de_la_periode_precedente", return_value=26400.0
    ):
        run.poser_le_depart_du_mois(ctx, "emp-1", 2026, 4, date(2026, 4, 1), date(2026, 4, 30))
    return ctx, compteurs


def test_une_demission_du_mois_pose_les_compteurs_de_conges():
    ctx, compteurs = _poser(({"indemnite_conges": {"montant": 999.0}}, False))
    compteurs.assert_called_once_with("emp-1", 2026, 4)
    assert ctx.depart_du_mois is True
    assert ctx.cp_fin_de_contrat == PERIODES
    # L'estimation du dossier reste : le moteur ne la remplace que s'il calcule.
    assert ctx.exit_indemnities == {"indemnite_conges": {"montant": 999.0}}


def test_un_depart_sans_indemnites_calculees_compte_aussi():
    ctx, compteurs = _poser((None, True))
    compteurs.assert_called_once()
    assert ctx.depart_du_mois is True


def test_sans_depart_ce_mois_rien_n_est_lu():
    ctx, compteurs = _poser((None, False))
    compteurs.assert_not_called()
    assert ctx.depart_du_mois is False
    assert ctx.cp_fin_de_contrat is None
