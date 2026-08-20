"""Le planning ne doit jamais amputer ni écraser les métadonnées d'absence."""


def test_entree_calendrier_refuse_les_cles_serveur_du_payload():
    """Les métadonnées d'absence n'entrent jamais par le schéma d'API.

    Elles pilotent le maintien de salaire et les IJSS : un porteur de
    `schedules.update` ne doit pas pouvoir les injecter sans passer par la
    validation d'absence.
    """
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
    assert dumped == {"jour": 3, "type": "arret_maladie", "heures_prevues": 0.0}


def test_fusion_ignore_les_cles_serveur_injectees_par_le_payload():
    """« Copier le mois précédent » rejoue arret_type sur un mois sans arrêt."""
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [{"jour": 3, "type": "travail", "heures_prevues": 7.0}]
    incoming = [
        {
            "jour": 3,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "arret_type": "maladie_simple",
            "subrogation_active": True,
            "origine": "absence",
        }
    ]

    merged = merge_planned_entries(existing, incoming)
    assert merged[0]["type"] == "arret_maladie"
    assert "arret_type" not in merged[0]
    assert "subrogation_active" not in merged[0]
    assert "origine" not in merged[0]


def test_fusion_ne_laisse_pas_le_payload_reecrire_une_cle_serveur():
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [
        {
            "jour": 3,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "arret_type": "maladie_simple",
            "subrogation_active": True,
        }
    ]
    incoming = [
        {
            "jour": 3,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "arret_type": "accident_travail",
            "subrogation_active": False,
        }
    ]

    merged = merge_planned_entries(existing, incoming)
    assert merged[0]["arret_type"] == "maladie_simple"
    assert merged[0]["subrogation_active"] is True


def test_fusion_purge_les_cles_serveur_quand_le_jour_redevient_travaille():
    """Sinon le jour reste gelé à vie contre les régénérations, sans recours UI."""
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [
        {
            "jour": 3,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "origine": "absence",
            "arret_type": "maladie_simple",
            "subrogation_active": True,
            "nombre_enfants": 2,
            "historique_arrets_annee": [{"debut": "2026-01-05"}],
            "date_debut_arret_reel": "2026-07-01",
            "salaire_periode_reelle": 1800.0,
        }
    ]
    incoming = [{"jour": 3, "type": "travail", "heures_prevues": 7.0}]

    merged = merge_planned_entries(existing, incoming)
    assert merged[0]["type"] == "travail"
    assert merged[0]["heures_prevues"] == 7.0
    for cle in (
        "origine",
        "arret_type",
        "subrogation_active",
        "nombre_enfants",
        "historique_arrets_annee",
        "date_debut_arret_reel",
        "salaire_periode_reelle",
    ):
        assert cle not in merged[0]


def test_fusion_conserve_les_cles_serveur_entre_deux_types_d_absence():
    """Garde-fou : la purge ne doit pas frapper un jour resté en absence."""
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [
        {
            "jour": 3,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "origine": "absence",
            "arret_type": "maladie_simple",
        }
    ]
    merged = merge_planned_entries(
        existing, [{"jour": 3, "type": "arret_maladie", "heures_prevues": 0}]
    )
    assert merged[0]["origine"] == "absence"
    assert merged[0]["arret_type"] == "maladie_simple"


def test_les_cles_serveur_sont_definies_a_un_seul_endroit():
    from app.shared.domain.absence_calendar import SERVER_OWNED_ABSENCE_KEYS

    assert SERVER_OWNED_ABSENCE_KEYS == frozenset(
        {
            "origine",
            "arret_type",
            "subrogation_active",
            "nombre_enfants",
            "historique_arrets_annee",
            "date_debut_arret_reel",
            "salaire_periode_reelle",
        }
    )


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


