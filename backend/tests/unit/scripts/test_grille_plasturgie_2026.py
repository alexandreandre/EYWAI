"""La grille des minima de la plasturgie suit l'accord du 19 février 2026 (art. 3.1, Légifrance
KALIARTI000054177244), pas les montants plus bas de la règle extraite en base."""

from __future__ import annotations

import pytest

from scripts.grille_plasturgie_2026 import DATE_EFFET, GRILLE_2026, grille_corrigee

pytestmark = pytest.mark.unit

#: Les montants de la règle en base le 26/10/2026, sous le titre et la date de l'accord.
EN_BASE = [(700, 1730), (710, 1741), (720, 1760), (730, 1811), (740, 1891), (750, 2008), (800, 2143),
           (810, 2295), (820, 2515), (830, 2697), (900, 3221), (910, 3375), (920, 3879), (930, 5044),
           (940, 6290)]


def _regles():
    minima = [{"valeur": float(v), "coefficient": float(c)} for c, v in EN_BASE]
    return {"salaires_minima": minima,
            "grilles_salaires": [
                {"minima": [dict(m) for m in minima], "date_effet": DATE_EFFET,
                 "source_titre": "Accord du 19 février 2026 relatif aux salaires", "zone_type": "national"},
                {"minima": [{"valeur": 1700.0, "coefficient": 700.0}], "date_effet": "2025-03-01",
                 "source_titre": "Accord de 2025", "zone_type": "national"},
            ]}


def test_la_grille_de_l_accord_du_19_fevrier_2026():
    assert GRILLE_2026[900] == 3366.0 and GRILLE_2026[700] == 1835.0 and GRILLE_2026[940] == 6543.0
    assert len(GRILLE_2026) == 15


def test_les_montants_faux_de_la_base_sont_remplaces_dans_les_deux_listes():
    corrigees, ecarts = grille_corrigee(_regles())
    assert {int(m["coefficient"]): m["valeur"] for m in corrigees["salaires_minima"]} == GRILLE_2026
    accord = corrigees["grilles_salaires"][0]
    assert {int(m["coefficient"]): m["valeur"] for m in accord["minima"]} == GRILLE_2026
    assert len(ecarts) == 30   # 15 coefficients, dans les deux listes
    assert "coefficient 900 : 3221.00 → 3366.00" in ecarts


def test_une_autre_grille_n_est_pas_touchee_et_une_grille_juste_ne_bouge_plus():
    corrigees, _ = grille_corrigee(_regles())
    assert corrigees["grilles_salaires"][1]["minima"] == [{"valeur": 1700.0, "coefficient": 700.0}]
    assert grille_corrigee(corrigees)[1] == []
