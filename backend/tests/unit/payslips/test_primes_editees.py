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


# --- Une prime ajoutée ne porte que ses propres champs (audit du 28/09, K1) ---

def test_une_prime_ajoutee_ne_garde_que_ses_champs():
    forgee = {
        **NOUVELLE["nouvelle_saisie"],
        "employee_id": "autre-salarie",
        "company_id": "autre-societe",
        "year": 2025,
        "month": 1,
        "manual_override": False,
        "payroll_quantity": 12,
    }
    diff = diff_primes(_bulletin(), _bulletin({**NOUVELLE, "nouvelle_saisie": forgee}))

    assert diff.ajoutees == (
        {
            "name": "Prime de fin de chantier",
            "is_socially_taxed": True,
            "is_taxable": True,
            "catalog_prime_id": None,
            "amount": 100.0,
        },
    )


def test_prime_ajoutee_propre_retire_tout_champ_inconnu():
    from app.modules.payslips.domain.primes_editees import prime_ajoutee_propre

    assert prime_ajoutee_propre({"name": "X", "employee_id": "e", "month": 3}) == {"name": "X"}


def test_l_insertion_impose_le_salarie_la_societe_et_la_periode_du_bulletin():
    from unittest.mock import MagicMock, patch

    from app.modules.payslips.application import primes_editees as app_primes
    from app.modules.payslips.domain.primes_editees import DiffPrimes

    client = MagicMock()
    diff = DiffPrimes(ajoutees=({"name": "Prime", "amount": 10.0, "employee_id": "autre"},))
    with patch.object(app_primes, "supabase", client):
        app_primes.appliquer_primes_editees(
            diff, employee_id="e1", company_id="c1", year=2026, month=9
        )

    assert client.table.return_value.insert.call_args.args[0] == [
        {
            "name": "Prime",
            "amount": 10.0,
            "employee_id": "e1",
            "company_id": "c1",
            "year": 2026,
            "month": 9,
            "manual_override": True,
        }
    ]


def test_un_montant_corrige_au_bulletin_n_est_plus_ecrase_par_la_generation():
    from unittest.mock import MagicMock, patch

    from app.modules.payslips.application import primes_editees as app_primes
    from app.modules.payslips.domain.primes_editees import DiffPrimes

    client = MagicMock()
    with patch.object(app_primes, "supabase", client):
        app_primes.appliquer_primes_editees(
            DiffPrimes(modifiees=(("s-1", 150.0),)),
            employee_id="e1", company_id="c1", year=2026, month=9,
        )

    client.table.return_value.update.assert_called_once_with(
        {"amount": 150.0, "manual_override": True}
    )
