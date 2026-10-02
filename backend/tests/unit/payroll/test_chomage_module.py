"""Assurance chômage au taux modulé (bonus-malus) de la société.

Comitech relève du bonus-malus : la gestionnaire applique 2,95 % depuis le
printemps 2026, à tous les salariés sauf l'apprenti, resté au taux de droit
commun (bulletins Quadra d'août et de septembre 2026). EYWAI appliquait 4 %
à tout le monde, faute de réglage.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.application.empreinte_entrees_service import (
    parametres_societe_pour_empreinte,
)
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations

from .helpers import baremes_snapshot, build_test_contexte

pytestmark = pytest.mark.unit


def _contexte(**kw):
    """Le barème de test n'a pas l'assurance chômage : celle de la base (4 %)."""
    baremes = baremes_snapshot()
    baremes["cotisations"]["cotisations"].append(
        {"id": "assurance_chomage", "base": "brut", "libelle": "Assurance Chômage", "patronal": 0.04, "salarial": None}
    )
    return build_test_contexte(baremes=baremes, **kw)


def _chomage(ctx, brut):
    lignes, _ = calculer_cotisations(ctx, brut, 0.0, 0.0)
    return next(l for l in lignes if l.get("coti_id") == "assurance_chomage")


def _avec_taux_module(ctx, taux):
    ctx.entreprise.setdefault("parametres_paie", {}).setdefault("taux_specifiques", {})[
        "taux_assurance_chomage"
    ] = taux
    return ctx


def test_le_taux_module_de_la_societe_s_applique():
    ctx = _avec_taux_module(_contexte(salaire_base=4311.70), 2.95)
    assert _chomage(ctx, 4311.70)["montant_patronal"] == pytest.approx(127.20, abs=0.005)


def test_sans_reglage_le_taux_de_droit_commun_reste():
    ctx = _contexte(salaire_base=4311.70)
    assert _chomage(ctx, 4311.70)["montant_patronal"] == pytest.approx(172.47, abs=0.005)


def test_l_apprenti_garde_le_taux_de_droit_commun():
    ctx = _avec_taux_module(
        _contexte(salaire_base=1152.16, type_contrat="Apprentissage"), 2.95
    )
    ligne = _chomage(ctx, 1152.16)
    assert ligne["montant_patronal"] != pytest.approx(round(1152.16 * 0.0295, 2), abs=0.005)


def test_l_empreinte_ne_change_pas_sans_reglage():
    societe = {"taux_at_mp": 3.15, "settings": {"date_paiement": "fin_de_mois"}}
    assert "taux_assurance_chomage" not in parametres_societe_pour_empreinte(societe)


def test_l_empreinte_suit_le_taux_module():
    societe = {"taux_at_mp": 3.15, "settings": {"taux_assurance_chomage": 2.95}}
    assert parametres_societe_pour_empreinte(societe)["taux_assurance_chomage"] == 2.95
