"""Un net à payer négatif est toujours signalé, sans bloquer.

Arrêt maladie sur tout le mois : les cotisations restent supérieures au brut,
le net sort négatif. Rien n'est viré ; la somme se reprend le mois suivant.
"""

from app.modules.payroll.domain.report_nap_negatif import (
    est_un_report,
    message_net_negatif,
    mois_reporte,
    mois_suivant,
    nom_du_report,
)
from app.modules.payroll.engine.controles_convention import avertissements_de_generation
from app.modules.payslips.infrastructure.payslip_list_meta import payslip_list_meta

MESSAGE_SEPTEMBRE = (
    "Net à payer négatif : −115,43 €. Rien ne sera viré en septembre 2026. "
    "Reprenez cette somme en octobre 2026."
)


def _bulletin(net: float, *, annee: int = 2026, mois: int = 9) -> dict:
    return {
        "en_tete": {"annee": annee, "mois": mois},
        "salaire_brut": 19.61,
        "net_a_payer": net,
        "synthese_net": {},
        "alertes_baremes": [],
    }


def test_le_message_nomme_le_montant_et_les_deux_mois():
    assert message_net_negatif(-115.43, 2026, 9) == MESSAGE_SEPTEMBRE


def test_decembre_reporte_sur_janvier_de_l_annee_suivante():
    assert mois_suivant(2026, 12) == (2027, 1)
    assert "Reprenez cette somme en janvier 2027." in message_net_negatif(-12.0, 2026, 12)


def test_sans_periode_le_message_reste_lisible():
    assert message_net_negatif(-1594.6, None, None) == (
        "Net à payer négatif : −1 594,60 €. Rien ne sera viré ce mois-ci. "
        "Reprenez cette somme le mois suivant."
    )


def test_la_generation_renvoie_l_alerte():
    assert MESSAGE_SEPTEMBRE in avertissements_de_generation(_bulletin(-115.43))


def test_un_net_nul_ou_positif_ne_declenche_rien():
    for net in (0.0, 12.5):
        assert not any(
            "Net à payer négatif" in str(a) for a in avertissements_de_generation(_bulletin(net))
        )


def test_la_liste_des_bulletins_ne_montre_plus_un_genere_sans_nuance():
    meta = payslip_list_meta(_bulletin(-115.43))
    assert MESSAGE_SEPTEMBRE in meta["warnings"]


def test_le_nom_du_report_porte_le_mois_du_bulletin_negatif():
    assert nom_du_report(2026, 9) == "Report NAP négatif 09/2026"
    assert mois_reporte("Report NAP négatif 09/2026") == (2026, 9)
    assert mois_reporte("Acompte") is None


def test_seules_les_saisies_de_report_passent_au_bulletin():
    from app.modules.payroll.domain.report_nap_negatif import reports_du_mois

    saisies = [
        {"name": "Report NAP négatif 09/2026", "amount": -115.43, "sur_le_net": True},
        {"name": "Acompte du 15", "amount": -300.0, "sur_le_net": True},
    ]
    assert reports_du_mois(saisies) == [{"libelle": "Report NAP négatif 09/2026", "montant": 115.43}]


def test_seules_les_saisies_de_report_passent_au_bulletin():
    from app.modules.payroll.domain.report_nap_negatif import reports_du_mois

    saisies = [
        {"name": "Report NAP négatif 09/2026", "amount": -115.43, "sur_le_net": True},
        {"name": "Acompte du 15", "amount": -300.0, "sur_le_net": True},
    ]
    assert reports_du_mois(saisies) == [{"libelle": "Report NAP négatif 09/2026", "montant": 115.43}]


def test_un_report_se_reconnait_par_le_catalogue_ou_par_le_nom():
    assert est_un_report({"catalog_prime_id": "report_nap_negatif", "name": "X"})
    assert est_un_report({"name": "report nap negatif 09/2026"})
    assert not est_un_report({"name": "Acompte du 15"})
