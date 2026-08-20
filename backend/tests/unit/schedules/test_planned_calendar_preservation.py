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


def test_fusion_conserve_les_metadonnees_absentes_du_payload():
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [
        {
            "jour": 3,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "arret_type": "maladie_simple",
            "subrogation_active": True,
            "nombre_enfants": 2,
        },
        {"jour": 4, "type": "travail", "heures_prevues": 7.0},
    ]
    # Le client renvoie le mois « appauvri » (cas réel du GET actuel)
    incoming = [
        {"jour": 3, "type": "arret_maladie", "heures_prevues": 0},
        {"jour": 4, "type": "travail", "heures_prevues": 7.0},
    ]

    merged = merge_planned_entries(existing, incoming)
    jour3 = next(e for e in merged if e["jour"] == 3)
    assert jour3["arret_type"] == "maladie_simple"
    assert jour3["subrogation_active"] is True
    assert jour3["nombre_enfants"] == 2


def test_fusion_applique_bien_les_changements_demandes():
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [{"jour": 5, "type": "travail", "heures_prevues": 7.0}]
    incoming = [{"jour": 5, "type": "conge", "heures_prevues": 0}]

    merged = merge_planned_entries(existing, incoming)
    assert merged[0]["type"] == "conge"
    assert merged[0]["heures_prevues"] == 0


def test_fusion_accepte_un_mois_vierge_et_des_jours_nouveaux():
    from app.modules.schedules.domain.rules import merge_planned_entries

    merged = merge_planned_entries([], [{"jour": 1, "type": "travail", "heures_prevues": 7.0}])
    assert merged == [{"jour": 1, "type": "travail", "heures_prevues": 7.0}]


def test_update_planned_calendar_ne_detruit_pas_les_metadonnees(monkeypatch):
    from app.modules.schedules.application import commands
    from app.modules.schedules.schemas.requests import (
        PlannedCalendarEntry,
        PlannedCalendarRequest,
    )

    stocke = {
        "calendrier_prevu": [
            {
                "jour": 3,
                "type": "arret_maladie",
                "heures_prevues": 0,
                "arret_type": "maladie_simple",
                "subrogation_active": True,
            }
        ]
    }
    monkeypatch.setattr(
        commands, "get_employee_company_and_statut", lambda _id: ("comp-1", "Employé")
    )
    monkeypatch.setattr(
        commands.queries, "get_planned_calendar", lambda *a, **k: stocke
    )
    capture = {}

    def fake_upsert(employee_id, company_id, year, month, planned_calendar=None, **kw):
        capture["planned"] = planned_calendar

    monkeypatch.setattr(commands.schedule_repository, "upsert_schedule", fake_upsert)

    payload = PlannedCalendarRequest(
        year=2026,
        month=7,
        calendrier_prevu=[
            PlannedCalendarEntry(jour=3, type="arret_maladie", heures_prevues=0)
        ],
    )
    commands.update_planned_calendar("emp-1", payload)

    jour3 = capture["planned"]["calendrier_prevu"][0]
    assert jour3["arret_type"] == "maladie_simple"
    assert jour3["subrogation_active"] is True


def test_jour_d_absence_porte_son_origine():
    from app.modules.absences.infrastructure.providers import CalendarUpdateProvider

    entry = CalendarUpdateProvider()._day_entry(
        3, "arret_maladie", 0, arret_type="maladie_simple"
    )
    assert entry["origine"] == "absence"


def _semaine_travail_lundi_vendredi(_monday):
    """resolve_week_day_map : lundi→vendredi travaillés 7 h, week-end au repos."""
    return {
        iso: {"type": "travail", "hours": 7.0, "day": iso} for iso in range(1, 6)
    }


def test_regeneration_conserve_un_jour_d_absence_meme_en_overwrite_all():
    from app.modules.schedules.domain import calendar_generation_rules as gen

    existant = [
        {
            "jour": 3,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "arret_type": "maladie_simple",
            "origine": "absence",
        }
    ]
    resultat = gen.build_month_calendrier_prevu(
        2026,
        7,
        _semaine_travail_lundi_vendredi,
        existing_entries=existant,
        overwrite_mode=gen.OVERWRITE_ALL,
    )
    jour3 = next(e for e in resultat if e["jour"] == 3)
    assert jour3["type"] == "arret_maladie"
    assert jour3["arret_type"] == "maladie_simple"


def test_regeneration_ecrase_bien_un_jour_ordinaire():
    """Garde-fou : la protection ne doit pas figer les jours sans origine absence."""
    from app.modules.schedules.domain import calendar_generation_rules as gen

    existant = [{"jour": 3, "type": "repos", "heures_prevues": 0}]
    resultat = gen.build_month_calendrier_prevu(
        2026,
        7,
        _semaine_travail_lundi_vendredi,
        existing_entries=existant,
        overwrite_mode=gen.OVERWRITE_ALL,
    )
    jour3 = next(e for e in resultat if e["jour"] == 3)
    assert jour3["type"] == "travail"
    assert jour3["heures_prevues"] == 7.0
