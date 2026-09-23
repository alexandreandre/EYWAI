"""Une prime ajoutée, corrigée ou retirée sur le bulletin repasse par le moteur.

Retour de Gaëlle du 23/09/2026 : une prime ajoutée dans « Modifier le
bulletin » changeait le brut, mais ni le cumul brut ni les bases de
cotisations. Désormais elle devient une variable du mois et le bulletin est
recalculé (spec 2026-09-23).
"""

from unittest.mock import patch

import pytest

from app.modules.payslips.application.commands import edit_payslip
from app.modules.payslips.application.dto import EditPayslipInput, PayslipBadRequestError

pytestmark = pytest.mark.unit

BASE = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 14.28, "gain": 2165.85}
PRIME = {"libelle": "Prime exceptionnelle", "gain": 100.0, "saisie_id": "s-1"}
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
AVANT = {
    "id": "ps-1",
    "employee_id": "emp-1",
    "company_id": "comp-1",
    "year": 2026,
    "month": 8,
    "payslip_data": {"calcul_du_brut": [BASE, PRIME]},
}
MODULE = "app.modules.payslips.application.commands"


def _commande(*lignes):
    return EditPayslipInput(
        payslip_id="ps-1",
        payslip_data={"calcul_du_brut": [BASE, *lignes]},
        changes_summary="Prime",
        current_user_id="user-gaelle",
        current_user_name="Gaëlle",
    )


@pytest.fixture(autouse=True)
def _contexte():
    with patch(f"{MODULE}._fetch_payslip_status", return_value={"id": "ps-1", "status": "brouillon"}), patch(
        f"{MODULE}._fetch_payslip_for_recalc", return_value=AVANT
    ), patch(f"{MODULE}.payslip_editor_provider") as editeur:
        editeur.save_edited.return_value = {"status": "success", "message": "ok"}
        yield editeur


def test_ajouter_une_prime_ecrit_la_saisie_et_regenere_une_fois():
    with patch(f"{MODULE}.verifier_appartenance"), patch(
        f"{MODULE}.appliquer_primes_editees"
    ) as appliquer, patch(f"{MODULE}.generate_payslip") as regenerer:
        edit_payslip(_commande(PRIME, NOUVELLE))

    diff = appliquer.call_args.args[0]
    assert diff.ajoutees[0]["name"] == "Prime de fin de chantier"
    assert appliquer.call_args.kwargs == {
        "employee_id": "emp-1", "company_id": "comp-1", "year": 2026, "month": 8,
    }
    regenerer.assert_called_once()
    entree = regenerer.call_args.args[0]
    assert (entree.employee_id, entree.year, entree.month) == ("emp-1", 2026, 8)
    assert entree.force_calendrier_incomplet and entree.regenerer_bulletin_valide


def test_retirer_une_prime_retire_sa_saisie():
    with patch(f"{MODULE}.verifier_appartenance") as verifier, patch(
        f"{MODULE}.appliquer_primes_editees"
    ) as appliquer, patch(f"{MODULE}.generate_payslip"):
        edit_payslip(_commande())

    assert verifier.call_args.args[0] == {"s-1"}
    assert appliquer.call_args.args[0].retirees == ("s-1",)


def test_une_saisie_etrangere_est_refusee_avant_tout_enregistrement(_contexte):
    with patch(
        f"{MODULE}.verifier_appartenance", side_effect=PayslipBadRequestError("saisie inconnue")
    ), patch(f"{MODULE}.appliquer_primes_editees") as appliquer, patch(
        f"{MODULE}.generate_payslip"
    ) as regenerer:
        with pytest.raises(PayslipBadRequestError):
            edit_payslip(_commande())

    _contexte.save_edited.assert_not_called()
    appliquer.assert_not_called()
    regenerer.assert_not_called()


def test_retoucher_une_ligne_calculee_ne_recalcule_rien():
    retouchee = {**BASE, "gain": 2000.0}
    with patch(f"{MODULE}.appliquer_primes_editees") as appliquer, patch(
        f"{MODULE}.generate_payslip"
    ) as regenerer:
        edit_payslip(_commande(retouchee, PRIME))

    appliquer.assert_not_called()
    regenerer.assert_not_called()


def test_heures_sup_et_prime_ensemble_une_seule_regeneration():
    hs = {"libelle": "Heures suppl. majorées à 25%", "quantite": 4.0, "taux": 17.85, "gain": 71.4}
    with patch(f"{MODULE}.verifier_appartenance"), patch(f"{MODULE}.appliquer_primes_editees"), patch(
        f"{MODULE}._remplacer_heures_sup_declarees"
    ) as declarer, patch(f"{MODULE}.generate_payslip") as regenerer:
        edit_payslip(_commande(PRIME, NOUVELLE, hs))

    declarer.assert_called_once()
    regenerer.assert_called_once()


def test_un_echec_du_moteur_est_rendu_sans_perdre_la_saisie():
    with patch(f"{MODULE}.verifier_appartenance"), patch(
        f"{MODULE}.appliquer_primes_editees"
    ) as appliquer, patch(f"{MODULE}.generate_payslip", side_effect=RuntimeError("moteur KO")):
        resultat = edit_payslip(_commande(PRIME, NOUVELLE))

    appliquer.assert_called_once()
    assert "moteur KO" in resultat["recalcul_erreur"]


def test_le_bulletin_enregistre_ne_garde_pas_la_marque_de_nouvelle_saisie(_contexte):
    """Sinon, si le moteur échoue, le prochain enregistrement recréerait la prime."""
    with patch(f"{MODULE}.verifier_appartenance"), patch(f"{MODULE}.appliquer_primes_editees"), patch(
        f"{MODULE}.generate_payslip", side_effect=RuntimeError("moteur KO")
    ):
        edit_payslip(_commande(PRIME, NOUVELLE))

    enregistre = _contexte.save_edited.call_args.kwargs["new_payslip_data"]
    lignes = enregistre["calcul_du_brut"]
    assert all("nouvelle_saisie" not in ligne for ligne in lignes)
    assert any(ligne["libelle"] == "Prime de fin de chantier" for ligne in lignes)
