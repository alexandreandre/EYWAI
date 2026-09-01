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


def test_fusion_conserve_les_jours_stockes_absents_du_payload():
    """Un payload partiel ne doit pas faire disparaître le reste du mois."""
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [
        {"jour": 1, "type": "travail", "heures_prevues": 7.0},
        {
            "jour": 3,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "origine": "absence",
            "arret_type": "maladie_simple",
        },
        {"jour": 4, "type": "travail", "heures_prevues": 7.0},
    ]
    incoming = [{"jour": 4, "type": "conge", "heures_prevues": 0}]

    merged = merge_planned_entries(existing, incoming)
    assert [e["jour"] for e in merged] == [1, 3, 4]
    jour3 = next(e for e in merged if e["jour"] == 3)
    assert jour3["arret_type"] == "maladie_simple"
    assert next(e for e in merged if e["jour"] == 4)["type"] == "conge"


def test_fusion_trie_les_jours():
    from app.modules.schedules.domain.rules import merge_planned_entries

    merged = merge_planned_entries(
        [{"jour": 10, "type": "travail", "heures_prevues": 7.0}],
        [
            {"jour": 5, "type": "travail", "heures_prevues": 7.0},
            {"jour": 2, "type": "travail", "heures_prevues": 7.0},
        ],
    )
    assert [e["jour"] for e in merged] == [2, 5, 10]


def test_fusion_normalise_les_jours_en_chaine():
    """Des `jour` en chaîne existent en base — la fusion doit les rapprocher.

    `calendar_generation_rules.build_month_calendrier_prevu` s'en défend déjà
    explicitement (int(e.get("jour")) sous try/except).
    """
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [
        {
            "jour": "3",
            "type": "arret_maladie",
            "heures_prevues": 0,
            "origine": "absence",
            "arret_type": "maladie_simple",
        }
    ]
    incoming = [{"jour": 3, "type": "arret_maladie", "heures_prevues": 0}]

    merged = merge_planned_entries(existing, incoming)
    assert len(merged) == 1
    assert merged[0]["jour"] == 3
    assert merged[0]["arret_type"] == "maladie_simple"


def test_fusion_ignore_une_entree_inexploitable_sans_perdre_le_mois():
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [{"jour": 1, "type": "travail", "heures_prevues": 7.0}]
    incoming = [
        {"type": "travail", "heures_prevues": 7.0},  # pas de jour
        {"jour": "n/a", "type": "travail"},  # jour illisible
        "pas un dict",
        {"jour": 2, "type": "conge", "heures_prevues": 0},
    ]

    merged = merge_planned_entries(existing, incoming)
    assert [e["jour"] for e in merged] == [1, 2]


def test_fusion_supporte_des_jours_melanges_int_et_chaine():
    """Le tri ne doit pas exploser sur un mois mi-int mi-chaîne."""
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [
        {"jour": "10", "type": "travail", "heures_prevues": 7.0},
        {"jour": 2, "type": "travail", "heures_prevues": 7.0},
    ]
    merged = merge_planned_entries(
        existing, [{"jour": 5, "type": "travail", "heures_prevues": 7.0}]
    )
    assert [e["jour"] for e in merged] == [2, 5, 10]


def test_le_schema_borne_le_jour_du_mois():
    import pytest
    from pydantic import ValidationError

    from app.modules.schedules.schemas.requests import PlannedCalendarEntry

    for jour_invalide in (0, 32, -1):
        with pytest.raises(ValidationError):
            PlannedCalendarEntry(jour=jour_invalide, type="travail")


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
            "date_fin_arret_reel",
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


