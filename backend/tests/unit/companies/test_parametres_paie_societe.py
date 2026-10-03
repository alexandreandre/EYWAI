"""Réglages de paie de la société saisis à l'écran « Paramètres de paie ».

Quatre réglages, lus par le moteur, n'avaient aucun écran et ont été posés par
script : le taux d'assurance chômage notifié (bonus-malus), l'effectif retenu
pour les seuils, la date de paiement et la journée de solidarité. La
gestionnaire de paie doit pouvoir les régler seule, par le même PATCH
/api/company/details que le taux AT/MP : même permission, trace d'audit, et
fusion dans `settings` sans toucher aux autres clés.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.security import get_current_user
from app.main import app
from app.modules.companies.application import commands
from app.modules.companies.schemas.requests import CompanyDetailsUpdate
from app.modules.users.schemas.responses import CompanyAccess, User

pytestmark = pytest.mark.unit

_SOCIETE = "aaaaaaaa-2222-2222-2222-222222222222"
_COMMANDES = "app.modules.companies.application.commands"


# ----- Validation du corps de requête -----


class TestTauxAssuranceChomage:
    @pytest.mark.parametrize("taux", [2.95, 4.0, 5.0, "3.4"])
    def test_un_taux_dans_les_bornes_du_bonus_malus_passe(self, taux):
        corps = CompanyDetailsUpdate(taux_assurance_chomage=taux)
        assert corps.to_update_dict() == {"taux_assurance_chomage": float(taux)}

    @pytest.mark.parametrize("taux", [2.94, 0, 5.01, 5.05, -1])
    def test_hors_des_bornes_il_est_refuse_en_disant_lesquelles(self, taux):
        with pytest.raises(ValidationError) as exc:
            CompanyDetailsUpdate(taux_assurance_chomage=taux)
        message = exc.value.errors()[0]["msg"]
        assert "2,95 %" in message and "5 %" in message
        assert not message.startswith("Value error")

    def test_un_texte_qui_n_est_pas_un_nombre_est_refuse_en_francais(self):
        with pytest.raises(ValidationError) as exc:
            CompanyDetailsUpdate(taux_assurance_chomage="beaucoup")
        assert "nombre" in exc.value.errors()[0]["msg"]

    def test_null_explicite_demande_le_retour_au_taux_normal(self):
        corps = CompanyDetailsUpdate(taux_assurance_chomage=None)
        assert corps.to_update_dict() == {"taux_assurance_chomage": None}

    def test_absent_du_corps_il_ne_change_rien(self):
        assert CompanyDetailsUpdate(phone="0102030405").to_update_dict() == {
            "phone": "0102030405"
        }


class TestEffectif:
    @pytest.mark.parametrize("effectif", [0, 1, 19, 250])
    def test_un_entier_positif_ou_nul_passe(self, effectif):
        assert CompanyDetailsUpdate(effectif=effectif).to_update_dict() == {
            "effectif": effectif
        }

    @pytest.mark.parametrize("effectif", [-1, 12.5, "douze"])
    def test_negatif_ou_non_entier_il_est_refuse(self, effectif):
        with pytest.raises(ValidationError) as exc:
            CompanyDetailsUpdate(effectif=effectif)
        assert "entier" in exc.value.errors()[0]["msg"]

    def test_il_ne_peut_pas_etre_vide(self):
        """Le moteur compare l'effectif aux seuils : vide, il ne saurait pas
        calculer. On refuse plutôt que d'ignorer en silence."""
        with pytest.raises(ValidationError) as exc:
            CompanyDetailsUpdate(effectif=None)
        assert "entier" in exc.value.errors()[0]["msg"]


class TestDatePaiement:
    @pytest.mark.parametrize("choix", ["dernier_jour_du_mois", "arrete_des_variables"])
    def test_les_deux_choix_du_moteur_passent(self, choix):
        assert CompanyDetailsUpdate(date_paiement=choix).to_update_dict() == {
            "date_paiement": choix
        }

    def test_un_autre_choix_est_refuse(self):
        with pytest.raises(ValidationError) as exc:
            CompanyDetailsUpdate(date_paiement="le_15")
        assert "Dernier jour du mois" in exc.value.errors()[0]["msg"]

    def test_null_explicite_revient_au_comportement_historique(self):
        assert CompanyDetailsUpdate(date_paiement=None).to_update_dict() == {
            "date_paiement": None
        }

    def test_les_choix_sont_ceux_que_le_moteur_connait(self):
        from app.modules.companies.domain.parametres_paie import DATES_PAIEMENT
        from app.modules.payroll.engine.bulletin import (
            DATE_PAIEMENT_ARRETE,
            DATE_PAIEMENT_DERNIER_JOUR,
        )

        assert set(DATES_PAIEMENT) == {DATE_PAIEMENT_DERNIER_JOUR, DATE_PAIEMENT_ARRETE}


