"""Réduction générale (RGDU 2026) d'un salarié au forfait annuel en jours.

Règle (CSS D241-7, IV, 3e alinéa ; BOSS, allègements généraux, § 860) : pour un
salarié au forfait en jours sur l'année, le SMIC annuel de référence est
« corrigé du rapport entre le nombre de jours prévu au forfait du salarié, et
218 jours ». Un mois complet vaut donc 151,67 h × jours du forfait / 218, soit
150,28 h pour 216 jours ; un forfait ne compte jamais au-delà de 218 jours (pas
de majoration pour les jours de repos rachetés). Une absence non payée, ou un
arrêt sans maintien intégral, corrige ce SMIC du rapport entre la rémunération
due au titre du mois et celle qui l'aurait été sans l'absence (D241-7, IV,
5e alinéa ; BOSS § 770-810).

Le moteur comptait 7 h par jour travaillé (147 h pour 21 jours), et la reprise
de Quadra posait 0 h à l'ouverture : la formule annualisée concluait à plus de
3 SMIC et remboursait toute la réduction de l'année (+1 043,10 € de charges au
lieu de −166,79 € pour un cadre à 216 jours et 3 750 € en septembre 2026).

Cas de référence : bulletins Quadra de Comitech, cadre au forfait 216 jours,
3 750 € par mois, février à septembre 2026. Quadra déclare la réduction à
partir de février (aucune en janvier), compte la prime de partage de la valeur
dans la rémunération (L241-13, III) et a retenu 12,31 € en juin. Avec 150,28 h
par mois, la formule légale redonne ses huit lignes « EXO., ECRET. ET ALLEG. »,
dont −166,79 € en septembre.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_reduction_generale import (
    OuvertureReductionIncomplete,
    calculer_reduction_generale,
    heures_reduction_forfait_jours,
    rapport_salaires_forfait_jours,
)
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _contexte_2026(mois: int, cumuls: dict | None = None):
    ctx = build_test_contexte(statut="Cadre", salaire_base=3750.0, effectif=25)
    ctx.year = 2026
    ctx.month = mois
    # SMIC de référence figé à 12,02 € pour toute l'année 2026 (décret 2026-509).
    ctx.baremes["reduction_generale"]["smic_reference_horaire"] = 12.02
    ctx.cumuls = {"cumuls": cumuls or {}}
    return ctx


class TestHeuresDuForfait:
    def test_forfait_216_jours_150_28_heures_par_mois(self):
        assert heures_reduction_forfait_jours(216) == 150.28

    def test_forfait_218_jours_mois_legal_complet(self):
        assert heures_reduction_forfait_jours(218) == 151.67

    def test_forfait_au_dela_de_218_jours_plafonne(self):
        # Jours de repos rachetés : aucune majoration du SMIC (BOSS § 860).
        assert heures_reduction_forfait_jours(230) == 151.67

    def test_ne_depend_pas_des_jours_travailles_du_mois(self):
        # Un mois de 22 jours ouvrés et un mois de 20 donnent le même SMIC :
        # seule la durée du forfait compte, pas 7 h par jour travaillé.
        assert heures_reduction_forfait_jours(216, 1.0) == heures_reduction_forfait_jours(216)

    def test_absence_reduit_du_rapport_des_salaires(self):
        # 150,2752 × 0,5 = 75,1376.
        assert heures_reduction_forfait_jours(216, 0.5) == 75.14

    def test_rapport_borne_entre_zero_et_un(self):
        assert heures_reduction_forfait_jours(216, 1.2) == 150.28
        assert heures_reduction_forfait_jours(216, -0.3) == 0.0

    def test_jours_du_forfait_inconnus_refuses(self):
        with pytest.raises(ValueError):
            heures_reduction_forfait_jours(0)


class TestRapportDesSalaires:
    def test_mois_complet(self):
        assert rapport_salaires_forfait_jours(3750.0, 0.0, 0.0) == 1.0

    def test_absence_non_payee(self):
        # Paternité de 2 jours sans maintien (Quadra, janvier) : 3 409,09 / 3 750.
        assert rapport_salaires_forfait_jours(3750.0, 340.91, 0.0) == pytest.approx(
            3409.09 / 3750.0
        )

    def test_arret_avec_maintien_integral(self):
        assert rapport_salaires_forfait_jours(3750.0, 1704.55, 1704.55) == 1.0

    def test_arret_avec_maintien_partiel(self):
        assert rapport_salaires_forfait_jours(3750.0, 1704.55, 852.28) == pytest.approx(
            (3750.0 - 1704.55 + 852.28) / 3750.0
        )

    def test_retenue_superieure_au_salaire(self):
        assert rapport_salaires_forfait_jours(3750.0, 4000.0, 0.0) == 0.0

    def test_salaire_nul(self):
        assert rapport_salaires_forfait_jours(0.0, 0.0, 0.0) == 0.0


def _brut_forfait(calendrier, *, date_entree="2020-01-01", primes=None):
    from datetime import date

    from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait

    ctx = build_test_contexte(statut="Cadre", salaire_base=3750.0, date_entree=date_entree)
    ctx.year, ctx.month = 2026, 9
    return calculer_salaire_brut_forfait(
        ctx, calendrier, date(2026, 9, 1), date(2026, 9, 30), primes_saisies=primes or []
    )


def _jour(jour: int, type_: str, heures: float = 1.0, **extra):
    return {"date_complete": f"2026-09-{jour:02d}", "type": type_, "heures": heures, **extra}


class TestBrutForfaitExposeLeRapport:
    """Le calcul du brut donne ce qu'il faut au rapport des salaires."""

    def test_mois_complet_sans_retenue(self):
        res = _brut_forfait([_jour(1, "travail_base"), _jour(2, "travail_base")])
        assert res["salaire_forfait_mois"] == 3750.0
        assert res["retenues_absence_mois"] == 0.0

    def test_absence_non_remuneree_retenue(self):
        res = _brut_forfait([_jour(1, "absence_non_remuneree"), _jour(2, "absence_non_remuneree")])
        assert res["retenues_absence_mois"] == pytest.approx(2 * round(3750.0 / 21.67, 2), abs=0.01)
        assert res["salaire_forfait_mois"] - res["retenues_absence_mois"] == pytest.approx(
            res["salaire_brut_total"], abs=0.01
        )

    def test_arret_maladie_retenu(self):
        res = _brut_forfait([_jour(1, "arret_maladie", 0, arret_type="maladie_simple")])
        assert res["retenues_absence_mois"] == round(3750.0 / 21.67, 2)

    def test_prime_hors_rapport(self):
        res = _brut_forfait(
            [_jour(1, "travail_base")], primes=[{"libelle": "Prime", "montant": 500.0}]
        )
        assert res["salaire_brut_total"] == 4250.0
        assert res["retenues_absence_mois"] == 0.0

    def test_entree_en_cours_de_mois(self):
        # Entrée le mardi 15/09 : 10 jours ouvrés hors contrat sur 22.
        res = _brut_forfait([_jour(15, "travail_base")], date_entree="2026-09-15")
        assert res["retenues_absence_mois"] == pytest.approx(10 * 3750.0 / 22, abs=0.01)


