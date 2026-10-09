"""Garde : aucun texte montré à la gestionnaire n'écrit un pluriel « (s) ».

« 3 jour(s) à saisir » se lit mal et se corrige : le nombre décide du singulier
ou du pluriel. Les messages des gardes de génération, du contrôle avant paie
et de l'analyse sont vérifiés ici.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[3] / "app"

FICHIERS = [
    "modules/payslips/application/commands.py",
    "modules/payroll/application/preflight_anomalies.py",
    "modules/payslips/application/anomalies_report.py",
    "modules/absences/application/commands.py",
    "modules/absences/application/fractionnement_queries.py",
    "modules/absences/application/notifications.py",
    "modules/absences/domain/rules.py",
    "modules/dashboard/domain/rules.py",
    "modules/exports/application/notifications.py",
    "modules/exports/domain/rules.py",
    "modules/exports/infrastructure/export_paiement_salaires.py",
    "modules/exports/infrastructure/export_provision_cp.py",
    "modules/exports/infrastructure/export_virement_acomptes.py",
    "modules/oeth_settings/application/queries.py",
    "modules/participation/api/router.py",
    "modules/participation/application/campaign_import_service.py",
    "modules/participation/application/participation_notifications.py",
    "modules/pas_rates/domain/rapprochement.py",
    "modules/payroll/exports/paiement_salaires.py",
    "modules/schedules/application/ai_fill.py",
    "modules/schedules/application/calendar_generation.py",
    "modules/schedules/application/commands.py",
    "modules/schedules/application/nl_fast_path.py",
    "modules/schedules/application/planning_import/quadra_calendar.py",
    "modules/schedules/application/preset_apply.py",
    "modules/schedules/application/timesheet_import/commit_service.py",
    "modules/schedules/application/timesheet_import_service.py",
    "modules/schedules/application/timesheet_page_merge.py",
    "modules/schedules/application/timesheet_quality.py",
]

MOTIF = re.compile(r"[A-Za-zÀ-ÿ]\((s|e|es|x)\)")


def _chaines(fichier: str):
    arbre = ast.parse((APP / fichier).read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
            yield noeud.lineno, noeud.value


def test_aucun_pluriel_entre_parentheses_dans_les_messages():
    fautes = [
        f"{fichier}:{ligne} : {texte.strip()[:70]}"
        for fichier in FICHIERS
        for ligne, texte in _chaines(fichier)
        if MOTIF.search(texte)
    ]
    assert not fautes, "\n".join(fautes)


def test_pluriel_accorde_le_nombre():
    from app.shared.domain.pluriel import pluriel

    assert pluriel(0, "jour") == "0 jour"
    assert pluriel(1, "jour") == "1 jour"
    assert pluriel(2, "jour") == "2 jours"
    assert pluriel(3, "cotisation patronale négative", "cotisations patronales négatives") == (
        "3 cotisations patronales négatives"
    )


def test_accord_n_ecrit_que_le_mot():
    from app.shared.domain.pluriel import accord

    assert accord(1, "validé") == "validé"
    assert accord(0, "validé") == "validé"
    assert accord(2, "validé") == "validés"
    assert accord(2, "mis à jour", "mis à jour") == "mis à jour"
