"""Une seule façon de savoir si un salarié est au forfait jours.

En base, `employees.statut` ne vaut que « Cadre » ou « Non-Cadre » ; la case
`is_forfait_jour` dit le forfait (58 fiches au 17/11/2026). `is_forfait_jour(statut)`
appelé sans la case répond donc toujours « non ». L'audit du 17/11 a trouvé
quatre lecteurs dans ce cas (onglet « Corriger », entretien annuel du forfait,
demi-journées d'absence, calendriers par modèle).

Règle : lire la fiche avec `is_forfait_jour` et appeler `est_au_forfait_jours(fiche)`,
ou `is_forfait_jour(statut, fiche["is_forfait_jour"])`. Un appel au libellé seul
n'est permis qu'ici, avec sa raison : en général, le statut vient déjà de
`effective_statut_for_payroll`, qui ajoute « au forfait jour » quand la case est cochée.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

APP = Path(__file__).resolve().parents[3] / "app"

STATUT_EFFECTIF = "statut lu par effective_statut_for_payroll (case comprise)"

LIBELLE_SEUL_PERMIS: dict[tuple[str, str], str] = {
    ("modules/payslips/application/comparison_service.py", "get_payslip_comparison_for_user"): STATUT_EFFECTIF,
    ("modules/payslips/application/comparison_service.py", "get_payslip_trend_for_user"): STATUT_EFFECTIF,
    ("modules/payslips/application/comparison_service.py", "validate_payslip_for_user"): STATUT_EFFECTIF,
    ("modules/payslips/application/commands.py", "_generer_sous_verrou"): STATUT_EFFECTIF,
    ("modules/payslips/infrastructure/providers.py", "generate"): STATUT_EFFECTIF,
    ("modules/payslips/infrastructure/providers.py", "generate_en_bac_a_sable"): STATUT_EFFECTIF,
    ("modules/schedules/application/badgeuse_import.py", "import_actual_hours_from_badgeuse"): STATUT_EFFECTIF,
    ("modules/schedules/application/commands.py", "update_planned_calendar"): STATUT_EFFECTIF,
    ("modules/schedules/application/commands.py", "update_actual_hours"): STATUT_EFFECTIF,
    ("modules/schedules/application/commands.py", "calculate_payroll_events"): STATUT_EFFECTIF,
    ("modules/schedules/application/commands.py", "apply_schedule_model"): STATUT_EFFECTIF,
    ("modules/schedules/domain/rules.py", "normalize_planned_calendar_for_forfait_jour"): STATUT_EFFECTIF,
    ("modules/schedules/domain/rules.py", "normalize_actual_hours_for_forfait_jour"): STATUT_EFFECTIF,
    ("modules/payroll/documents/payslip_generator.py", "process_payslip_generation"): (
        "générateur des heures : un salarié au forfait n'y passe jamais (aiguillage sur la case)"
    ),
    ("modules/absences/application/commands.py", "create_absence_request"): (
        "décision en attente (17/11) : refuser la demi-journée au forfait serait un blocage nouveau"
    ),
    ("modules/absences/application/commands.py", "create_absences_from_planning"): (
        "décision en attente (17/11) : la demi-journée au forfait passerait en journée entière"
    ),
}


def _appels_au_libelle_seul() -> set[tuple[str, str]]:
    trouves: set[tuple[str, str]] = set()
    for fichier in APP.rglob("*.py"):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for fonction in ast.walk(arbre):
            if not isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for appel in ast.walk(fonction):
                if not isinstance(appel, ast.Call):
                    continue
                f = appel.func
                nom = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
                if nom == "is_forfait_jour" and len(appel.args) + len(appel.keywords) == 1:
                    trouves.add((fichier.relative_to(APP).as_posix(), fonction.name))
    return trouves


def test_aucun_nouveau_lecteur_du_forfait_au_libelle_seul():
    nouveaux = sorted(_appels_au_libelle_seul() - set(LIBELLE_SEUL_PERMIS))
    assert not nouveaux, (
        f"Forfait jours lu sur le libellé seul : {nouveaux}. Le libellé ne le dit jamais en base : "
        "lisez la case (`est_au_forfait_jours(fiche)` avec `is_forfait_jour` dans le select)."
    )


def test_la_liste_des_permis_reste_vraie():
    disparus = sorted(set(LIBELLE_SEUL_PERMIS) - _appels_au_libelle_seul())
    assert not disparus, f"Retirez ces entrées de LIBELLE_SEUL_PERMIS : {disparus}"


@pytest.mark.parametrize(
    ("fiche", "attendu"),
    [
        ({"statut": "Cadre", "is_forfait_jour": True}, True),
        ({"statut": "Non-Cadre", "is_forfait_jour": True}, True),
        ({"statut": "Cadre", "is_forfait_jour": False}, False),
        ({"statut": "Cadre au forfait jour"}, True),
        ({"statut": "Cadre"}, False),
        (None, False),
    ],
)
def test_est_au_forfait_jours_lit_la_case_d_abord(fiche, attendu):
    from app.shared.domain.employment_rules import est_au_forfait_jours

    assert est_au_forfait_jours(fiche) is attendu
