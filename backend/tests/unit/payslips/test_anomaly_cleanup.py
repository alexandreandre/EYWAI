"""Tests unitaires — purge batch des alertes moteur paie."""

from datetime import date
from unittest.mock import MagicMock, patch

from app.modules.payslips.infrastructure.anomaly_cleanup import (
    cleanup_payslips_on_exit_archived,
    purge_all_engine_alerts_from_payslips,
)


class TestPurgeAllEngineAlerts:
    def test_updates_rows_with_alertes_baremes(self):
        sb = MagicMock()
        chain = MagicMock()
        sb.table.return_value = chain
        chain.select.return_value = chain
        chain.range.return_value = chain
        chain.eq.return_value = chain
        chain.update.return_value = chain

        execute_results = [
            MagicMock(
                data=[
                    {
                        "id": "ps-1",
                        "payslip_data": {
                            "salaire_brut": 2000,
                            "alertes_baremes": [{"code": "x", "message": "y"}],
                        },
                    }
                ]
            ),
            MagicMock(data=[]),
        ]
        chain.execute.side_effect = execute_results

        count = purge_all_engine_alerts_from_payslips(sb, page_size=100)
        assert count == 1
        chain.update.assert_called_once()


class TestCleanupExitArchivedRegularisation:
    def _sb_with_rows(self, rows):
        sb = MagicMock()
        chain = MagicMock()
        sb.table.return_value = chain
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.execute.return_value = MagicMock(data=rows)
        return sb

    def test_regularisation_bulletin_is_never_deleted(self):
        """Un bulletin de régularisation postérieur au départ ne doit pas être supprimé."""
        rows = [
            {
                "id": "ps-regul",
                "year": 2027,
                "month": 5,
                "status": "valide",
                "payslip_data": {},
                "bulletin_kind": "regularisation_participation",
            },
            {
                "id": "ps-draft",
                "year": 2027,
                "month": 5,
                "status": "brouillon",
                "payslip_data": {},
                "bulletin_kind": None,
            },
        ]
        sb = self._sb_with_rows(rows)
        deleted = []
        with patch(
            "app.modules.payslips.infrastructure.anomaly_cleanup.payslip_repository"
        ) as repo:
            repo.delete.side_effect = lambda pid: deleted.append(pid)
            cleanup_payslips_on_exit_archived(
                "e-1", "c-1", date(2026, 12, 31), supabase_client=sb
            )
        # Seul le brouillon standard postérieur au départ est supprimé.
        assert deleted == ["ps-draft"]


class TestCleanupFenetrePeriodePaie:
    """Arrêté glissant : le bulletin dont la PÉRIODE contient le dernier jour
    travaillé ne doit jamais être supprimé, même s'il est du mois civil suivant."""

    def _sb(self, payslip_rows, company_row):
        sb = MagicMock()

        pay_chain = MagicMock()
        pay_chain.select.return_value = pay_chain
        pay_chain.eq.return_value = pay_chain
        pay_chain.execute.return_value = MagicMock(data=payslip_rows)

        comp_chain = MagicMock()
        comp_chain.select.return_value = comp_chain
        comp_chain.eq.return_value = comp_chain
        comp_chain.maybe_single.return_value = comp_chain
        comp_chain.execute.return_value = MagicMock(data=company_row)

        sb.table.side_effect = (
            lambda name: comp_chain if name == "companies" else pay_chain
        )
        return sb

    _ROWS = [
        {
            "id": "ps-juillet",
            "year": 2026,
            "month": 7,
            "status": "brouillon",
            "payslip_data": {},
            "bulletin_kind": None,
        },
        {
            "id": "ps-aout",
            "year": 2026,
            "month": 8,
            "status": "brouillon",
            "payslip_data": {},
            "bulletin_kind": None,
        },
    ]

    def _run(self, company_row):
        deleted = []
        with patch(
            "app.modules.payslips.infrastructure.anomaly_cleanup.payslip_repository"
        ) as repo:
            repo.delete.side_effect = lambda pid: deleted.append(pid)
            cleanup_payslips_on_exit_archived(
                "e-1",
                "c-1",
                date(2026, 6, 30),
                supabase_client=self._sb(self._ROWS, company_row),
            )
        return deleted

    def test_arrete_glissant_conserve_le_bulletin_porteur_du_stc(self):
        """(4, -2) : période de juillet 2026 = 22/06→26/07, elle contient le
        30/06 — le brouillon de juillet (STC/précarité) est conservé, celui
        d'août (période dès le 27/07) est supprimé."""
        deleted = self._run({"paie_jour_de_fin": 4, "paie_occurrence": -2})
        assert deleted == ["ps-aout"]

    def test_mois_calendaire_comportement_inchange(self):
        """Mois civil : juillet commence le 01/07 > 30/06 → les deux brouillons
        postérieurs au départ sont supprimés, comme avant."""
        deleted = self._run({"paie_jour_de_fin": 31, "paie_occurrence": -1})
        assert deleted == ["ps-juillet", "ps-aout"]

    def test_paie_jour_de_fin_null_replie_sur_mois_calendaire(self):
        """paie_jour_de_fin NULL : le moteur de bulletins traite la société en
        mois calendaire — le cleanup doit faire pareil (pas le défaut glissant
        4/-2), sinon les brouillons M+1 survivent à l'archivage."""
        deleted = self._run({"paie_jour_de_fin": None, "paie_occurrence": None})
        assert deleted == ["ps-juillet", "ps-aout"]