def test_validation_arret_ne_retype_jamais_les_jours_non_travailles(monkeypatch):
    """ANTI-RÉGRESSION PAIE : un jour `arret_maladie` à 0 h est déduit comme un
    jour PLEIN par calcul_brut (repli durée contractuelle) — les week-ends,
    repos et fériés d'un arrêt ne doivent donc JAMAIS être retypés. Les vraies
    bornes calendaires passent par date_debut/date_fin_arret_reel."""
    from datetime import date

    existant = [
        {"jour": 14, "type": "travail", "heures_prevues": 7.0},
        {"jour": 15, "type": "weekend", "heures_prevues": 0},
        {"jour": 16, "type": "repos", "heures_prevues": 0},
        {"jour": 17, "type": "ferie", "heures_prevues": 0},
    ]
    provider, capture = _provider_avec_calendrier(monkeypatch, existant)

    provider.update_calendar_from_days(
        "emp-1",
        [date(2026, 8, j) for j in (14, 15, 16, 17)],
        "arret_maladie",
        arret_type="maladie_simple",
    )

    jour14 = next(e for e in capture["ecrit"] if e["jour"] == 14)
    assert jour14["type"] == "arret_maladie"
    assert jour14["origine"] == "absence"
    # Les bornes réelles de la période (week-end de fin compris) sont portées
    # par le jour converti, pour le moteur maintien/IJSS/prévoyance.
    assert jour14["date_debut_arret_reel"] == "2026-08-14"
    assert jour14["date_fin_arret_reel"] == "2026-08-17"
    for jour, type_attendu in ((15, "weekend"), (16, "repos"), (17, "ferie")):
        entree = next(e for e in capture["ecrit"] if e["jour"] == jour)
        assert entree["type"] == type_attendu, f"jour {jour}"
        assert "origine" not in entree
        assert entree["date_debut_arret_reel"] == "2026-08-14"
        assert entree["date_fin_arret_reel"] == "2026-08-17"
        assert entree["arret_type"] == "maladie_simple"


def test_reprojection_rafraichit_les_jours_deja_en_arret(monkeypatch):
    """Script de reprise / prolongation : un jour déjà typé arret_maladie voit
    ses métadonnées (bornes, subrogation, historique) rafraîchies — sinon un
    même arrêt porterait des métadonnées incohérentes selon le jour lu."""
    from datetime import date

    existant = [
        {
            "jour": 14,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "origine": "absence",
            "arret_type": "maladie_simple",
            "subrogation_active": True,
        },
    ]
    provider, capture = _provider_avec_calendrier(monkeypatch, existant)

    provider.update_calendar_from_days(
        "emp-1",
        [date(2026, 8, 14), date(2026, 8, 15), date(2026, 8, 16)],
        "arret_maladie",
        arret_type="maladie_simple",
        subrogation_active=False,
    )

    jour14 = next(e for e in capture["ecrit"] if e["jour"] == 14)
    assert jour14["type"] == "arret_maladie"
    assert jour14["subrogation_active"] is False
    assert jour14["date_fin_arret_reel"] == "2026-08-16"


def test_mois_non_planifie_remplit_les_week_ends_en_weekend(monkeypatch):
    """Branche « mois non planifié » : les jours de remplissage tombant un
    samedi/dimanche sont insérés en `weekend` 0 h (plus jamais `travail` 7 h),
    et un jour d'arrêt tombant le week-end n'est pas typé arret_maladie."""
    from datetime import date

    provider, capture = _provider_avec_calendrier(monkeypatch, None)

    # Arrêt ven. 14/08 → lun. 17/08/2026 sur un mois sans planning.
    provider.update_calendar_from_days(
        "emp-1",
        [date(2026, 8, j) for j in (14, 15, 16, 17)],
        "arret_maladie",
        arret_type="maladie_simple",
    )

    ecrit = {e["jour"]: e for e in capture["ecrit"]}
    assert len(ecrit) == 31
    assert ecrit[14]["type"] == "arret_maladie"
    assert ecrit[14]["date_fin_arret_reel"] == "2026-08-17"
    assert ecrit[17]["type"] == "arret_maladie"
    # 15 et 16 août 2026 = samedi et dimanche : jamais retypés.
    assert ecrit[15]["type"] == "weekend"
    assert ecrit[16]["type"] == "weekend"
    assert ecrit[15]["date_fin_arret_reel"] == "2026-08-17"
    assert ecrit[16]["arret_type"] == "maladie_simple"
    # Remplissage : samedi 1er août en weekend 0 h, lundi 3 août en travail.
    assert ecrit[1]["type"] == "weekend"
    assert ecrit[1]["heures_prevues"] == 0
    assert ecrit[3]["type"] == "travail"


