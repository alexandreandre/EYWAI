"""Intitulé de la convention collective repris du catalogue."""

from unittest.mock import MagicMock

from app.modules.collective_agreements.application.idcc_resolution import (
    build_convention_collective_payload,
)


def _client(nom):
    client = MagicMock()
    reponse = MagicMock()
    reponse.data = [{"name": nom}] if nom else []
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = reponse
    return client


class TestLibelleConvention:
    def test_repli_sur_le_catalogue_quand_la_societe_ne_renseigne_rien(self):
        client = _client("Convention collective nationale de la métallurgie")
        payload = build_convention_collective_payload(
            {}, {"idcc": "3248"}, supabase_client=client
        )
        assert payload["idcc"] == "3248"
        assert payload["libelle"].startswith("Convention collective nationale")

    def test_la_valeur_de_la_societe_reste_prioritaire(self):
        client = _client("Depuis le catalogue")
        payload = build_convention_collective_payload(
            {}, {"idcc": "3248", "collective_agreement": "Saisie société"},
            supabase_client=client,
        )
        assert payload["libelle"] == "Saisie société"

    def test_catalogue_muet_ne_casse_rien(self):
        payload = build_convention_collective_payload(
            {}, {"idcc": "3248"}, supabase_client=_client(None)
        )
        assert payload == {"idcc": "3248", "libelle": ""}
