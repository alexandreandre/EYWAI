"""Tests du journal des échanges avec l'assistant RH."""

from unittest.mock import Mock, patch

import pytest

from app.modules.copilot.infrastructure import journal

pytestmark = pytest.mark.unit


class TestEnregistrerTour:
    def _appel(self, **surcharge):
        defauts = dict(
            company_id="c1",
            user_id="u1",
            question="Combien de CDI ?",
            routage="data",
            outils=["employee_count"],
            latence_ms=1200,
            reponse_caracteres=340,
        )
        defauts.update(surcharge)
        journal.enregistrer_tour(**defauts)

    def test_ecrit_la_ligne_attendue(self):
        client = Mock()
        with patch.object(journal, "get_supabase_client", return_value=client), \
                patch.object(journal.threading, "Thread") as thread:
            self._appel()
            # L'écriture part dans un fil détaché : hors du chemin critique.
            assert thread.call_args.kwargs["daemon"] is True
            cible, (ligne,) = thread.call_args.kwargs["target"], thread.call_args.kwargs["args"]
            cible(ligne)

        insert = client.table.return_value.insert
        insert.assert_called_once()
        ligne = insert.call_args.args[0]
        assert ligne["company_id"] == "c1"
        assert ligne["routage"] == "data"
        assert ligne["outils"] == ["employee_count"]
        assert ligne["latence_ms"] == 1200
        # La réponse elle-même n'est jamais conservée, seulement sa longueur.
        assert "reponse" not in ligne
        assert ligne["reponse_caracteres"] == 340

    def test_question_tres_longue_est_tronquee(self):
        client = Mock()
        with patch.object(journal, "get_supabase_client", return_value=client), \
                patch.object(journal.threading, "Thread") as thread:
            self._appel(question="x" * 5000)
            thread.call_args.kwargs["target"](*thread.call_args.kwargs["args"])
        ligne = client.table.return_value.insert.call_args.args[0]
        assert len(ligne["question"]) == journal.MAX_QUESTION_CHARS

    def test_une_base_indisponible_ne_leve_jamais(self):
        client = Mock()
        client.table.side_effect = RuntimeError("base injoignable")
        with patch.object(journal, "get_supabase_client", return_value=client):
            journal._ecrire({"question": "x"})  # ne doit pas lever
