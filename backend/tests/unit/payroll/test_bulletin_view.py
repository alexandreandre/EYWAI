"""Vue de présentation du bulletin — gabarit Cegid."""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.bulletin_view import (
    calculer_evolution_remuneration,
    _civilite,
    _date_fr,
    _formater_nir,
    construire_vue_bulletin,
)


def bulletin_minimal() -> dict:
    """Bulletin réduit aux clés que la vue consomme, calqué sur CARTOL juin 2026."""
    return {
        "en_tete": {
            "periode": "Juin 2026",
            "annee": 2026,
            "mois": 6,
            "date_paiement": "30/06/2026",
            "entreprise": {
                "raison_sociale": "Société CARTOL",
                "siret": "95147478200020",
                "naf_ape": "2562B",
                "adresse": {
                    "rue": "10 BOULEVARD GEORGES POMPIDOU",
                    "code_postal": "79140",
                    "ville": "CERIZAY",
                },
            },
            "salarie": {
                "nom": "ALVES",
                "prenom": "Lucas",
                "nom_complet": "Lucas ALVES",
                "sexe": "M",
                "matricule": "ALVES",
                "nir": "102098519123974",
                "adresse": {
                    "rue": "32 rue de la Fabrique",
                    "code_postal": "79250",
                    "ville": "NUEIL LES AUBIERS",
                },
                "mode_paiement": "virement",
                "emploi": "Opérateur polyvalent",
                "date_entree": "2026-04-08",
                "date_anciennete": "2026-04-08",
                "classification_brute": {"coefficient": "A"},
                "convention_collective": "Convention collective nationale de la métallurgie",
            },
        },
        "calcul_du_brut": [],
        "details_conges": [],
        "details_absences": [],
        "salaire_brut": 1436.21,
        "cotisations_officielles": [],
        "structure_cotisations": {"total_salarial": 0.0, "total_patronal": 0.0},
        "synthese_net": {},
        "primes_non_soumises": [],
        "net_a_payer": 910.64,
        "pied_de_page": {},
        "parametres": {"smic_horaire": 12.31, "pss_mensuel": 3337.50},
    }


class TestHelpers:
    def test_nir_groupe_comme_cegid(self):
        assert _formater_nir("102098519123974") == "1 02 09 85 191 239 74"

    def test_nir_non_standard_rendu_tel_quel(self):
        assert _formater_nir("12345") == "12345"

    def test_nir_absent_donne_chaine_vide(self):
        assert _formater_nir(None) == ""

    @pytest.mark.parametrize("valeur", ["M", "m", "H", "1"])
    def test_civilite_masculine(self, valeur):
        assert _civilite(valeur) == "MR"

    @pytest.mark.parametrize("valeur", ["F", "f", "2"])
    def test_civilite_feminine(self, valeur):
        assert _civilite(valeur) == "MME"

    def test_civilite_inconnue_absente(self):
        assert _civilite(None) is None
        assert _civilite("X") is None

    def test_date_iso_vers_francais(self):
        assert _date_fr("2026-04-08") == "08/04/2026"

    def test_date_absente_donne_chaine_vide(self):
        assert _date_fr(None) == ""


class TestBandeau:
    def test_bandeau_reprend_identification_entreprise(self):
        bandeau = construire_vue_bulletin(bulletin_minimal())["bandeau"]
        assert bandeau["raison_sociale"] == "Société CARTOL"
        assert bandeau["siret"] == "95147478200020"
        assert bandeau["naf_ape"] == "2562B"
        assert bandeau["adresse"] == [
            "10 BOULEVARD GEORGES POMPIDOU",
            "79140 CERIZAY",
        ]

    def test_date_de_paiement_en_francais(self):
        bulletin = bulletin_minimal()
        # Le moteur renvoie une date ISO (_calculer_date_paiement).
        bulletin["en_tete"]["date_paiement"] = "2026-06-30"
        bandeau = construire_vue_bulletin(bulletin)["bandeau"]
        assert bandeau["date_paiement"] == "30/06/2026"

    def test_bandeau_calcule_les_bornes_de_periode(self):
        bandeau = construire_vue_bulletin(bulletin_minimal())["bandeau"]
        assert bandeau["periode"] == "Juin 2026"
        assert bandeau["du"] == "01/06/2026"
        assert bandeau["au"] == "30/06/2026"

    def test_bandeau_sans_mois_n_invente_pas_de_bornes(self):
        bulletin = bulletin_minimal()
        del bulletin["en_tete"]["mois"]
        bandeau = construire_vue_bulletin(bulletin)["bandeau"]
        assert bandeau["du"] == ""
        assert bandeau["au"] == ""


