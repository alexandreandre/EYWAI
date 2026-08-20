"""Tests unitaires — persistance batch import pointages."""

from app.modules.schedules.application.persist_timesheet import persist_timesheet_batch
from app.modules.schedules.schemas.ai import AiDayEntry
from app.modules.schedules.schemas.persist import PersistTimesheetEmployee, PersistTimesheetRequest


class TestPersistTimesheetBatch:
    def test_merges_days_per_employee(self):
        planned_store: dict[str, list] = {"e1": [{"jour": 1, "type": "travail", "heures_prevues": 8}]}
        actual_store: dict[str, list] = {}

        def get_planned(eid, y, m):
            return list(planned_store.get(eid, []))

        def get_actual(eid, y, m):
            return list(actual_store.get(eid, []))

        def update_planned(eid, y, m, rows):
            planned_store[eid] = rows

        def update_actual(eid, y, m, rows):
            actual_store[eid] = rows

        payload = PersistTimesheetRequest(
            year=2026,
            month=5,
            employees=[
                PersistTimesheetEmployee(
                    employee_id="e1",
                    days=[
                        AiDayEntry(jour=26, heures=7.0, type="travail", nature="reel"),
                        AiDayEntry(jour=27, heures=7.0, type="travail", nature="prevu"),
                    ],
                )
            ],
        )
        result = persist_timesheet_batch(
            payload,
            get_planned=get_planned,
            get_actual=get_actual,
            update_planned=update_planned,
            update_actual=update_actual,
        )
        assert result.total_days_written == 2
        assert result.results[0].success is True
        assert any(d["jour"] == 26 for d in actual_store["e1"])
        assert any(d["jour"] == 27 for d in planned_store["e1"])
        assert any(d["jour"] == 1 for d in planned_store["e1"])


def _arret_valide(jour: int) -> dict:
    return {
        "jour": jour,
        "type": "arret_maladie",
        "heures_prevues": 0,
        "origine": "absence",
        "arret_type": "maladie_simple",
        "subrogation_active": True,
    }


class TestImportPointagesEtAbsences:
    """L'import de pointages est le chemin destructeur le plus utilisé.

    Il appelle `_merge_days` en direct, sans passer par
    `update_planned_calendar` : il reconstruisait chaque jour à trois clés,
    effaçant `arret_type` — plus aucun maintien calculé, bulletin faux.
    """

    def _run(self, existing_planned, jours_prevus):
        from app.modules.schedules.application.persist_timesheet import (
            persist_timesheet_batch,
        )
        from app.modules.schedules.schemas.ai import AiDayEntry
        from app.modules.schedules.schemas.persist import (
            PersistTimesheetEmployee,
            PersistTimesheetRequest,
        )

        planned_store = {"e1": list(existing_planned)}
        payload = PersistTimesheetRequest(
            year=2026,
            month=7,
            employees=[
                PersistTimesheetEmployee(
                    employee_id="e1",
                    days=[
                        AiDayEntry(nature="prevu", **jour) for jour in jours_prevus
                    ],
                )
            ],
        )
        result = persist_timesheet_batch(
            payload,
            get_planned=lambda eid, y, m: list(planned_store.get(eid, [])),
            get_actual=lambda eid, y, m: [],
            update_planned=lambda eid, y, m, rows: planned_store.__setitem__(eid, rows),
            update_actual=lambda eid, y, m, rows: None,
        )
        return result, planned_store["e1"]

    def test_un_releve_d_heures_n_ecrase_pas_un_arret_valide(self):
        result, planned = self._run(
            [_arret_valide(3), {"jour": 4, "type": "travail", "heures_prevues": 7.0}],
            [{"jour": 3, "heures": 7.0, "type": "travail"}],
        )
        jour3 = next(d for d in planned if d["jour"] == 3)
        assert jour3["type"] == "arret_maladie"
        assert jour3["arret_type"] == "maladie_simple"
        assert jour3["subrogation_active"] is True

    def test_le_refus_est_signale_dans_les_warnings_du_batch(self):
        result, _ = self._run(
            [_arret_valide(3)],
            [{"jour": 3, "heures": 7.0, "type": "travail"}],
        )
        assert result.results[0].success is True
        assert len(result.warnings) == 1
        assert result.warnings[0]["employee_id"] == "e1"
        assert result.warnings[0]["jour"] == 3

    def test_les_autres_jours_du_releve_sont_bien_appliques(self):
        _, planned = self._run(
            [_arret_valide(3), {"jour": 4, "type": "travail", "heures_prevues": 7.0}],
            [
                {"jour": 3, "heures": 7.0, "type": "travail"},
                {"jour": 4, "heures": 8.5, "type": "travail"},
            ],
        )
        assert next(d for d in planned if d["jour"] == 4)["heures_prevues"] == 8.5

    def test_un_jour_ordinaire_reste_modifiable_par_l_import(self):
        """Garde-fou : la protection ne doit pas bloquer l'import courant."""
        _, planned = self._run(
            [{"jour": 4, "type": "travail", "heures_prevues": 7.0}],
            [{"jour": 4, "heures": 0.0, "type": "repos"}],
        )
        jour4 = next(d for d in planned if d["jour"] == 4)
        assert jour4["type"] == "repos"
        assert jour4["heures_prevues"] == 0.0
