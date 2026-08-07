"""Un mandat expiré doit sortir avec un nombre de jours négatif, pas avec None.

Sans cela, l'export Excel ne sait pas distinguer un mandat expiré d'un mandat en cours
et affiche tout le monde « Actif ».
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.modules.cse.infrastructure import cse_service_impl


def _ligne(end_date: date) -> dict:
    return {
        "id": "elu-1",
        "employee_id": "emp-1",
        "role": "titulaire",
        "college": "1er collège",
        "start_date": (end_date - timedelta(days=1461)).isoformat(),
        "end_date": end_date.isoformat(),
        "is_active": True,
        "employees": {
            "id": "emp-1",
            "first_name": "Prenom",
            "last_name": "NOM",
            "job_title": "Opérateur",
        },
    }


def _mock_supabase(lignes: list[dict]) -> MagicMock:
    reponse = MagicMock()
    reponse.data = lignes
    chaine = MagicMock()
    chaine.select.return_value = chaine
    chaine.eq.return_value = chaine
    chaine.gte.return_value = chaine
    chaine.order.return_value = chaine
    chaine.execute.return_value = reponse
    client = MagicMock()
    client.table.return_value = chaine
    return client


def test_mandat_expire_renvoie_un_nombre_de_jours_negatif():
    fin = date.today() - timedelta(days=45)
    with patch.object(cse_service_impl, "supabase", _mock_supabase([_ligne(fin)])):
        membres = cse_service_impl.get_elected_members("co-1", active_only=False)
    assert membres[0].days_remaining == -45


def test_mandat_en_cours_renvoie_un_nombre_de_jours_positif():
    fin = date.today() + timedelta(days=200)
    with patch.object(cse_service_impl, "supabase", _mock_supabase([_ligne(fin)])):
        membres = cse_service_impl.get_elected_members("co-1", active_only=False)
    assert membres[0].days_remaining == 200


def test_mandat_qui_finit_aujourdhui_renvoie_zero():
    with patch.object(cse_service_impl, "supabase", _mock_supabase([_ligne(date.today())])):
        membres = cse_service_impl.get_elected_members("co-1", active_only=False)
    assert membres[0].days_remaining == 0