class TestSalarieEtIdentite:
    def test_nom_precede_de_la_civilite_nom_en_premier(self):
        salarie = construire_vue_bulletin(bulletin_minimal())["salarie"]
        assert salarie["civilite"] == "MR"
        assert salarie["nom_ligne"] == "ALVES Lucas"

    def test_adresse_postale_sur_deux_lignes(self):
        salarie = construire_vue_bulletin(bulletin_minimal())["salarie"]
        assert salarie["adresse"] == ["32 rue de la Fabrique", "79250 NUEIL LES AUBIERS"]

    def test_identite_reprend_matricule_nir_et_emploi(self):
        identite = construire_vue_bulletin(bulletin_minimal())["identite"]
        assert identite["matricule"] == "ALVES"
        assert identite["nir"] == "1 02 09 85 191 239 74"
        assert identite["emploi"] == "Opérateur polyvalent"
        assert identite["date_entree"] == "08/04/2026"
        assert identite["coefficient"] == "A"

    def test_anciennete_se_replie_sur_la_date_d_entree(self):
        bulletin = bulletin_minimal()
        bulletin["en_tete"]["salarie"]["date_anciennete"] = None
        identite = construire_vue_bulletin(bulletin)["identite"]
        assert identite["anciennete"] == "08/04/2026"


def solde_conges_complet() -> dict:
    return {
        "date_reference": "30/06/2026",
        "conges_payes": {"periode": "2026-2027", "acquis": 2.08, "pris": 0.0, "solde": 2.08},
        "conges_payes_periode_precedente": {
            "periode": "2025-2026",
            "acquis": 4.0,
            "pris": 0.0,
            "solde": 4.0,
        },
        "rtt": {"acquis": 0.0, "pris": 0.0, "solde": 0.0},
        "repos_compensateur": {"acquis": 0.0, "pris": 0.0, "solde": 0.0},
        "cp_seniority_days": 0,
    }


class TestCompteurs:
    def test_colonnes_cp_dans_l_ordre_cegid(self):
        bulletin = bulletin_minimal()
        bulletin["pied_de_page"]["solde_conges"] = solde_conges_complet()
        compteurs = construire_vue_bulletin(bulletin)["compteurs"]
        assert [c["titre"] for c in compteurs["colonnes"]] == ["CP N-1", "CP N"]
        assert compteurs["colonnes"][0]["solde"] == 4.0
        assert compteurs["date_reference"] == "30/06/2026"

    def test_rtt_et_repos_ajoutes_seulement_s_ils_existent(self):
        bulletin = bulletin_minimal()
        solde = solde_conges_complet()
        solde["rtt"] = {"acquis": 10.0, "pris": 2.0, "solde": 8.0}
        solde["repos_compensateur"] = {"acquis": 3.0, "pris": 0.0, "solde": 3.0}
        bulletin["pied_de_page"]["solde_conges"] = solde
        compteurs = construire_vue_bulletin(bulletin)["compteurs"]
        assert [c["titre"] for c in compteurs["colonnes"]] == [
            "CP N-1",
            "CP N",
            "RTT",
            "Repos comp.",
        ]

    def test_cp_periode_precedente_vide_masquee(self):
        bulletin = bulletin_minimal()
        solde = solde_conges_complet()
        solde["conges_payes_periode_precedente"] = {"acquis": 0.0, "pris": 0.0, "solde": 0.0}
        bulletin["pied_de_page"]["solde_conges"] = solde
        compteurs = construire_vue_bulletin(bulletin)["compteurs"]
        assert [c["titre"] for c in compteurs["colonnes"]] == ["CP N"]

    def test_notes_annexes_reprises_en_bas_du_bloc(self):
        bulletin = bulletin_minimal()
        solde = solde_conges_complet()
        solde["cp_seniority_days"] = 2
        solde["fractionnement"] = {
            "jours_acquis": 1,
            "libelle": "1 jour de fractionnement",
            "reference_date": "31/05/2026",
        }
        bulletin["pied_de_page"]["solde_conges"] = solde
        compteurs = construire_vue_bulletin(bulletin)["compteurs"]
        assert any("fractionnement" in note for note in compteurs["notes"])
        assert any("ancienneté" in note for note in compteurs["notes"])

    def test_sans_solde_de_conges_pas_de_bloc(self):
        assert construire_vue_bulletin(bulletin_minimal())["compteurs"] is None


