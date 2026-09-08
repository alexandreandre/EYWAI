"""Corriger les heures supplémentaires sur le bulletin le fait recalculer.

Avant : modifier la quantité ne changeait que le brut. Les cotisations et le
net restaient ceux du calcul d'origine, et le bulletin partait faux sans que
rien ne le signale (retour Gaëlle du 08/09/2026 sur BUGNY).

Depuis : les deux paliers sont redéclarés au moteur, qui régénère tout.
"""

from unittest.mock import patch

import pytest

from app.modules.payslips.application.commands import (
    LIBELLE_HS_DECLAREES,
    LIBELLE_HS_DECLAREES_50,
    edit_payslip,
)
from app.modules.payslips.application.dto import EditPayslipInput


def _bulletin(hs_25: float | None, hs_50: float | None) -> dict:
    """Bulletin calqué sur BUGNY juillet 2026 : structurelles + conjoncturelles."""
    lignes = [
        {"libelle": "Salaire de base", "quantite": 151.67, "taux": 14.28},
        {
            "libelle": "Heures suppl. structurelles majorées à 25%",
            "quantite": 17.33,
            "taux": 17.85,
        },
    ]
    if hs_25 is not None:
        lignes.append(
            {"libelle": "Heures suppl. majorées à 25%", "quantite": hs_25, "taux": 17.85}
        )
    if hs_50 is not None:
        lignes.append(
            {"libelle": "Heures suppl. majorées à 50%", "quantite": hs_50, "taux": 21.42}
        )
    return {"calcul_du_brut": lignes}


AVANT = {
    "id": "ps-bugny",
    "employee_id": "emp-bugny",
    "company_id": "comp-1",
    "year": 2026,
    "month": 7,
    "payslip_data": _bulletin(12.0, 3.5),
}


def _commande(payslip_data: dict) -> EditPayslipInput:
    return EditPayslipInput(
        payslip_id="ps-bugny",
        payslip_data=payslip_data,
        changes_summary="Correction des heures supplémentaires",
        current_user_id="user-gaelle",
        current_user_name="Gaëlle",
    )


@pytest.fixture(autouse=True)
def _contexte():
    with patch(
        "app.modules.payslips.application.commands._fetch_payslip_status",
        return_value={"id": "ps-bugny", "status": "brouillon"},
    ), patch(
        "app.modules.payslips.application.commands._fetch_payslip_for_recalc",
        return_value=AVANT,
    ), patch(
        "app.modules.payslips.application.commands.payslip_editor_provider"
    ) as editeur:
        editeur.save_edited.return_value = {"payslip": {"id": "ps-bugny"}}
        yield


