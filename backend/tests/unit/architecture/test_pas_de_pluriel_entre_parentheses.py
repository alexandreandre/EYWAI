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