def test_validation_conge_ne_convertit_pas_les_week_ends(monkeypatch):
    """Le déverrouillage calendaire ne vaut que pour les arrêts : un congé payé
    continue de ne se poser que sur des jours de travail planifiés."""
    from datetime import date

    existant = [
        {"jour": 14, "type": "travail", "heures_prevues": 7.0},
        {"jour": 15, "type": "weekend", "heures_prevues": 0},
    ]
    provider, capture = _provider_avec_calendrier(monkeypatch, existant)

    provider.update_calendar_from_days(
        "emp-1", [date(2026, 8, 14), date(2026, 8, 15)], "conge_paye"
    )

    jour14 = next(e for e in capture["ecrit"] if e["jour"] == 14)
    jour15 = next(e for e in capture["ecrit"] if e["jour"] == 15)
    assert jour14["type"] == "conges_payes"
    assert jour15["type"] == "weekend"


def test_validation_arret_ne_requalifie_pas_un_conge_pose(monkeypatch):
    """La requalification congé→arrêt est un sujet séparé (cf.
    dev-lot1-preservation-planning) : un jour déjà en congé reste intact."""
    from datetime import date

    existant = [{"jour": 14, "type": "conges_payes", "heures_prevues": 0}]
    provider, capture = _provider_avec_calendrier(monkeypatch, existant)

    provider.update_calendar_from_days(
        "emp-1", [date(2026, 8, 14)], "arret_maladie", arret_type="maladie_simple"
    )

    assert capture["ecrit"][0]["type"] == "conges_payes"


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


def test_regeneration_ne_gele_pas_un_jour_travaille_mal_marque():
    """Un marqueur `origine` mal posé ne doit pas suffire à figer un jour.

    Les deux conditions comptent : origine == "absence" ET type d'absence.
    """
    from app.modules.schedules.domain import calendar_generation_rules as gen

    existant = [
        {"jour": 3, "type": "travail", "heures_prevues": 0, "origine": "absence"}
    ]
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


def test_regeneration_ne_gele_pas_un_type_d_absence_sans_marqueur():
    """Symétrique : un type d'absence sans `origine` reste régénérable."""
    from app.modules.schedules.domain import calendar_generation_rules as gen

    existant = [{"jour": 3, "type": "conge", "heures_prevues": 0}]
    resultat = gen.build_month_calendrier_prevu(
        2026,
        7,
        _semaine_travail_lundi_vendredi,
        existing_entries=existant,
        overwrite_mode=gen.OVERWRITE_ALL,
    )
    assert next(e for e in resultat if e["jour"] == 3)["type"] == "travail"


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


def test_fusion_mode_preservation_ne_requalifie_pas_une_absence():
    """Écriture de masse (apply-model, copie) : le jour d'absence est gardé tel quel."""
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [
        {
            "jour": 10,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "origine": "absence",
            "arret_type": "maladie_simple",
        }
    ]
    incoming = [{"jour": 10, "type": "travail", "heures_prevues": 7.0}]

    avertissements: list = []
    merged = merge_planned_entries(
        existing, incoming, preserve_absence_days=True, warnings=avertissements
    )
    assert merged[0]["type"] == "arret_maladie"
    assert merged[0]["arret_type"] == "maladie_simple"
    assert avertissements == [
        {
            "jour": 10,
            "code": "absence_validee_preservee",
            "type_avant": "arret_maladie",
            "type_refuse": "travail",
        }
    ]


