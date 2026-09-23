"""Ce qui a changé dans les primes saisies entre deux versions d'un bulletin."""

import pytest

from app.modules.payslips.domain.primes_editees import diff_primes

pytestmark = pytest.mark.unit

BASE = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 14.28, "gain": 2165.85}


def _prime(saisie_id, gain, libelle="Prime exceptionnelle"):
    return {"libelle": libelle, "quantite": None, "taux": None, "gain": gain, "saisie_id": saisie_id}


def _bulletin(*lignes, non_soumises=()):
    return {"calcul_du_brut": [BASE, *lignes], "primes_non_soumises": list(non_soumises)}


NOUVELLE = {
    "libelle": "Prime de fin de chantier",
    "gain": 100.0,
    "nouvelle_saisie": {
        "name": "Prime de fin de chantier",
        "amount": 100.0,
        "is_socially_taxed": True,
        "is_taxable": True,
        "catalog_prime_id": None,
    },
}


def test_rien_ne_change_diff_vide():
    avant = _bulletin(_prime("s-1", 100.0))
    assert diff_primes(avant, _bulletin(_prime("s-1", 100.0))).vide


def test_une_prime_ajoutee_depuis_le_bulletin():
    diff = diff_primes(_bulletin(), _bulletin(NOUVELLE))

    assert diff.ajoutees == (
        {
            "name": "Prime de fin de chantier",
            "amount": 100.0,
            "is_socially_taxed": True,
            "is_taxable": True,
            "catalog_prime_id": None,
        },
    )
    assert not diff.modifiees and not diff.retirees


def test_le_montant_retouche_apres_ajout_fait_foi():
    retouchee = {**NOUVELLE, "gain": 120.0}
    assert diff_primes(_bulletin(), _bulletin(retouchee)).ajoutees[0]["amount"] == 120.0


def test_un_montant_corrige():
    diff = diff_primes(_bulletin(_prime("s-1", 100.0)), _bulletin(_prime("s-1", 150.0)))
    assert diff.modifiees == (("s-1", 150.0),)


def test_une_prime_retiree():
    diff = diff_primes(_bulletin(_prime("s-1", 100.0)), _bulletin())
    assert diff.retirees == ("s-1",)
    assert diff.ids_touches == {"s-1"}


def test_une_prime_non_soumise_se_lit_sur_son_montant():
    avant = _bulletin(non_soumises=[{"libelle": "Panier", "montant": 7.5, "saisie_id": "s-2"}])
    apres = _bulletin(non_soumises=[{"libelle": "Panier", "montant": 15.0, "saisie_id": "s-2"}])
    assert diff_primes(avant, apres).modifiees == (("s-2", 15.0),)


def test_une_ligne_calculee_retouchee_n_est_pas_une_prime():
    retouchee = {**BASE, "gain": 2000.0}
    assert diff_primes(_bulletin(), {"calcul_du_brut": [retouchee]}).vide


def test_un_lien_inconnu_du_bulletin_d_origine_est_ignore():
    """Un saisie_id absent d'avant n'a rien à corriger : on ne l'invente pas."""
    assert diff_primes(_bulletin(), _bulletin(_prime("s-9", 100.0))).vide


def test_ajout_et_retrait_dans_le_meme_enregistrement():
    diff = diff_primes(_bulletin(_prime("s-1", 100.0)), _bulletin(NOUVELLE))
    assert diff.retirees == ("s-1",)
    assert len(diff.ajoutees) == 1


def test_sans_marques_retire_nouvelle_saisie_sans_toucher_au_reste():
    from app.modules.payslips.domain.primes_editees import sans_marques_de_saisie

    avant = _bulletin(_prime("s-1", 100.0), NOUVELLE)
    propre = sans_marques_de_saisie(avant)

    assert "nouvelle_saisie" in avant["calcul_du_brut"][2]  # l'original n'est pas modifié
    assert "nouvelle_saisie" not in propre["calcul_du_brut"][2]
    assert propre["calcul_du_brut"][1]["saisie_id"] == "s-1"
