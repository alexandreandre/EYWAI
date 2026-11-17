"""Activité partielle, arrêts, paniers : la même règle sur chaque profil de salarié.

Le vrai chemin du bulletin (aiguillage, générateur, moteur) tourne au bac à sable
sur une base en mémoire (voir `profils_salaries`). Un profil marqué `xfail`
strict est un trou connu : le jour où il est comblé, le test le dit et le
marqueur doit partir.
"""

from __future__ import annotations

import json

import pytest

from app.modules.activite_partielle.domain.calcul import LIBELLE_INDEMNITE, LIBELLE_RETENUE
from tests.unit.payroll.profils_salaries import PROFILS, alertes, banc  # noqa: F401

pytestmark = pytest.mark.unit

#: Lundi 5 et mardi 6 octobre 2026.
LUNDI, MARDI = 5, 6


def _trou_du_forfait(raison: str):
    """Les profils, le forfait jours attendu en échec tant que le trou existe."""
    return [
        pytest.param(p, marks=pytest.mark.xfail(strict=True, reason=raison))
        if p == "forfait_jours"
        else p
        for p in PROFILS
    ]


def _texte(donnees: dict) -> str:
    return json.dumps(donnees, ensure_ascii=False, default=str)


@pytest.mark.parametrize(
    "profil",
    _trou_du_forfait("Activité partielle non branchée au forfait jours (lot 1 de la session A, 17/11)"),
)
def test_activite_partielle_au_calendrier_fait_ses_deux_lignes(banc, profil):  # noqa: F811
    donnees = banc.generer(profil, jours={LUNDI: "activite_partielle", MARDI: "activite_partielle"})

    texte = _texte(donnees)
    assert LIBELLE_RETENUE in texte
    assert LIBELLE_INDEMNITE in texte


@pytest.mark.parametrize("profil", PROFILS)
def test_sans_activite_partielle_aucune_ligne(banc, profil):  # noqa: F811
    texte = _texte(banc.generer(profil))
    assert LIBELLE_RETENUE not in texte
    assert LIBELLE_INDEMNITE not in texte


@pytest.mark.parametrize(
    "profil",
    _trou_du_forfait("Alerte « arrêt sans demande » absente au forfait jours (lot 1 de la session A, 17/11)"),
)
def test_arret_pose_au_calendrier_sans_demande_est_signale(banc, profil):  # noqa: F811
    donnees = banc.generer(profil, jours={LUNDI: "arret_maladie"})

    assert "arret_sans_demande" in alertes(donnees)


PANIERS_AU_DESSUS_DU_PLAFOND = {
    "name": "Panier repas",
    "amount": 200.0,
    "payroll_quantity": 20,
    "quantity_kind": "count",
    "situation_repas": "sur_lieu_travail",
    "is_socially_taxed": False,
    "is_taxable": False,
}


@pytest.mark.parametrize(
    "profil",
    _trou_du_forfait("Réintégration du panier plafonné absente au forfait jours (lot 1 de la session A, 17/11)"),
)
def test_panier_au_dessus_du_plafond_est_reintegre(banc, profil):  # noqa: F811
    donnees = banc.generer(profil, saisies=[PANIERS_AU_DESSUS_DU_PLAFOND])

    assert "Réintégration panier" in _texte(donnees)


_RETENUE_AU_DELA_DU_SALAIRE = pytest.mark.xfail(
    strict=True,
    reason="Mois entier chômé : 22 jours × 7 h = 154 h retenues, au-delà des 151,67 h "
    "mensualisées ; brut négatif (relecture du 17/11, pour la session A)",
)


@pytest.mark.parametrize(
    "profil",
    [
        pytest.param(p, marks=_RETENUE_AU_DELA_DU_SALAIRE)
        if p in ("heures", "apprenti", "temps_partiel")
        else p
        for p in PROFILS
    ],
)
def test_un_mois_entier_chome_ne_retient_pas_plus_que_le_salaire(banc, profil):  # noqa: F811
    """Relecture du 17/11 : un mois entièrement chômé ne retient pas plus que le
    salaire du mois ; le brut ne devient jamais négatif."""
    from calendar import monthrange
    from datetime import date

    from tests.unit.payroll.profils_salaries import ANNEE, MOIS

    ouvres = [j for j in range(1, monthrange(ANNEE, MOIS)[1] + 1) if date(ANNEE, MOIS, j).weekday() < 5]
    donnees = banc.generer(profil, jours={j: "activite_partielle" for j in ouvres})

    assert float(donnees.get("salaire_brut") or 0.0) >= 0.0