class TestJoursDuForfait:
    """Le nombre de jours « prévu au forfait du salarié » (BOSS § 860)."""

    def _ctx(self, ajuste=None):
        ctx = build_test_contexte(statut="Cadre", salaire_base=3750.0)
        if ajuste is not None:
            ctx.contrat["forfait_annual_days_adjusted"] = ajuste
        return ctx

    def test_forfait_du_salarie_ajuste_d_abord(self, monkeypatch):
        from app.modules.payroll.documents import payslip_run_forfait as run

        def interdit(_company_id):
            raise AssertionError("pas de lecture quand le forfait du salarié est connu")

        monkeypatch.setattr(
            "app.modules.absences.infrastructure.leave_settings_repository.get_leave_policy",
            interdit,
        )
        assert run.jours_du_forfait_pour_reduction(self._ctx(214.0), "societe") == 214.0

    def test_sinon_forfait_de_la_societe(self, monkeypatch):
        import dataclasses

        from app.modules.absences.domain.leave_policy import DEFAULT_LEAVE_POLICY
        from app.modules.payroll.documents import payslip_run_forfait as run

        politique = dataclasses.replace(DEFAULT_LEAVE_POLICY, rtt_forfait_annual_days=216)
        monkeypatch.setattr(
            "app.modules.absences.infrastructure.leave_settings_repository.get_leave_policy",
            lambda _company_id: politique,
        )
        assert run.jours_du_forfait_pour_reduction(self._ctx(), "societe") == 216.0

    def test_lecture_impossible_arrete_le_calcul(self, monkeypatch):
        from app.modules.payroll.documents import payslip_run_forfait as run
        from app.modules.payroll.engine.lectures import LectureIndispensable

        def en_panne(_company_id):
            raise RuntimeError("base injoignable")

        monkeypatch.setattr(
            "app.modules.absences.infrastructure.leave_settings_repository.get_leave_policy",
            en_panne,
        )
        with pytest.raises(LectureIndispensable):
            run.jours_du_forfait_pour_reduction(self._ctx(), "societe")


class TestHeuresDuMoisForfait:
    """Ce que le bulletin forfait passe à la réduction et au cumul d'heures."""

    def test_mois_complet_quel_que_soit_le_nombre_de_jours_travailles(self):
        from app.modules.payroll.documents import payslip_run_forfait as run

        brut = {"salaire_forfait_mois": 3750.0, "retenues_absence_mois": 0.0,
                "nombre_jours_travailles": 21}
        assert run.heures_reduction_du_mois(brut, None, 216) == 150.28

    def test_arret_avec_maintien_partiel(self):
        from app.modules.payroll.documents import payslip_run_forfait as run

        brut = {"salaire_forfait_mois": 3750.0, "retenues_absence_mois": 1730.77}
        maintien = {"maintien": {"maintien_verse": 865.39}}
        attendu = round(35 * 52 / 12 * 216 / 218 * (3750.0 - 1730.77 + 865.39) / 3750.0, 2)
        assert run.heures_reduction_du_mois(brut, maintien, 216) == attendu


