"""La garde des bulletins importés survit à une base sans la colonne `origine`.

La migration `20260917090000_reprise_paie_bascule` n'est pas appliquée partout :
en production, `payslips.origine` n'existe pas encore. Sélectionner cette
colonne y ferait échouer la suppression et l'édition d'un bulletin.
"""

from unittest.mock import MagicMock, patch

from app.modules.payslips.application.commands import _fetch_payslip_status


def _supabase(reponses):
    """Un client dont les `execute()` successifs jouent `reponses` (valeur ou exception)."""
    chaine = MagicMock()
    for methode in ("select", "eq", "maybe_single"):
        getattr(chaine, methode).return_value = chaine
    chaine.execute.side_effect = reponses
    client = MagicMock()
    client.table.return_value = chaine
    return client, chaine


def test_le_statut_est_lu_meme_sans_la_colonne_origine():
    erreur = Exception('column payslips.origine does not exist')
    ok = MagicMock(data={"id": "ps-1", "status": "brouillon"})
    client, chaine = _supabase([erreur, ok])
    with patch("app.modules.payslips.application.commands.supabase", client):
        assert _fetch_payslip_status("ps-1") == {"id": "ps-1", "status": "brouillon"}
    colonnes = [appel.args[0] for appel in chaine.select.call_args_list]
    assert colonnes == ["id, status, origine", "id, status"]


def test_avec_la_colonne_l_origine_est_rendue():
    ok = MagicMock(data={"id": "ps-1", "status": "brouillon", "origine": "importe"})
    client, _ = _supabase([ok])
    with patch("app.modules.payslips.application.commands.supabase", client):
        assert _fetch_payslip_status("ps-1")["origine"] == "importe"


def test_un_bulletin_inconnu_reste_none():
    client, _ = _supabase([MagicMock(data=None)])
    with patch("app.modules.payslips.application.commands.supabase", client):
        assert _fetch_payslip_status("ps-absent") is None