def test_update_planned_calendar_refuse_d_ecrire_si_la_relecture_echoue(monkeypatch):
    """Une panne de lecture ne doit pas se solder par un écrasement en HTTP 200.

    Un mois inexistant renvoie `{"calendrier_prevu": []}` sans lever :
    l'exception ne survient donc que sur une vraie panne — précisément le cas
    où il ne faut surtout pas remplacer le mois par le payload appauvri.
    """
    import pytest

    from app.modules.schedules.application import commands
    from app.modules.schedules.application.exceptions import ScheduleAppError
    from app.modules.schedules.schemas.requests import (
        PlannedCalendarEntry,
        PlannedCalendarRequest,
    )

    monkeypatch.setattr(
        commands, "get_employee_company_and_statut", lambda _id: ("comp-1", "Employé")
    )

    def _lecture_en_panne(*_a, **_k):
        raise RuntimeError("PostgREST indisponible")

    monkeypatch.setattr(commands.queries, "get_planned_calendar", _lecture_en_panne)

    appels = []
    monkeypatch.setattr(
        commands.schedule_repository,
        "upsert_schedule",
        lambda *a, **k: appels.append(a),
    )

    payload = PlannedCalendarRequest(
        year=2026,
        month=7,
        calendrier_prevu=[
            PlannedCalendarEntry(jour=3, type="travail", heures_prevues=7.0)
        ],
    )
    with pytest.raises(ScheduleAppError) as exc:
        commands.update_planned_calendar("emp-1", payload)

    assert exc.value.status_code == 503
    assert appels == []


def _provider_avec_calendrier(monkeypatch, calendrier_existant):
    """
    Monte un CalendarUpdateProvider sur un faux Supabase, et rend la fonction
    qui capture le calendrier finalement écrit.

    `calendrier_existant=None` simule un mois pas encore planifié (branche de
    repli), sinon la branche nominale (mois déjà en base) — c'est cette
    seconde branche qui traite la quasi-totalité des validations réelles.
    """
    from unittest.mock import MagicMock

    from app.modules.absences.infrastructure import providers as mod

    capture = {}
    emp = MagicMock()
    emp.data = {"company_id": "comp-1", "duree_hebdomadaire": 35}
    schedule = MagicMock()
    schedule.data = (
        {"planned_calendar": {"calendrier_prevu": calendrier_existant}}
        if calendrier_existant is not None
        else None
    )

    def table(nom):
        t = MagicMock()
        if nom == "employees":
            t.select.return_value.match.return_value.maybe_single.return_value.execute.return_value = emp
        else:
            t.select.return_value.match.return_value.maybe_single.return_value.execute.return_value = schedule

            def _insert(payload):
                capture["ecrit"] = payload["planned_calendar"]["calendrier_prevu"]
                return MagicMock()

            def _update(payload):
                capture["ecrit"] = payload["planned_calendar"]["calendrier_prevu"]
                return MagicMock()

            t.insert.side_effect = _insert
            t.update.side_effect = _update
        return t

    fake = MagicMock()
    fake.table.side_effect = table
    monkeypatch.setattr(mod, "supabase", fake)
    return mod.CalendarUpdateProvider(), capture


def test_validation_absence_marque_l_origine_sur_un_mois_deja_planifie(monkeypatch):
    """Branche nominale : c'est elle qui traite presque toutes les validations."""
    from datetime import date

    existant = [
        {"jour": j, "type": "travail", "heures_prevues": 7.0} for j in range(1, 6)
    ]
    provider, capture = _provider_avec_calendrier(monkeypatch, existant)

    provider.update_calendar_from_days(
        "emp-1", [date(2026, 7, 3)], "arret_maladie", arret_type="maladie_simple"
    )

    jour3 = next(e for e in capture["ecrit"] if e["jour"] == 3)
    assert jour3["type"] == "arret_maladie"
    assert jour3["origine"] == "absence"
    assert jour3["arret_type"] == "maladie_simple"


def test_les_jours_de_remplissage_ne_sont_pas_marques(monkeypatch):
    """Mois non planifié : seuls les jours de l'absence portent le marqueur.

    Sinon le mois entier deviendrait immunisé contre toute régénération.
    """
    from datetime import date

    provider, capture = _provider_avec_calendrier(monkeypatch, None)

    provider.update_calendar_from_days(
        "emp-1", [date(2026, 7, 3)], "arret_maladie", arret_type="maladie_simple"
    )

    marques = [e for e in capture["ecrit"] if e.get("origine") == "absence"]
    assert [e["jour"] for e in marques] == [3]
    assert len(capture["ecrit"]) == 31


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