class TestJourSolidarite:
    def test_une_date_iso_est_gardee_telle_quelle(self):
        assert CompanyDetailsUpdate(jour_solidarite="2026-05-25").to_update_dict() == {
            "jour_solidarite": "2026-05-25"
        }

    @pytest.mark.parametrize("saisie", ["2026-02-30", "25/05/2026", "lundi", 20260525])
    def test_une_date_invalide_est_refusee(self, saisie):
        with pytest.raises(ValidationError) as exc:
            CompanyDetailsUpdate(jour_solidarite=saisie)
        assert "date" in exc.value.errors()[0]["msg"]

    def test_null_explicite_retire_la_date(self):
        assert CompanyDetailsUpdate(jour_solidarite=None).to_update_dict() == {
            "jour_solidarite": None
        }


# ----- Écriture : fusion dans settings et audit -----


def _utilisateur(role: str = "rh") -> User:
    return User(
        id="bbbbbbbb-3333-3333-3333-333333333333",
        email="paie@societe-test.fr",
        first_name="Paula",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=_SOCIETE, company_name="Société test", role=role, is_primary=True)
        ],
        active_company_id=_SOCIETE,
    )


def _societe(**champs):
    ligne = {
        "id": _SOCIETE,
        "company_name": "Société test",
        "effectif": 19,
        "taux_at_mp": 3.15,
        "settings": {
            "dsn_import": {"organismes": [{"code": "X"}]},
            "compensation_heures_entre_semaines": True,
        },
    }
    ligne.update(champs)
    return ligne


def _depot(avant):
    depot = MagicMock()
    depot.get_by_id.return_value = avant

    def _ecrire(company_id, donnees):
        apres = dict(avant)
        apres.update(donnees)
        return apres

    depot.update_company.side_effect = _ecrire
    return depot


def _ecrire(update, avant=None, utilisateur=None):
    avant = avant or _societe()
    depot = _depot(avant)
    audit = MagicMock()
    with patch(f"{_COMMANDES}.company_repository", depot), patch(
        f"{_COMMANDES}.audit_repository", audit
    ):
        resultat = commands.update_company_details(_SOCIETE, update, utilisateur or _utilisateur())
    return resultat, depot, audit


class TestFusionDansSettings:
    def test_le_taux_chomage_rejoint_settings_sans_toucher_aux_autres_cles(self):
        _, depot, _ = _ecrire({"taux_assurance_chomage": 2.95})
        ecrit = depot.update_company.call_args[0][1]
        assert ecrit == {
            "settings": {
                "dsn_import": {"organismes": [{"code": "X"}]},
                "compensation_heures_entre_semaines": True,
                "taux_assurance_chomage": 2.95,
            }
        }

    def test_null_retire_la_cle_et_garde_les_autres(self):
        avant = _societe(
            settings={"taux_assurance_chomage": 2.95, "jour_solidarite": "2026-05-25", "x": 1}
        )
        _, depot, _ = _ecrire(
            {"taux_assurance_chomage": None, "jour_solidarite": None}, avant=avant
        )
        assert depot.update_company.call_args[0][1] == {"settings": {"x": 1}}

    def test_les_quatre_reglages_ensemble(self):
        _, depot, _ = _ecrire(
            {
                "effectif": 21,
                "taux_assurance_chomage": 4.2,
                "date_paiement": "dernier_jour_du_mois",
                "jour_solidarite": "2026-05-25",
            }
        )
        ecrit = depot.update_company.call_args[0][1]
        assert ecrit["effectif"] == 21
        assert ecrit["settings"]["taux_assurance_chomage"] == 4.2
        assert ecrit["settings"]["date_paiement"] == "dernier_jour_du_mois"
        assert ecrit["settings"]["jour_solidarite"] == "2026-05-25"
        assert ecrit["settings"]["compensation_heures_entre_semaines"] is True

    def test_sans_reglage_de_settings_la_colonne_settings_n_est_pas_reecrite(self):
        _, depot, _ = _ecrire({"effectif": 21})
        assert depot.update_company.call_args[0][1] == {"effectif": 21}

    def test_settings_absent_en_base(self):
        _, depot, _ = _ecrire({"date_paiement": "arrete_des_variables"}, avant=_societe(settings=None))
        assert depot.update_company.call_args[0][1] == {
            "settings": {"date_paiement": "arrete_des_variables"}
        }

    def test_la_valeur_relue_est_renvoyee(self):
        resultat, _, _ = _ecrire({"effectif": 21, "taux_assurance_chomage": 2.95})
        assert resultat["effectif"] == 21
        assert resultat["settings"]["taux_assurance_chomage"] == 2.95


