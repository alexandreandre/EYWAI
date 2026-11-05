"""Le Smic de la contribution OETH : celui du 31 décembre de l'année due (guide Urssaf, p. 26)."""

from unittest.mock import MagicMock, patch

from app.modules.oeth_settings.domain.rules import smic_au_31_decembre
from app.modules.oeth_settings.infrastructure import headcount_service

BAREME = {
    "annee": 2026,
    "cas_general": 12.31,
    "smic_horaire_brut": 12.31,
    "historique": [
        {"date_debut": "2026-01-01", "cas_general": 12.02},
        {"date_debut": "2026-06-01", "cas_general": 12.31},
    ],
}


def test_2025_garde_le_smic_du_guide():
    assert smic_au_31_decembre(BAREME, 2025) == 11.88


def test_2026_prend_le_dernier_palier_de_l_annee():
    assert smic_au_31_decembre(BAREME, 2026) == 12.31


def test_un_palier_de_l_annee_suivante_ne_compte_pas():
    bareme = {
        **BAREME,
        "historique": BAREME["historique"] + [{"date_debut": "2027-01-01", "cas_general": 12.60}],
    }
    assert smic_au_31_decembre(bareme, 2026) == 12.31


def test_un_palier_du_31_decembre_compte():
    bareme = {"historique": [{"date_debut": "2026-12-31", "cas_general": 12.50}]}
    assert smic_au_31_decembre(bareme, 2026) == 12.50


def test_sans_historique_la_valeur_de_l_annee_du_bareme():
    assert smic_au_31_decembre({"annee": 2026, "smic_horaire_brut": 12.31}, 2026) == 12.31


def test_sans_historique_une_autre_annee_garde_le_repli():
    assert smic_au_31_decembre({"annee": 2026, "smic_horaire_brut": 12.31}, 2025) == 11.88


def test_bareme_vide_garde_le_repli():
    assert smic_au_31_decembre({}, 2025) == 11.88
    assert smic_au_31_decembre({}, 2024) == 11.65


def test_palier_illisible_ignore():
    bareme = {"historique": [{"date_debut": "n'importe", "cas_general": 99}, {"cas_general": 98}]}
    assert smic_au_31_decembre(bareme, 2025) == 11.88


def test_load_smic_horaire_lit_le_bareme_actif():
    table = MagicMock()
    table.select.return_value.eq.return_value.eq.return_value.is_.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data={"config_data": BAREME}
    )
    with patch.object(headcount_service, "supabase") as base:
        base.table.return_value = table
        assert headcount_service.load_smic_horaire(2025) == 11.88
        assert headcount_service.load_smic_horaire(2026) == 12.31
