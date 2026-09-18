"""Bascule de reprise : ce qui doit être refusé, et ce qui doit passer."""

from unittest.mock import patch

from app.shared.reprise_paie import (
    Bascule,
    lire_bascule,
    mois_precedent,
    raison_de_blocage_avant_bascule,
    raison_de_cumul_manquant,
    rang_du_mois,
)

BASCULE_JUIN = Bascule(annee=2026, mois=6, source="bulletins", logiciel_precedent="Quadra")


class TestArithmetiqueDesMois:
    def test_le_rang_ordonne_deux_mois_a_travers_l_annee(self):
        assert rang_du_mois(2026, 12) < rang_du_mois(2027, 1)

    def test_mois_precedent_franchit_l_annee(self):
        assert mois_precedent(2027, 1) == (2026, 12)
        assert mois_precedent(2026, 7) == (2026, 6)

    def test_premier_mois_calcule_apres_une_bascule_de_decembre(self):
        assert Bascule(2026, 12).premier_mois_calcule == (2027, 1)

    def test_la_bascule_couvre_son_propre_mois(self):
        assert BASCULE_JUIN.couvre(2026, 6)
        assert BASCULE_JUIN.couvre(2026, 1)
        assert not BASCULE_JUIN.couvre(2026, 7)


class TestRefusDeCalculerLePasse:
    def test_un_mois_avant_la_bascule_est_refuse_et_la_raison_nomme_la_reprise(self):
        raison = raison_de_blocage_avant_bascule(None, 2026, 3, bascule=BASCULE_JUIN)
        assert raison is not None
        assert "03/2026" in raison
        assert "Quadra" in raison
        assert "07/2026" in raison

    def test_le_mois_de_bascule_lui_meme_est_refuse(self):
        assert raison_de_blocage_avant_bascule(None, 2026, 6, bascule=BASCULE_JUIN)

    def test_le_premier_mois_calcule_passe(self):
        assert raison_de_blocage_avant_bascule(None, 2026, 7, bascule=BASCULE_JUIN) is None

    def test_sans_bascule_aucun_mois_n_est_refuse(self):
        with patch("app.shared.reprise_paie.lire_bascule", return_value=None):
            assert raison_de_blocage_avant_bascule("soc", 2026, 3) is None


class TestCumulManquant:
    def test_un_cumul_present_ne_bloque_jamais(self):
        assert (
            raison_de_cumul_manquant(None, "emp", 2026, 7, True, bascule=BASCULE_JUIN)
            is None
        )

    def test_solde_d_ouverture_absent_au_premier_mois_calcule(self):
        raison = raison_de_cumul_manquant(None, "emp", 2026, 7, False, bascule=BASCULE_JUIN)
        assert raison is not None
        assert "solde d'ouverture" in raison
        assert "06/2026" in raison

    def test_chaine_rompue_apres_la_bascule(self):
        raison = raison_de_cumul_manquant(None, "emp", 2026, 9, False, bascule=BASCULE_JUIN)
        assert raison is not None
        assert "chaîne des cumuls est rompue" in raison
        assert "08/2026" in raison

    def test_janvier_suivant_une_bascule_exige_le_cumul_de_decembre(self):
        raison = raison_de_cumul_manquant(None, "emp", 2027, 1, False, bascule=BASCULE_JUIN)
        assert raison is not None
        assert "12/2026" in raison

    def test_premier_bulletin_d_un_salarie_part_de_zero_sans_bascule(self):
        with patch("app.shared.reprise_paie.lire_bascule", return_value=None), patch(
            "app.shared.reprise_paie._un_bulletin_existe_avant", return_value=False
        ):
            assert raison_de_cumul_manquant("soc", "emp", 2026, 5, False) is None

    def test_sans_bascule_un_bulletin_anterieur_rend_le_cumul_obligatoire(self):
        with patch("app.shared.reprise_paie.lire_bascule", return_value=None), patch(
            "app.shared.reprise_paie._un_bulletin_existe_avant", return_value=True
        ):
            raison = raison_de_cumul_manquant("soc", "emp", 2026, 5, False)
            assert raison is not None
            assert "04/2026" in raison


class TestLectureDeLaBascule:
    def test_sans_societe_pas_de_bascule(self):
        assert lire_bascule(None) is None

    def test_une_base_injoignable_ne_bloque_pas_la_paie(self):
        with patch("app.shared.reprise_paie.supabase") as faux:
            faux.table.side_effect = RuntimeError("table absente")
            assert lire_bascule("soc") is None

    def test_une_bascule_mal_formee_est_ignoree(self):
        with patch("app.shared.reprise_paie.supabase") as faux:
            reponse = faux.table.return_value.select.return_value.eq.return_value
            reponse.maybe_single.return_value.execute.return_value.data = {
                "cutoff_year": "pas une annee",
                "cutoff_month": 6,
            }
            assert lire_bascule("soc") is None

    def test_une_bascule_lue_porte_sa_source_et_son_logiciel(self):
        with patch("app.shared.reprise_paie.supabase") as faux:
            reponse = faux.table.return_value.select.return_value.eq.return_value
            reponse.maybe_single.return_value.execute.return_value.data = {
                "cutoff_year": 2026,
                "cutoff_month": 6,
                "source": "dsn",
                "previous_software": "Quadra",
                "note": "reprise Colorplast",
            }
            bascule = lire_bascule("soc")
            assert bascule == Bascule(2026, 6, "dsn", "Quadra", "reprise Colorplast")
