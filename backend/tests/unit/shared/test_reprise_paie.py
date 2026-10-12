"""Bascule de reprise : ce qui doit être refusé, et ce qui doit passer."""

from datetime import date
from unittest.mock import patch

import pytest as _pytest


@_pytest.fixture(autouse=True)
def _sans_date_d_entree(monkeypatch):
    """Pas de base en test unitaire : la date d'entrée se passe en paramètre."""
    from app.shared import reprise_paie

    monkeypatch.setattr(reprise_paie, "_date_entree", lambda _e: None)

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

    def test_une_entree_en_septembre_n_exige_pas_le_cumul_d_aout(self):
        assert (
            raison_de_cumul_manquant(
                "soc", "emp", 2026, 9, False, date_entree=date(2026, 9, 21)
            )
            is None
        )

    def test_premier_bulletin_d_un_salarie_part_de_zero_sans_bascule(self):
        with patch("app.shared.reprise_paie.lire_bascule", return_value=None), patch(
            "app.shared.reprise_paie._un_bulletin_existe_avant", return_value=False
        ), patch("app.shared.reprise_paie.historique_de_paie_avant_martine", return_value=None):
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


class TestFinDeLaRepriseAuPremierMois:
    def test_le_premier_mois_calcule_connait_le_dernier_jour_paye_par_l_ancien_logiciel(self):
        from datetime import date

        from app.shared.reprise_paie import fin_de_la_reprise_au_premier_mois

        assert fin_de_la_reprise_au_premier_mois(None, 2026, 7, bascule=BASCULE_JUIN) == date(2026, 6, 30)

    def test_ni_les_mois_repris_ni_les_suivants(self):
        from app.shared.reprise_paie import fin_de_la_reprise_au_premier_mois

        assert fin_de_la_reprise_au_premier_mois(None, 2026, 6, bascule=BASCULE_JUIN) is None
        assert fin_de_la_reprise_au_premier_mois(None, 2026, 8, bascule=BASCULE_JUIN) is None

    def test_la_bascule_de_decembre_ouvre_janvier(self):
        from datetime import date

        from app.shared.reprise_paie import Bascule, fin_de_la_reprise_au_premier_mois

        decembre = Bascule(annee=2025, mois=12)
        assert fin_de_la_reprise_au_premier_mois(None, 2026, 1, bascule=decembre) == date(2025, 12, 31)


class TestPremierBulletinApresLaBascule:
    """Une embauche postérieure au mois précédent n'a rien à chaîner (29/09/2026) :
    une embauche de septembre, après une bascule au 31/08, était refusée faute de
    « solde d'ouverture » que l'ancien logiciel n'a jamais eu à produire."""

    def test_une_embauche_de_septembre_n_est_pas_bloquee(self):
        from datetime import date

        bascule = Bascule(annee=2026, mois=8)
        assert raison_de_cumul_manquant(
            None, "emp", 2026, 9, False, bascule=bascule, date_entree=date(2026, 9, 15)
        ) is None

    def test_un_salarie_present_a_la_bascule_reste_bloque_sans_son_solde(self):
        from datetime import date

        bascule = Bascule(annee=2026, mois=8)
        raison = raison_de_cumul_manquant(
            None, "emp", 2026, 9, False, bascule=bascule, date_entree=date(2026, 8, 24)
        )
        assert raison is not None and "solde d'ouverture" in raison

    def test_une_embauche_d_octobre_n_a_pas_de_chaine_rompue(self):
        from datetime import date

        bascule = Bascule(annee=2026, mois=8)
        assert raison_de_cumul_manquant(
            None, "emp", 2026, 10, False, bascule=bascule, date_entree=date(2026, 10, 1)
        ) is None


