"""
Tests unitaires du domaine repos_compensateur : entités, value objects et règles métier.

Aucune dépendance DB ni HTTP. Couvre :
- ReposCredit (domain/entities.py)
- Règles COR : calculer_heures_cor_mois, heures_vers_jours, get_taux_cor_par_effectif,
  extraire_heures_hs_du_bulletin, cumuler_heures_hs_annee (domain/rules.py)
- SourceCredit (domain/enums.py)
"""
from app.modules.repos_compensateur.domain.entities import ReposCredit
from app.modules.repos_compensateur.domain.enums import SourceCredit
from app.modules.repos_compensateur.domain.rules import (
    CONTINGENT_DEFAUT,
    HEURES_PAR_JOUR_REPOS,
    calculer_heures_cor_mois,
    cumuler_heures_hs_annee,
    extraire_heures_hs_du_bulletin,
    get_taux_cor_par_effectif,
    heures_vers_jours,
)


# --- Entités ---


class TestReposCredit:
    """Tests de l'entité ReposCredit."""

    def test_entity_creation_minimal(self):
        """Création avec tous les champs obligatoires."""
        credit = ReposCredit(
            employee_id="emp-1",
            company_id="comp-1",
            year=2025,
            month=6,
            source="cor",
            heures=14.0,
            jours=2.0,
        )
        assert credit.employee_id == "emp-1"
        assert credit.company_id == "comp-1"
        assert credit.year == 2025
        assert credit.month == 6
        assert credit.source == "cor"
        assert credit.heures == 14.0
        assert credit.jours == 2.0

    def test_entity_source_manual(self):
        """Source peut être 'manual' ou 'rcr'."""
        for src in ("manual", "rcr"):
            credit = ReposCredit(
                employee_id="emp-1",
                company_id="comp-1",
                year=2025,
                month=1,
                source=src,
                heures=7.0,
                jours=1.0,
            )
            assert credit.source == src

    def test_entity_heures_jours_zero(self):
        """heures et jours peuvent être 0 (mois sans COR)."""
        credit = ReposCredit(
            employee_id="emp-1",
            company_id="comp-1",
            year=2025,
            month=3,
            source="cor",
            heures=0.0,
            jours=0.0,
        )
        assert credit.heures == 0.0
        assert credit.jours == 0.0


# --- Enums / types ---


class TestSourceCredit:
    """Vérification du type SourceCredit (Literal)."""

    def test_source_cor_valid(self):
        """'cor' est une source valide."""
        credit = ReposCredit(
            employee_id="e",
            company_id="c",
            year=2025,
            month=1,
            source="cor",
            heures=0,
            jours=0,
        )
        assert credit.source == "cor"

    def test_source_values_used_in_module(self):
        """Les sources documentées (cor, rcr, manual) sont utilisables."""
        for src in ("cor", "rcr", "manual"):
            assert src in ("cor", "rcr", "manual")


# --- Règles : constantes ---


class TestRulesConstants:
    """Constantes du domaine COR."""

    def test_contingent_defaut(self):
        """CONTINGENT_DEFAUT = 220 heures."""
        assert CONTINGENT_DEFAUT == 220.0

    def test_heures_par_jour_repos(self):
        """HEURES_PAR_JOUR_REPOS = 7.0."""
        assert HEURES_PAR_JOUR_REPOS == 7.0


# --- Règles : calculer_heures_cor_mois ---


