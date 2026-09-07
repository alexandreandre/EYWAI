"""Fusion paramètres paie entreprise à l'import DSN."""

from app.modules.dsn_import.domain.establishment_extract import (
    apply_payroll_merge,
    compute_payroll_merge_conflicts,
)


def test_apply_payroll_merge_overwrites_at_mp_seulement():
    """AT/MP suit la DSN ; le régime de période (jour_de_fin, occurrence),
    réglé à la main dans l'onglet Entreprise, n'est jamais écrasé — sinon un
    ré-import décalerait la fenêtre d'arrêté des variables (Colorplast (4, -2)
    deviendrait (4, -1) = dernier vendredi, une semaine d'écart)."""
    payload = {
        "taux_at_mp": 3.15,
        "paie_occurrence": -1,
        "paie_jour_de_fin": 31,
    }
    existing = {
        "taux_at_mp": 3.1,
        "paie_occurrence": -2,
        "paie_jour_de_fin": 4,
    }

    merged = apply_payroll_merge(payload, existing)

    assert merged["taux_at_mp"] == 3.15
    assert "paie_occurrence" not in merged
    assert "paie_jour_de_fin" not in merged


def test_apply_payroll_merge_fills_periode_when_empty():
    payload = {"paie_jour_de_fin": 31, "paie_occurrence": -1, "taux_at_mp": 3.15}
    existing = {"taux_at_mp": 3.1}

    merged = apply_payroll_merge(payload, existing)

    assert merged["taux_at_mp"] == 3.15
    assert merged["paie_jour_de_fin"] == 31
    assert merged["paie_occurrence"] == -1


def test_compute_payroll_merge_conflicts_empty():
    payload = {"taux_at_mp": 3.15}
    existing = {"taux_at_mp": 3.1}
    assert compute_payroll_merge_conflicts(payload, existing) == {}
