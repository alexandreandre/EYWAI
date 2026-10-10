"""Aucune route des bulletins ni des saisies ne renvoie le texte d'une exception
en erreur 500 (« NomDeClasse: erreur », « list index out of range »…). Le détail
reste dans les journaux ; l'écran reçoit une phrase qui dit quoi faire."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.core import constants

RACINE = Path(__file__).resolve().parents[3] / "app" / "modules"
ROUTEURS = [
    RACINE / "payslips" / "api" / "router.py",
    RACINE / "monthly_inputs" / "api" / "router.py",
]


def _erreurs_500_qui_exposent_l_exception(chemin: Path) -> list[int]:
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    fautives: list[int] = []
    for noeud in ast.walk(arbre):
        if not (isinstance(noeud, ast.Call) and getattr(noeud.func, "id", "") == "HTTPException"):
            continue
        mots = {k.arg: k.value for k in noeud.keywords}
        statut = mots.get("status_code")
        if not (isinstance(statut, ast.Constant) and statut.value == 500):
            continue
        detail = mots.get("detail")
        if detail is not None and any(
            isinstance(n, ast.Name) and n.id == "e" for n in ast.walk(detail)
        ):
            fautives.append(noeud.lineno)
    return fautives


@pytest.mark.parametrize("chemin", ROUTEURS, ids=lambda c: c.parent.parent.name)
def test_aucune_erreur_500_n_expose_le_texte_de_l_exception(chemin):
    assert _erreurs_500_qui_exposent_l_exception(chemin) == []


def test_le_message_interne_dit_quoi_faire():
    message = constants.MESSAGE_ERREUR_INTERNE
    assert "Réessayez" in message
    assert "Martine" in message
    assert "support" in message


def test_le_catalogue_de_primes_ne_montre_pas_le_nom_de_la_classe():
    from app.modules.monthly_inputs.api import router as m

    utilisateur = type("U", (), {"active_company_id": "co-1", "has_access_to_company": lambda s, c: True})()
    with (
        patch.object(m.queries, "get_primes_catalogue", side_effect=KeyError("clé_technique")),
        pytest.raises(HTTPException) as exc,
    ):
        m.get_primes_catalogue(current_user=utilisateur)
    assert exc.value.status_code == 500
    assert "KeyError" not in exc.value.detail
    assert "clé_technique" not in exc.value.detail
    assert exc.value.detail == constants.MESSAGE_ERREUR_INTERNE
