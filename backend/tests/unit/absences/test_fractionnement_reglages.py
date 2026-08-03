"""Réglages du fractionnement : méthode par défaut, exclusions, effets de bord.

La méthode « MBC » était le calcul par défaut des sept sociétés alors qu'elle
reproduit le tableur d'une seule d'entre elles et exige une saisie manuelle. La
méthode légale, elle, se calcule à partir des congés réellement posés.

L'exclusion des cadres au forfait-jours était figée dans le code : c'est un
usage d'entreprise, donc un réglage.

Enfin, générer un bulletin de novembre créait une ligne de droit en base. Un
affichage ne doit rien écrire — sinon un nombre faux devient durable sans que
personne ne l'ait décidé.
"""

from __future__ import annotations

from unittest.mock import patch

from app.modules.absences.infrastructure.fractionnement_repository import (
    get_fractionnement_settings_row,
)


# --- méthode par défaut ------------------------------------------------------


def test_la_methode_legale_est_le_defaut_dune_societe_non_parametree():
    with patch(
        "app.modules.absences.infrastructure.fractionnement_repository.supabase"
    ) as fake:
        fake.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        row = get_fractionnement_settings_row("comp-1")
    assert row["calculation_method"] == "legal"
    assert row["fractionnement_enabled"] is False


# --- exclusion des cadres au forfait ----------------------------------------


def test_les_cadres_au_forfait_sont_exclus_par_defaut():
    with patch(
        "app.modules.absences.infrastructure.fractionnement_repository.supabase"
    ) as fake:
        fake.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        row = get_fractionnement_settings_row("comp-1")
    assert row["exclude_forfait_jours"] is True


def test_lexclusion_des_cadres_au_forfait_est_desactivable():
    from app.modules.absences.application import fractionnement_queries as fq

    settings = {
        "fractionnement_enabled": True,
        "cp_unit": "ouvres",
        "ouvres_to_ouvrables_ratio": 1.2,
        "fifth_week_deduction_ouvres": 5.0,
        "calculation_method": "manual",
        "exclude_forfait_jours": False,
    }
    with patch.object(fq, "get_fractionnement_settings", return_value=settings), patch.object(
        fq.supabase, "table", return_value=_FakeForfaitEmployee()
    ), patch.object(fq, "_solde_cp_n1_ouvres_at_date", return_value=0.0), patch.object(
        fq, "resolve_fractionnement_inputs", return_value=_INPUTS
    ), patch.object(
        fq.frac_repo, "get_fractionnement_input", return_value={"manual_solde_ouvrables": 6.0}
    ):
        row = fq.compute_fractionnement_for_employee("emp-1", "comp-1", 2026)

    assert row is not None, "un cadre au forfait doit être pris en compte si l'exclusion est levée"
    assert row["days_granted"] == 2


def test_le_cadre_au_forfait_reste_exclu_quand_le_reglage_est_actif():
    from app.modules.absences.application import fractionnement_queries as fq

    settings = {
        "fractionnement_enabled": True,
        "cp_unit": "ouvres",
        "ouvres_to_ouvrables_ratio": 1.2,
        "fifth_week_deduction_ouvres": 5.0,
        "calculation_method": "manual",
        "exclude_forfait_jours": True,
    }
    with patch.object(fq, "get_fractionnement_settings", return_value=settings), patch.object(
        fq.supabase, "table", return_value=_FakeForfaitEmployee()
    ):
        assert fq.compute_fractionnement_for_employee("emp-1", "comp-1", 2026) is None


# --- le bulletin n'écrit plus ------------------------------------------------


def test_le_bulletin_de_novembre_naccorde_rien_de_lui_meme():
    """Sans droit validé par les RH, le bulletin n'affiche ni ne crée de jour."""
    from app.modules.absences.application import fractionnement_queries as fq

    balances = {"conges_payes": {"acquis": 25.0, "solde": 10.0}}
    with patch.object(
        fq, "get_fractionnement_settings", return_value={"fractionnement_enabled": True}
    ), patch.object(
        fq.frac_repo, "get_fractionnement_grant", return_value=None
    ), patch.object(
        fq.frac_repo, "upsert_fractionnement_grant"
    ) as upsert:
        result = fq.apply_fractionnement_to_payslip_balances(
            "emp-1", "comp-1", 2026, 11, balances
        )

    upsert.assert_not_called()
    assert result["conges_payes"]["solde"] == 10.0
    assert "fractionnement" not in result


def test_le_bulletin_de_novembre_credite_un_droit_valide():
    from app.modules.absences.application import fractionnement_queries as fq

    balances = {"conges_payes": {"acquis": 25.0, "solde": 10.0}}
    grant = {
        "days_granted": 2,
        "status": "validated",
        "validated_at": "2026-10-31T00:00:00+00:00",
        "calculation_snapshot": {"source": "fractionnement_legal"},
    }
    with patch.object(
        fq, "get_fractionnement_settings", return_value={"fractionnement_enabled": True}
    ), patch.object(
        fq.frac_repo, "get_fractionnement_grant", return_value=grant
    ), patch.object(
        fq.frac_repo, "upsert_fractionnement_grant"
    ) as upsert:
        result = fq.apply_fractionnement_to_payslip_balances(
            "emp-1", "comp-1", 2026, 11, balances
        )

    upsert.assert_not_called()
    assert result["conges_payes"]["acquis"] == 27.0
    assert result["conges_payes"]["solde"] == 12.0
    assert result["fractionnement"]["jours_acquis"] == 2


def test_un_droit_seulement_calcule_nest_pas_credite():
    """Un aperçu non validé ne doit pas se retrouver sur un bulletin."""
    from app.modules.absences.application import fractionnement_queries as fq

    balances = {"conges_payes": {"acquis": 25.0, "solde": 10.0}}
    grant = {"days_granted": 2, "status": "computed", "calculation_snapshot": {}}
    with patch.object(
        fq, "get_fractionnement_settings", return_value={"fractionnement_enabled": True}
    ), patch.object(fq.frac_repo, "get_fractionnement_grant", return_value=grant):
        result = fq.apply_fractionnement_to_payslip_balances(
            "emp-1", "comp-1", 2026, 11, balances
        )

    assert result["conges_payes"]["solde"] == 10.0
    assert "fractionnement" not in result


_INPUTS = {
    "cp_reported_june_ouvres": 0.0,
    "cp_seniority_deduction_ouvres": 0.0,
    "auto_report_june_ouvres": 0.0,
    "auto_seniority_deduction_ouvres": 0.0,
    "report_june_manual_override": False,
    "seniority_manual_override": False,
    "prefill_source": {"report_june": "saisie_requise", "seniority": "auto"},
}


class _FakeForfaitEmployee:
    """Un cadre au forfait-jours."""

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        class _Resp:
            data = [
                {
                    "id": "emp-1",
                    "statut": "cadre",
                    "is_forfait_jour": True,
                    "first_name": "Test",
                    "last_name": "Cadre",
                }
            ]

        return _Resp()
