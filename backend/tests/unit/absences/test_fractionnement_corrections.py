"""Fractionnement CP — corrections des défauts relevés au point #19.

Quatre défauts, indépendants de tout arbitrage métier :

1. le barème ne couvre pas la bande ]5 ; 6[ jours ouvrables, si bien qu'un
   reliquat plus élevé peut ouvrir moins de droits ;
2. la méthode légale annule le droit dès que 12 jours continus ont été posés,
   alors que l'article L3141-23 en fait la condition d'ouverture du droit sur
   le reliquat pris hors période ;
3. la méthode légale compare un plafond exprimé en jours ouvrables au nombre de
   jours saisis, quel que soit le décompte de la société ;
4. le préremplissage du report au 1ᵉʳ juin lit le même solde que celui du
   31 octobre : la soustraction s'annule et le calcul rend toujours zéro.
"""

from __future__ import annotations

import pytest

from app.modules.absences.domain.fractionnement import (
    FractionnementMbcInput,
    compute_fractionnement_days_mbc,
)
from app.modules.absences.domain.fractionnement_legal import (
    FractionnementLegalInput,
    compute_fractionnement_legal,
)


def _mbc_days_for_ouvrables(ouvrables: float) -> int:
    """Nombre de jours accordés pour un solde exprimé en jours ouvrables."""
    ratio = 1.2
    return compute_fractionnement_days_mbc(
        FractionnementMbcInput(
            solde_cp_n1_ouvres=ouvrables / ratio,
            cp_reported_june_ouvres=0,
            cp_seniority_deduction_ouvres=0,
            fifth_week_deduction_ouvres=0,
            ouvres_to_ouvrables_ratio=ratio,
        )
    ).days_granted


# --- 1. barème ---------------------------------------------------------------


def test_bareme_couvre_la_bande_entre_cinq_et_six_ouvrables():
    """5,4 ouvrables ouvre droit à 1 jour, comme 5,0 — pas à zéro."""
    assert _mbc_days_for_ouvrables(5.4) == 1


@pytest.mark.parametrize(
    "ouvrables,attendu",
    [
        (0.0, 0),
        (2.99, 0),
        (3.0, 1),
        (5.0, 1),
        (5.9, 1),
        (6.0, 2),
        (12.0, 2),
    ],
)
def test_bareme_seuils(ouvrables, attendu):
    assert _mbc_days_for_ouvrables(ouvrables) == attendu


def test_bareme_est_monotone():
    """Un reliquat plus élevé n'ouvre jamais moins de droits."""
    precedent = 0
    for dixiemes in range(0, 121):
        courant = _mbc_days_for_ouvrables(dixiemes / 10)
        assert courant >= precedent, f"recul du barème à {dixiemes / 10} ouvrables"
        precedent = courant


# --- 2. les 12 jours continus ------------------------------------------------


def _demande(jours: list[str]) -> list[dict]:
    return [{"type": "conge_paye", "status": "validated", "selected_days": jours}]


def test_douze_jours_continus_ouvrent_le_droit_sur_le_reliquat():
    """
    12 jours ouvrables continus posés en période : le reliquat de 12 jours,
    pris hors période, ouvre droit à 2 jours (L3141-23).
    """
    jours = [f"2026-07-{d:02d}" for d in range(1, 13)]
    result = compute_fractionnement_legal(
        FractionnementLegalInput(validated_requests=_demande(jours), grant_year=2026)
    )
    assert result.days_granted == 2


def test_conge_principal_entierement_pose_en_periode_ne_donne_rien():
    """24 jours ouvrables posés entre mai et octobre : aucun reliquat."""
    jours = [f"2026-07-{d:02d}" for d in range(1, 25)]
    result = compute_fractionnement_legal(
        FractionnementLegalInput(validated_requests=_demande(jours), grant_year=2026)
    )
    assert result.days_granted == 0


# --- 3. unité de décompte ----------------------------------------------------


def test_conge_principal_complet_en_ouvres_ne_donne_aucun_jour():
    """
    Une société qui décompte en jours ouvrés pose 20 jours pour le congé
    principal complet : il ne reste rien à fractionner.
    """
    jours = [f"2026-07-{d:02d}" for d in range(1, 21)]
    result = compute_fractionnement_legal(
        FractionnementLegalInput(
            validated_requests=_demande(jours),
            grant_year=2026,
            cp_unit="ouvres",
        )
    )
    assert result.days_granted == 0


