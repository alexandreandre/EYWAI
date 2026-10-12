"""Les exports lisent aussi les brouillons : les messages le disent, l'aperçu compte.

Aucun export ne filtre sur le statut du bulletin. Les textes parlaient pourtant
de bulletins « validés » : faux dans tous les cas réels. L'aperçu dit maintenant
combien de bulletins ne sont pas validés et combien sont « à recalculer ». Ce
qui est exporté ne change pas.
"""

from unittest.mock import patch

import pytest

from app.modules.exports.application import queries
from app.modules.exports.domain.etat_bulletins import (
    EXPORTS_LUS_SUR_BULLETINS,
    avertissements_etat_bulletins,
)
from app.modules.exports.infrastructure import export_ecritures_comptables, export_journal_paie
from app.modules.exports.schemas import ExportPreviewRequest

pytestmark = pytest.mark.unit


class TestPhrases:
    def test_rien_a_dire_quand_tout_est_valide_et_a_jour(self):
        assert avertissements_etat_bulletins(0, 0, 0) == []

    def test_non_valides_et_a_recalculer_au_pluriel(self):
        assert avertissements_etat_bulletins(12, 3, 0) == [
            "12 bulletins non validés : l'export reprend aussi les brouillons.",
            "3 bulletins à recalculer : leurs données ont changé depuis le calcul, "
            "l'export reprend leur dernier calcul.",
        ]

    def test_au_singulier(self):
        """Relevé I.1 : « 1 bulletin à recalculer : leurs données… »."""
        assert avertissements_etat_bulletins(1, 1, 0) == [
            "1 bulletin non validé : l'export reprend aussi les brouillons.",
            "1 bulletin à recalculer : ses données ont changé depuis le calcul, "
            "l'export reprend son dernier calcul.",
        ]

    def test_un_etat_non_verifie_est_dit(self):
        assert avertissements_etat_bulletins(0, 0, 4) == [
            "L'état « à recalculer » de 4 bulletins n'a pas pu être vérifié."
        ]

    def test_les_exports_qui_lisent_les_bulletins(self):
        assert {"journal_paie", "virement_salaires", "od_globale", "fec", "dsn_mensuelle"} <= (
            EXPORTS_LUS_SUR_BULLETINS
        )
        assert "conges_absences" not in EXPORTS_LUS_SUR_BULLETINS
        assert "virement_acomptes" not in EXPORTS_LUS_SUR_BULLETINS


class TestMessageDeVide:
    def test_journal_de_paie_sans_bulletin(self):
        with patch.object(
            export_journal_paie,
            "get_journal_paie_data",
            return_value=([], {"employees_count": 0}),
        ):
            apercu = export_journal_paie.preview_journal_paie("co-1", "2026-09")
        messages = [a["message"] for a in apercu["anomalies"]]
        assert messages == ["Aucun bulletin de paie pour cette période"]

    def test_ecritures_et_envoi_compta_disent_la_meme_chose(self):
        assert export_ecritures_comptables.MESSAGE_AUCUN_BULLETIN == (
            "Aucun bulletin de paie pour cette période"
        )

    def test_l_envoi_compta_sans_bulletin(self):
        from app.modules.exports.application.dispatch import _synthetic_blocking_anomaly
        from app.modules.exports.schemas import ExportPreviewResponse, ExportTotals

        apercu = ExportPreviewResponse(
            export_type="journal_paie",
            period="2026-09",
            employees_count=0,
            totals=ExportTotals(),
            anomalies=[],
            warnings=[],
            can_generate=False,
        )
        anomalie = _synthetic_blocking_anomaly("journal_paie", apercu)
        assert anomalie.message == "Aucun bulletin de paie pour cette période"


class TestApercuDesExports:
    def _apercu(self, export_type, etat):
        fausse = {
            "employees_count": 2,
            "totals": {"employees_count": 2},
            "anomalies": [],
            "warnings": ["déjà là"],
            "can_generate": True,
        }
        with patch.object(queries.providers, "preview_journal_paie", return_value=fausse), patch.object(
            queries, "lire_etat_bulletins", return_value=etat
        ) as lecture:
            reponse = queries.preview_export(
                "co-1", ExportPreviewRequest(export_type=export_type, period="2026-09")
            )
        return reponse, lecture

    def test_l_apercu_du_journal_compte_les_brouillons_et_les_perimes(self):
        reponse, _ = self._apercu("journal_paie", (5, 2, 0))
        assert reponse.warnings[0] == "déjà là"
        assert "5 bulletins non validés" in reponse.warnings[1]
        assert "2 bulletins à recalculer" in reponse.warnings[2]
        assert reponse.can_generate is True

    def test_ne_change_ni_les_anomalies_ni_la_generation(self):
        reponse, _ = self._apercu("journal_paie", (5, 2, 0))
        assert reponse.anomalies == []
        assert reponse.employees_count == 2

    def test_rien_ajoute_quand_tout_est_valide(self):
        reponse, _ = self._apercu("journal_paie", (0, 0, 0))
        assert reponse.warnings == ["déjà là"]


class TestLectureDeLEtat:
    """Compte les non-validés et les « à recalculer » ; un repris n'est jamais à recalculer."""

    def _lire(self, bulletins, etats, **kwargs):
        from types import SimpleNamespace

        from app.modules.exports.infrastructure import etat_bulletins

        def etat(employee_id, year, month):
            valeur = etats[employee_id]
            if isinstance(valeur, Exception):
                raise valeur
            return None if valeur is None else SimpleNamespace(a_recalculer=valeur)

        with patch.object(etat_bulletins, "_bulletins_du_mois", return_value=bulletins), patch(
            "app.modules.payroll.application.empreinte_entrees_service.etat_dans_la_chaine",
            side_effect=etat,
        ):
            return etat_bulletins.lire_etat_bulletins("co-1", "2026-09", **kwargs)

    def test_compte_brouillons_et_perimes(self):
        bulletins = [
            {"employee_id": "a", "status": "valide"},
            {"employee_id": "b", "status": "brouillon"},
            {"employee_id": "c", "status": "brouillon"},
        ]
        assert self._lire(bulletins, {"a": False, "b": True, "c": False}) == (2, 1, 0)

    def test_un_bulletin_repris_n_est_pas_a_recalculer(self):
        bulletins = [{"employee_id": "a", "status": "brouillon", "origine": "importe"}]
        assert self._lire(bulletins, {"a": True}) == (1, 0, 0)

    def test_un_etat_illisible_est_dit_non_verifie(self):
        bulletins = [{"employee_id": "a", "status": "valide"}]
        assert self._lire(bulletins, {"a": ValueError("x")}) == (0, 0, 1)

    def test_etat_inconnu_n_est_pas_a_recalculer(self):
        bulletins = [{"employee_id": "a", "status": "valide"}]
        assert self._lire(bulletins, {"a": None}) == (0, 0, 0)