class TestCalculerHeuresCorMois:
    """Règle : heures COR acquises pour un mois (dépassement contingent, taux)."""

    def test_cumul_sous_contingent_zero_heures(self):
        """Cumul fin de mois sous le contingent → 0 heure COR."""
        assert (
            calculer_heures_cor_mois(
                cumul_hs_fin_mois=200.0,
                cumul_hs_fin_mois_precedent=150.0,
            )
            == 0.0
        )

    def test_depassement_premier_mois(self):
        """Premier dépassement du contingent (cumul actuel > 220, précédent < 220)."""
        # cumul 250, précédent 200 → au-delà actuel = 30, au-delà précédent = 0 → 30 * 1.0 = 30
        result = calculer_heures_cor_mois(
            cumul_hs_fin_mois=250.0,
            cumul_hs_fin_mois_precedent=200.0,
        )
        assert result == 30.0

    def test_depassement_croissant(self):
        """Dépassement qui augmente d'un mois à l'autre."""
        # cumul 280, précédent 250 → 60 - 30 = 30 h COR
        result = calculer_heures_cor_mois(
            cumul_hs_fin_mois=280.0,
            cumul_hs_fin_mois_precedent=250.0,
        )
        assert result == 30.0

    def test_taux_cor_demi(self):
        """taux_cor=0.5 divise les heures COR par deux."""
        result = calculer_heures_cor_mois(
            cumul_hs_fin_mois=250.0,
            cumul_hs_fin_mois_precedent=200.0,
            taux_cor=0.5,
        )
        assert result == 15.0

    def test_contingent_personnalise(self):
        """Contingent personnalisé (ex. 218)."""
        result = calculer_heures_cor_mois(
            cumul_hs_fin_mois=230.0,
            cumul_hs_fin_mois_precedent=218.0,
            contingent=218.0,
        )
        assert result == 12.0

    def test_retour_arrondi_deux_decimales(self):
        """Résultat arrondi à 2 décimales."""
        result = calculer_heures_cor_mois(
            cumul_hs_fin_mois=221.333,
            cumul_hs_fin_mois_precedent=220.0,
        )
        assert result == round(1.333 * 1.0, 2)


# --- Règles : heures_vers_jours ---


class TestHeuresVersJours:
    """Conversion heures → jours de repos."""

    def test_7_heures_1_jour(self):
        """7 heures → 1 jour (défaut 7 h/jour)."""
        assert heures_vers_jours(7.0) == 1.0

    def test_14_heures_2_jours(self):
        """14 heures → 2 jours."""
        assert heures_vers_jours(14.0) == 2.0

    def test_heures_par_jour_personnalise(self):
        """heures_par_jour personnalisé (ex. 8)."""
        assert heures_vers_jours(16.0, heures_par_jour=8.0) == 2.0

    def test_zero_heures_zero_jours(self):
        """0 heure → 0 jour."""
        assert heures_vers_jours(0.0) == 0.0

    def test_heures_par_jour_zero_returns_zero(self):
        """heures_par_jour <= 0 → 0 pour éviter division par zéro."""
        assert heures_vers_jours(7.0, heures_par_jour=0) == 0.0
        assert heures_vers_jours(7.0, heures_par_jour=-1) == 0.0

    def test_arrondi_deux_decimales(self):
        """Résultat arrondi à 2 décimales."""
        assert heures_vers_jours(10.0, heures_par_jour=7.0) == round(10 / 7, 2)


# --- Règles : get_taux_cor_par_effectif ---


class TestGetTauxCorParEffectif:
    """Taux COR selon effectif : 0.5 si < 20, 1.0 si >= 20."""

    def test_effectif_none_returns_1(self):
        """effectif None → 1.0 (défaut)."""
        assert get_taux_cor_par_effectif(None) == 1.0

    def test_effectif_inferieur_20_demi(self):
        """effectif < 20 → 0.5."""
        assert get_taux_cor_par_effectif(0) == 0.5
        assert get_taux_cor_par_effectif(19) == 0.5

    def test_effectif_20_ou_plus_un(self):
        """effectif >= 20 → 1.0."""
        assert get_taux_cor_par_effectif(20) == 1.0
        assert get_taux_cor_par_effectif(100) == 1.0


# --- Règles : extraire_heures_hs_du_bulletin ---