def bulletin_avec_cotisations() -> dict:
    bulletin = bulletin_minimal()
    bulletin["calcul_du_brut"] = [
        {
            "libelle": "SALAIRE DE BASE",
            "quantite": 151.67,
            "taux": 12.31,
            "gain": 1867.06,
            "perte": None,
        }
    ]
    bulletin["cotisations_officielles"] = [
        {
            "code": "sante",
            "libelle": "Santé",
            "lignes": [
                {
                    "libelle": "Sécu.Soc-Mal.Mater.Inval.Déc.",
                    "base": 1436.21,
                    "taux_salarial": None,
                    "montant_salarial": 0.0,
                    "taux_patronal": 0.07,
                    "montant_patronal": 100.53,
                }
            ],
            "total_salarial": 0.0,
            "total_patronal": 100.53,
        },
        {
            "code": "retraite",
            "libelle": "Retraite",
            "lignes": [
                {
                    "libelle": "Sécu.Soc Plafonnée",
                    "base": 1436.21,
                    "taux_salarial": 0.069,
                    "montant_salarial": 99.10,
                    "taux_patronal": 0.0855,
                    "montant_patronal": 122.80,
                }
            ],
            "total_salarial": 99.10,
            "total_patronal": 122.80,
        },
        {
            "code": "csg_non_deductible",
            "libelle": "CSG/CRDS non déductible",
            "lignes": [
                {
                    "libelle": "CSG/CRDS non déductible à l'IR",
                    "base": 1457.66,
                    "taux_salarial": 0.029,
                    "montant_salarial": 42.27,
                    "taux_patronal": None,
                    "montant_patronal": 0.0,
                }
            ],
            "total_salarial": 42.27,
            "total_patronal": 0.0,
        },
    ]
    bulletin["synthese_net"] = {"net_imposable": 1128.07}
    return bulletin


def _libelles(lignes, type_ligne=None):
    return [
        ligne["libelle"]
        for ligne in lignes
        if type_ligne is None or ligne["type"] == type_ligne
    ]


class TestCorps:
    def test_ordre_general_du_corps(self):
        lignes = construire_vue_bulletin(bulletin_avec_cotisations())["lignes"]
        libelles = _libelles(lignes)
        assert libelles.index("SALAIRE DE BASE") < libelles.index("SALAIRE BRUT")
        assert libelles.index("SALAIRE BRUT") < libelles.index("SANTÉ")
        assert libelles.index("SANTÉ") < libelles.index("TOTAL DES RETENUES")
        assert libelles.index("TOTAL DES RETENUES") < libelles.index("NET IMPOSABLE")

    def test_codes_cegid_sur_les_rubriques(self):
        lignes = construire_vue_bulletin(bulletin_avec_cotisations())["lignes"]
        rubriques = {
            ligne["libelle"]: ligne["code"]
            for ligne in lignes
            if ligne["type"] == "rubrique"
        }
        assert rubriques["SANTÉ"] == "Q100"
        assert rubriques["RETRAITE"] == "Q300"
        assert rubriques["CSG/CRDS NON DÉDUCTIBLE À L'IR"] == "Q801"

    def test_csg_non_deductible_apres_le_net_imposable(self):
        lignes = construire_vue_bulletin(bulletin_avec_cotisations())["lignes"]
        libelles = _libelles(lignes)
        assert libelles.index("NET IMPOSABLE") < libelles.index(
            "CSG/CRDS NON DÉDUCTIBLE À L'IR"
        )

    def test_total_des_retenues_exclut_la_csg_non_deductible(self):
        lignes = construire_vue_bulletin(bulletin_avec_cotisations())["lignes"]
        total = next(l for l in lignes if l["libelle"] == "TOTAL DES RETENUES")
        assert total["montant_salarial"] == pytest.approx(99.10)
        assert total["montant_patronal"] == pytest.approx(223.33)

    def test_prevoyance_sans_code_cegid(self):
        bulletin = bulletin_avec_cotisations()
        bulletin["cotisations_officielles"].append(
            {
                "code": "cotisations_statutaires",
                "libelle": "Cotisations statutaires et conventionnelles",
                "lignes": [
                    {
                        "libelle": "PRÉVOYANCE",
                        "base": 1436.21,
                        "taux_salarial": 0.0118,
                        "montant_salarial": 16.95,
                        "taux_patronal": 0.0118,
                        "montant_patronal": 16.95,
                    }
                ],
                "total_salarial": 16.95,
                "total_patronal": 16.95,
            }
        )
        lignes = construire_vue_bulletin(bulletin)["lignes"]
        rubrique = next(
            l for l in lignes if l["libelle"].startswith("COTISATIONS STATUTAIRES")
        )
        assert rubrique["code"] is None

    def test_notes_de_frais_agregees_en_une_ligne(self):
        bulletin = bulletin_avec_cotisations()
        bulletin["notes_de_frais"] = [
            {"libelle": "Péage", "montant": 12.40},
            {"libelle": "Repas", "montant": 18.00},
        ]
        lignes = construire_vue_bulletin(bulletin)["lignes"]
        frais = [l for l in lignes if "frais professionnels" in l["libelle"].lower()]
        assert len(frais) == 1
        assert frais[0]["montant_salarial"] == pytest.approx(30.40)
        assert "Péage" not in _libelles(lignes)

    def test_primes_non_soumises_apres_le_net_imposable(self):
        bulletin = bulletin_avec_cotisations()
        bulletin["primes_non_soumises"] = [
            {"libelle": "INDEMNITÉ DE PANIER", "montant": 20.0}
        ]
        libelles = _libelles(construire_vue_bulletin(bulletin)["lignes"])
        assert libelles.index("NET IMPOSABLE") < libelles.index("INDEMNITÉ DE PANIER")

    def test_retenues_sur_le_net_reprises_en_lignes(self):
        bulletin = bulletin_avec_cotisations()
        bulletin["remboursements_avances"] = {"total_rembourse": 150.0}
        bulletin["retenues_saisies"] = {"total_preleve": 40.0}
        bulletin["remboursements_prets"] = {"total_rembourse": 60.0}
        lignes = construire_vue_bulletin(bulletin)["lignes"]
        montants = {l["libelle"]: l["montant_salarial"] for l in lignes}
        # Négatives : ce sont des retenues sur le net.
        assert montants["Acomptes et avances"] == pytest.approx(-150.0)
        assert montants["Retenues sur salaire"] == pytest.approx(-40.0)
        assert montants["Remboursement prêt employeur"] == pytest.approx(-60.0)


