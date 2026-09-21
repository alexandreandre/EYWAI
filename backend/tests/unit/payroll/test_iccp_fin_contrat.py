"""Indemnité de congés payés de fin de contrat : la règle légale, par période.

Recette : Aurélien Demory, juillet 2026 (spec
2026-09-21-indemnite-cp-fin-de-contrat-legale-design.md) — 306,78 + 459,61 = 766,39.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.iccp_fin_contrat import (
    PeriodeConges,
    indemnite_fin_de_contrat,
    indemnite_par_periode,
    valeur_jour_maintien,
)

N_1 = PeriodeConges(libelle="2025-2026", brut=4171.35, droits=3.78, restants=2.78)
N = PeriodeConges(libelle="2026-2027", brut=4596.09, droits=4.16, restants=4.16)


class TestValeurJourMaintien:
    def test_a_39_h(self):
        assert valeur_jour_maintien(12.31, 39.0, 0.25) == pytest.approx(98.48)

    def test_a_35_h(self):
        assert valeur_jour_maintien(12.31, 35.0, 0.25) == pytest.approx(86.17)


class TestParPeriode:
    def test_periode_precedente_de_demory_au_dixieme(self):
        d = indemnite_par_periode(N_1, taux=0.10, valeur_jour=98.48)
        assert d.dixieme == pytest.approx(306.78)  # 417,14 × 2,78 / 3,78
        assert d.maintien == pytest.approx(273.77)  # 2,78 × 98,48
        assert d.retenu == pytest.approx(306.78) and d.methode == "dixieme"

    def test_periode_en_cours_de_demory(self):
        d = indemnite_par_periode(N, taux=0.10, valeur_jour=98.48)
        assert d.dixieme == pytest.approx(459.61)
        assert d.maintien == pytest.approx(409.68)
        assert d.retenu == pytest.approx(459.61)

    def test_le_maintien_l_emporte_quand_il_est_plus_favorable(self):
        d = indemnite_par_periode(PeriodeConges("x", brut=1000.0, droits=2.0, restants=2.0), taux=0.10, valeur_jour=98.48)
        assert d.retenu == pytest.approx(196.96) and d.methode == "maintien"

    def test_sans_brut_connu_la_periode_se_regle_au_maintien(self):
        d = indemnite_par_periode(PeriodeConges("x", brut=None, droits=3.0, restants=1.0), taux=0.10, valeur_jour=98.48)
        assert d.dixieme is None and d.retenu == pytest.approx(98.48) and d.methode == "maintien_seul"

    def test_sans_droits_connus_pas_de_prorata(self):
        d = indemnite_par_periode(PeriodeConges("x", brut=1000.0, droits=0.0, restants=1.0), taux=0.10, valeur_jour=98.48)
        assert d.dixieme is None and d.methode == "maintien_seul"

    def test_sans_jour_restant_rien(self):
        d = indemnite_par_periode(PeriodeConges("x", brut=1000.0, droits=2.0, restants=0.0), taux=0.10, valeur_jour=98.48)
        assert d.retenu == 0.0


class TestFinDeContrat:
    def test_demory_au_centime(self):
        r = indemnite_fin_de_contrat([N_1, N], taux=0.10, valeur_jour=98.48)
        assert r.total == pytest.approx(766.39)
        assert [p.retenu for p in r.periodes] == pytest.approx([306.78, 459.61])

    def test_les_periodes_sans_reste_ne_comptent_pas(self):
        r = indemnite_fin_de_contrat([PeriodeConges("x", 1000.0, 2.0, 0.0), N], taux=0.10, valeur_jour=98.48)
        assert r.total == pytest.approx(459.61) and len(r.periodes) == 1

    def test_mention(self):
        r = indemnite_fin_de_contrat([N_1, N], taux=0.10, valeur_jour=98.48)
        assert r.mention == (
            "Indemnité de congés payés de fin de contrat : période 2025-2026, 2,78 j restants "
            "sur 3,78 : dixième 306,78 (10 % de 4 171,35 × 2,78/3,78) ou maintien 273,77 "
            "(2,78 j × 98,48) → 306,78 ; période 2026-2027, 4,16 j restants sur 4,16 : "
            "dixième 459,61 (10 % de 4 596,09 × 4,16/4,16) ou maintien 409,68 (4,16 j × 98,48) "
            "→ 459,61. Total 766,39."
        )

    def test_mention_sans_brut_connu(self):
        r = indemnite_fin_de_contrat([PeriodeConges("2025-2026", None, 3.0, 1.0)], taux=0.10, valeur_jour=98.48)
        assert "rémunération de la période inconnue, maintien seul" in r.mention

    def test_le_resume_se_serialise(self):
        r = indemnite_fin_de_contrat([N_1, N], taux=0.10, valeur_jour=98.48).resume()
        assert r["methode"] == "par_periode" and r["total"] == pytest.approx(766.39)
        assert r["periodes"][0]["libelle"] == "2025-2026" and r["periodes"][0]["retenu"] == pytest.approx(306.78)
        assert r["valeur_jour"] == 98.48 and r["taux"] == 0.10 and "mention" in r