def test_fusion_mode_edition_signale_la_requalification():
    """Édition délibérée : la requalification passe, mais elle est signalée."""
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [
        {
            "jour": 10,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "origine": "absence",
            "arret_type": "maladie_simple",
        }
    ]
    incoming = [{"jour": 10, "type": "travail", "heures_prevues": 7.0}]

    avertissements: list = []
    merged = merge_planned_entries(existing, incoming, warnings=avertissements)
    assert merged[0]["type"] == "travail"
    assert "arret_type" not in merged[0]
    assert avertissements == [
        {
            "jour": 10,
            "code": "absence_validee_requalifiee",
            "type_avant": "arret_maladie",
            "type_apres": "travail",
        }
    ]


def test_apply_model_preserve_les_absences_validees(monkeypatch):
    """Le bouton « Appliquer un modèle » ne détruit plus un arrêt validé."""
    from types import SimpleNamespace

    from app.modules.schedules.application import commands

    stocke = {
        "calendrier_prevu": [
            {
                "jour": 10,
                "type": "arret_maladie",
                "heures_prevues": 0,
                "origine": "absence",
                "arret_type": "maladie_simple",
                "subrogation_active": True,
            }
        ]
    }
    monkeypatch.setattr(
        commands.employee_company_reader,
        "get_company_and_statut",
        lambda _id: ("comp-1", "Employé"),
    )
    monkeypatch.setattr(
        commands.queries, "get_planned_calendar", lambda *a, **k: stocke
    )
    capture = {}
    monkeypatch.setattr(
        commands.schedule_repository, "exists_schedule", lambda *a, **k: True
    )
    monkeypatch.setattr(
        commands.schedule_repository,
        "update_planned_calendar_only",
        lambda emp, y, m, pc: capture.setdefault("planned", pc),
    )
    monkeypatch.setattr(
        commands.schedule_repository,
        "insert_schedule",
        lambda *a, **k: capture.setdefault("planned", a[4] if len(a) > 4 else k),
    )

    jour_travaille = SimpleNamespace(type="travail", hours=7.0)
    semaine = SimpleNamespace(
        monday=jour_travaille, tuesday=jour_travaille, wednesday=jour_travaille,
        thursday=jour_travaille, friday=jour_travaille,
        saturday=SimpleNamespace(type="repos", hours=0),
        sunday=SimpleNamespace(type="repos", hours=0),
    )
    request = SimpleNamespace(
        year=2026, month=7,
        employee_ids=["emp-1"],
        week_configs={n: semaine for n in range(1, 6)},
    )
    rh = SimpleNamespace(
        active_company_id="comp-1",
        has_rh_access_in_company=lambda _cid: True,
    )
    resultat = commands.apply_schedule_model(request, rh)

    jours = capture["planned"]["calendrier_prevu"]
    jour10 = next(e for e in jours if e["jour"] == 10)
    assert jour10["type"] == "arret_maladie"
    assert jour10["arret_type"] == "maladie_simple"
    # Le reste du mois est bien régénéré
    jour9 = next(e for e in jours if e["jour"] == 9)
    assert jour9["type"] == "travail"
    # Et le refus est signalé à l'appelant
    assert any(
        w.get("code") == "absence_validee_preservee" for w in resultat.get("warnings", [])
    )


def test_type_mapping_absences_reste_couvert_par_les_types_calendrier():
    """Verrou anti-dérive : tout type que la validation d'absence écrit au
    calendrier doit rester connu de ABSENCE_CALENDAR_TYPES, sinon la
    préservation et la purge cessent de le couvrir en silence."""
    from app.shared.domain.absence_calendar import (
        ABSENCE_CALENDAR_TYPES,
        ABSENCE_TYPE_TO_CALENDAR_TYPE,
    )

    types_ecrits = set(ABSENCE_TYPE_TO_CALENDAR_TYPE.values())
    types_ecrits.add("arret_maladie")  # branche IJSS_ELIGIBLE_TYPES
    inconnus = types_ecrits - set(ABSENCE_CALENDAR_TYPES)
    assert not inconnus, f"types écrits au calendrier non couverts : {inconnus}"

    # Et le provider consomme bien la source unique (pas un dict local qui
    # pourrait dériver).
    import inspect

    from app.modules.absences.infrastructure import providers as mod

    source = inspect.getsource(mod.CalendarUpdateProvider.update_calendar_from_days)
    assert "ABSENCE_TYPE_TO_CALENDAR_TYPE" in source


