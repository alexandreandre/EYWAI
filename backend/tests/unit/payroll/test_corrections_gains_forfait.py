"""Au forfait jours, une ligne corrigée fait suivre le brut et le rapport des
salaires de la réduction générale (salaire du forfait, retenues d'absence)."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait
from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT, code_de_ligne
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

MARS = (date(2026, 3, 1), date(2026, 3, 31))
ABSENCE = [{"date_complete": "2026-03-16", "type": "absence_non_remuneree", "heures": 7.8}]
CODE_ABSENCE = "brut:absence_non_remuneree:16-03-26-1-jour"


def _brut(*corrections):
    contexte = build_test_contexte(statut="Cadre", salaire_base=3608.0, specificites_extra={"is_forfait_jour": True})
    contexte.year = 2026
    if corrections:
        contexte.corrections_du_mois = JournalDesCorrections(list(corrections))
    return calculer_salaire_brut_forfait(contexte, ABSENCE, *MARS, [])


def _ligne(resultat, code):
    return next(l for l in resultat["lignes_composants_brut"] if code_de_ligne(BLOC_BRUT, l) == code)


def _c(code, libelle, **champs):
    return CorrectionDeLigne(ligne=code, libelle=libelle, motif="Test", saisie_id="s1", **champs)


def test_sans_correction_le_forfait_est_identique():
    reference = _brut()
    assert reference["salaire_forfait_mois"] == 3608.0
    assert type(reference["lignes_composants_brut"]) is list
    assert _brut() == reference


def test_le_salaire_du_forfait_corrige_suit_dans_le_brut_et_le_rapport_des_salaires():
    reference = _brut()
    corrige = _brut(_c("brut:salaire_base", "Salaire de base (forfait jour)", montant=3700.0))
    assert _ligne(corrige, "brut:salaire_base")["gain"] == 3700.0
    assert corrige["salaire_brut_total"] == pytest.approx(reference["salaire_brut_total"] + 92.0)
    assert corrige["salaire_forfait_mois"] == 3700.0


def test_une_absence_corrigee_suit_dans_les_retenues_du_mois():
    reference = _brut()
    absence0 = _ligne(reference, CODE_ABSENCE)
    corrige = _brut(_c(CODE_ABSENCE, absence0["libelle"], base=2.0))
    absence1 = _ligne(corrige, CODE_ABSENCE)
    assert absence1["perte"] == round(2.0 * absence0["taux"], 2)
    assert corrige["retenues_absence_mois"] == pytest.approx(
        reference["retenues_absence_mois"] + absence1["perte"] - absence0["perte"], abs=0.005
    )
    assert corrige["salaire_brut_total"] == pytest.approx(
        reference["salaire_brut_total"] - (absence1["perte"] - absence0["perte"]), abs=0.005
    )
