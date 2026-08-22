"""Lot 4 Task 4 : les heures badgées vivent en Europe/Paris.

Les timestamps stockés sont corrects (timestamptz) ; le bug était
l'arithmétique murale sans conversion : un badge de 8 h à Paris l'été,
stocké 06:00 UTC, était lu comme 6 h → 2 h de fausses HS « entrée en
avance », et les nuits se coupaient à la date UTC.
"""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch


def test_en_heure_locale_convertit_l_ete_et_l_hiver():
    from app.shared.domain.temps_local import en_heure_locale

    ete = datetime(2026, 7, 3, 6, 0, tzinfo=timezone.utc)
    assert (en_heure_locale(ete).hour, en_heure_locale(ete).minute) == (8, 0)
    hiver = datetime(2026, 1, 15, 7, 30, tzinfo=timezone.utc)
    assert (en_heure_locale(hiver).hour, en_heure_locale(hiver).minute) == (8, 30)


def test_un_timestamp_naif_est_traite_comme_utc():
    """Héritage : d'anciens now() naïfs sur horloge UTC existent en base."""
    from app.shared.domain.temps_local import en_heure_locale

    naif = datetime(2026, 7, 3, 6, 0)
    assert en_heure_locale(naif).hour == 8


def test_first_last_punch_minutes_en_heure_murale_paris():
    from app.modules.schedules.application import badgeuse_import as mod
    from app.modules.badgeuse.domain.time_tracking import TimeEntryType

    def entree(h, m, t):
        e = MagicMock()
        e.timestamp = datetime(2026, 7, 3, h, m, tzinfo=timezone.utc)
        e.event_type = t
        return e

    entries = [
        entree(6, 0, TimeEntryType.ENTREE),   # 08:00 Paris
        entree(14, 30, TimeEntryType.SORTIE), # 16:30 Paris
    ]
    with patch.object(
        mod.time_entry_repository, "get_entries_for_employee_on_day",
        return_value=entries,
    ):
        entry_min, exit_min = mod._first_last_punch_minutes(
            "emp-1", "comp-1", date(2026, 7, 3)
        )
    assert entry_min == 8 * 60
    assert exit_min == 16 * 60 + 30


def test_les_nuits_se_groupent_sur_le_jour_local():
    """22:30 UTC = 00:30 Paris le lendemain : le badge appartient au jour
    local, pas à la date UTC."""
    from app.modules.badgeuse.domain.time_tracking import (
        TimeEntryType,
        group_entries_by_day,
    )

    e = MagicMock()
    e.timestamp = datetime(2026, 7, 3, 22, 30, tzinfo=timezone.utc)
    e.event_type = TimeEntryType.ENTREE
    groupes = group_entries_by_day([e])
    assert list(groupes.keys()) == [date(2026, 7, 4)]


def test_la_fenetre_du_jour_couvre_le_jour_local():
    """La requête du « jour » doit couvrir minuit→minuit PARIS, exprimé en
    UTC — pas minuit→minuit UTC (qui rate les badges de 22h-minuit UTC
    de la veille locale)."""
    from app.modules.badgeuse.infrastructure.repository import TimeEntryRepository

    repo = TimeEntryRepository()
    capture = {}

    def fake_between(employee_id, company_id, start, end):
        capture["start"], capture["end"] = start, end
        return []

    with patch.object(repo, "get_entries_for_employee_between", fake_between):
        repo.get_entries_for_employee_on_day("emp-1", "comp-1", date(2026, 7, 3))
    # 3 juillet Paris = [02:00 UTC le 3... non : minuit Paris = 22:00 UTC la veille
    assert capture["start"].astimezone(timezone.utc).hour == 22
    assert capture["start"].astimezone(timezone.utc).day == 2
    assert capture["end"].astimezone(timezone.utc).hour == 21  # 23:59 Paris


