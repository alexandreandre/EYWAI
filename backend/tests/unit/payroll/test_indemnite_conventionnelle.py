"""Indemnité conventionnelle de licenciement, de départ ou de mise à la retraite.

Aucun champ ne permettait de saisir une indemnité conventionnelle plus
favorable que le minimum légal. Cas réel : un départ volontaire à la retraite
de juin 2026 (plus de 30 ans d'ancienneté), payé 12 712,27 € par l'ancien
logiciel au barème de la convention collective, quand Martine ne connaît que
le minimum légal de deux mois de salaire (5 533,08 € sur un salaire de
référence de 2 766,54 €).

Décision d'Alexandre : pas de barème conventionnel extrait ; le minimum légal,
et une saisie du montant conventionnel. L'indemnité versée est la plus haute
des deux.

Sources ouvertes le 11/10/2026 :
- BOSS, « Indemnités de rupture » (mis à jour le 26/06/2026), § 280 : « Il n'y
  a pas de cumul possible entre l'indemnité légale et l'indemnité
  conventionnelle : seule l'indemnité conventionnelle est due si elle est plus
  favorable. » ; § 1550 : « L'indemnité légale étant un minimum, le salarié
  peut bénéficier le cas échéant d'une indemnité plus favorable prévue dans la
  convention ou accord collectif » ; § 1630 (mise à la retraite) : « au
  minimum à l'indemnité légale de licenciement, sauf dispositions
  conventionnelles ou contractuelles plus avantageuses ».
- Même rubrique, § 80, 300, 360, 1640 et 1650 : la limite de la CSG/CRDS et le
  troisième critère des limites d'exonération sont « le montant prévu par la
  convention collective de branche, l'accord professionnel ou
  interprofessionnel ou, à défaut, par la loi ». Le montant saisi est traité
  comme ce minimum conventionnel de branche.
- Cahier technique DSN 2026.1 (S21.G00.52.001) : 004 indemnité conventionnelle
  de mise à la retraite, 006 indemnité conventionnelle de départ à la retraite,
  007 indemnité légale de licenciement, 021 indemnité conventionnelle
  (supplémentaire aux indemnités légales).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.dsn_export.domain.evenements import indemnites_de_rupture
from app.modules.employee_exits.application import commands
from app.modules.employee_exits.application.dto import EmployeeExitApplicationError
from app.modules.employee_exits.schemas.requests import EmployeeExitCreate, EmployeeExitUpdate
from app.modules.payroll.engine.bulletin import creer_bulletin_sortie
from app.modules.payroll.engine.calcul_indemnites_sortie import calculer_indemnites_sortie
from app.modules.payroll.engine.indemnites_sortie_brut import lignes_indemnites_sortie_soumises
from tests.unit.base_en_memoire import BaseEnMemoire
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

_ICCP = "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"
_SANS_ICCP = {"montant": 0.0, "description": "ICCP", "details": {}}
PASS_2026 = 48060.0


def _salarie(hire_date: str = "1996-06-04") -> dict:
    return {
        "id": "emp-1",
        "hire_date": hire_date,
        "contract_type": "CDI",
        "salaire_de_base": {"valeur": 2500.0},
        "baremes": {"pss": {"annuel": PASS_2026, "mensuel": 4005.0}},
    }


def _bulletins(annee_fin: int, mois_fin: int, brut: float = 2766.54) -> BaseEnMemoire:
    """Douze bulletins jusqu'au mois précédant `mois_fin`, et l'année précédente."""
    lignes = []
    annee, mois = annee_fin, mois_fin
    for _ in range(12):
        mois -= 1
        if mois == 0:
            annee, mois = annee - 1, 12
        lignes.append(
            {
                "employee_id": "emp-1",
                "year": annee,
                "month": mois,
                "payslip_data": {
                    "salaire_brut": brut,
                    "calcul_du_brut": [{"libelle": "Salaire de base", "gain": brut}],
                },
            }
        )
    return BaseEnMemoire(
        {
            "payslips": lignes,
            "employee_schedules": [
                {
                    "employee_id": "emp-1",
                    "year": annee_fin - 1,
                    "month": 12,
                    "cumuls": {"cumuls": {"brut_annee_civile": 30000.0}},
                }
            ],
        }
    )


def _depart(exit_type: str = "depart_retraite", notes: dict | None = None, **extra) -> dict:
    return {
        "id": "exit-1",
        "exit_type": exit_type,
        "exit_request_date": "2026-05-31",
        "last_working_day": "2026-06-30",
        "notice_period_days": 0,
        "notice_indemnity_type": "not_applicable",
        "exit_notes": notes or {},
        **extra,
    }


# ---------------------------------------------------------------------------
# Départ volontaire : soumis, au brut, déclaré en 006
# ---------------------------------------------------------------------------


@patch(_ICCP, return_value=_SANS_ICCP)
def test_le_depart_volontaire_verse_le_montant_conventionnel_plus_eleve(_iccp):
    dossier = calculer_indemnites_sortie(
        _salarie(), _depart(notes={"indemnite_conventionnelle": 12712.27}), _bulletins(2026, 6)
    )

    indemnite = dossier["indemnite_depart_retraite"]
    assert indemnite["montant"] == 12712.27
    assert indemnite["montant_legal"] == 5533.08
    assert indemnite["base_calcul"] == "Conventionnelle"
    assert "12 712,27" in indemnite["calcul"] and "5 533,08" in indemnite["calcul"]
    assert dossier["total_gross_indemnities"] == 12712.27

    contexte = build_test_contexte(salaire_base=2500.0)
    contexte.exit_indemnities = dossier
    lignes = lignes_indemnites_sortie_soumises(contexte)
    assert ("Indemnité conventionnelle de départ à la retraite", 12712.27) in [
        (l["libelle"], l["gain"]) for l in lignes
    ]
    assert indemnites_de_rupture({"calcul_du_brut": lignes}, sortie=True) == [("006", 12712.27, True)]


@patch(_ICCP, return_value=_SANS_ICCP)
def test_un_montant_conventionnel_plus_bas_laisse_le_minimum_legal(_iccp):
    dossier = calculer_indemnites_sortie(
        _salarie(), _depart(notes={"indemnite_conventionnelle": 1000.0}), _bulletins(2026, 6)
    )

    indemnite = dossier["indemnite_depart_retraite"]
    assert indemnite["montant"] == 5533.08
    assert indemnite["base_calcul"] == "Légale"
    assert "1 000,00" in indemnite["calcul"]


@patch(_ICCP, return_value=_SANS_ICCP)
def test_sans_montant_conventionnel_le_dossier_dit_ou_le_saisir(_iccp):
    dossier = calculer_indemnites_sortie(_salarie(), _depart(), _bulletins(2026, 6))

    alertes = dossier["indemnite_depart_retraite"]["alertes"]
    assert not any("pas encore de champ" in a for a in alertes)
    assert any("Indemnité conventionnelle" in a for a in alertes)


# ---------------------------------------------------------------------------
# Licenciement et mise à la retraite : le montant conventionnel est le minimum
# de branche du régime social (CSG/CRDS, limites d'exonération)
# ---------------------------------------------------------------------------


def _licenciement(**notes) -> dict:
    return _depart(
        "licenciement",
        notes=notes,
        exit_request_date="2026-09-01",
        last_working_day="2026-10-31",
        notice_period_days=0,
    )


@patch(_ICCP, return_value=_SANS_ICCP)
def test_le_licenciement_verse_le_conventionnel_et_le_retient_comme_minimum_de_branche(_iccp):
    salarie = _salarie("2016-01-01")
    legal = calculer_indemnites_sortie(salarie, _licenciement(), _bulletins(2026, 9))[
        "indemnite_licenciement"
    ]["montant"]
    assert 0 < legal < 20000.0

    dossier = calculer_indemnites_sortie(
        salarie, _licenciement(indemnite_conventionnelle=20000.0), _bulletins(2026, 9)
    )

    indemnite = dossier["indemnite_licenciement"]
    assert indemnite["montant"] == 20000.0
    assert indemnite["montant_legal"] == legal
    assert indemnite["description"].startswith("Indemnité conventionnelle de licenciement")
    regime = indemnite["regime_social"]
    assert regime["minimum"] == 20000.0
    assert regime["exoneree_csg"] == 20000.0
    assert regime["assiette_csg_seule"] == 0.0
    assert regime["conventionnelle"] is True
    assert dossier["total_gross_indemnities"] == 20000.0


@patch(_ICCP, return_value=_SANS_ICCP)
def test_la_faute_grave_ne_verse_pas_le_conventionnel(_iccp):
    exit_data = _licenciement(indemnite_conventionnelle=20000.0)
    exit_data["is_gross_misconduct"] = True
    dossier = calculer_indemnites_sortie(_salarie("2016-01-01"), exit_data, _bulletins(2026, 9))

    assert dossier["indemnite_licenciement"]["montant"] == 0.0


@patch(_ICCP, return_value=_SANS_ICCP)
def test_la_mise_a_la_retraite_verse_le_conventionnel_avec_la_contribution_de_40(_iccp):
    exit_data = _depart(
        notes={"retirement_initiator": "employer", "indemnite_conventionnelle": 30000.0},
        exit_request_date="2026-03-01",
        last_working_day="2026-04-30",
    )
    dossier = calculer_indemnites_sortie(_salarie("2006-01-01"), exit_data, _bulletins(2026, 3))

    indemnite = dossier["indemnite_mise_retraite"]
    assert indemnite["montant"] == 30000.0
    assert indemnite["base_calcul"] == "Conventionnelle"
    regime = indemnite["regime_social"]
    assert regime["minimum"] == 30000.0
    assert regime["contribution_patronale"] == round(regime["exoneree_cotisations"] * 0.40, 2)


def test_le_bulletin_et_la_dsn_disent_le_conventionnel_et_sa_part_legale():
    regime = {
        "nature": "licenciement",
        "montant": 20000.0,
        "minimum": 20000.0,
        "exoneree_impot": 20000.0,
        "exoneree_cotisations": 20000.0,
        "soumise_cotisations": 0.0,
        "exoneree_csg": 20000.0,
        "assiette_csg_seule": 0.0,
        "contribution_patronale": 0.0,
        "taux_contribution_patronale": 0.0,
        "imposable": 0.0,
        "conventionnelle": True,
        "mention": "Exonérée de cotisations dans la limite de 20 000,00 €.",
    }
    dossier = {
        "indemnite_licenciement": {
            "montant": 20000.0,
            "montant_legal": 6000.0,
            "base_calcul": "Conventionnelle",
            "description": "Indemnité conventionnelle de licenciement (convention collective de branche)",
            "libelle_bulletin": "Indemnité conventionnelle de licenciement",
            "regime_social": regime,
        }
    }
    contexte = build_test_contexte(salaire_base=2400.0)
    contexte.exit_indemnities = dossier
    nets = {"net_a_payer": 1900.0, "net_imposable": 1900.0, "montant_net_social": 1900.0}
    bulletin = creer_bulletin_sortie(contexte, 2400.0, [], [], nets, [], dossier, 2026, 10)

    (ligne,) = bulletin["indemnites_sortie"]["lignes_exonerees"]
    assert ligne["libelle"] == "Indemnité conventionnelle de licenciement"
    assert indemnites_de_rupture(bulletin, sortie=True) == [
        ("007", 6000.0, False),
        ("021", 14000.0, False),
    ]


# ---------------------------------------------------------------------------
# Saisie : à la création et dans l'onglet « Indemnités »
# ---------------------------------------------------------------------------


def test_l_ecran_porte_le_montant_conventionnel_a_la_creation_et_ensuite():
    depart = EmployeeExitCreate(
        employee_id="emp-1",
        exit_type="licenciement",
        exit_request_date="2026-09-01",
        last_working_day="2026-10-31",
        indemnite_conventionnelle=20000.0,
    )
    assert depart.indemnite_conventionnelle == 20000.0
    assert EmployeeExitUpdate(indemnite_conventionnelle=None).model_fields_set == {
        "indemnite_conventionnelle"
    }


def _creer(exit_type: str, **extra) -> dict:
    with patch.object(
        commands,
        "get_employee_by_id",
        return_value={"company_id": "co", "employment_status": "actif", "first_name": "A", "last_name": "B"},
    ), patch.object(commands, "exit_block_reason", return_value=None), patch.object(
        commands, "EmployeeExitRepository"
    ) as depot, patch.object(commands, "update_employee_employment_status"), patch.object(
        commands, "create_default_checklist_sync"
    ), patch.object(commands, "_run_post_create_indemnities_and_docs"):
        depot.return_value.create.side_effect = lambda ligne: {**ligne, "id": "exit-1"}
        return commands.create_employee_exit(
            {
                "employee_id": "emp-1",
                "exit_type": exit_type,
                "exit_request_date": "2026-05-31",
                "last_working_day": "2026-06-30",
                "notice_period_days": 0,
                "notice_indemnity_type": "not_applicable",
                **extra,
            },
            "co",
            "user-1",
            supabase_client=MagicMock(),
        )


def test_la_creation_range_le_montant_conventionnel_dans_le_dossier():
    cree = _creer("depart_retraite", retirement_initiator="employee", indemnite_conventionnelle=12712.27)
    assert cree["exit_notes"] == {"retirement_initiator": "employee", "indemnite_conventionnelle": 12712.27}

    cree = _creer("demission", indemnite_conventionnelle=500.0)
    assert not (cree.get("exit_notes") or {}).get("indemnite_conventionnelle")


def _modifier(existant: dict, donnees: dict):
    with patch.object(commands, "EmployeeExitRepository") as depot, patch.object(
        commands, "get_employee_full", return_value={"id": "emp-1"}
    ), patch.object(commands, "get_indemnity_calculator") as calculateur:
        depot.return_value.get_by_id.return_value = existant
        depot.return_value.update.side_effect = lambda _id, _co, maj: {**existant, **maj}
        calculateur.return_value.calculate.side_effect = lambda _emp, depart, _sb: {
            "vu": dict(depart.get("exit_notes") or {}),
            "indemnite_conges": {"jours_restants": 0},
        }
        return commands.update_employee_exit("exit-1", "co", donnees, supabase_client=MagicMock())


def test_la_saisie_dans_l_onglet_recalcule_le_dossier():
    existant = {
        "id": "exit-1",
        "employee_id": "emp-1",
        "exit_type": "licenciement",
        "last_working_day": "2026-10-31",
        "status": "licenciement_notifie",
        "exit_notes": {"autre": 1},
    }
    maj = _modifier(existant, {"indemnite_conventionnelle": 20000.0})
    assert maj["exit_notes"] == {"autre": 1, "indemnite_conventionnelle": 20000.0}
    assert maj["calculated_indemnities"]["vu"]["indemnite_conventionnelle"] == 20000.0

    maj = _modifier({**existant, "exit_notes": maj["exit_notes"]}, {"indemnite_conventionnelle": None})
    assert "indemnite_conventionnelle" not in maj["exit_notes"]


def test_la_saisie_est_refusee_pour_une_demission():
    existant = {"id": "exit-1", "employee_id": "emp-1", "exit_type": "demission", "status": "demission_recue"}
    with pytest.raises(EmployeeExitApplicationError) as erreur:
        _modifier(existant, {"indemnite_conventionnelle": 500.0})
    assert erreur.value.status_code == 400
