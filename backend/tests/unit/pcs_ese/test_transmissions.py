"""Les mois dont une DSN mensuelle est partie : ce qui y est déclaré ne repart pas le mois suivant."""

from app.modules.pcs_ese.infrastructure.transmissions import periodes_declarees


def test_seules_les_dsn_mensuelles_parties_comptent():
    lignes = [
        {"period": "2026-09", "dsn_type": "dsn_mensuelle_normale", "status": "acknowledged"},
        {"period": "2026-10", "dsn_type": "dsn_mensuelle_normale", "status": "manual"},
        {"period": "2026-11", "dsn_type": "dsn_mensuelle_normale", "status": "generated"},
        {"period": "2026-12", "dsn_type": "dsn_mensuelle_normale", "status": "rejected"},
        {"period": "2026-12", "dsn_type": "signalement_arret", "status": "sent"},
    ]
    assert periodes_declarees(lignes) == frozenset({"2026-09", "2026-10"})


def test_aucune_dsn_partie():
    assert periodes_declarees([]) == frozenset()
    assert periodes_declarees([{"period": "2026-10", "status": "generated"}]) == frozenset()
