"""
Non-régression — calculer_salaire_brut() et creer_bulletin_final() (Ticket 4 étape A).

Contexte mocké via types.SimpleNamespace (pas d’instanciation ContextePaie / Supabase).
Les montants attendus reflètent le comportement actuel du moteur (mars 2025, 35 h, 2500 €).
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.bulletin import creer_bulletin_final
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.contexte import ChargerContexte, ContextePaie


def _weekdays_march_2025() -> list[date]:
    """Jours ouvrés du 1er au 31 mars 2025 (21 jours)."""
    out: list[date] = []
    d = date(2025, 3, 1)
    while d <= date(2025, 3, 31):
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _baremes_minimal() -> dict:
    return {
        "heures_supp": {
            "regles_calcul_communes": {
                "taux_majoration_par_defaut": {
                    "heures_supplementaires": [
                        {"taux": 0.25},
                        {"taux": 0.50},
                    ]
                }
            }
        },
        "cotisations": {},
        "smic": {},
        "pss": {"annuel": 48000.0},
        "frais_pro": {},
        "primes": [],
        "conventions_collectives": {},
    }


def _proprietes_du_contexte_reel() -> set[str]:
    """Noms des propriétés portées par le VRAI ContextePaie."""
    return {
        nom for nom, valeur in vars(ContextePaie).items() if isinstance(valeur, property)
    }


def _make_contexte_mock() -> SimpleNamespace:
    """Fausse fiche de paie, construite sur la surface RÉELLE de ContextePaie.

    Chaque propriété du contexte réel DOIT recevoir une valeur ici, et
    `test_la_fausse_fiche_suit_le_contrat_reel` échoue si ce n'est plus le
    cas. C'est précisément ce qui a manqué : le moteur a gagné des champs
    (`heures_sup_du_mois`, `heures_sup_du_mois_50`…) que cette fiche n'a pas
    suivis, et les quatre tests de non-régression du brut mouraient sur un
    AttributeError avant même d'atteindre leurs comparaisons de montants.
    Ils sont restés gelés du 7 au 23 août : plus aucun montant de référence
    n'était vérifié sur le cœur du moteur.
    """
    return SimpleNamespace(
        salaire_base_mensuel=2500.0,
        duree_hebdo_contrat=35.0,
        statut_salarie="Non-Cadre",
        statut_categoriel_dsn="",
        effectif=10,
        baremes=_baremes_minimal(),
        # --- Éléments variables du mois : aucun, pour isoler le brut de base
        saisie_du_mois={},
        primes_du_mois={},
        heures_sup_du_mois=0.0,
        heures_sup_du_mois_50=0.0,
        heures_absence_du_mois=0.0,
        cumuls_annee_precedente={"brut_reference_n_1": 0.0},
        # --- SMIC de référence (mars 2025) et dates du contrat
        smic_horaire=11.88,
        smic_mensuel=round(11.88 * 35 * 52 / 12, 2),
        date_entree="2020-01-01",
        date_anciennete_prime="2020-01-01",
        date_conclusion_contrat="2020-01-01",
        date_debut_execution="2020-01-01",
        date_fin_contrat="",
        date_naissance="1985-06-15",
        # --- Situations particulières : toutes fausses pour ce scénario
        is_alsace_moselle=False,
        is_forfait_jour=False,
        is_mandataire=False,
        is_personnel_rd_eligible_jei=False,
        is_professionnalisation=False,
        is_stagiaire=False,
        contrat={
            "contrat": {
                "date_entree": "2020-01-01",
                "statut": "Non-Cadre",
                "temps_travail": {"duree_hebdomadaire": 35.0},
                "emploi": "Employé test",
            },
            "remuneration": {
                "salaire_de_base": {"valeur": 2500.0},
                "avantages_en_nature": {},
                "convention_collective": {},
                "classification_conventionnelle": {},
            },
            "salarie": {"prenom": "Jean", "nom": "Dupont", "nir": ""},
            "specificites_paie": {"prelevement_a_la_source": {"taux": 0.0}},
            "saisie_du_mois": {},
        },
        entreprise={
            "parametres_paie": {},
            "identification": {
                "raison_sociale": "ACME SA",
                "siret": "12345678901234",
                "adresse": "1 rue du Test",
            },
        },
        cumuls={"cumuls": {"brut_reference_n_1": 0.0}},
        is_cdd=False,
        est_dernier_mois_cdd=lambda *_args, **_kwargs: False,
        is_interim=False,
        est_dernier_mois_mission=lambda *_args, **_kwargs: False,
        is_apprenti=False,
        is_alternant=False,
        type_contrat="CDI",
    )


def _periode_mars_2025() -> tuple[date, date]:
    return date(2025, 3, 1), date(2025, 3, 31)


def _heures_journalieres_21j() -> float:
    return round(151.67 / 21, 4)


# --- Références capturées sur le moteur actuel (2025-03) ---

SALAIRE_BRUT_TOTAL_S1 = 2500.0
REMUNERATION_HS_S1 = 0.0

SALAIRE_BRUT_TOTAL_S2 = 2261.9
PERTE_ABSENCE_S2 = 119.05  # par jour d’absence non rémunérée

SALAIRE_BRUT_TOTAL_S3 = 2582.42
REMUNERATION_HS_S3 = 82.42
GAIN_HS25_S3 = 82.42

SALAIRE_BRUT_TOTAL_S4 = 2500.0
RETENUE_CP_S4 = 576.91


def test_imports_contexte_symbols_exist():
    assert ContextePaie is not None
    assert callable(ChargerContexte)


class TestCalculerSalaireBrutNonRegression:
    def test_scenario_1_mois_complet_sans_absence(self):
        wd = _weekdays_march_2025()
        assert len(wd) == 21
        h = _heures_journalieres_21j()
        calendrier = [
            {"date_complete": d.isoformat(), "type": "travail_base", "heures": h}
            for d in wd[:21]
        ]
        ctx = _make_contexte_mock()
        d0, d1 = _periode_mars_2025()
        r = calculer_salaire_brut(ctx, calendrier, d0, d1)

        assert r["salaire_brut_total"] == pytest.approx(SALAIRE_BRUT_TOTAL_S1, abs=0.02)
        assert r["remuneration_brute_heures_supp"] == pytest.approx(
            REMUNERATION_HS_S1, abs=0.02
        )
        lignes = r["lignes_composants_brut"]
        salaire_base = [L for L in lignes if L.get("libelle") == "Salaire de base"]
        assert len(salaire_base) == 1
        assert salaire_base[0]["gain"] == pytest.approx(2500.0, abs=0.02)

    def test_scenario_2_absence_non_remuneree_deux_jours(self):
        wd = _weekdays_march_2025()
        h = _heures_journalieres_21j()
        calendrier = [
            {"date_complete": d.isoformat(), "type": "travail_base", "heures": h}
            for d in wd[:19]
        ]
        calendrier += [
            {"date_complete": d.isoformat(), "type": "absence_non_remuneree", "heures": h}
            for d in wd[19:21]
        ]
        ctx = _make_contexte_mock()
        d0, d1 = _periode_mars_2025()
        r = calculer_salaire_brut(ctx, calendrier, d0, d1)

        assert r["salaire_brut_total"] == pytest.approx(SALAIRE_BRUT_TOTAL_S2, abs=0.02)
        assert r["salaire_brut_total"] < 2500.0
        absences = [
            L
            for L in r["lignes_composants_brut"]
            if "Absence non rémunérée" in (L.get("libelle") or "")
        ]
        assert len(absences) == 2
        for L in absences:
            assert (L.get("perte") or 0) == pytest.approx(PERTE_ABSENCE_S2, abs=0.02)
            assert (L.get("perte") or 0) > 0

    def test_scenario_3_heures_supplementaires_25(self):
        wd = _weekdays_march_2025()
        h = _heures_journalieres_21j()
        calendrier = [
            {"date_complete": d.isoformat(), "type": "travail_base", "heures": h}
            for d in wd[:20]
        ]
        dernier = wd[20]
        calendrier.append(
            {
                "date_complete": dernier.isoformat(),
                "type": "travail_base",
                "heures": round(151.67 - 20 * h, 4),
            }
        )
        calendrier.append(
            {"date_complete": dernier.isoformat(), "type": "travail_hs25", "heures": 4.0}
        )
        ctx = _make_contexte_mock()
        d0, d1 = _periode_mars_2025()
        r = calculer_salaire_brut(ctx, calendrier, d0, d1)

        assert r["salaire_brut_total"] == pytest.approx(SALAIRE_BRUT_TOTAL_S3, abs=0.02)
        assert r["remuneration_brute_heures_supp"] == pytest.approx(
            REMUNERATION_HS_S3, abs=0.02
        )
        hs_lines = [
            L
            for L in r["lignes_composants_brut"]
            if "Heures suppl. majorées à 25%" in (L.get("libelle") or "")
        ]
        assert len(hs_lines) == 1
        assert hs_lines[0]["gain"] == pytest.approx(GAIN_HS25_S3, abs=0.02)

    def test_scenario_4_conges_payes_cinq_jours(self):
        wd = _weekdays_march_2025()
        h = _heures_journalieres_21j()
        calendrier = [
            {"date_complete": d.isoformat(), "type": "travail_base", "heures": h}
            for d in wd[:16]
        ]
        calendrier += [
            {"date_complete": d.isoformat(), "type": "conges_payes", "heures": h}
            for d in wd[16:21]
        ]
        ctx = _make_contexte_mock()
        d0, d1 = _periode_mars_2025()
        r = calculer_salaire_brut(ctx, calendrier, d0, d1)

        assert r["salaire_brut_total"] == pytest.approx(SALAIRE_BRUT_TOTAL_S4, abs=0.02)
        assert r["salaire_brut_total"] > 0
        cp = [
            L
            for L in r["lignes_composants_brut"]
            if "Absence congés payés" in (L.get("libelle") or "")
        ]
        assert len(cp) == 1
        assert (cp[0].get("perte") or 0) == pytest.approx(RETENUE_CP_S4, abs=0.02)


class TestCreerBulletinFinalNonRegression:
    def test_assemblage_scenario_1(self):
        ctx = _make_contexte_mock()
        d0, d1 = _periode_mars_2025()
        wd = _weekdays_march_2025()
        h = _heures_journalieres_21j()
        calendrier = [
            {"date_complete": d.isoformat(), "type": "travail_base", "heures": h}
            for d in wd[:21]
        ]
        brut = calculer_salaire_brut(ctx, calendrier, d0, d1)
        nets = {"net_a_payer": 1950.0, "net_social": 2000.0, "net_imposable": 1980.0}
        bulletin = creer_bulletin_final(
            ctx,
            brut["salaire_brut_total"],
            brut["lignes_composants_brut"],
            [],
            nets,
            [],
            2025,
            3,
        )
        assert bulletin["salaire_brut"] == pytest.approx(SALAIRE_BRUT_TOTAL_S1, abs=0.02)
        assert bulletin["en_tete"]["periode"] == "Mars 2025"
        assert bulletin["en_tete"]["entreprise"]["raison_sociale"] == "ACME SA"
        assert len(bulletin["calcul_du_brut"]) >= 1
        assert bulletin["details_conges"] == []
        assert bulletin["net_a_payer"] == pytest.approx(1950.0, abs=0.02)

    def test_assemblage_scenario_4_conges_dans_details_conges(self):
        ctx = _make_contexte_mock()
        d0, d1 = _periode_mars_2025()
        wd = _weekdays_march_2025()
        h = _heures_journalieres_21j()
        calendrier = [
            {"date_complete": d.isoformat(), "type": "travail_base", "heures": h}
            for d in wd[:16]
        ]
        calendrier += [
            {"date_complete": d.isoformat(), "type": "conges_payes", "heures": h}
            for d in wd[16:21]
        ]
        brut = calculer_salaire_brut(ctx, calendrier, d0, d1)
        bulletin = creer_bulletin_final(
            ctx,
            brut["salaire_brut_total"],
            brut["lignes_composants_brut"],
            [],
            {"net_a_payer": 1900.0},
            [],
            2025,
            3,
        )
        assert bulletin["salaire_brut"] == pytest.approx(SALAIRE_BRUT_TOTAL_S4, abs=0.02)
        assert len(bulletin["details_conges"]) >= 1
        assert any(
            "cong" in (L.get("libelle") or "").lower()
            for L in bulletin["details_conges"]
        )


class TestFausseFicheSuitLeContratReel:
    """Garde anti-dérive.

    Le 7 août, le moteur a gagné des propriétés que la fausse fiche de paie
    de ce fichier n'a pas suivies. Les quatre tests de non-régression du brut
    sont alors morts sur un AttributeError — avant leurs comparaisons de
    montants — et ont été gelés dans known_failures.txt. Résultat : plus
    aucun montant de référence n'était vérifié sur le calcul du brut pendant
    seize jours, sans que rien ne le signale.

    Ce test compare la surface de la fausse fiche à celle du VRAI contexte :
    une propriété ajoutée au moteur fait échouer la CI, avec le nom du champ
    à renseigner.
    """

    def test_toutes_les_proprietes_du_contexte_ont_une_valeur(self):
        attendues = _proprietes_du_contexte_reel()
        posees = set(vars(_make_contexte_mock()))
        manquantes = sorted(attendues - posees)
        assert not manquantes, (
            "Le contexte de paie a gagné des propriétés que la fausse fiche "
            "de ce fichier ne pose pas — les tests de non-régression du brut "
            "mourraient dessus sans vérifier un seul montant. À renseigner "
            f"dans _make_contexte_mock : {', '.join(manquantes)}"
        )

    def test_la_fausse_fiche_n_invente_pas_de_champ(self):
        """L'inverse : un champ posé ici qui n'existe plus côté moteur
        signale une valeur devenue morte, donc un test qui n'exerce plus
        ce qu'il croit exercer."""
        proprietes = _proprietes_du_contexte_reel()
        # Les attributs d'instance et les fonctions utilitaires ne sont pas
        # des propriétés : on ne les compare pas.
        tolerees = {
            "baremes", "contrat", "entreprise", "cumuls",
            "est_dernier_mois_cdd", "est_dernier_mois_mission",
        }
        posees = set(vars(_make_contexte_mock())) - tolerees
        inventees = sorted(posees - proprietes)
        assert not inventees, (
            "Champs posés par la fausse fiche mais absents du contexte réel "
            f"— valeurs mortes : {', '.join(inventees)}"
        )