def test_decompte_en_ouvres_reliquat_partiel():
    """10 ouvrés posés sur 20 : reliquat 10 ouvrés = 12 ouvrables → 2 jours."""
    jours = [f"2026-07-{d:02d}" for d in range(1, 11)]
    result = compute_fractionnement_legal(
        FractionnementLegalInput(
            validated_requests=_demande(jours),
            grant_year=2026,
            cp_unit="ouvres",
        )
    )
    assert result.solde_ouvrables == pytest.approx(12.0)
    assert result.days_granted == 2


# --- 4. préremplissage du report au 1ᵉʳ juin ---------------------------------


def test_report_juin_non_preremplii_par_defaut(monkeypatch):
    """
    Sans saisie RH, le report du 1ᵉʳ juin vaut zéro : le déduire du solde du
    31 octobre reviendrait à soustraire ce même solde de lui-même.
    """
    from app.modules.absences.application import fractionnement_prefill as prefill

    monkeypatch.setattr(
        prefill.frac_repo, "get_fractionnement_input", lambda *a, **k: None
    )
    monkeypatch.setattr(
        prefill.cp_repo, "get_cp_seniority_grant", lambda *a, **k: None
    )

    resolved = prefill.resolve_fractionnement_inputs(
        "company-1", "employee-1", 2026, ratio=1.2, cp_unit="ouvres"
    )

    assert resolved["cp_reported_june_ouvres"] == 0.0
    assert resolved["auto_report_june_ouvres"] == 0.0
    assert resolved["prefill_source"]["report_june"] == "saisie_requise"


def test_report_juin_saisi_par_les_rh_est_conserve(monkeypatch):
    from app.modules.absences.application import fractionnement_prefill as prefill

    monkeypatch.setattr(
        prefill.frac_repo,
        "get_fractionnement_input",
        lambda *a, **k: {
            "cp_reported_june_ouvres": 28.0,
            "report_june_manual_override": True,
            "seniority_manual_override": False,
        },
    )
    monkeypatch.setattr(
        prefill.cp_repo, "get_cp_seniority_grant", lambda *a, **k: None
    )

    resolved = prefill.resolve_fractionnement_inputs(
        "company-1", "employee-1", 2026, ratio=1.2, cp_unit="ouvres"
    )

    assert resolved["cp_reported_june_ouvres"] == 28.0
    assert resolved["prefill_source"]["report_june"] == "manual"


# --- 5. méthode manuelle : la saisie doit remonter jusqu'à l'écran ----------


def test_previsualisation_expose_le_solde_saisi_a_la_main():
    """
    La méthode « Manuelle » lit `manual_solde_ouvrables`. Sans ce champ dans la
    prévisualisation, l'écran ne peut ni l'afficher ni le modifier, et la
    méthode rend zéro pour tout le monde.
    """
    from unittest.mock import patch

    from app.modules.absences.application import fractionnement_queries as fq

    with patch.object(
        fq,
        "get_fractionnement_settings",
        return_value={
            "fractionnement_enabled": True,
            "cp_unit": "ouvres",
            "ouvres_to_ouvrables_ratio": 1.2,
            "fifth_week_deduction_ouvres": 5.0,
            "calculation_method": "manual",
        },
    ), patch.object(
        fq.supabase,
        "table",
        return_value=_FakeEmployeeTable(),
    ), patch.object(
        fq, "is_forfait_jour", return_value=False
    ), patch.object(
        fq, "_solde_cp_n1_ouvres_at_date", return_value=0.0
    ), patch.object(
        fq,
        "resolve_fractionnement_inputs",
        return_value={
            "cp_reported_june_ouvres": 0.0,
            "cp_seniority_deduction_ouvres": 0.0,
            "auto_report_june_ouvres": 0.0,
            "auto_seniority_deduction_ouvres": 0.0,
            "report_june_manual_override": False,
            "seniority_manual_override": False,
            "prefill_source": {"report_june": "saisie_requise", "seniority": "auto"},
        },
    ), patch.object(
        fq.frac_repo,
        "get_fractionnement_input",
        return_value={"manual_solde_ouvrables": 7.5},
    ):
        row = fq.compute_fractionnement_for_employee("emp-1", "comp-1", 2026)

    assert row is not None
    assert row["manual_solde_ouvrables"] == 7.5
    assert row["days_granted"] == 2


class _FakeEmployeeTable:
    """Minimum de surface PostgREST pour la lecture d'un salarié."""

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
                    "statut": "employe",
                    "is_forfait_jour": False,
                    "first_name": "Test",
                    "last_name": "Salarié",
                }
            ]

        return _Resp()
