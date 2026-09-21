"""Tests métadonnées listes bulletins."""

from app.modules.payslips.infrastructure.payslip_list_meta import payslip_list_meta


class TestPayslipListMeta:
    def test_warnings_net_superieur_brut(self):
        meta = payslip_list_meta({"salaire_brut": 1200.0, "net_a_payer": 1300.0})
        assert meta["net_a_payer"] == 1300.0
        assert meta["warnings"] == ["Net > Brut"]

    def test_pas_warning_net_superieur_brut_avec_participation_numeraire(self):
        meta = payslip_list_meta(
            {
                "salaire_brut": 2232.77,
                "net_a_payer": 3516.33,
                "calcul_du_brut": [
                    {
                        "libelle": (
                            "Participation 2025 — numéraire "
                            "(brut, exonéré de cotisations)"
                        ),
                        "gain": 3022.27,
                        "is_informative": True,
                    }
                ],
                "alertes_baremes": [],
            }
        )

        assert meta["warnings"] == []

    def test_pas_warning_net_superieur_brut_avec_participation_forfait(self):
        meta = payslip_list_meta(
            {
                "salaire_brut": 3984.0,
                "net_a_payer": 6722.64,
                "calcul_du_brut": [],
                "participations": [
                    {
                        "libelle": "Participation 2025 — numéraire",
                        "brut": 5818.27,
                        "part_pee": 0.0,
                    }
                ],
                "alertes_baremes": [],
            }
        )

        assert meta["warnings"] == []

    def test_pas_warning_net_superieur_brut_avec_frais_pro_hors_brut(self):
        meta = payslip_list_meta(
            {
                "salaire_brut": 125.65,
                "net_a_payer": 244.23,
                "synthese_net": {"acompte_verse": -150.0},
                "alertes_baremes": [],
            }
        )

        assert meta["warnings"] == []

    def test_warnings_from_alertes_baremes(self):
        meta = payslip_list_meta(
            {
                "salaire_brut": 2000.0,
                "net_a_payer": 1800.0,
                "alertes_baremes": [
                    {"code": "cc_test", "message": "Alerte test", "critique": False}
                ],
            }
        )
        assert meta["warnings"] == ["Alerte test"]



def test_les_points_a_arbitrer_sont_a_part_des_alertes():
    """La liste ne doit pas compter un point à arbitrer comme une alerte orange."""
    meta = payslip_list_meta(
        {
            "net_a_payer": 100.0,
            "alertes_baremes": [
                {"code": "cc_classification_manquante", "critique": False, "message": "Classif."},
                {"code": "transport_plafond_annuel_depasse", "critique": False, "a_arbitrer": True,
                 "message": "Transport : 700,00 € versés."},
            ],
        }
    )
    assert meta["warnings"] == ["Classif."]
    assert meta["points_a_arbitrer"] == ["Transport : 700,00 € versés."]


def test_sans_point_a_arbitrer_la_liste_est_vide():
    assert payslip_list_meta({"net_a_payer": 1.0})["points_a_arbitrer"] == []
    assert payslip_list_meta("rien")["points_a_arbitrer"] == []
