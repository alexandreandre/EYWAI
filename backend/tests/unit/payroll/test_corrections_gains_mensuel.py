"""Une ligne de gain corrigée au mensuel : ce qui en dérive suit (spec § 5 et § 6).

Le brut, la précarité, l'indemnité compensatrice, la rémunération et les heures
des heures sup, le sous-total contractuel et les heures du SMIC de référence
partent des lignes corrigées. Sans correction, rien ne bouge.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT, code_de_ligne
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JANVIER = (date(2026, 1, 1), date(2026, 1, 31))


def _calendrier(hs=None, absences=None, heures_jour=7.0):
    cal = []
    jour = date(2026, 1, 1)
    while jour.month == 1:
        if jour.weekday() < 5:
            cal.append({"date_complete": jour.isoformat(), "type": "travail_base", "heures": heures_jour})
        jour = date.fromordinal(jour.toordinal() + 1)
    for iso, (type_ev, heures) in (hs or {}).items():
        cal.append({"date_complete": iso, "type": type_ev, "heures": heures})
    for iso, heures in (absences or {}).items():
        cal.append({"date_complete": iso, "type": "absence_injustifiee_base", "heures": heures})
    return cal


def _contexte(*corrections, **options):
    contexte = build_test_contexte(**options)
    contexte.year = 2026
    if corrections:
        contexte.corrections_du_mois = JournalDesCorrections(list(corrections))
    return contexte


def _ligne(resultat, code):
    return next(l for l in resultat["lignes_composants_brut"] if code_de_ligne(BLOC_BRUT, l) == code)


def _c(code, libelle, **champs):
    return CorrectionDeLigne(ligne=code, libelle=libelle, motif="Test", saisie_id="s1", **champs)


def test_sans_correction_le_brut_est_identique():
    cal = _calendrier(hs={"2026-01-15": ("travail_hs25", 4.0)}, absences={"2026-01-21": 3.5})
    reference = calculer_salaire_brut(_contexte(), cal, *JANVIER, [])
    avec_journal_vide = _contexte()
    avec_journal_vide.corrections_du_mois = JournalDesCorrections([])
    assert calculer_salaire_brut(avec_journal_vide, cal, *JANVIER, []) == reference
    assert type(reference["lignes_composants_brut"]) is list


def test_la_base_du_salaire_de_base_corrigee_suit_dans_le_brut_et_les_heures():
    reference = calculer_salaire_brut(_contexte(), _calendrier(), *JANVIER, [])
    base0 = _ligne(reference, "brut:salaire_base")
    corrige = calculer_salaire_brut(
        _contexte(_c("brut:salaire_base", "Salaire de base", base=160.0)), _calendrier(), *JANVIER, []
    )
    base1 = _ligne(corrige, "brut:salaire_base")
    attendu = round(160.0 * base0["taux"], 2)
    assert base1["gain"] == attendu and base1["valeur_calculee"]["gain"] == base0["gain"]
    assert corrige["salaire_brut_total"] == pytest.approx(reference["salaire_brut_total"] + attendu - base0["gain"], abs=0.005)
    assert corrige["heures_base_remunerees"] == pytest.approx(160.0)


def test_des_heures_sup_corrigees_suivent_dans_leurs_heures_et_leur_remuneration():
    cal = _calendrier(hs={"2026-01-15": ("travail_hs25", 4.0)})
    reference = calculer_salaire_brut(_contexte(), cal, *JANVIER, [])
    hs0 = _ligne(reference, "brut:heures_sup:25")
    corrige = calculer_salaire_brut(
        _contexte(_c("brut:heures_sup:25", hs0["libelle"], base=6.0)), cal, *JANVIER, []
    )
    hs1 = _ligne(corrige, "brut:heures_sup:25")
    assert hs1["gain"] == round(6.0 * hs0["taux"], 2)
    assert corrige["total_heures_supp"] == pytest.approx(reference["total_heures_supp"] + 2.0)
    assert corrige["remuneration_brute_heures_supp"] == pytest.approx(
        reference["remuneration_brute_heures_supp"] + hs1["gain"] - hs0["gain"], abs=0.005
    )


def test_une_absence_corrigee_suit_dans_les_heures_non_payees():
    cal = _calendrier(absences={"2026-01-21": 3.5})
    reference = calculer_salaire_brut(_contexte(), cal, *JANVIER, [])
    code = "brut:absence_injustifiee:du-21-01-26-base"
    abs0 = _ligne(reference, code)
    corrige = calculer_salaire_brut(_contexte(_c(code, abs0["libelle"], base=7.0)), cal, *JANVIER, [])
    abs1 = _ligne(corrige, code)
    assert abs1["perte"] == round(7.0 * abs0["taux"], 2)
    assert corrige["heures_absence_non_payees"] == pytest.approx(reference["heures_absence_non_payees"] + 3.5)
    assert corrige["salaire_brut_total"] == pytest.approx(
        reference["salaire_brut_total"] - (abs1["perte"] - abs0["perte"]), abs=0.005
    )


def test_le_sous_total_et_les_heures_structurelles_suivent():
    options = dict(salaire_base=2123.38, duree_hebdo=39.0)
    # Les heures structurelles viennent du contrat, pas du planning : le
    # calendrier ordinaire suffit (sonde du 23/10 : base, structurelles, sous-total).
    reference = calculer_salaire_brut(_contexte(**options), _calendrier(), *JANVIER, [])
    hs0 = _ligne(reference, "brut:hs_structurelles")
    corrige = calculer_salaire_brut(
        _contexte(_c("brut:hs_structurelles", hs0["libelle"], base=20.0), **options),
        _calendrier(),
        *JANVIER,
        [],
    )
    hs1 = _ligne(corrige, "brut:hs_structurelles")
    sous_total = _ligne(corrige, "brut:sous_total")
    assert sous_total["gain"] == round(_ligne(corrige, "brut:salaire_base")["gain"] + hs1["gain"], 2)
    assert corrige["total_heures_supp"] == pytest.approx(reference["total_heures_supp"] + 20.0 - hs0["quantite"])
    assert corrige["remuneration_brute_heures_supp"] == pytest.approx(
        reference["remuneration_brute_heures_supp"] + hs1["gain"] - hs0["gain"], abs=0.005
    )


def _cdd(*corrections):
    contexte = _contexte(
        *corrections,
        salaire_base=2200.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-04-30",
        cumuls={"brut_total": 8800.0},
        specificites_extra={"dsn_reprise": {"motif_recours": "02"}},
    )
    return calculer_salaire_brut(contexte, [], date(2026, 4, 1), date(2026, 4, 30), [])


def test_la_precarite_et_l_indemnite_compensatrice_suivent_le_salaire_corrige():
    reference = _cdd()
    assert _ligne(reference, "brut:precarite")["gain"] == pytest.approx(1100.0)
    corrige = _cdd(_c("brut:salaire_base", "Salaire de base", base=160.0))
    gain = _ligne(corrige, "brut:salaire_base")["gain"]
    precarite = _ligne(corrige, "brut:precarite")["gain"]
    assert precarite == pytest.approx(round((8800.0 + gain) * 0.1, 2), abs=0.01)
    assert _ligne(corrige, "brut:iccp:cdd")["gain"] == pytest.approx(round((8800.0 + gain + precarite) * 0.1, 2), abs=0.01)


def test_l_indemnite_compensatrice_suit_la_precarite_corrigee():
    corrige = _cdd(_c("brut:precarite", "Prime de précarité (CDD)", montant=1000.0))
    assert _ligne(corrige, "brut:precarite")["gain"] == 1000.0
    assert _ligne(corrige, "brut:iccp:cdd")["gain"] == pytest.approx(1200.0, abs=0.01)
