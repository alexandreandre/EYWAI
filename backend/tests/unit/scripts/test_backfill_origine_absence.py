"""Script de reprise du marqueur `origine="absence"` — parties pures.

Aucun accès réseau : les lectures sont injectées via de faux clients.
"""

import json

from scripts import backfill_origine_absence as script


class TestMarquage:
    def test_marque_les_jours_d_absence_sans_origine(self):
        calendrier = [
            {"jour": 3, "type": "arret_maladie", "heures_prevues": 0},
            {"jour": 4, "type": "travail", "heures_prevues": 7.0},
        ]
        marque, jours = script.mark_entries(calendrier, {3, 4})
        assert jours == [3]
        assert marque[0]["origine"] == "absence"
        assert "origine" not in marque[1]

    def test_idempotent(self):
        calendrier = [
            {"jour": 3, "type": "conge", "heures_prevues": 0, "origine": "absence"}
        ]
        _, jours = script.mark_entries(calendrier, {3})
        assert jours == []


class TestAbsencesPerdues:
    """Les salariés déjà lésés : absence validée, planning d'un autre type."""

    def test_signale_un_jour_d_absence_devenu_travaille(self):
        calendrier = [
            {"jour": 3, "type": "travail", "heures_prevues": 7.0},
            {"jour": 4, "type": "conge", "heures_prevues": 0},
        ]
        perdues = script.absences_perdues(calendrier, {3, 4})
        assert perdues == [
            {"jour": 3, "type_planning": "travail", "categorie": "absence_perdue"}
        ]

    def test_signale_un_jour_absent_du_planning(self):
        perdues = script.absences_perdues(
            [{"jour": 4, "type": "conge", "heures_prevues": 0}], {3, 4}
        )
        assert perdues == [
            {"jour": 3, "type_planning": None, "categorie": "absence_perdue"}
        ]

    def test_rien_a_signaler_quand_tout_concorde(self):
        calendrier = [{"jour": 3, "type": "arret_maladie", "heures_prevues": 0}]
        assert script.absences_perdues(calendrier, {3}) == []


class _FakeQuery:
    """Mime le chaînage postgrest, en enregistrant les `range` demandés."""

    def __init__(self, table, rows, appels):
        self._table = table
        self._rows = rows
        self._appels = appels
        self._filtres = {}

    def select(self, *_a, **_k):
        return self

    def eq(self, colonne, valeur):
        self._filtres[colonne] = valeur
        return self

    def in_(self, colonne, valeurs):
        self._filtres[colonne] = list(valeurs)
        return self

    def order(self, *_a, **_k):
        return self

    def range(self, debut, fin):
        self._plage = (debut, fin)
        return self

    def execute(self):
        rows = self._rows
        for colonne, valeur in self._filtres.items():
            if isinstance(valeur, list):
                rows = [r for r in rows if r.get(colonne) in valeur]
            else:
                rows = [r for r in rows if r.get(colonne) == valeur]
        debut, fin = self._plage
        self._appels.append((self._table, self._filtres.copy(), debut, fin))
        return type("R", (), {"data": rows[debut : fin + 1]})()


class _FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.appels = []

    def table(self, nom):
        return _FakeQuery(nom, self.tables.get(nom, []), self.appels)


class TestPagination:
    def test_les_lectures_sont_paginees(self):
        """PostgREST tronque silencieusement à 1000 lignes."""
        employes = [
            {"id": f"e{i}", "company_id": "c1", "first_name": "A", "last_name": "B"}
            for i in range(2500)
        ]
        fake = _FakeSupabase({"employees": employes})
        rows = script.fetch_employees(fake)
        assert len(rows) == 2500
        plages = [(d, f) for (t, _, d, f) in fake.appels if t == "employees"]
        assert plages == [(0, 999), (1000, 1999), (2000, 2999)]

    def test_le_filtre_societe_est_pousse_dans_la_requete(self):
        employes = [
            {"id": "e1", "company_id": "c1"},
            {"id": "e2", "company_id": "c2"},
        ]
        fake = _FakeSupabase({"employees": employes})
        rows = script.fetch_employees(fake, company_id="c2")
        assert [r["id"] for r in rows] == ["e2"]
        filtres = [f for (t, f, _d, _fin) in fake.appels if t == "employees"]
        assert filtres[0].get("company_id") == "c2"

    def test_les_absences_validees_sont_paginees_et_filtrees(self):
        absences = [
            {
                "id": f"a{i}",
                "employee_id": "e1",
                "status": "validated",
                "selected_days": ["2026-07-03"],
            }
            for i in range(1200)
        ] + [{"id": "x", "employee_id": "e1", "status": "pending", "selected_days": []}]
        fake = _FakeSupabase({"absence_requests": absences})
        rows = script.fetch_validated_absences(fake, ["e1"])
        assert len(rows) == 1200
        assert all(r["status"] == "validated" for r in rows)


class TestRevert:
    def test_la_sauvegarde_porte_le_calendrier_d_avant(self, tmp_path):
        changements = [
            {
                "employee_id": "e1",
                "year": 2026,
                "month": 7,
                "jours": [3],
                "planned_calendar": {"calendrier_prevu": [{"jour": 3}]},
                "planned_calendar_avant": {"calendrier_prevu": []},
            }
        ]
        chemin = tmp_path / "backup.json"
        script.write_backup(chemin, changements)
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
        assert contenu[0]["planned_calendar_avant"] == {"calendrier_prevu": []}

    def test_revert_restaure_le_calendrier_d_avant(self, tmp_path):
        chemin = tmp_path / "backup.json"
        chemin.write_text(
            json.dumps(
                [
                    {
                        "employee_id": "e1",
                        "year": 2026,
                        "month": 7,
                        "planned_calendar_avant": {
                            "calendrier_prevu": [{"jour": 3, "type": "conge"}]
                        },
                    }
                ]
            ),
            encoding="utf-8",
        )
        ecrits = []
        script.do_revert(
            chemin,
            write_planned_calendar=lambda eid, y, m, cal: ecrits.append(
                (eid, y, m, cal)
            ),
        )
        assert ecrits == [
            ("e1", 2026, 7, {"calendrier_prevu": [{"jour": 3, "type": "conge"}]})
        ]

    def test_revert_refuse_une_sauvegarde_sans_calendrier_d_avant(self, tmp_path):
        chemin = tmp_path / "vieux.json"
        chemin.write_text(
            json.dumps([{"employee_id": "e1", "year": 2026, "month": 7}]),
            encoding="utf-8",
        )
        ecrits = []
        code = script.do_revert(
            chemin,
            write_planned_calendar=lambda *a: ecrits.append(a),
        )
        assert code != 0
        assert ecrits == []
