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


def _retenues_ap(donnees: object) -> list[float]:
    """Les montants de la ligne « Heures chômées (act. part.) », où qu'elle soit."""
    trouvees: list[float] = []
    if isinstance(donnees, dict):
        if donnees.get("libelle") == LIBELLE_RETENUE and donnees.get("gain") is not None:
            trouvees.append(float(donnees["gain"]))
        for valeur in donnees.values():
            trouvees += _retenues_ap(valeur)
    elif isinstance(donnees, list):
        for valeur in donnees:
            trouvees += _retenues_ap(valeur)
    return trouvees


def _ne_retient_pas_plus_que_le_salaire(donnees: dict, profil: str) -> None:
    from tests.unit.payroll.profils_salaries import fiche

    salaire = float(fiche(profil)["salaire_de_base"]["valeur"])
    retenues = _retenues_ap(donnees)
    assert retenues, "pas de ligne d'activité partielle"
    # Le brut ramené à 0 par le moteur forfait ne prouve rien : la ligne, si.
    assert -sum(retenues) <= salaire + 0.01


def _texte(donnees: dict) -> str:
    return json.dumps(donnees, ensure_ascii=False, default=str)


@pytest.mark.parametrize("profil", PROFILS)
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


@pytest.mark.parametrize("profil", PROFILS)
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


@pytest.mark.parametrize("profil", PROFILS)
def test_panier_au_dessus_du_plafond_est_reintegre(banc, profil):  # noqa: F811
    donnees = banc.generer(profil, saisies=[PANIERS_AU_DESSUS_DU_PLAFOND])

    assert "Réintégration panier" in _texte(donnees)


@pytest.mark.parametrize("profil", PROFILS)
def test_un_mois_entier_chome_ne_retient_pas_plus_que_le_salaire(banc, profil):  # noqa: F811
    """Relecture du 17/11 : un mois entièrement chômé ne retient pas plus que le
    salaire du mois ; le brut ne devient jamais négatif. Un mois entier vaut la
    durée mensuelle du contrat (R5122-19, al. 2), pas 22 × 7 h."""
    from calendar import monthrange
    from datetime import date

    from tests.unit.payroll.profils_salaries import ANNEE, MOIS

    ouvres = [j for j in range(1, monthrange(ANNEE, MOIS)[1] + 1) if date(ANNEE, MOIS, j).weekday() < 5]
    donnees = banc.generer(profil, jours={j: "activite_partielle" for j in ouvres})

    assert float(donnees.get("salaire_brut") or 0.0) >= 0.0
    _ne_retient_pas_plus_que_le_salaire(donnees, profil)


@pytest.mark.parametrize("profil", PROFILS)
def test_un_mois_chome_avec_un_jour_sans_solde_ne_retient_pas_tout_deux_fois(banc, profil):  # noqa: F811
    """Relecture du 17/11 au soir : un jour d'activité partielle est payé par
    ses deux lignes ; il n'est pas une absence. Avec un jour sans solde, le mois
    n'est pas « absent en entier » (brut à −2 500 € avant)."""
    from calendar import monthrange
    from datetime import date

    from tests.unit.payroll.profils_salaries import ANNEE, MOIS

    ouvres = [j for j in range(1, monthrange(ANNEE, MOIS)[1] + 1) if date(ANNEE, MOIS, j).weekday() < 5]
    jours = {j: "activite_partielle" for j in ouvres[1:]}
    jours[ouvres[0]] = "absence_non_remuneree"
    donnees = banc.generer(profil, jours=jours)

    assert float(donnees.get("salaire_brut") or 0.0) >= 0.0
    _ne_retient_pas_plus_que_le_salaire(donnees, profil)


PRIME_DU_CATALOGUE = {
    "name": "Prime objectif",
    "amount": 300.0,
    "catalog_prime_id": "prime_objectif",
    "export_code": "P12",
    "is_socially_taxed": True,
    "is_taxable": True,
}


@pytest.mark.parametrize("profil", PROFILS)
def test_une_prime_du_catalogue_garde_son_code_d_export(banc, profil):  # noqa: F811
    """17/11 : au forfait, la prime perdait son code d'export et son lien au
    catalogue ; une seule fonction range les saisies des deux générateurs."""
    texte = _texte(banc.generer(profil, saisies=[PRIME_DU_CATALOGUE]))

    assert "Prime objectif (P12)" in texte
