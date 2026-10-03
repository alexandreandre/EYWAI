"""Fusion paramètres paie entreprise à l'import DSN."""

from unittest.mock import MagicMock, patch

import pytest

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


# ----- Effectif saisi à l'écran « Paramètres de paie » -----
#
# Le bon chiffre est l'effectif moyen de l'année précédente, que seule la
# gestionnaire connaît ; la DSN ne porte que l'effectif de fin de mois. Une
# fois saisi à l'écran, un ré-import DSN ne doit jamais le remplacer, ni
# effacer les réglages de paie rangés dans settings.


@pytest.mark.parametrize("saisi", [19, 0])
def test_un_effectif_deja_renseigne_n_est_jamais_ecrase_par_la_dsn(saisi):
    merged = apply_payroll_merge({"effectif": 23, "taux_at_mp": 3.15}, {"effectif": saisi})
    assert "effectif" not in merged


def test_un_effectif_vide_est_rempli_par_la_dsn():
    merged = apply_payroll_merge({"effectif": 23}, {"effectif": None, "taux_at_mp": 3.1})
    assert merged["effectif"] == 23


def test_le_reimport_dsn_ne_touche_ni_l_effectif_ni_les_reglages_de_paie():
    from app.modules.dsn_import.application import commit

    existante = {
        "id": "cccccccc-5555-5555-5555-555555555555",
        "siret": "00000000000017",
        "effectif": 19,
        "taux_at_mp": 3.1,
        "paie_jour_de_fin": 4,
        "paie_occurrence": -2,
        "settings": {
            "taux_assurance_chomage": 2.95,
            "date_paiement": "dernier_jour_du_mois",
            "jour_solidarite": "2026-05-25",
            "dsn_import": {"organismes": []},
        },
    }
    payload = {
        "siret": "00000000000017",
        "company_name": "Société test",
        "effectif": 23,
        "taux_at_mp": 3.15,
        "dsn_organismes": [{"code": "X"}],
    }
    client = MagicMock()
    with patch.object(commit.repo, "find_company_by_siret", return_value=existante), patch.object(
        commit, "get_supabase_admin_client", return_value=client
    ):
        commit._commit_establishment(payload, None, "update", existante)

    ecritures = [c.args[0] for c in client.table.return_value.update.call_args_list]
    assert ecritures, "le ré-import doit au moins suivre le taux AT/MP"
    assert all("effectif" not in e for e in ecritures)
    reglages = [e["settings"] for e in ecritures if "settings" in e]
    assert reglages, "les organismes DSN passent par settings : la fusion doit être vérifiée"
    for settings in reglages:
        assert settings["taux_assurance_chomage"] == 2.95
        assert settings["date_paiement"] == "dernier_jour_du_mois"
        assert settings["jour_solidarite"] == "2026-05-25"