def test_lecture_tolerante_mais_saisie_bornee():
    """Un jour hors bornes stocké reste lisible ; il reste refusé en saisie."""
    import pytest
    from pydantic import ValidationError

    from app.modules.schedules.schemas.requests import (
        PlannedCalendarEntry,
        PlannedCalendarEntryOut,
    )

    # Donnée historique corrompue : la lecture ne doit pas exploser (500 GET)
    assert PlannedCalendarEntryOut(jour=42, type="travail").jour == 42
    # Mais la saisie reste bornée
    with pytest.raises(ValidationError):
        PlannedCalendarEntry(jour=42, type="travail")


def test_le_get_expose_origine_mais_la_saisie_le_refuse_toujours():
    """Le client doit VOIR origine (pour exclure ces jours de ses copies de
    masse) sans jamais pouvoir l'ÉCRIRE."""
    from app.modules.schedules.schemas.requests import (
        PlannedCalendarEntry,
        PlannedCalendarEntryOut,
    )

    lu = PlannedCalendarEntryOut(
        jour=3, type="arret_maladie", heures_prevues=0, origine="absence"
    )
    assert lu.origine == "absence"

    saisi = PlannedCalendarEntry(
        jour=3, type="arret_maladie", heures_prevues=0, origine="absence"
    )
    assert "origine" not in saisi.model_dump()


def test_le_resume_de_batch_conserve_les_refus_de_commit():
    from app.modules.schedules.schemas.timesheet_import import (
        TimesheetImportBatchSummary,
    )

    resume = TimesheetImportBatchSummary(
        committed_days=3,
        commit_warnings=[
            {"employee_id": "e1", "jour": 4, "code": "absence_validee_preservee"}
        ],
    )
    assert resume.model_dump()["commit_warnings"][0]["jour"] == 4


def test_preservation_refuse_aussi_une_requalification_absence_vers_absence():
    """Fermeture collective en jours « Congé » : un arrêt validé ne doit pas
    devenir un CP en silence (maintien/IJSS perdus, CP débités)."""
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [
        {
            "jour": 10,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "origine": "absence",
            "arret_type": "maladie_simple",
            "subrogation_active": True,
        }
    ]
    incoming = [{"jour": 10, "type": "conge", "heures_prevues": 0}]

    avertissements: list = []
    merged = merge_planned_entries(
        existing, incoming, preserve_absence_days=True, warnings=avertissements
    )
    assert merged[0]["type"] == "arret_maladie"
    assert merged[0]["arret_type"] == "maladie_simple"
    assert avertissements == [
        {
            "jour": 10,
            "code": "absence_validee_preservee",
            "type_avant": "arret_maladie",
            "type_refuse": "conge",
        }
    ]


def test_edition_absence_vers_absence_signale_et_purge_les_metadonnees():
    """L'édition délibérée arrêt→congé passe, mais se signale — et les
    métadonnées de l'arrêt ne restent pas orphelines sur un jour de congé."""
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [
        {
            "jour": 10,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "origine": "absence",
            "arret_type": "maladie_simple",
            "subrogation_active": True,
        }
    ]
    incoming = [{"jour": 10, "type": "conge", "heures_prevues": 0}]

    avertissements: list = []
    merged = merge_planned_entries(existing, incoming, warnings=avertissements)
    assert merged[0]["type"] == "conge"
    for cle in ("arret_type", "subrogation_active", "origine"):
        assert cle not in merged[0], cle
    assert avertissements == [
        {
            "jour": 10,
            "code": "absence_validee_requalifiee",
            "type_avant": "arret_maladie",
            "type_apres": "conge",
        }
    ]
