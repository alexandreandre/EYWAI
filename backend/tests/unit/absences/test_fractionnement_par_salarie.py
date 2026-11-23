"""Fractionnement : case par salarié (arbitrages du 23/11).

Un salarié peut renoncer par écrit à ses jours de fractionnement (cas d'un salarié
de Mont Blanc). La RH décoche sa case : aucun jour calculé, aucun jour validé,
rien au bulletin de novembre ; il reste listé pour pouvoir être recoché.
"""

from __future__ import annotations

from unittest.mock import patch

from app.modules.absences.application import fractionnement_queries as fq

SETTINGS = {
    "fractionnement_enabled": True,
    "cp_unit": "ouvres",
    "ouvres_to_ouvrables_ratio": 1.2,
    "fifth_week_deduction_ouvres": 5.0,
    "calculation_method": "manual",
    "exclude_forfait_jours": True,
}


class _Table:
    """Faux `supabase.table(...)` : renvoie toujours les mêmes lignes, note les mises à jour."""

    def __init__(self, data):
        self.data = data
        self.updates = []

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def in_(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def update(self, row):
        self.updates.append(row)
        return self

    def execute(self):
        table = self

        class _Resp:
            data = table.data

        return _Resp()


def _salarie(actif):
    row = {"id": "emp-1", "statut": "non_cadre", "is_forfait_jour": False, "first_name": "A", "last_name": "B"}
    if actif is not None:
        row["cp_fractionnement_actif"] = actif
    return row


def _calcul(actif):
    with patch.object(fq, "get_fractionnement_settings", return_value=SETTINGS), patch.object(
        fq.supabase, "table", return_value=_Table([_salarie(actif)])
    ), patch.object(fq, "_solde_cp_n1_ouvres_at_date", return_value=0.0), patch.object(
        fq, "resolve_fractionnement_inputs",
        return_value={"cp_reported_june_ouvres": 0.0, "cp_seniority_deduction_ouvres": 0.0},
    ), patch.object(fq.frac_repo, "get_fractionnement_input", return_value={"manual_solde_ouvrables": 6.0}):
        return fq.compute_fractionnement_for_employee("emp-1", "comp-1", 2026)


def test_un_salarie_decoche_n_a_aucun_jour():
    assert _calcul(False) is None


def test_coche_par_defaut_y_compris_sans_la_colonne():
    assert _calcul(True)["days_granted"] == 2
    assert _calcul(None)["days_granted"] == 2


def test_le_decoche_reste_liste_a_zero_pour_etre_recoche():
    with patch.object(fq.supabase, "table", return_value=_Table([_salarie(False)])):
        rows = fq.list_fractionnement_preview("comp-1", 2026)
    assert [(r["employee_id"], r["actif"], r["days_granted"]) for r in rows] == [("emp-1", False, 0)]


def test_valider_tout_saute_le_decoche():
    ecrits = []
    with patch.object(fq, "list_fractionnement_preview", return_value=[
        {"employee_id": "emp-1", "actif": False, "days_granted": 0},
        {"employee_id": "emp-2", "actif": True, "days_granted": 2, "calculation_snapshot": {}},
    ]), patch.object(fq.frac_repo, "upsert_fractionnement_grant", side_effect=lambda *a, **k: ecrits.append(a[1])):
        res = fq.validate_fractionnement_grants("comp-1", 2026)
    assert ecrits == ["emp-2"]
    assert res["validated_count"] == 1


def test_un_droit_deja_valide_ne_sort_pas_au_bulletin_si_decoche():
    soldes = {"conges_payes": {"acquis": 25.0, "solde": 10.0}}
    with patch.object(fq, "get_fractionnement_settings", return_value=SETTINGS), patch.object(
        fq.frac_repo, "get_fractionnement_grant", return_value={"status": "validated", "days_granted": 2}
    ), patch.object(fq.supabase, "table", return_value=_Table([{"cp_fractionnement_actif": False}])):
        res = fq.apply_fractionnement_to_payslip_balances("emp-1", "comp-1", 2026, 11, dict(soldes))
    assert res["conges_payes"]["solde"] == 10.0
    assert "fractionnement" not in res


def test_cocher_ecrit_la_case_du_salarie():
    table = _Table([])
    with patch.object(fq.supabase, "table", return_value=table):
        assert fq.set_fractionnement_actif("comp-1", "emp-1", False) == {"employee_id": "emp-1", "actif": False}
    assert table.updates == [{"cp_fractionnement_actif": False}]
