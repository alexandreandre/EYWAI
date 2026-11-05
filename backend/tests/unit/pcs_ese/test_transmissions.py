"""La dernière DSN mensuelle partie : ce qui est déjà déclaré ne repart pas."""

from app.modules.pcs_ese.infrastructure.transmissions import periode_la_plus_recente


def test_seules_les_dsn_mensuelles_parties_comptent():
    lignes = [
        {"period": "2026-09", "dsn_type": "dsn_mensuelle_normale", "status": "acknowledged"},
        {"period": "2026-10", "dsn_type": "dsn_mensuelle_normale", "status": "manual"},
        {"period": "2026-11", "dsn_type": "dsn_mensuelle_normale", "status": "generated"},
        {"period": "2026-12", "dsn_type": "dsn_mensuelle_normale", "status": "rejected"},
        {"period": "2026-12", "dsn_type": "signalement_arret", "status": "sent"},
    ]
    assert periode_la_plus_recente(lignes) == "2026-10"


def test_aucune_dsn_partie():
    assert periode_la_plus_recente([]) is None
    assert periode_la_plus_recente([{"period": "2026-10", "status": "generated"}]) is None
