"""Tests métadonnées listes bulletins."""

from app.modules.payslips.infrastructure.payslip_list_meta import payslip_list_meta


class TestPayslipListMeta:
    def test_warnings_net_superieur_brut(self):
        meta = payslip_list_meta({"salaire_brut": 1200.0, "net_a_payer": 1300.0})
        assert meta["net_a_payer"] == 1300.0
        assert len(meta["warnings"]) == 1

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
