"""Tests bulletin de paie — format officiel (MNS, rubriques, template)."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from app.modules.payroll.engine.bulletin import creer_bulletin_final
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import calculer_montant_net_social, calculer_net_et_impot
from app.modules.payroll.engine.calcul_reduction_generale import calculer_reduction_generale
from app.modules.payroll.engine.cotisations_rubriques import (
    RUBRIQUES_ORDRE,
    construire_cotisations_officielles,
    enrichir_ligne_cotisation,
    resoudre_rubrique,
)
from tests.unit.payroll.helpers import build_test_contexte, run_bulletin_pipeline_heures


class TestMontantNetSocial:
    def test_mns_standard_egale_net_social_sans_primes_ni_mutuelle(self):
        ctx = build_test_contexte(salaire_base=2000.0)
        ctx.year = 2026
        lignes, total_sal = calculer_cotisations(ctx, 2000.0)
        red = calculer_reduction_generale(ctx, 2000.0, 151.67)
        if red:
            lignes.append(red)
        nets = calculer_net_et_impot(ctx, 2000.0, lignes, total_sal, [], 0.0)
        mns = calculer_montant_net_social(ctx, 2000.0, total_sal, [])
        assert mns == pytest.approx(nets["montant_net_social"], abs=0.01)
        assert mns == pytest.approx(2000.0 - total_sal, abs=0.01)

    def test_mns_avec_primes_non_soumises(self):
        ctx = build_test_contexte(salaire_base=2500.0)
        primes = [{"libelle": "PPV", "montant": 500.0}]
        _, total_sal = calculer_cotisations(ctx, 2500.0)
        mns = calculer_montant_net_social(ctx, 2500.0, total_sal, primes)
        assert mns == pytest.approx(2500.0 + 500.0 - total_sal, abs=0.01)

    def test_mns_avec_mutuelle_patronale(self):
        ctx = build_test_contexte(
            salaire_base=2000.0,
            specificites_extra={
                "mutuelle": {
                    "adhesion": True,
                    "montant_patronal": 30.0,
                    "montant_salarial": 15.0,
                    "part_patronale_soumise_a_csg": True,
                }
            },
        )
        lignes, total_sal = calculer_cotisations(ctx, 2000.0)
        mns = calculer_montant_net_social(ctx, 2000.0, total_sal, [])
        assert mns == pytest.approx(2000.0 + 30.0 - total_sal, abs=0.01)
        assert any(l.get("coti_id") == "mutuelle" for l in lignes)


class TestCotisationsRubriques:
    def test_mapping_coti_id_vieillesse_retraite(self):
        assert resoudre_rubrique("vieillesse_plafonnee") == "retraite"
        assert resoudre_rubrique("retraite_comp_t1") == "retraite"

    def test_fallback_libelle_mutuelle(self):
        assert resoudre_rubrique(None, "Mutuelle Frais de Santé") == "sante"

    def test_fallback_reduction_generale_exonerations(self):
        assert (
            resoudre_rubrique(None, "Réduction générale de cotisations patronales")
            == "exonerations"
        )

    def test_enrichir_ligne_conserve_cles_existantes(self):
        ligne = enrichir_ligne_cotisation(
            {
                "libelle": "Vieillesse plafonnée",
                "base": 2000.0,
                "montant_salarial": 138.0,
                "montant_patronal": 171.0,
            },
            coti_id="vieillesse_plafonnee",
        )
        assert ligne["coti_id"] == "vieillesse_plafonnee"
        assert ligne["rubrique"] == "retraite"
        assert ligne["montant_salarial"] == 138.0

    def test_cotisations_officielles_ordre_et_totaux(self):
        lignes = [
            enrichir_ligne_cotisation(
                {
                    "libelle": "Vieillesse plafonnée",
                    "montant_salarial": 100.0,
                    "montant_patronal": 50.0,
                },
                "vieillesse_plafonnee",
            ),
            enrichir_ligne_cotisation(
                {
                    "libelle": "CSG déductible",
                    "montant_salarial": 80.0,
                    "montant_patronal": 0.0,
                },
                "csg_deductible",
            ),
            enrichir_ligne_cotisation(
                {
                    "libelle": "Réduction générale de cotisations patronales",
                    "montant_salarial": 0.0,
                    "montant_patronal": -200.0,
                },
                "reduction_generale",
            ),
        ]
        rubriques, total_exo = construire_cotisations_officielles(lignes)
        codes = [r["code"] for r in rubriques]
        assert codes.index("retraite") < codes.index("csg_deductible")
        assert "exonerations" in codes
        assert total_exo == pytest.approx(200.0, abs=0.01)
        retraite = next(r for r in rubriques if r["code"] == "retraite")
        assert retraite["total_salarial"] == pytest.approx(100.0)
        assert retraite["total_patronal"] == pytest.approx(50.0)


class TestBulletinFinalOfficiel:
    def test_creer_bulletin_final_contient_champs_officiels(self):
        ctx = build_test_contexte(salaire_base=2000.0)
        ctx.year = 2026
        ctx.contrat.setdefault("remuneration", {})["classification_conventionnelle"] = {
            "coefficient": "275",
            "niveau": "III",
        }
        ctx.contrat["remuneration"]["convention_collective"] = {
            "libelle": "Syntec",
            "idcc": "1486",
        }
        ctx.entreprise.setdefault("identification", {})["naf_ape"] = "6201Z"

        lignes, total_sal = calculer_cotisations(ctx, 2000.0)
        red = calculer_reduction_generale(ctx, 2000.0, 151.67)
        if red:
            lignes.append(red)
        nets = calculer_net_et_impot(ctx, 2000.0, lignes, total_sal, [], 0.0)

        bulletin = creer_bulletin_final(
            ctx,
            2000.0,
            [
                {
                    "libelle": "Salaire de base",
                    "quantite": 151.67,
                    "taux": 13.18,
                    "gain": 2000.0,
                    "perte": None,
                }
            ],
            lignes,
            nets,
            [],
            2026,
            4,
        )

        assert bulletin["cotisations_officielles"]
        assert bulletin["total_exonerations"] >= 0
        assert bulletin["synthese_net"]["montant_net_social"] is not None
        assert bulletin["en_tete"]["entreprise"]["naf_ape"] == "6201Z"
        assert bulletin["en_tete"]["salarie"]["classification"] == "275 III"
        assert "Syntec" in bulletin["en_tete"]["salarie"]["convention_collective"]
        assert bulletin["en_tete"]["date_paiement"]
        assert bulletin["pied_de_page"]["mentions_legales"]["conservation"]
        assert "service-public.fr" in bulletin["pied_de_page"]["mentions_legales"]["information"]

    def test_creer_bulletin_final_alerte_net_superieur_brut(self):
        ctx = build_test_contexte(salaire_base=1000.0)
        nets = {
            "net_a_payer": 1100.0,
            "net_imposable": 1050.0,
            "montant_net_social": 1080.0,
            "impot_prelevement_a_la_source": 0.0,
        }
        bulletin = creer_bulletin_final(ctx, 1000.0, [], [], nets, [], 2026, 6)
        codes = [a.get("code") for a in bulletin.get("alertes_baremes") or []]
        assert "net_superieur_brut" in codes

    def test_pipeline_golden_inclut_mns(self):
        ctx = build_test_contexte(salaire_base=2000.0)
        r = run_bulletin_pipeline_heures(ctx)
        assert "montant_net_social" not in r  # helper retourne dict résumé
        # Vérifier via calcul direct
        lignes, total_sal = calculer_cotisations(ctx, r["brut"])
        mns = calculer_montant_net_social(ctx, r["brut"], total_sal, [])
        assert mns == pytest.approx(r["brut"] - r["total_cotisations_salariales"], abs=0.05)


class TestTemplateBulletinOfficiel:
    def test_pied_de_page_contient_solde_conges(self):
        ctx = build_test_contexte(salaire_base=2000.0)
        ctx.year = 2026
        ctx.contrat["employee_id"] = "emp-test-1"
        lignes, total_sal = calculer_cotisations(ctx, 2000.0)
        nets = calculer_net_et_impot(ctx, 2000.0, lignes, total_sal, [], 0.0)

        solde_payload = {
            "date_reference": "30/04/2026",
            "conges_payes": {
                "acquis": 13.0,
                "pris": 2.0,
                "solde": 11.0,
                "periode": "01/06/2025 – 31/05/2026",
            },
            "conges_payes_periode_precedente": {
                "acquis": 30.0,
                "pris": 25.0,
                "solde": 5.0,
                "periode": "01/06/2024 – 31/05/2025",
            },
            "rtt": {"acquis": 0.0, "pris": 0.0, "solde": 0.0},
            "repos_compensateur": {"acquis": 0.0, "pris": 0.0, "solde": 0.0},
        }
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.modules.payroll.engine.bulletin.build_solde_conges_pied_de_page",
                lambda *_a, **_k: solde_payload,
            )
            bulletin = creer_bulletin_final(
                ctx,
                2000.0,
                [],
                lignes,
                nets,
                [],
                2026,
                4,
            )

        assert bulletin["pied_de_page"]["solde_conges"]["conges_payes"]["solde"] == 11.0

    def test_rendu_template_contient_solde_conges_en_bas(self):
        ctx = build_test_contexte(salaire_base=2000.0)
        ctx.year = 2026
        lignes, total_sal = calculer_cotisations(ctx, 2000.0)
        nets = calculer_net_et_impot(ctx, 2000.0, lignes, total_sal, [], 0.0)
        bulletin = creer_bulletin_final(ctx, 2000.0, [], lignes, nets, [], 2026, 4)
        bulletin.setdefault("pied_de_page", {})["solde_conges"] = {
            "date_reference": "30/04/2026",
            "conges_payes": {
                "acquis": 13.0,
                "pris": 2.0,
                "solde": 11.0,
                "periode": "01/06/2025 – 31/05/2026",
            },
            "conges_payes_periode_precedente": {
                "acquis": 30.0,
                "pris": 25.0,
                "solde": 5.0,
                "periode": "01/06/2024 – 31/05/2025",
            },
            "rtt": {"acquis": 0.0, "pris": 0.0, "solde": 0.0},
            "repos_compensateur": {"acquis": 0.0, "pris": 0.0, "solde": 0.0},
        }

        template_dir = (
            Path(__file__).resolve().parents[3]
            / "app"
            / "runtime"
            / "payroll"
            / "templates"
        )
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        html = env.get_template("template_bulletin.html").render(bulletin)

        assert "Solde de congés au 30/04/2026" in html
        assert "11.00 j" in html
        assert "CP période en cours" in html
        idx_solde = html.index("Solde de congés")
        idx_mentions = html.index("service-public.fr")
        assert idx_solde < idx_mentions

    def test_rendu_template_contient_montant_net_social(self):
        ctx = build_test_contexte(salaire_base=2000.0)
        ctx.year = 2026
        lignes, total_sal = calculer_cotisations(ctx, 2000.0)
        red = calculer_reduction_generale(ctx, 2000.0, 151.67)
        if red:
            lignes.append(red)
        nets = calculer_net_et_impot(ctx, 2000.0, lignes, total_sal, [], 0.0)
        bulletin = creer_bulletin_final(
            ctx,
            2000.0,
            [
                {
                    "libelle": "Salaire de base",
                    "quantite": 151.67,
                    "taux": 13.18,
                    "gain": 2000.0,
                    "perte": None,
                }
            ],
            lignes,
            nets,
            [],
            2026,
            4,
        )

        template_dir = (
            Path(__file__).resolve().parents[3]
            / "app"
            / "runtime"
            / "payroll"
            / "templates"
        )
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("template_bulletin.html")
        html = template.render(bulletin)

        assert html.strip()
        assert "Montant net social" in html or "MONTANT NET SOCIAL" in html
        assert "service-public.fr" in html
        assert bulletin["en_tete"]["entreprise"]["raison_sociale"] in html
        for code, _ in RUBRIQUES_ORDRE[:3]:
            rub = next(
                (r for r in bulletin["cotisations_officielles"] if r["code"] == code),
                None,
            )
            if rub:
                assert rub["libelle"] in html