class TestCorrectionDesHeuresSup:
    def test_corriger_12h_en_13h_redeclare_et_regenere(self):
        with patch(
            "app.modules.payslips.application.commands._remplacer_heures_sup_declarees"
        ) as declarer, patch(
            "app.modules.payslips.application.commands.generate_payslip"
        ) as regenerer:
            edit_payslip(_commande(_bulletin(13.0, 3.5)))

        declarer.assert_called_once()
        assert declarer.call_args.kwargs["heures_25"] == 13.0
        # Le palier non touché est redéclaré tel quel : ne pas l'envoyer le
        # remettrait à zéro et ferait disparaître 3,5 h du bulletin.
        assert declarer.call_args.kwargs["heures_50"] == 3.5
        assert declarer.call_args.kwargs["employee_id"] == "emp-bugny"
        assert declarer.call_args.kwargs["year"] == 2026
        assert declarer.call_args.kwargs["month"] == 7

        regenerer.assert_called_once()
        entree = regenerer.call_args.args[0]
        assert entree.employee_id == "emp-bugny"
        assert entree.year == 2026
        assert entree.month == 7

    def test_les_structurelles_ne_declenchent_rien(self):
        """Elles viennent du contrat : les redéclarer les figerait à tort."""
        modifie = _bulletin(12.0, 3.5)
        modifie["calcul_du_brut"][1]["quantite"] = 18.0

        with patch(
            "app.modules.payslips.application.commands._remplacer_heures_sup_declarees"
        ) as declarer, patch(
            "app.modules.payslips.application.commands.generate_payslip"
        ) as regenerer:
            edit_payslip(_commande(modifie))

        declarer.assert_not_called()
        regenerer.assert_not_called()

    def test_modifier_autre_chose_enregistre_sans_recalculer(self):
        autre = _bulletin(12.0, 3.5)
        autre["calcul_du_brut"][0]["quantite"] = 150.0

        with patch(
            "app.modules.payslips.application.commands._remplacer_heures_sup_declarees"
        ) as declarer, patch(
            "app.modules.payslips.application.commands.generate_payslip"
        ) as regenerer:
            edit_payslip(_commande(autre))

        declarer.assert_not_called()
        regenerer.assert_not_called()

    def test_deplacer_une_heure_entre_paliers_ne_declare_rien(self):
        """12 h + 3,5 h corrigé en 13 h + 2,5 h : même total, le moteur ne
        bouge pas. Déclarer quand même laisserait des saisies fantômes en
        désaccord avec le bulletin."""
        with patch(
            "app.modules.payslips.application.commands._remplacer_heures_sup_declarees"
        ) as declarer, patch(
            "app.modules.payslips.application.commands.generate_payslip"
        ) as regenerer:
            edit_payslip(_commande(_bulletin(13.0, 2.5)))

        declarer.assert_not_called()
        regenerer.assert_not_called()

    def test_un_seul_palier_a_zero_declenche_bien_le_recalcul(self):
        """Le total change, et l'autre palier subsiste : le moteur applique."""
        with patch(
            "app.modules.payslips.application.commands._remplacer_heures_sup_declarees"
        ) as declarer, patch(
            "app.modules.payslips.application.commands.generate_payslip"
        ):
            edit_payslip(_commande(_bulletin(0.0, 3.5)))

        assert declarer.call_args.kwargs["heures_25"] == 0.0
        assert declarer.call_args.kwargs["heures_50"] == 3.5

    def test_remise_a_zero_des_deux_paliers_reste_un_simple_enregistrement(self):
        """Le moteur ne lit pas (0, 0) comme une déclaration : il repasserait au
        calendrier et rétablirait les heures. On ne prétend donc pas recalculer."""
        with patch(
            "app.modules.payslips.application.commands._remplacer_heures_sup_declarees"
        ) as declarer, patch(
            "app.modules.payslips.application.commands.generate_payslip"
        ) as regenerer:
            edit_payslip(_commande(_bulletin(0.0, 0.0)))

        declarer.assert_not_called()
        regenerer.assert_not_called()

    def test_le_recalcul_vient_apres_l_enregistrement(self):
        """L'historique doit garder trace de sa saisie avant que le moteur ne
        réécrive le bulletin."""
        ordre: list[str] = []

        with patch(
            "app.modules.payslips.application.commands.payslip_editor_provider"
        ) as editeur, patch(
            "app.modules.payslips.application.commands._remplacer_heures_sup_declarees"
        ), patch(
            "app.modules.payslips.application.commands.generate_payslip"
        ) as regenerer:
            editeur.save_edited.side_effect = lambda **_: (
                ordre.append("enregistre") or {"payslip": {}}
            )
            regenerer.side_effect = lambda *_: ordre.append("regenere")
            edit_payslip(_commande(_bulletin(13.0, 3.5)))

        assert ordre == ["enregistre", "regenere"]


class TestLibellesDesSaisiesDeclarees:
    """Les libellés posés doivent rester lisibles par le générateur."""

    def test_reconnus_comme_heures_sup_conjoncturelles(self):
        from app.modules.payroll.documents.payslip_generator import (
            _heures_sup_conjoncturelles_from_monthly_inputs,
        )

        lignes = [
            {"name": LIBELLE_HS_DECLAREES, "payroll_quantity": 13.0},
            {"name": LIBELLE_HS_DECLAREES_50, "payroll_quantity": 3.5},
        ]
        assert _heures_sup_conjoncturelles_from_monthly_inputs(lignes) == (13.0, 3.5)

    def test_le_premier_palier_ne_contient_pas_50(self):
        """« 50 » dans le libellé bascule la ligne sur le second palier."""
        assert "50" not in LIBELLE_HS_DECLAREES
        assert "50" in LIBELLE_HS_DECLAREES_50

    def test_aucun_libelle_ne_dit_structurelle(self):
        """« struct » ferait ignorer la ligne par le générateur."""
        assert "struct" not in LIBELLE_HS_DECLAREES.lower()
        assert "struct" not in LIBELLE_HS_DECLAREES_50.lower()