def test_l_horodatage_par_defaut_est_aware_utc():
    """Le chemin sans `now` fourni doit produire un instant aware — le
    lint a attrapé un import manquant que les tests ne couvraient pas."""
    from app.modules.badgeuse.application import _internals as mod

    inserted = {}
    with patch.object(mod, "time_entry_repository") as fake_repo:
        fake_repo.insert_entry.side_effect = lambda **kw: inserted.update(kw)
        mod._insert_toggle_entry(
            employee_id="emp-1",
            company_id="comp-1",
            entries=[],
            source=list(mod.TimeEntrySource)[0],
            created_by="u-1",
        )
    assert inserted["timestamp"].tzinfo is not None


def test_le_badge_qr_produit_un_instant_aware():
    """F2 — le 2e badge du jour via QR levait TypeError : now() naïf
    soustrait aux timestamps aware de la base."""
    from datetime import datetime, timezone

    from app.modules.badgeuse.application import qr_service as mod

    entree_du_jour = MagicMock()
    entree_du_jour.timestamp = datetime(2026, 7, 3, 6, 0, tzinfo=timezone.utc)
    capture = {}

    fake_deps = MagicMock()
    fake_deps._employee_is_forfait_jour.return_value = False
    fake_deps.resolve_employee_for_qr.return_value = {"id": "emp-1"}
    fake_deps.time_entry_repository.get_entries_for_employee_on_day.return_value = [
        entree_du_jour
    ]

    def fake_toggle(**kw):
        capture.update(kw)
        raise RuntimeError("stop-ici")

    fake_deps._insert_toggle_entry.side_effect = fake_toggle
    with (
        patch.object(mod, "deps", fake_deps),
        patch.object(
            mod, "_resolve_employee_from_qr",
            return_value={"id": "emp-1", "company_id": "comp-1"},
            create=True,
        ),
        patch.object(
            mod, "decode_qr_payload",
            return_value={"employee_id": "emp-1"},
            create=True,
        ),
    ):
        try:
            mod.punch_from_qr(
                qr_payload=None,
                employee_id="emp-1",
                company_id="comp-1",
                actor_user_id="u-1",
            )
        except (RuntimeError, ValueError, KeyError, AttributeError):
            pass
        except TypeError as exc:
            raise AssertionError(f"TypeError aware/naïf: {exc}")
    if "now" in capture and capture["now"] is not None:
        assert capture["now"].tzinfo is not None


def test_le_jour_de_reponse_suit_l_instant_badge_en_local():
    """Un badge à 22:30 UTC appartient au lendemain Paris : la relecture du
    jour doit interroger le jour LOCAL, pas la date UTC."""
    from datetime import datetime, timezone

    from app.modules.badgeuse.application import _internals as mod

    capture = {}
    with patch.object(mod, "time_entry_repository") as fake_repo:
        fake_repo.get_entries_for_employee_on_day.side_effect = (
            lambda **kw: capture.update(kw) or []
        )
        try:
            mod._build_punch_response(
                employee_id="emp-1",
                company_id="comp-1",
                employee_row={"first_name": "A", "last_name": "B"},
                event_type=list(mod.TimeEntryType)[0],
                punched_at=datetime(2026, 7, 3, 22, 30, tzinfo=timezone.utc),
            )
        except (KeyError, AttributeError, TypeError):
            pass  # l'aval est moqué grossièrement ; seul `day` nous importe
    from datetime import date

    assert capture["day"] == date(2026, 7, 4)


def test_la_saisie_rh_d_un_badge_est_en_heure_murale():
    """C3 — « 08:00 » saisi par la RH doit rester 08:00 Paris à la relecture,
    pas devenir 10:00 (naïf stocké comme UTC)."""
    import inspect

    from app.modules.badgeuse.api import router as mod

    src = inspect.getsource(mod)
    assert "tzinfo=FUSEAU_ENTREPRISE" in src
    # plus aucune construction naïve de timestamp de badge
    assert "datetime.combine(day, datetime.min.time()).replace" not in src
