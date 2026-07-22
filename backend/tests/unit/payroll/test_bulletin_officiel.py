"""Tests bulletin de paie — format officiel (MNS, rubriques, template)."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from app.modules.payroll.engine.bulletin import (
    _calculer_cout_total_employeur,
    creer_bulletin_final,
)
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
        """La part patronale mutuelle n'entre pas dans le MNS (aligné Cegid) ;
        elle reste réintégrée au net imposable (cf. _calculer_net_imposable)."""
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
        assert mns == pytest.approx(2000.0 - total_sal, abs=0.01)
        assert any(l.get("coti_id") == "mutuelle" for l in lignes)


class TestCoutTotalEmployeur:
    def test_sans_participation_brut_plus_charges_patronales(self):
        cout = _calculer_cout_total_employeur(
            2444.33,
            468.02,
            [],
            [],
        )
        assert cout == pytest.approx(2912.35, abs=0.01)

    def test_avec_participation_et_acompte_non_retenu_sur_masse(self):
        """Référence Cegid COTTE mai 2026 : brut + pat + participation − acompte."""
        brut_lines = [
            {
                "libelle": "Participation 2025 — numéraire (brut, exonéré de cotisations)",
                "gain": 3225.33,
            }
        ]
        primes = [
            {
                "libelle": "Acompte participation 2025 (déjà versé)",
                "montant": -1000.0,
            }
        ]
        cout = _calculer_cout_total_employeur(2444.33, 468.02, primes, brut_lines)
        assert cout == pytest.approx(5137.68, abs=0.01)

    def test_rappel_ijss_net_n_augmente_pas_le_cout_employeur(self):
        primes = [
            {
                "libelle": "IJSS nettes (rappel)",
                "montant": 38.15,
                "is_rappel_ijss": True,
            }
        ]

        cout = _calculer_cout_total_employeur(2356.03, 704.01, primes, [])

        assert cout == pytest.approx(3060.04, abs=0.01)

    def test_indemnite_activite_partielle_augmente_le_cout_employeur(self):
        revenus_remplacement = [
            {
                "prime_id": "indemnite_activite_partielle",
                "libelle": "Indemnité activité partielle",
                "montant": 533.12,
            }
        ]

        cout = _calculer_cout_total_employeur(
            1520.75,
            480.94,
            [],
            [],
            revenus_remplacement,
        )

        assert cout == pytest.approx(2534.81, abs=0.01)

    def test_mns_utilise_montant_net_social_pour_net_avant_impot(self):
        ctx = build_test_contexte(salaire_base=2444.33)
        nets = {
            "net_social": 1954.81,
            "montant_net_social": 3867.29,
            "net_imposable": 4763.79,
            "net_a_payer": 3767.25,
            "montant_impot_pas": 100.04,
        }
        bulletin = creer_bulletin_final(ctx, 2444.33, [], [], nets, [], 2026, 5)
        assert bulletin["synthese_net"]["net_social_avant_impot"] == pytest.approx(
            3867.29, abs=0.01
        )


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
        assert bulletin["en_tete"]["salarie"]["classification"] == "275"
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

    def test_pas_alerte_net_superieur_brut_si_participation_numeraire(self):
        ctx = build_test_contexte(salaire_base=1000.0)
        nets = {
            "net_a_payer": 1800.0,
            "net_imposable": 1750.0,
            "montant_net_social": 1780.0,
            "impot_prelevement_a_la_source": 0.0,
        }
        details_brut = [
            {
                "libelle": "Participation 2025 — numéraire (brut, exonéré de cotisations)",
                "gain": 1000.0,
                "is_informative": True,
            }
        ]

        bulletin = creer_bulletin_final(
            ctx, 1000.0, details_brut, [], nets, [], 2026, 5
        )

        codes = [a.get("code") for a in bulletin.get("alertes_baremes") or []]
        assert "net_superieur_brut" not in codes

    def test_pas_alerte_net_superieur_brut_si_participation_forfait(self):
        ctx = build_test_contexte(salaire_base=3984.0)
        nets = {
            "net_a_payer": 6722.64,
            "net_imposable": 8500.0,
            "montant_net_social": 6700.0,
            "impot_prelevement_a_la_source": 0.0,
            "participations": [
                {
                    "libelle": "Participation 2025 — numéraire",
                    "brut": 5818.27,
                    "part_pee": 0.0,
                }
            ],
        }

        bulletin = creer_bulletin_final(
            ctx, 3984.0, [], [], nets, [], 2026, 5
        )

        codes = [a.get("code") for a in bulletin.get("alertes_baremes") or []]
        assert "net_superieur_brut" not in codes
        assert bulletin["participations"][0]["brut"] == 5818.27

    def test_pas_alerte_net_superieur_brut_si_activite_partielle(self):
        ctx = build_test_contexte(salaire_base=1520.75)
        nets = {
            "net_a_payer": 1661.11,
            "net_imposable": 1764.48,
            "montant_net_social": 1661.11,
            "impot_prelevement_a_la_source": 0.0,
        }
        revenus_remplacement = [
            {
                "prime_id": "indemnite_activite_partielle",
                "libelle": "Indemnité activité partielle",
                "montant": 533.12,
            }
        ]

        bulletin = creer_bulletin_final(
            ctx,
            1520.75,
            [],
            [],
            nets,
            [],
            2026,
            6,
            primes_soumises_impot=revenus_remplacement,
        )

        codes = [a.get("code") for a in bulletin.get("alertes_baremes") or []]
        assert "net_superieur_brut" not in codes
        assert bulletin["revenus_hors_brut_imposables"] == revenus_remplacement

    def test_pas_alerte_net_superieur_brut_si_frais_pro_hors_brut(self):
        ctx = build_test_contexte(salaire_base=125.65)
        nets = {
            "net_a_payer": 244.23,
            "net_imposable": 146.05,
            "montant_net_social": 94.23,
            "impot_prelevement_a_la_source": 0.0,
            "acompte_verse": -150.0,
        }

        bulletin = creer_bulletin_final(
            ctx, 125.65, [], [], nets, [], 2026, 6
        )

        codes = [a.get("code") for a in bulletin.get("alertes_baremes") or []]
        assert "net_superieur_brut" not in codes

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