class TestColonneLaterale:
    def _vue(self):
        bulletin = bulletin_minimal()
        bulletin["cumuls"] = {
            "periode": {"annee_en_cours": 2026},
            "cumuls": {
                "brut_total": 4788.07,
                "net_imposable": 3621.64,
                "impot_preleve_a_la_source": 420.57,
                "heures_remunerees": 392.49,
                "heures_supplementaires_remunerees": 12.15,
            },
        }
        bulletin["pied_de_page"] = {
            "cout_total_employeur": 1649.98,
            "total_exonerations": 544.13,
        }
        return construire_vue_bulletin(bulletin)["lateral"]

    def _bloc(self, titre):
        return next(bloc for bloc in self._vue() if bloc["titre"] == titre)

    def test_smic_et_plafond_affiches(self):
        valeurs = {v["libelle"]: v["valeur"] for v in self._bloc("BARÈMES")["valeurs"]}
        assert valeurs["SMIC horaire"] == "12,31"
        assert valeurs["Plafond Sécu"] == "3 337,50"

    def test_bloc_heures(self):
        valeurs = {v["libelle"]: v["valeur"] for v in self._bloc("HEURES")["valeurs"]}
        assert valeurs["Cumul heures"] == "392,49"
        assert valeurs["Cumul h. sup"] == "12,15"

    def test_bloc_cumuls_et_cout_employeur(self):
        valeurs = {v["libelle"]: v["valeur"] for v in self._bloc("CUMULS")["valeurs"]}
        assert valeurs["Bruts"] == "4 788,07"
        assert valeurs["Allègement cotis. employeur"] == "544,13"
        assert valeurs["Total versé employeur"] == "1 649,98"

    def test_mode_de_paiement(self):
        valeurs = {v["libelle"]: v["valeur"] for v in self._bloc("PAIEMENT")["valeurs"]}
        assert valeurs["Mode"] == "par Virement"

    def test_blocs_vides_absents(self):
        titres = [
            bloc["titre"] for bloc in construire_vue_bulletin(bulletin_minimal())["lateral"]
        ]
        assert "HEURES" not in titres
        assert "CUMULS" not in titres