class TestCasQuadraSeptembre:
    """Cadre au forfait 216 jours, Comitech, septembre 2026."""

    def test_meme_base_que_quadra_redonne_166_79(self):
        # Base de Quadra au 31/08 : brut de février à août avec la PPV de juillet
        # (28 500 €), SMIC 12 688,17 € (juin à 12,31 €), soit 1 055,59 h à 12,02 €.
        # Réduction déjà appliquée : 1 043,10 €.
        ctx = _contexte_2026(
            9,
            {
                "brut_total": 28500.00,
                "heures_remunerees": 1055.59,
                "reduction_generale_patronale": -1043.10,
            },
        )
        # Septembre : 3 750 € et 100 € de PPV.
        ligne = calculer_reduction_generale(ctx, 3850.00, heures_reduction_forfait_jours(216))
        assert ligne["taux_patronal"] == 0.0374
        assert ligne["montant_patronal"] == -166.79
        assert ligne["valeur_cumulative_a_enregistrer"] == 1209.89

    def test_smic_fige_12_02_toute_l_annee(self):
        # Même base, juin régularisé à 12,02 € (décret 2026-509 ; BOSS § 360) :
        # 7 mois × 150,28 h. La loi donne −153,85 € ; Quadra, resté à 12,31 €
        # en juin, en déclare 12,94 € de plus.
        ctx = _contexte_2026(
            9,
            {
                "brut_total": 28500.00,
                "heures_remunerees": 1051.96,
                "reduction_generale_patronale": -1043.10,
            },
        )
        ligne = calculer_reduction_generale(ctx, 3850.00, heures_reduction_forfait_jours(216))
        assert ligne["montant_patronal"] == -153.85

    def test_ancien_calcul_remboursait_toute_la_reduction(self):
        # Ouverture à 0 h et 21 jours × 7 h : brut cumulé au-delà de 3 SMIC, la
        # réduction de l'année repartait en charges. Le moteur refuse désormais.
        ctx = _contexte_2026(
            9,
            {
                "brut_total": 31809.09,
                "heures_remunerees": 0.0,
                "reduction_generale_patronale": -1043.10,
            },
        )
        with pytest.raises(OuvertureReductionIncomplete) as erreur:
            calculer_reduction_generale(ctx, 3750.00, heures_reduction_forfait_jours(216))
        message = str(erreur.value)
        assert "1 043,10" in message
        assert "heures" in message


class TestOuvertureSansHeures:
    def test_refus_message_clair(self):
        ctx = _contexte_2026(
            9,
            {
                "brut_total": 31809.09,
                "heures_remunerees": 0.0,
                "reduction_generale_patronale": -1043.10,
            },
        )
        with pytest.raises(OuvertureReductionIncomplete, match="n'est pas calculé"):
            calculer_reduction_generale(ctx, 3750.00, 150.28)

    def test_est_une_valueerror_pour_l_api(self):
        # Le générateur transforme une ValueError en refus 400 avec la phrase.
        assert issubclass(OuvertureReductionIncomplete, ValueError)

    def test_janvier_ne_lit_pas_le_cumul(self):
        # En janvier les compteurs repartent de zéro : aucune incohérence.
        ctx = _contexte_2026(
            1,
            {
                "brut_total": 45000.0,
                "heures_remunerees": 0.0,
                "reduction_generale_patronale": -1500.0,
            },
        )
        assert calculer_reduction_generale(ctx, 3750.00, 150.28) is not None

    def test_premier_mois_sans_cumul(self):
        ctx = _contexte_2026(9, {})
        assert calculer_reduction_generale(ctx, 3750.00, 150.28) is not None

    def test_cumul_coherent_accepte(self):
        ctx = _contexte_2026(
            9,
            {
                "brut_total": 30000.0,
                "heures_remunerees": 1202.24,
                "reduction_generale_patronale": -1100.0,
            },
        )
        assert calculer_reduction_generale(ctx, 3750.00, 150.28) is not None

    def test_aucune_reduction_deja_appliquee_accepte(self):
        # Brut sans heures mais aucune réduction appliquée : rien à rembourser à
        # tort (ex. salarié resté au-dessus de 3 SMIC), le calcul se fait.
        ctx = _contexte_2026(
            9,
            {
                "brut_total": 90000.0,
                "heures_remunerees": 0.0,
                "reduction_generale_patronale": 0.0,
            },
        )
        calculer_reduction_generale(ctx, 10000.00, 150.28)
