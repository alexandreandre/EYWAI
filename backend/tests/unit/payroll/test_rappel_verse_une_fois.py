"""Un rappel de salaire déjà versé ne revient pas au bulletin suivant. [G17]

Hausse de 2 000 à 2 100 € au 01/08, août et septembre payés à 2 000 € : le
bulletin d'octobre rappelle 200 €. Le marqueur `rappel_deja_verse` était lu
mais jamais écrit : novembre relisait août et septembre à l'ancienne base (ils
ne sont pas régénérés) et rappelait encore 200 €, décembre aussi.

Désormais chaque bulletin qui verse un rappel garde ce qu'il a versé pour
chaque mois (`parametres.rappel_salaire_par_mois`) ; un mois compte comme payé
de sa base et des rappels déjà versés pour lui par un autre bulletin. Le
libellé porte des dates françaises.
"""

from __future__ import annotations

import pytest

from app.modules.employees.domain.salary_timeline import calculer_rappel_mois_anterieurs
from app.modules.payroll.application.salary_evolution_payroll import (
    _rappels_deja_verses,
)
from app.modules.payroll.engine.bulletin import creer_bulletin_final
from app.modules.payroll.engine.salary_evolution_brut import lignes_rappel_salaire

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

HAUSSE = [
    {
        "effective_date": "2026-08-01",
        "ancien_salaire": {"valeur": 2000.0},
        "nouveau_salaire": {"valeur": 2100.0},
    }
]
PAYES_A_L_ANCIENNE_BASE = {(2026, 8): 2000.0, (2026, 9): 2000.0}


def test_octobre_rappelle_aout_et_septembre_mois_par_mois():
    r = calculer_rappel_mois_anterieurs(HAUSSE, 2026, 10, PAYES_A_L_ANCIENNE_BASE)

    assert r["montant"] == pytest.approx(200.0)
    assert r["par_mois"] == {"2026-08": pytest.approx(100.0), "2026-09": pytest.approx(100.0)}


def test_novembre_ne_rappelle_pas_ce_qu_octobre_a_verse():
    bases = {**PAYES_A_L_ANCIENNE_BASE, (2026, 10): 2100.0}
    r = calculer_rappel_mois_anterieurs(
        HAUSSE,
        2026,
        11,
        bases,
        rappels_deja_verses={(2026, 8): 100.0, (2026, 9): 100.0},
    )

    assert r["montant"] == 0.0
    assert r["par_mois"] == {}


def test_un_rappel_partiel_deja_verse_laisse_le_reste():
    r = calculer_rappel_mois_anterieurs(
        HAUSSE, 2026, 10, PAYES_A_L_ANCIENNE_BASE, rappels_deja_verses={(2026, 8): 60.0}
    )

    assert r["montant"] == pytest.approx(140.0)


def test_les_rappels_deja_verses_se_lisent_sur_les_autres_bulletins():
    lignes = [
        {"year": 2026, "month": 10, "parametres": {"rappel_salaire_par_mois": {"2026-08": 100.0, "2026-09": 100.0}}},
        {"year": 2026, "month": 9, "parametres": {"salaire_base_mensuel": 2000.0}},
        # Le bulletin recalculé ne compte pas ce qu'il a lui-même versé.
        {"year": 2026, "month": 11, "parametres": {"rappel_salaire_par_mois": {"2026-08": 5.0}}},
    ]

    assert _rappels_deja_verses(lignes, 2026, 11) == {(2026, 8): 100.0, (2026, 9): 100.0}


def test_le_bulletin_garde_ce_qu_il_a_rappele_pour_chaque_mois():
    ctx = build_test_contexte(salaire_base=2100.0)
    ctx.contrat["remuneration"]["evolution_salaire_mois"] = {
        "salaire_debut_mois": 2100.0,
        "salaire_fin_mois": 2100.0,
        "prorata": None,
        "rappel": {
            "montant": 200.0,
            "periode_debut": "2026-08-01",
            "periode_fin": "2026-09-30",
            "par_mois": {"2026-08": 100.0, "2026-09": 100.0},
        },
    }
    bulletin = creer_bulletin_final(
        ctx, 2300.0, [], [], {"net_a_payer": 1800.0}, [], 2026, 10
    )

    assert bulletin["parametres"]["rappel_salaire_par_mois"] == {
        "2026-08": 100.0,
        "2026-09": 100.0,
    }


def test_sans_rappel_le_bulletin_ne_porte_pas_la_cle():
    ctx = build_test_contexte(salaire_base=2100.0)
    bulletin = creer_bulletin_final(ctx, 2100.0, [], [], {"net_a_payer": 1650.0}, [], 2026, 10)

    assert "rappel_salaire_par_mois" not in bulletin["parametres"]


def test_le_libelle_porte_des_dates_francaises():
    ctx = build_test_contexte(salaire_base=2100.0)
    ctx.contrat["remuneration"]["evolution_salaire_mois"] = {
        "rappel": {"montant": 200.0, "periode_debut": "2026-08-01", "periode_fin": "2026-09-30"},
    }

    (ligne,) = lignes_rappel_salaire(ctx)

    assert ligne["libelle"] == "Rappel de salaire (période du 01/08/2026 au 30/09/2026)"
