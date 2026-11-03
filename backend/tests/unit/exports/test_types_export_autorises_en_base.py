"""Chaque type d'export accepté par le serveur doit l'être aussi par la base.

Le 03/11/2026, la provision de congés payés de MAJI (mai, 31 045,79 €) a planté
à la génération : la ligne d'historique `provision_cp` violait la contrainte
`exports_history_export_type_check`. Le serveur accepte le type, la base non.
Ce test lit la dernière migration qui pose la contrainte et vérifie que la liste
du serveur y est entière : un nouveau type ne passe plus sans sa migration.
"""

from __future__ import annotations

import re
import typing
from pathlib import Path

import pytest

from app.modules.exports.schemas.requests import ExportType

pytestmark = pytest.mark.unit

MIGRATIONS = Path(__file__).resolve().parents[4] / "supabase/migrations"
CONTRAINTE = "exports_history_export_type_check"


def _types_de_la_derniere_contrainte() -> set[str]:
    fichiers = sorted(
        f for f in MIGRATIONS.glob("*.sql") if CONTRAINTE in f.read_text(encoding="utf-8")
    )
    assert fichiers, "aucune migration ne pose la contrainte des types d'export"
    sql = re.sub(r"--[^\n]*", "", fichiers[-1].read_text(encoding="utf-8"))
    ajout = sql.split(f"ADD CONSTRAINT {CONTRAINTE}", 1)[1].split(";", 1)[0]
    return set(re.findall(r"'([a-z0-9_]+)'", ajout))


def test_tous_les_types_du_serveur_sont_autorises_en_base():
    serveur = set(typing.get_args(ExportType))
    base = _types_de_la_derniere_contrainte()
    assert serveur - base == set()