class TestEvolutionRemuneration:
    """Mention obligatoire art. R3243-1, absente de notre bulletin jusqu'ici."""

    def test_valeur_du_bulletin_cartol_alves_juin_2026(self):
        # 1436,21 x 3,15 % - 1457,66 x 1,7 % = 45,24 - 24,78 = 20,46
        assert calculer_evolution_remuneration(1436.21, 1457.66) == pytest.approx(20.46)

    def test_jamais_negative(self):
        assert calculer_evolution_remuneration(100.0, 10000.0) == 0.0

    def test_sans_base_csg_repli_sur_le_brut(self):
        assert calculer_evolution_remuneration(1000.0, 0.0) == pytest.approx(14.5)


class TestPied:
    def _bulletin(self):
        bulletin = bulletin_avec_cotisations()
        bulletin["synthese_net"] = {
            "net_imposable": 1128.07,
            "montant_net_social": 1105.80,
            "net_social_avant_impot": 1105.80,
            "impot_prelevement_a_la_source": {
                "base": 1128.07,
                "taux": 17.30,
                "montant": 195.16,
            },
        }
        bulletin["cumuls"] = {
            "periode": {"annee_en_cours": 2026},
            "cumuls": {
                "net_imposable": 3621.64,
                "impot_preleve_a_la_source": 420.57,
            },
        }
        bulletin["net_a_payer"] = 910.64
        bulletin["pied_de_page"]["mentions_legales"] = {
            "conservation": "Conservez ce bulletin sans limitation de durée.",
            "information": "Pour en savoir plus : www.service-public.fr",
        }
        return bulletin

    def test_nets_et_net_a_payer(self):
        pied = construire_vue_bulletin(self._bulletin())["pied"]
        assert pied["montant_net_social"] == pytest.approx(1105.80)
        assert pied["net_avant_impot"] == pytest.approx(1105.80)
        assert pied["net_a_payer"] == pytest.approx(910.64)

    def test_mention_evolution_remuneration_presente(self):
        pied = construire_vue_bulletin(self._bulletin())["pied"]
        assert pied["evolution_remuneration"] == pytest.approx(20.46)

    def test_tableau_impot_avec_cumuls(self):
        impot = construire_vue_bulletin(self._bulletin())["pied"]["impot"]
        assert impot["taux"] == pytest.approx(17.30)
        assert impot["montant"] == pytest.approx(195.16)
        assert impot["cumul_net_imposable"] == pytest.approx(3621.64)
        assert impot["cumul_impot"] == pytest.approx(420.57)

    def test_mentions_legales_et_convention(self):
        pied = construire_vue_bulletin(self._bulletin())["pied"]
        assert any("service-public.fr" in m for m in pied["mentions_legales"])
        assert "métallurgie" in pied["convention_collective"]

    def test_rectification_signalee_discretement(self):
        bulletin = self._bulletin()
        bulletin["manually_edited"] = True
        bulletin["edited_at"] = "02/08/2026 à 14:30"
        pied = construire_vue_bulletin(bulletin)["pied"]
        assert pied["rectification"] == "Bulletin rectifié le 02/08/2026 à 14:30"

    def test_sans_rectification_pas_de_mention(self):
        assert construire_vue_bulletin(self._bulletin())["pied"]["rectification"] == ""


def _rendre(bulletin: dict) -> str:
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader

    template_dir = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "runtime"
        / "payroll"
        / "templates"
    )
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    return env.get_template("template_bulletin.html").render(
        vue=construire_vue_bulletin(bulletin)
    )


class TestRendu:
    def test_le_gabarit_affiche_les_zones_attendues(self):
        html = _rendre(bulletin_avec_cotisations())
        for attendu in (
            "BULLETIN DE SALAIRE",
            "Société CARTOL",
            "ALVES Lucas",
            "Matricule",
            "1 02 09 85 191 239 74",
            "Q100",
            "SANTÉ",
            "TOTAL DES RETENUES",
            "NET IMPOSABLE",
            "Net à payer au salarié",
        ):
            assert attendu in html, f"{attendu} absent du rendu"

    def test_ordre_des_zones(self):
        html = _rendre(bulletin_avec_cotisations())
        assert html.index("BULLETIN DE SALAIRE") < html.index("Matricule")
        assert html.index("Matricule") < html.index("TOTAL DES RETENUES")
        assert html.index("TOTAL DES RETENUES") < html.index("Net à payer au salarié")

    def test_aucune_section_vide_sans_donnees(self):
        html = _rendre(bulletin_minimal())
        assert "CUMULS" not in html
        assert "Solde de congés" not in html


