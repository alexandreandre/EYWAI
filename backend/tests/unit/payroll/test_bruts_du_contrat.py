"""La rémunération d'un contrat pour le dossier de départ (estimation).

Base de la prime de fin de contrat : la rémunération totale brute versée
durant le contrat (L1243-8 ; service-public F40). Le bulletin du mois de sortie
porte déjà les indemnités de départ : le dossier estime ce mois au salaire,
jamais à son bulletin. Rien n'est lu avant l'entrée ni après la sortie
(L1242-16 : « pendant la durée de son contrat »).

Cas d'origine : CDD du 29/06 au 30/09/2026 à 3 000 €, bulletin de septembre de
l'ancien logiciel à 5 782,59 € (prime, congés et repos du forfait compris).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.reference_remuneration import (
    bruts_du_contrat,
    lire_bruts_periode_reference,
)

pytestmark = pytest.mark.unit


class _Requete:
    def __init__(self, bulletins, illisibles):
        self._bulletins = bulletins
        self._illisibles = illisibles
        self._mois = None

    def select(self, *_a, **_k):
        return self

    def match(self, filtre):
        self._mois = (filtre["year"], filtre["month"])
        return self

    def is_(self, *_a, **_k):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if self._mois in self._illisibles:
            raise RuntimeError("lecture impossible")
        brut = self._bulletins.get(self._mois)
        return type("R", (), {"data": None if brut is None else {"payslip_data": {"salaire_brut": brut}}})()


class _Base:
    def __init__(self, bulletins, illisibles=()):
        self._bulletins = bulletins
        self._illisibles = set(illisibles)
        self.mois_lus: list[tuple[int, int]] = []

    def table(self, nom):
        assert nom == "payslips"
        base = self

        class _Suivie(_Requete):
            def match(self, filtre):
                base.mois_lus.append((filtre["year"], filtre["month"]))
                return super().match(filtre)

        return _Suivie(self._bulletins, self._illisibles)


BULLETINS = {(2026, 6): 272.73, (2026, 7): 3000.0, (2026, 8): 3000.0, (2026, 9): 5782.59}


def test_le_mois_de_sortie_est_estime_au_salaire_jamais_lu_sur_son_bulletin():
    base = _Base(BULLETINS)

    total, mois_lus, alertes = bruts_du_contrat(
        "emp-1", date(2026, 6, 29), date(2026, 9, 30), base, salaire=3000.0, estimer_le_dernier_mois=True
    )

    assert total == 9272.73
    assert mois_lus == 3
    assert (2026, 9) not in base.mois_lus
    assert alertes == []


def test_un_mois_sans_bulletin_vaut_le_salaire_au_prorata_des_jours_sous_contrat_et_le_dossier_le_dit():
    bulletins = {k: v for k, v in BULLETINS.items() if k != (2026, 6)}

    total, _, alertes = bruts_du_contrat(
        "emp-1", date(2026, 6, 29), date(2026, 8, 31), _Base(bulletins), salaire=3000.0, estimer_le_dernier_mois=False
    )

    assert total == 6200.0  # 2/30 × 3 000 + 3 000 + 3 000
    assert alertes == ["Bulletin 06/2026 absent — salaire du contrat utilisé."]


def test_un_bulletin_illisible_n_est_pas_dit_absent():
    _, _, alertes = bruts_du_contrat(
        "emp-1",
        date(2026, 6, 29),
        date(2026, 8, 31),
        _Base(BULLETINS, illisibles=[(2026, 7)]),
        salaire=3000.0,
        estimer_le_dernier_mois=False,
    )

    assert alertes == ["Bulletin 07/2026 illisible — salaire du contrat utilisé."]


def test_le_repli_du_dossier_s_arrete_a_la_sortie_et_part_de_l_entree():
    base = _Base(BULLETINS)

    ref = lire_bruts_periode_reference(
        "emp-1",
        date(2026, 6, 30),
        base,
        salaire_contractuel_fallback=3000.0,
        entree=date(2026, 6, 29),
        sortie=date(2026, 6, 30),
    )

    assert ref.base_totale == 200.0  # juin estimé : 2/30 × 3 000, rien après
    assert base.mois_lus == []
    assert not any("2027" in a or "07/2026" in a for a in ref.alertes)


def test_un_contrat_d_un_seul_mois_estime_ne_dit_pas_qu_il_manque_des_bulletins():
    from app.modules.payroll.engine.reference_remuneration import lire_brut_total_contrat

    total, alertes = lire_brut_total_contrat(
        "emp-1",
        date(2026, 6, 29),
        date(2026, 6, 30),
        _Base(BULLETINS),
        salaire_contractuel_fallback=3000.0,
        estimer_le_mois_de_sortie=True,
    )

    assert total == 200.0
    assert alertes == []


def test_un_mois_de_sortie_sans_salaire_connu_le_dit():
    total, _, alertes = bruts_du_contrat(
        "emp-1", date(2026, 9, 1), date(2026, 9, 30), _Base({}), salaire=0.0, estimer_le_dernier_mois=True
    )

    assert total == 0.0
    assert alertes == ["Mois de sortie 09/2026 non estimé — salaire du contrat inconnu."]
