"""R-085 : un bulletin repris de l'ancien logiciel ne sert pas de référence de comparaison.

Le net à payer d'un bulletin repris est celui de l'ancien logiciel, souvent après acompte : le
comparer à un net calculé déclencherait à tort l'alerte « net à payer » (critique, elle bloque
la validation). Tant qu'il était en brouillon, il n'était pas lu ; une fois validé il le serait
sans ce filtre. Simulation sur octobre à blanc : 180 bulletins sur 247 bloqués à tort.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.payslips.infrastructure import comparison_queries as cq


def _chaine_avec_lignes(lignes):
    """Une requête qui retient chaque filtre posé et rend `lignes` à l'exécution."""
    table = MagicMock()
    table.select.return_value = table
    for nom in ("eq", "neq", "or_", "order", "limit"):
        getattr(table, nom).return_value = table
    table.execute.return_value = MagicMock(data=lignes)
    return table


def _filtres(table):
    return [c.args for c in table.neq.call_args_list]


def test_le_mois_precedent_ne_lit_pas_un_bulletin_repris():
    table = _chaine_avec_lignes([])
    with patch.object(cq, "supabase") as base:
        base.table.return_value = table
        assert cq.fetch_previous_validated_payslip("e", "c", 2026, 10) is None
    assert ("origine", "importe") in _filtres(table)


def test_les_nets_des_mois_d_avant_ne_lisent_pas_un_bulletin_repris():
    table = _chaine_avec_lignes([])
    with patch.object(cq, "supabase") as base:
        base.table.return_value = table
        assert cq.fetch_validated_payslips_strictly_before("e", "c", 2026, 10, 3) == []
    assert ("origine", "importe") in _filtres(table)
