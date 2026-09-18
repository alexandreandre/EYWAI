"""Remise à zéro des compteurs d'année civile au 1ᵉʳ janvier.

Le générateur lit délibérément décembre N-1 pour produire janvier. Les compteurs
dont la fenêtre est l'année civile doivent donc être écartés à la lecture, et
remis à zéro à l'écriture. Ceux dont la fenêtre est autre — le contrat pour la
prime de précarité, le 1ᵉʳ juin au 31 mai pour la base du dixième des congés —
ne doivent surtout pas l'être.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.modules.payroll.documents.payslip_run_common import mettre_a_jour_cumuls
from app.modules.payroll.engine.calcul_net import _base_pas_du_mois
from app.modules.payroll.engine.calcul_reduction_generale import _lire_cumuls_precedents
from tests.unit.payroll.helpers import build_test_contexte

#: Ce que décembre N-1 laisse en base : une année entière de cumuls.
#: `build_test_contexte` enveloppe déjà cette table sous la clé « cumuls ».
DECEMBRE_N_MOINS_1 = {
    "brut_total": 42000.0,
    "heures_remunerees": 1820.0,
    "reduction_generale_patronale": -6800.0,
    "net_imposable": 36000.0,
    "impot_preleve_a_la_source": 1450.0,
    "heures_supplementaires_remunerees": 180.0,
    "montant_hs_remunerees": 3200.0,
}

#: Les compteurs dont la fenêtre est l'année civile.
COMPTEURS_ANNEE_CIVILE = (
    "net_imposable",
    "impot_preleve_a_la_source",
    "heures_remunerees",
    "heures_supplementaires_remunerees",
    "montant_hs_remunerees",
    "reduction_generale_patronale",
)


class TestLectureDeLaReductionGenerale:
    """La régularisation progressive ne doit pas hériter de l'année précédente."""

    def test_janvier_ecarte_les_cumuls_de_decembre(self):
        contexte = build_test_contexte(cumuls=DECEMBRE_N_MOINS_1)
        contexte.month = 1
        brut, heures, deja_appliquee = _lire_cumuls_precedents(contexte)
        assert (brut, heures, deja_appliquee) == (0.0, 0.0, 0.0)

    def test_fevrier_lit_bien_le_mois_precedent(self):
        contexte = build_test_contexte(cumuls=DECEMBRE_N_MOINS_1)
        contexte.month = 2
        brut, heures, deja_appliquee = _lire_cumuls_precedents(contexte)
        assert brut == pytest.approx(42000.0)
        assert heures == pytest.approx(1820.0)
        # La réduction est stockée en négatif et lue en valeur absolue.
        assert deja_appliquee == pytest.approx(6800.0)

    def test_sans_mois_connu_le_comportement_reste_celui_de_la_lecture(self):
        contexte = build_test_contexte(cumuls=DECEMBRE_N_MOINS_1)
        if hasattr(contexte, "month"):
            contexte.month = None
        brut, _, _ = _lire_cumuls_precedents(contexte)
        assert brut == pytest.approx(42000.0)


class TestBasePasApprenti:
    """Le plafond d'exonération de l'apprenti court sur l'année civile."""

    def _contexte_apprenti(self, cumuls):
        contexte = build_test_contexte(
            cumuls=cumuls,
            type_contrat="apprentissage",
            date_naissance="2005-01-01",
            specificites_extra={
                "exonerations": {
                    "exoneration_ir": {"actif": True, "plafond_annuel_pct_smic": 0.79}
                }
            },
        )
        return contexte

    def test_en_janvier_l_apprenti_repart_sous_le_plafond(self):
        contexte = self._contexte_apprenti(DECEMBRE_N_MOINS_1)
        contexte.month = 1
        # Le cumul de décembre dépasse largement le plafond : sans la garde,
        # le premier euro de janvier serait imposé.
        assert _base_pas_du_mois(contexte, 1500.0) == pytest.approx(0.0)

    def test_en_fevrier_le_cumul_de_l_annee_compte(self):
        contexte = self._contexte_apprenti(DECEMBRE_N_MOINS_1)
        contexte.month = 2
        base = _base_pas_du_mois(contexte, 1500.0)
        # Le cumul dépasse le plafond, donc tout le mois entre dans la base.
        assert base == pytest.approx(1500.0)


class TestEcritureDesCumuls:
    """À l'écriture, janvier remet à zéro l'année civile et garde le reste."""

    def _ecrire(self, mois: int):
        contexte = build_test_contexte(cumuls=json.loads(json.dumps(DECEMBRE_N_MOINS_1)))
        contexte.month = mois
        contexte.year = 2027
        dossier = Path(tempfile.mkdtemp(prefix="cumuls_janvier_"))
        mettre_a_jour_cumuls(
            contexte,
            salaire_brut_mois=2500.0,
            remuneration_hs_mois=100.0,
            resultats_nets_mois={
                "net_imposable": 2000.0,
                "montant_impot_pas": 60.0,
                "montant_net_hs_exonerees": 90.0,
                "hs_exonerees_ir_mois": 85.0,
            },
            reduction_generale_mois={"valeur_cumulative_a_enregistrer": 400.0},
            mois=mois,
            smic_mois=1800.0,
            pss_mois=4005.0,
            chemin_employe=dossier,
            heures_supplementaires_mois=6.0,
            heures_remunerees_mois=160.0,
        )
        ecrit = json.loads((dossier / "cumuls" / f"{mois:02d}.json").read_text(encoding="utf-8"))
        return ecrit["cumuls"]

    def test_janvier_ne_garde_que_le_mois_sur_les_compteurs_annuels(self):
        cumuls = self._ecrire(1)
        assert cumuls["net_imposable"] == pytest.approx(2000.0)
        assert cumuls["impot_preleve_a_la_source"] == pytest.approx(60.0)
        assert cumuls["heures_remunerees"] == pytest.approx(160.0)
        assert cumuls["heures_supplementaires_remunerees"] == pytest.approx(6.0)
        assert cumuls["montant_hs_remunerees"] == pytest.approx(100.0)
        assert cumuls["reduction_generale_patronale"] == pytest.approx(-400.0)

    def test_janvier_ne_touche_pas_au_brut_total(self):
        # `brut_total` sert aussi la prime de précarité (fenêtre du contrat) et la
        # base du dixième des congés (1ᵉʳ juin au 31 mai) : le remettre à zéro
        # casserait ces deux usages.
        assert self._ecrire(1)["brut_total"] == pytest.approx(42000.0 + 2500.0)

    def test_fevrier_continue_d_additionner(self):
        cumuls = self._ecrire(2)
        assert cumuls["net_imposable"] == pytest.approx(36000.0 + 2000.0)
        assert cumuls["heures_remunerees"] == pytest.approx(1820.0 + 160.0)
        assert cumuls["brut_total"] == pytest.approx(42000.0 + 2500.0)

    def test_tous_les_compteurs_annuels_sont_couverts_par_le_test(self):
        # Garde-fou : si un compteur est ajouté à la remise à zéro du code sans
        # être testé, ce test le signale.
        from app.modules.payroll.documents import payslip_run_common

        source = Path(payslip_run_common.__file__).read_text(encoding="utf-8")
        debut = source.index("if mois == 1:")
        bloc = source[debut : source.index("cumuls[\"brut_total\"]", debut)]
        for compteur in COMPTEURS_ANNEE_CIVILE:
            assert f'"{compteur}"' in bloc, f"{compteur} n'est plus remis à zéro"
        assert '"brut_total"' not in bloc, "brut_total ne doit pas être remis à zéro"
