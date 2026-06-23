"""Tests cotisations protection sociale Comitech (prévoyance NC lignes, retraite sup)."""

from __future__ import annotations

from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations

from .helpers import build_test_contexte


def _find_ligne(lignes, coti_id: str):
    return next((l for l in lignes if l.get("coti_id") == coti_id), None)


def test_prevoyance_non_cadre_via_lignes_specifiques_ta_tb():
    ctx = build_test_contexte(
        statut="Non-Cadre",
        salaire_base=5000.0,
        specificites_extra={
            "prevoyance": {
                "adhesion": True,
                "lignes_specifiques": [
                    {
                        "id": "epna",
                        "libelle": "Prévoyance GAN TA",
                        "salarial": 0.00465,
                        "patronal": 0.00465,
                        "base": "brut_plafonne",
                    },
                    {
                        "id": "epnb",
                        "libelle": "Prévoyance GAN TB",
                        "salarial": 0.00465,
                        "patronal": 0.00465,
                        "base": "tranche_2",
                    },
                ],
            },
        },
    )
    lignes, _ = calculer_cotisations(ctx, 5000.0, 0.0, 0.0)
    prev_lignes = [l for l in lignes if l.get("coti_id") == "prevoyance_non_cadre"]
    assert len(prev_lignes) == 2
    ta = next(l for l in prev_lignes if "TA" in l["libelle"])
    tb = next(l for l in prev_lignes if "TB" in l["libelle"])
    pss = ctx.baremes.get("pss", {}).get("mensuel", 0.0)
    assert ta["base"] == round(min(5000.0, pss), 2)
    assert ta["montant_salarial"] == round(ta["base"] * 0.00465, 2)
    assert tb["base"] == round(max(0, min(5000.0, 8 * pss) - pss), 2)


def test_retraite_sup_cadre_eres_ta():
    ctx = build_test_contexte(
        statut="Cadre",
        salaire_base=4000.0,
        specificites_extra={
            "retraite_sup": {
                "adhesion": True,
                "lignes_specifiques": [
                    {
                        "id": "eres_ta",
                        "libelle": "Retraite sup AG2R TA",
                        "salarial": 0.025,
                        "patronal": 0.025,
                        "base": "brut_plafonne",
                    },
                    {
                        "id": "eres_tb",
                        "libelle": "Retraite sup AG2R TB",
                        "salarial": 0.0,
                        "patronal": 0.0,
                        "base": "tranche_2",
                    },
                ],
            },
        },
    )
    lignes, _ = calculer_cotisations(ctx, 4000.0, 0.0, 0.0)
    retraite = _find_ligne(lignes, "retraite_sup")
    assert retraite is not None
    pss = ctx.baremes.get("pss", {}).get("mensuel", 0.0)
    base_ta = round(min(4000.0, pss), 2)
    assert retraite["base"] == base_ta
    assert retraite["montant_salarial"] == round(base_ta * 0.025, 2)
    assert retraite["montant_patronal"] == round(base_ta * 0.025, 2)
