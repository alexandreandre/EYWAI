"""Réduction générale d'un mois sans aucun salaire : pas d'heures rémunérées qui restent (L15, 27/11).

Bac à sable de Mont Blanc (filet de la vague 2) : un mois entier en absence non rémunérée, 36,67 h
(158,91 h au contrat), février à 20 jours ouvrés. La retenue jour par jour enlève 140 h, le
« Complément retenue absence intégrale du mois » retient le reste du salaire, mais pas ses heures :
18,91 h restaient « rémunérées » dans le SMIC de référence, et la prime d'ancienneté du mois
(299,18 €) portait 120,30 € de réduction générale.

Le salaire minimum de la formule se proratise selon la rémunération que l'absence laisse (BOSS,
allègements généraux, § 760 à 790 ; CSS D. 241-7, IV) ; un élément non affecté par l'absence (prime
mensuelle non proratisée) n'en ouvre pas. Mois sans aucun salaire : SMIC de référence nul. Un arrêt
maintenu en entier garde le SMIC comme si le salarié était présent (§ 750).

Aux deux générateurs, par le banc de profils (vrai aiguillage, rien écrit). Février 2026 : 20 jours
ouvrés, 140 h pour 151,67 h au contrat. Le forfait jours n'a pas ce résidu (garde-fou).
"""

from __future__ import annotations

import pytest

from tests.unit.payroll.profils_salaries import banc  # noqa: F401
from tests.unit.payroll.test_sans_solde_mois_entier import _periode_entiere_sans_solde

pytestmark = pytest.mark.unit

PRIME = [{"name": "Prime exceptionnelle", "amount": 300.0}]


def _reduction(donnees: dict) -> float:
    bloc = donnees["structure_cotisations"]["bloc_allegements"]
    lignes = bloc if isinstance(bloc, list) else bloc.get("lignes", [])
    return sum(
        float(l.get("montant_patronal") or 0.0)
        for l in lignes
        if "réduction générale" in str(l.get("libelle") or "").lower()
    )


#: Février (20 jours ouvrés, 140 h retenues sur 151,67 h) : le résidu ; avril (22 jours, 154 h) ne
#: l'avait pas, il reste en garde-fou, comme le forfait jours et le temps partiel.
@pytest.mark.parametrize("profil", ("heures", "forfait_jours", "temps_partiel", "apprenti"))
@pytest.mark.parametrize("mois", (2, 4))
def test_mois_entier_sans_solde_avec_une_prime_aucune_reduction(banc, profil, mois):  # noqa: F811
    donnees = _periode_entiere_sans_solde(banc, profil, mois, saisies=PRIME)
    assert float(donnees["salaire_brut"]) == pytest.approx(300.0, abs=0.01)
    assert _reduction(donnees) == pytest.approx(0.0, abs=0.005)


@pytest.mark.parametrize("mois", (2, 4))
def test_39_h_les_heures_sup_structurelles_sont_retenues_avec_le_salaire(banc, mois):  # noqa: F811
    """39 h (17,33 h sup structurelles) : mois entier sans solde, petite prime de 50 €. Les heures sup
    du contrat, retenues avec le salaire, ne restent pas dans le SMIC de référence (17,33 h × Smic
    dépassaient la prime et ouvraient une réduction)."""
    donnees = _periode_entiere_sans_solde(
        banc, "heures", mois, saisies=[{"name": "Prime exceptionnelle", "amount": 50.0}],
        fiche_en_plus={"duree_hebdomadaire": 39},
    )
    assert float(donnees["salaire_brut"]) == pytest.approx(50.0, abs=0.01)
    assert _reduction(donnees) == pytest.approx(0.0, abs=0.005)


def _smic_reference(donnees: dict) -> float:
    bloc = donnees["structure_cotisations"]["bloc_allegements"]
    lignes = bloc if isinstance(bloc, list) else bloc.get("lignes", [])
    return next(l for l in lignes if "générale" in str(l.get("libelle")))["smic_reference_mois"]


@pytest.mark.parametrize("duree,heures_contrat,heures_retirees", ((35, 151.67, 35.0), (39, 169.0, 39.0)))
def test_mois_partiel_sans_solde_garde_le_comportement_actuel_en_heures(banc, duree, heures_contrat, heures_retirees):  # noqa: F811
    """Garde-fou du comportement ACTUEL, non affirmé comme légal : L15 ne touche pas aux mois en partie
    travaillés. Cinq jours sans solde en février : le moteur retire les heures de l'absence, 35 h à 35 h
    (5 × 7 h), 39 h à 39 h (5 × 7 h de base et 5 × 0,80 h sup structurelles).

    Écart connu au BOSS, allègements généraux, § 770 : le salaire minimum se proratise sur le RAPPORT DES
    SALAIRES (salaire versé ÷ salaire de la présence), pas sur les heures. À 35 h, 2 500 € de base et
    5 jours retenus à 125 € : 151,67 × 1 875 ÷ 2 500 = 113,75 h, contre 116,67 h ici (7 h par jour sur
    un mois de 151,67 h). Corriger cette branche touche tous les mois à absence partielle, Colorplast
    compris : décision à prendre à part (relecture du 27/11)."""
    fiche = {"duree_hebdomadaire": duree}
    jours = {d: "absence_non_remuneree" for d in (9, 10, 11, 12, 13)}
    donnees = banc.generer("heures", jours=jours, mois=2, fiche_en_plus=fiche)
    plein = banc.generer("heures", jours={}, mois=2, fiche_en_plus=fiche)
    smic_horaire = _smic_reference(plein) / heures_contrat
    assert _smic_reference(donnees) == pytest.approx(
        round(smic_horaire * (heures_contrat - heures_retirees), 2), abs=0.011
    )
