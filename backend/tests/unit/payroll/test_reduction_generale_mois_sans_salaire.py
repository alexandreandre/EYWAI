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


def test_mois_partiel_sans_solde_garde_sa_reduction(banc):  # noqa: F811
    """Cinq jours sans solde en février : la réduction reste celle des heures payées."""
    jours = {d: "absence_non_remuneree" for d in (9, 10, 11, 12, 13)}
    donnees = banc.generer("heures", jours=jours, mois=2)
    assert _reduction(donnees) < -1.0
