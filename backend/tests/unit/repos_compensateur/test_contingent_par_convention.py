"""Contingent d'heures sup par défaut : celui de la convention, puis 220 h (D3121-24).

Audit du 02/11, n° 6 et 8 : Colorplast, Comitech et Mont Blanc (plasturgie)
étaient comptés à 220 h au lieu des 130 h de l'accord du 17/10/2000 (art. 4.4).
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.repos_compensateur.domain.contingent_rules import (
    contingent_legal_par_defaut,
)
from app.modules.repos_compensateur.infrastructure import settings_repository


@pytest.mark.parametrize("idcc", ["0292", "292", " 292 "])
def test_plasturgie_130_heures(idcc):
    assert contingent_legal_par_defaut(idcc) == 130.0


@pytest.mark.parametrize("idcc", ["3248", None, "", "1486"])
def test_sans_contingent_conventionnel_connu_220_heures(idcc):
    assert contingent_legal_par_defaut(idcc) == 220.0


def _supabase_avec(rows):
    client = MagicMock()
    chaine = client.table.return_value.select.return_value.eq.return_value.limit.return_value
    chaine.execute.return_value = MagicMock(data=rows)
    return client


def _lire(rows, idcc):
    with patch.object(settings_repository, "supabase", _supabase_avec(rows)), patch.object(
        settings_repository, "_idcc_de_la_societe", return_value=idcc
    ):
        return (
            settings_repository.get_contingent_settings("societe-1"),
            settings_repository.get_contingent_settings_row("societe-1"),
        )


def test_societe_sans_reglage_prend_le_contingent_de_sa_convention():
    reglages, ligne = _lire([], "0292")
    assert reglages.legal_cor_contingent_hours == 130.0
    assert ligne["legal_cor_contingent_hours"] == 130.0


def test_reglage_sans_contingent_saisi_prend_celui_de_la_convention():
    reglages, ligne = _lire(
        [{"company_id": "societe-1", "legal_cor_contingent_hours": None}], "0292"
    )
    assert reglages.legal_cor_contingent_hours == 130.0
    assert ligne["legal_cor_contingent_hours"] == 130.0


def test_un_contingent_saisi_reste_celui_de_la_societe():
    reglages, ligne = _lire(
        [{"company_id": "societe-1", "legal_cor_contingent_hours": 220}], "0292"
    )
    assert reglages.legal_cor_contingent_hours == 220.0
    assert ligne["legal_cor_contingent_hours"] == 220


def test_creer_le_reglage_sans_contingent_ecrit_celui_de_la_convention():
    """La colonne a 220 par défaut en base : une ligne créée sans le champ ne doit pas le prendre."""
    client = MagicMock()
    table = client.table.return_value
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    with patch.object(settings_repository, "supabase", client), patch.object(
        settings_repository, "_idcc_de_la_societe", return_value="0292"
    ):
        settings_repository.upsert_contingent_settings(
            "societe-1", {"management_contingent_hours": 360}
        )
    ecrit = table.insert.call_args.args[0]
    assert ecrit["legal_cor_contingent_hours"] == 130.0
    assert ecrit["management_contingent_hours"] == 360