class TestHistoriqueAvantMartineSansReprise:
    """[B12] Une société dont la paie se faisait ailleurs (DSN importées, bulletins
    repris), sans bascule ni solde d'ouverture : son premier bulletin partait de
    zéro, sans un mot. Cartol, Mont-Blanc et LEWIS, 206 salariés actifs au 12/10.
    Rejoué sur septembre de Colorplast, un départ à zéro fausse la réduction
    générale de 7 à 266 € par salarié et ampute une fin de CDD de 776 € nets."""

    HISTORIQUE = "DSN importées de 01/2026 à 06/2026"

    def _raison(self, *, date_entree=None, historique=HISTORIQUE, bulletin_avant=False):
        with patch("app.shared.reprise_paie.lire_bascule", return_value=None), patch(
            "app.shared.reprise_paie._un_bulletin_existe_avant", return_value=bulletin_avant
        ), patch(
            "app.shared.reprise_paie.historique_de_paie_avant_martine", return_value=historique
        ):
            return raison_de_cumul_manquant(
                "soc", "emp", 2026, 10, False, date_entree=date_entree
            )

    def test_le_premier_bulletin_est_refuse_et_le_message_dit_quoi_faire(self):
        raison = self._raison(date_entree=date(2019, 3, 4))
        assert raison is not None
        assert "avant Martine" in raison
        assert self.HISTORIQUE in raison
        assert "09/2026" in raison
        assert "solde d'ouverture" in raison
        assert "bascule" in raison

    def test_sans_date_d_entree_lisible_la_garde_reste_entiere(self):
        assert self._raison(date_entree=None) is not None

    def test_une_embauche_posterieure_au_mois_precedent_part_de_zero(self):
        """Embauché en octobre : rien à reprendre, l'ancien logiciel ne l'a jamais payé."""
        assert self._raison(date_entree=date(2026, 10, 1)) is None

    def test_une_societe_sans_historique_part_de_zero_comme_avant(self):
        assert self._raison(date_entree=date(2019, 3, 4), historique=None) is None

    def test_une_chaine_rompue_garde_son_propre_message(self):
        raison = self._raison(date_entree=date(2019, 3, 4), bulletin_avant=True)
        assert raison is not None and "chaîne des cumuls est rompue" in raison

    def test_une_societe_avec_bascule_garde_ses_messages(self):
        """Colorplast et Comitech : la bascule décide, l'historique n'ajoute rien."""
        with patch(
            "app.shared.reprise_paie.historique_de_paie_avant_martine", return_value=self.HISTORIQUE
        ):
            raison = raison_de_cumul_manquant(
                "soc", "emp", 2026, 9, False, bascule=Bascule(2026, 8, "bulletins", "Quadra"),
                date_entree=date(2019, 3, 4),
            )
        assert raison is not None and "Le solde d'ouverture de la reprise (08/2026)" in raison
        assert "avant Martine" not in raison


class TestLectureDeLHistoriqueAvantMartine:
    def _faux(self, *, siren="534386495", lots=(), importes=()):
        """Un faux client qui répond selon la table interrogée."""
        from unittest.mock import MagicMock

        def table(nom):
            t = MagicMock()
            chaine = t.select.return_value
            for _ in range(4):
                chaine.eq.return_value = chaine
                chaine.in_.return_value = chaine
                chaine.order.return_value = chaine
                chaine.limit.return_value = chaine
            donnees = {
                "companies": [{"siren": siren}] if siren else [],
                "dsn_import_batches": list(lots),
                "payslips": list(importes),
            }[nom]
            chaine.execute.return_value.data = donnees
            return t

        faux = MagicMock()
        faux.table.side_effect = table
        return faux

    def test_des_lots_dsn_valides_sont_un_historique(self):
        from app.shared.reprise_paie import historique_de_paie_avant_martine

        lots = [
            {"period_min": "2026-01", "period_max": "2026-03"},
            {"period_min": "2026-04", "period_max": "2026-06"},
        ]
        with patch("app.shared.reprise_paie.supabase", self._faux(lots=lots)):
            assert historique_de_paie_avant_martine("soc") == "DSN importées de 01/2026 à 06/2026"

    def test_des_bulletins_repris_sont_un_historique(self):
        from app.shared.reprise_paie import historique_de_paie_avant_martine

        with patch(
            "app.shared.reprise_paie.supabase",
            self._faux(importes=[{"year": 2026, "month": 8}]),
        ):
            assert historique_de_paie_avant_martine("soc") == "bulletins repris de l'ancien logiciel"

    def test_ni_lot_ni_bulletin_repris_pas_d_historique(self):
        from app.shared.reprise_paie import historique_de_paie_avant_martine

        with patch("app.shared.reprise_paie.supabase", self._faux()):
            assert historique_de_paie_avant_martine("soc") is None

    def test_une_base_injoignable_ne_bloque_pas_la_paie(self):
        from app.shared.reprise_paie import historique_de_paie_avant_martine

        with patch("app.shared.reprise_paie.supabase") as faux:
            faux.table.side_effect = RuntimeError("table absente")
            assert historique_de_paie_avant_martine("soc") is None
