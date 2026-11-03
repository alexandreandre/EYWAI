"""Le maintien de la métallurgie est plafonné au net (conception du 03/11/2026).

Art. 91.1.3 : le salarié ne peut percevoir « une indemnisation plus importante
que la rémunération nette qu'il aurait perçue s'il avait continué à travailler ».
Le garanti reste brut (100 % puis, pour un cadre, 50 %), IJ brutes déduites,
puis borné au net : les IJ y sont comptées nettes de CSG et CRDS et ramenées au
brut avec la part salariale du salarié. Sans IJ déduites, le plafond ne mord
pas. Initiales seulement.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

MAI = (date(2026, 5, 1), date(2026, 5, 31))

METALLO = {
    "bareme_convention": "metallurgie_3248",
    "subrogation_mode": "never",
    "deduire_ijss_sans_subrogation": True,
}


def _ctx(entree="2018-01-01", salaire=2260.0, statut="Non-Cadre"):
    return build_test_contexte(
        statut=statut, salaire_base=salaire, duree_hebdo=35.0, date_entree=entree,
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )


def _arret(debut, fin, override, type_arret="maladie_simple"):
    return {
        "arret_type": type_arret,
        "date_debut": debut,
        "date_fin": fin,
        "subrogation_active": False,
        "nombre_enfants": 0,
        "salaire_periode_reelle": 0.0,
        "arrets_connus": [{"debut": debut, "fin": fin, "type": type_arret}],
        "ijss_brut_override": override,
    }


def _resultat(override, reglages=METALLO, ctx=None):
    arret = _arret("2026-05-04", "2026-05-31", override)
    return calculer_maintien(arret, ctx or _ctx(), dict(reglages), *MAI)


def test_le_maintien_est_plafonne_au_net():
    r = _resultat(900.0)
    m = r["maintien"]
    assert m["regle_retenue"] == "convention"
    assert "plafond_net" in m
    p = m["plafond_net"]
    assert p["ijss_deduites"] == 900.0
    assert p["taux_ijss"] == pytest.approx(0.067)
    assert p["reduction"] > 0
    # 100 % sur tout l'arrêt : la cible est la valeur des jours. Le net reçu
    # (versé net + IJ nettes) égale le net que le salarié aurait perçu.
    net_recu = m["maintien_verse"] * (1 - p["taux_salarial"]) + 900.0 * (1 - p["taux_ijss"])
    assert net_recu == pytest.approx(m["maintien_cible"] * (1 - p["taux_salarial"]), abs=0.02)
    # La lecture brute versait la cible moins les IJ brutes, plus haut.
    assert m["maintien_verse"] < m["maintien_cible"] - 900.0 + 0.01 + p["reduction"]


def test_sans_deduction_des_ijss_pas_de_plafond():
    m = _resultat(900.0, reglages={**METALLO, "deduire_ijss_sans_subrogation": False})["maintien"]
    assert m["maintien_verse"] == m["maintien_cible"]
    assert "plafond_net" not in m


def test_une_mesure_impossible_ne_plafonne_pas_et_le_dit(monkeypatch):
    from app.modules.payroll.engine import maintien_salaire_service

    monkeypatch.setattr(maintien_salaire_service, "taux_salarial_marginal", lambda *a, **k: None)
    r = _resultat(900.0)
    m = r["maintien"]
    assert "plafond_net" not in m
    assert round(m["maintien_verse"], 2) == round(m["maintien_cible"] - 900.0, 2)
    assert (
        "Plafond au net non calculé (taux de cotisations salariales non mesuré) : "
        "le maintien n'est pas plafonné, plus favorable au salarié."
    ) in r["alertes"]
