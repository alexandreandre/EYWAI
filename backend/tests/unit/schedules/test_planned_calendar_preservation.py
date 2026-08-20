"""Le planning ne doit jamais amputer ni écraser les métadonnées d'absence."""


def test_entree_calendrier_conserve_les_cles_supplementaires():
    from app.modules.schedules.schemas.requests import PlannedCalendarEntry

    entry = PlannedCalendarEntry(
        jour=3,
        type="arret_maladie",
        heures_prevues=0,
        arret_type="maladie_simple",
        subrogation_active=True,
        nombre_enfants=2,
        date_debut_arret_reel="2026-07-14",
    )
    dumped = entry.model_dump()
    assert dumped["arret_type"] == "maladie_simple"
    assert dumped["subrogation_active"] is True
    assert dumped["nombre_enfants"] == 2
    assert dumped["date_debut_arret_reel"] == "2026-07-14"