class TestFideliteColonnes:
    """Le gabarit Cegid laisse vide ce qui ne concerne pas la colonne."""

    def test_cotisation_purement_patronale_sans_taux_salarial(self):
        lignes = construire_vue_bulletin(bulletin_avec_cotisations())["lignes"]
        ligne = next(l for l in lignes if l["libelle"].startswith("Sécu.Soc-Mal"))
        assert ligne["taux"] is None
        assert ligne["montant_salarial"] is None
        assert ligne["montant_patronal"] == pytest.approx(100.53)

    def test_montant_patronal_nul_laisse_vide(self):
        lignes = construire_vue_bulletin(bulletin_avec_cotisations())["lignes"]
        ligne = next(l for l in lignes if l["libelle"].startswith("CSG/CRDS"))
        assert ligne["montant_patronal"] is None


class TestNoteArbitrageConges:
    """La règle retenue pour l'indemnité de CP reste affichée (elle l'était avant)."""

    def test_arbitrage_affiche_en_ligne_de_note(self):
        bulletin = bulletin_avec_cotisations()
        bulletin["arbitrage_conges"] = (
            "L'indemnité de congés payés a été calculée selon la règle du 1/10ème."
        )
        lignes = construire_vue_bulletin(bulletin)["lignes"]
        note = next(l for l in lignes if l["type"] == "note")
        assert "1/10ème" in note["libelle"]
        libelles = [l["libelle"] for l in lignes]
        assert libelles.index(note["libelle"]) < libelles.index("SALAIRE BRUT")

    def test_sans_arbitrage_aucune_ligne_de_note(self):
        lignes = construire_vue_bulletin(bulletin_avec_cotisations())["lignes"]
        assert not [l for l in lignes if l["type"] == "note"]


class TestRepliAcompte:
    """Sans enrichissement saisies/avances, l'acompte ne subsiste que dans la synthèse."""

    def test_acompte_repris_depuis_la_synthese_des_nets(self):
        bulletin = bulletin_avec_cotisations()
        bulletin["synthese_net"]["acompte_verse"] = 300.0
        lignes = construire_vue_bulletin(bulletin)["lignes"]
        acompte = next(l for l in lignes if l["libelle"] == "Acomptes et avances")
        assert acompte["montant_salarial"] == pytest.approx(-300.0)

    def test_enrichissement_prioritaire_sur_la_synthese(self):
        bulletin = bulletin_avec_cotisations()
        bulletin["synthese_net"]["acompte_verse"] = 300.0
        bulletin["remboursements_avances"] = {"total_rembourse": 150.0}
        lignes = construire_vue_bulletin(bulletin)["lignes"]
        acompte = next(l for l in lignes if l["libelle"] == "Acomptes et avances")
        assert acompte["montant_salarial"] == pytest.approx(-150.0)


class TestClassificationReelle:
    """Les vraies fiches portent des clés DSN, pas « niveau » ni « coefficient »."""

    def test_repli_sur_la_classification_formatee_par_le_moteur(self):
        bulletin = bulletin_minimal()
        salarie = bulletin["en_tete"]["salarie"]
        # Cas réel ALVES (Cartol) : aucune des clés attendues par le gabarit.
        salarie["classification_brute"] = {
            "pcs": "9999",
            "idcc": "3248",
            "position": "200",
            "niveau_dsn": "2 A",
            "statut_categoriel": "Cadre",
            "libelle_emploi": "Opérateur polyvalent",
        }
        salarie["classification"] = "200"
        identite = construire_vue_bulletin(bulletin)["identite"]
        assert identite["classification"] == "2 A"
        # `statut_categoriel` contredit `employees.statut` sur 212 fiches :
        # ne rien afficher plutôt qu'un statut faux (Cegid laisse vide aussi).
        assert identite["qualification"] == ""

    def test_sans_niveau_dsn_on_reprend_la_chaine_du_moteur(self):
        bulletin = bulletin_minimal()
        bulletin["en_tete"]["salarie"]["classification_brute"] = {"position": "200"}
        bulletin["en_tete"]["salarie"]["classification"] = "200"
        identite = construire_vue_bulletin(bulletin)["identite"]
        assert identite["classification"] == "200"

    def test_coefficient_explicite_prioritaire(self):
        identite = construire_vue_bulletin(bulletin_minimal())["identite"]
        assert identite["coefficient"] == "A"