class TestTraceAudit:
    def test_un_changement_laisse_une_trace_avant_apres(self):
        _, _, audit = _ecrire({"effectif": 21, "taux_assurance_chomage": 2.95})
        audit.log.assert_called_once()
        args = audit.log.call_args[0]
        assert args[0] == _SOCIETE
        assert args[1] == "bbbbbbbb-3333-3333-3333-333333333333"
        assert args[2] == "paie@societe-test.fr"
        assert args[3] == "company.update"
        assert args[4] == "company"
        assert args[5] == _SOCIETE
        assert args[6]["changements"] == {
            "effectif": {"avant": 19, "apres": 21},
            "taux_assurance_chomage": {"avant": None, "apres": 2.95},
        }

    def test_le_taux_at_mp_laisse_la_meme_trace(self):
        _, _, audit = _ecrire({"taux_at_mp": 3.4})
        assert audit.log.call_args[0][6]["changements"] == {
            "taux_at_mp": {"avant": 3.15, "apres": 3.4}
        }

    def test_renvoyer_les_memes_valeurs_n_ecrit_rien_et_ne_trace_rien(self):
        avant = _societe(taux_at_mp="3.15", settings={"date_paiement": "dernier_jour_du_mois"})
        _, depot, audit = _ecrire(
            {"effectif": 19, "taux_at_mp": 3.15, "date_paiement": "dernier_jour_du_mois"},
            avant=avant,
        )
        depot.update_company.assert_not_called()
        audit.log.assert_not_called()

    def test_retirer_une_cle_absente_ne_trace_rien(self):
        _, depot, audit = _ecrire({"jour_solidarite": None})
        depot.update_company.assert_not_called()
        audit.log.assert_not_called()

    def test_societe_introuvable(self):
        depot = MagicMock()
        depot.get_by_id.return_value = None
        with patch(f"{_COMMANDES}.company_repository", depot), patch(
            f"{_COMMANDES}.audit_repository", MagicMock()
        ), pytest.raises(LookupError):
            commands.update_company_details(_SOCIETE, {"effectif": 3}, _utilisateur())
        depot.update_company.assert_not_called()


# ----- Route : même permission que le taux AT/MP -----


@pytest.fixture
def client():
    def _client(role: str):
        app.dependency_overrides[get_current_user] = lambda: _utilisateur(role)
        return TestClient(app)

    try:
        yield _client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


_ROUTEUR = "app.modules.companies.api.router"


def _relecture(company_data):
    return MagicMock(company_data=company_data, kpis={})


class TestRoute:
    def test_un_collaborateur_ne_peut_rien_regler(self, client):
        with patch(f"{_ROUTEUR}.commands.update_company_details") as ecriture:
            reponse = client("collaborateur").patch(
                "/api/company/details", json={"taux_assurance_chomage": 2.95}
            )
        assert reponse.status_code == 403
        ecriture.assert_not_called()

    def test_un_rh_regle_les_quatre_et_relit_la_societe(self, client):
        relu = _societe(effectif=21, settings={"taux_assurance_chomage": 2.95})
        with patch(f"{_ROUTEUR}.commands.update_company_details") as ecriture, patch(
            f"{_ROUTEUR}.queries.get_company_details_and_kpis", return_value=_relecture(relu)
        ):
            reponse = client("rh").patch(
                "/api/company/details",
                json={
                    "effectif": 21,
                    "taux_assurance_chomage": 2.95,
                    "date_paiement": "dernier_jour_du_mois",
                    "jour_solidarite": None,
                },
            )
        assert reponse.status_code == 200
        envoye = ecriture.call_args[0][1]
        assert envoye == {
            "effectif": 21,
            "taux_assurance_chomage": 2.95,
            "date_paiement": "dernier_jour_du_mois",
            "jour_solidarite": None,
        }
        assert reponse.json()["company_data"]["settings"]["taux_assurance_chomage"] == 2.95

    def test_une_erreur_de_saisie_dit_quoi_corriger_sans_jargon(self, client):
        with patch(f"{_ROUTEUR}.commands.update_company_details") as ecriture:
            reponse = client("rh").patch(
                "/api/company/details", json={"taux_assurance_chomage": 6}
            )
        assert reponse.status_code == 422
        message = reponse.json()["detail"][0]["msg"]
        assert message.startswith("Le taux d'assurance chômage")
        ecriture.assert_not_called()
