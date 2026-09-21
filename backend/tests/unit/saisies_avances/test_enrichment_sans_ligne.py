"""Les gardes de doublon de l'enrichissement supportent l'absence de ligne.

`maybe_single().execute()` renvoie None quand aucune ligne n'existe : lire
`.data` dessus faisait exploser tout l'enrichissement, et une saisie sur
salaire n'atteignait jamais le bulletin (Marion Gautheron, juillet 2026).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.modules.saisies_avances.infrastructure.enrichment import (
    get_existing_deduction,
    get_existing_repayment,
)


def _supabase_renvoyant(resultat):
    chaine = MagicMock()
    chaine.execute.return_value = resultat
    for methode in ("select", "eq", "maybe_single"):
        getattr(chaine, methode).return_value = chaine
    client = MagicMock()
    client.table.return_value = chaine
    return client


def test_aucune_deduction_existante_quand_la_requete_ne_renvoie_rien():
    with patch("app.modules.saisies_avances.infrastructure.enrichment.supabase", _supabase_renvoyant(None)):
        assert get_existing_deduction("saisie-1", "bulletin-1") is None


def test_aucun_remboursement_existant_quand_la_requete_ne_renvoie_rien():
    with patch("app.modules.saisies_avances.infrastructure.enrichment.supabase", _supabase_renvoyant(None)):
        assert get_existing_repayment("avance-1", "bulletin-1") is None


def test_la_ligne_existante_est_rendue():
    resultat = SimpleNamespace(data={"id": "d-1"})
    with patch("app.modules.saisies_avances.infrastructure.enrichment.supabase", _supabase_renvoyant(resultat)):
        assert get_existing_deduction("saisie-1", "bulletin-1") == {"id": "d-1"}