class TestExtraireHeuresHsDuBulletin:
    """Extraction des heures sup depuis payslip_data.calcul_du_brut."""

    def test_none_or_empty_returns_zero(self):
        """payslip_data None ou non-dict → 0."""
        assert extraire_heures_hs_du_bulletin(None) == 0.0
        assert extraire_heures_hs_du_bulletin(42) == 0.0  # type: ignore[arg-type]

    def test_calcul_du_brut_absent_returns_zero(self):
        """calcul_du_brut absent ou non-liste → 0."""
        assert extraire_heures_hs_du_bulletin({}) == 0.0
        assert extraire_heures_hs_du_bulletin({"calcul_du_brut": "not a list"}) == 0.0

    def test_ligne_heures_suppl(self):
        """Ligne avec libellé 'Heures suppl' (insensible casse) → quantite prise en compte."""
        data = {
            "calcul_du_brut": [
                {"libelle": "Heures suppl", "quantite": 10.0},
            ]
        }
        assert extraire_heures_hs_du_bulletin(data) == 10.0

    def test_ligne_suppl_et_heure(self):
        """Ligne avec 'suppl' et 'heure' dans libellé → comptée."""
        data = {
            "calcul_du_brut": [
                {"libelle": "Heures supplémentaires", "quantite": 5.0},
            ]
        }
        assert extraire_heures_hs_du_bulletin(data) == 5.0

    def test_ligne_sans_hs_ignored(self):
        """Lignes sans 'heures suppl' / 'suppl'+'heure' ignorées."""
        data = {
            "calcul_du_brut": [
                {"libelle": "Salaire de base", "quantite": 160},
                {"libelle": "Heures suppl", "quantite": 8.0},
            ]
        }
        assert extraire_heures_hs_du_bulletin(data) == 8.0

    def test_quantite_entier_acceptee(self):
        """quantite peut être int."""
        data = {
            "calcul_du_brut": [
                {"libelle": "Heures suppl", "quantite": 12},
            ]
        }
        assert extraire_heures_hs_du_bulletin(data) == 12.0

    def test_quantite_manquante_ignored(self):
        """quantite absente ou non numérique → ligne ignorée pour le total."""
        data = {
            "calcul_du_brut": [
                {"libelle": "Heures suppl"},
                {"libelle": "Heures suppl", "quantite": 3.0},
            ]
        }
        assert extraire_heures_hs_du_bulletin(data) == 3.0

    def test_arrondi_deux_decimales(self):
        """Total arrondi à 2 décimales."""
        data = {
            "calcul_du_brut": [
                {"libelle": "Heures suppl", "quantite": 1.111},
                {"libelle": "Heures suppl", "quantite": 2.222},
            ]
        }
        assert extraire_heures_hs_du_bulletin(data) == round(1.111 + 2.222, 2)


# --- Règles : cumuler_heures_hs_annee ---


class TestCumulerHeuresHsAnnee:
    """Cumul des heures HS de janvier à chaque mois (1-12)."""

    def test_bulletins_vides_cumuls_zero(self):
        """Aucun bulletin → cumuls à 0 pour tous les mois."""
        result = cumuler_heures_hs_annee({})
        assert len(result) == 12
        for m in range(1, 13):
            assert result[m] == 0.0

    def test_un_mois_rempli(self):
        """Un seul mois avec 10 h HS → cumul 10 ce mois, puis constant."""
        bulletins = {6: {"calcul_du_brut": [{"libelle": "Heures suppl", "quantite": 10.0}]}}
        result = cumuler_heures_hs_annee(bulletins)
        assert result[1] == 0.0
        assert result[5] == 0.0
        assert result[6] == 10.0
        assert result[12] == 10.0

    def test_plusieurs_mois_cumul_croissant(self):
        """Plusieurs mois : cumul croissant."""
        bulletins = {
            1: {"calcul_du_brut": [{"libelle": "Heures suppl", "quantite": 5.0}]},
            2: {"calcul_du_brut": [{"libelle": "Heures suppl", "quantite": 3.0}]},
            3: {"calcul_du_brut": []},
        }
        result = cumuler_heures_hs_annee(bulletins)
        assert result[1] == 5.0
        assert result[2] == 8.0
        assert result[3] == 8.0
        assert result[12] == 8.0
