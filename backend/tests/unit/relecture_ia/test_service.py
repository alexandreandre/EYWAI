"""Le service bout à bout, sur la base en mémoire et un faux relecteur."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.modules.relecture_ia.application import service
from app.modules.relecture_ia.domain.fiche import code_salarie
from app.modules.relecture_ia.infrastructure.client_claude import (
    ReponseRelecture,
    RelectureImpossible,
)
from app.modules.relecture_ia.infrastructure.repository import DepotRelecture
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

SOCIETE = "11111111-1111-1111-1111-111111111111"
AUTRE = "22222222-2222-2222-2222-222222222222"
SOCIETES = [{"company_id": SOCIETE, "nom": "Alpha"}, {"company_id": AUTRE, "nom": "Beta"}]
MAJ = "2026-11-01T10:00:00+00:00"


def _donnees(brut=2500.0, nom="Testeur"):
    return {
        "en_tete": {"salarie": {"nom": nom, "prenom": "Alix", "nir": "1 84 12 75 108 234 56"}},
        "calcul_du_brut": [{"libelle": "Salaire de base", "gain": brut}],
        "salaire_brut": brut,
        "net_a_payer": 1900.0,
    }


def _bulletin(i: int, company=SOCIETE, annee=2026, mois=10, kind=None, data=None):
    return {
        "id": f"p{i}",
        "company_id": company,
        "employee_id": f"e{i}",
        "year": annee,
        "month": mois,
        "contract_period_id": None,
        "bulletin_kind": kind,
        "updated_at": MAJ,
        "payslip_data": data if data is not None else _donnees(),
    }


def _base(*bulletins):
    return BaseEnMemoire(
        {
            "payslips": list(bulletins),
            "employees": [
                {
                    "id": b["employee_id"],
                    "first_name": "Alix",
                    "last_name": "Testeur",
                    "duree_hebdomadaire": 35.0,
                    "is_forfait_jour": False,
                }
                for b in bulletins
            ],
            "relectures_ia": [],
            "relectures_ia_bulletins": [],
            "relectures_ia_vus": [],
            "relecture_ia_regles": [],
        }
    )


class FauxRelecteur:
    def __init__(self, signalements=None, erreur=None):
        self.signalements = signalements or {}
        self.erreur = erreur
        self.appels: list[dict] = []

    def relire(self, systeme, fiche):
        self.appels.append({"systeme": systeme, "fiche": fiche})
        if self.erreur:
            raise self.erreur
        return ReponseRelecture(
            signalements=self.signalements.get(fiche["salarie"], []),
            usage={"input_tokens": 100, "output_tokens": 50},
        )


@pytest.fixture(autouse=True)
def cle(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-factice")


def _lancer(depot, company_ids=None):
    return service.lancer("u1", SOCIETES, 2026, 10, company_ids or [SOCIETE], depot=depot)


def _point(gravite="important", ligne="Salaire de base", chiffre="2500"):
    return {
        "gravite": gravite,
        "ligne": ligne,
        "raison": f"Le montant de {chiffre} € surprend.",
        "chiffres_cites": [chiffre],
    }


class TestPreparation:
    def test_compte_les_societes_avec_bulletins_seulement(self):
        depot = DepotRelecture(_base(_bulletin(1), _bulletin(2)))
        fenetre = service.preparer(SOCIETES, 2026, 10, depot=depot)
        assert [s["nom"] for s in fenetre["societes"]] == ["Alpha"]
        assert fenetre["societes"][0]["bulletins_generes"] == 2
        assert fenetre["total_a_relire"] == 2
        assert fenetre["societes"][0]["sans_regles"] is True
        assert fenetre["cout_estime_eur"] > 0
        assert fenetre["blocage"] is None

    def test_sans_cle_le_dit(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY")
        fenetre = service.preparer(SOCIETES, 2026, 10, depot=DepotRelecture(_base(_bulletin(1))))
        assert "clé" in fenetre["blocage"]

    def test_ne_lit_pas_le_contenu_des_bulletins(self):
        base = _base(_bulletin(1))
        lectures: list[str] = []
        origine = base.table

        def espion(nom):
            requete = origine(nom)
            select = requete.select

            def select_note(*colonnes, **kwargs):
                lectures.append(f"{nom}:{colonnes}")
                return select(*colonnes, **kwargs)

            requete.select = select_note
            return requete

        base.table = espion
        service.preparer(SOCIETES, 2026, 10, depot=DepotRelecture(base))
        assert not any("payslip_data" in l for l in lectures)


class TestLancer:
    def test_cree_les_lignes_et_demande_l_execution(self):
        base = _base(_bulletin(1), _bulletin(2))
        resultat = _lancer(DepotRelecture(base))
        assert resultat["statut"] == "lancee"
        assert resultat["a_executer"] is True
        assert len(base.lignes("relectures_ia_bulletins", statut="a_faire")) == 2
        assert base.ligne("relectures_ia", statut="en_cours")["total"] == 2

    def test_sans_cle_ne_lance_rien(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY")
        base = _base(_bulletin(1))
        resultat = _lancer(DepotRelecture(base))
        assert resultat["statut"] == "bloquee"
        assert base.lignes("relectures_ia") == []

    def test_societe_non_autorisee(self):
        with pytest.raises(service.SocieteRefusee):
            service.lancer("u1", SOCIETES, 2026, 10, ["autre"], depot=DepotRelecture(_base()))

    def test_aucune_societe(self):
        with pytest.raises(service.SansSocieteCochee):
            service.lancer("u1", SOCIETES, 2026, 10, [], depot=DepotRelecture(_base()))

    def test_une_seule_a_la_fois(self):
        depot = DepotRelecture(_base(_bulletin(1)))
        _lancer(depot)
        second = _lancer(depot)
        assert second["statut"] == "deja_en_cours"
        assert second["a_executer"] is False

    def test_course_perdue_sur_l_index_unique(self):
        class Refus:
            def table(self, _nom):
                raise RuntimeError("23505 duplicate key")

        depot = DepotRelecture(Refus())
        assert depot.creer_relecture({}, []) is None

    def test_rien_a_relire_ne_lance_rien(self):
        base = _base(_bulletin(1))
        depot = DepotRelecture(base)
        lance = _lancer(depot)
        service.executer(lance["relecture_id"], depot=depot, relecteur=FauxRelecteur())
        resultat = _lancer(depot)
        assert resultat["statut"] == "rien_a_relire"
        assert "Rien à relire" in resultat["message"]
        assert len(base.lignes("relectures_ia")) == 1

    def test_ne_relit_que_le_bulletin_modifie(self):
        base = _base(_bulletin(1), _bulletin(2))
        depot = DepotRelecture(base)
        lance = _lancer(depot)
        service.executer(lance["relecture_id"], depot=depot, relecteur=FauxRelecteur())
        base.ligne("payslips", id="p2")["updated_at"] = "2026-11-02T10:00:00+00:00"
        assert _lancer(depot)["statut"] == "lancee"
        en_cours = base.ligne("relectures_ia", statut="en_cours")
        assert en_cours["total"] == 1


class TestExecution:
    def _executer(self, base, relecteur):
        depot = DepotRelecture(base)
        lance = _lancer(depot)
        service.executer(lance["relecture_id"], depot=depot, relecteur=relecteur)
        return base.ligne("relectures_ia", id=lance["relecture_id"])

    def test_chemin_nominal(self):
        base = _base(_bulletin(1))
        code = code_salarie("e1")
        relecture = self._executer(base, FauxRelecteur({code: [_point()]}))
        assert relecture["statut"] == "terminee"
        assert relecture["traites"] == 1 and relecture["points"] == 1
        assert "1 bulletin relu" in relecture["message"]
        ligne = base.ligne("relectures_ia_bulletins", payslip_id="p1")
        assert ligne["statut"] == "fait"
        assert ligne["signalements"][0]["ligne"] == "Salaire de base"
        assert ligne["payslip_updated_at"] == MAJ
        assert float(relecture["cout_reel_usd"]) > 0

    def test_un_bulletin_n_est_jamais_modifie(self):
        base = _base(_bulletin(1))
        avant = dict(base.ligne("payslips", id="p1"))
        self._executer(base, FauxRelecteur({code_salarie("e1"): [_point()]}))
        assert base.ligne("payslips", id="p1") == avant

    def test_la_fiche_ne_contient_aucun_nom(self):
        relecteur = FauxRelecteur()
        self._executer(_base(_bulletin(1)), relecteur)
        fiche = relecteur.appels[0]["fiche"]
        assert fiche["salarie"] == code_salarie("e1")
        assert "Testeur" not in str(fiche) and "108 234" not in str(fiche)

    def test_compare_au_mois_precedent(self):
        precedent = _bulletin(9, mois=9, data=_donnees(brut=2400.0))
        precedent["employee_id"] = "e1"
        relecteur = FauxRelecteur()
        self._executer(_base(_bulletin(1), precedent), relecteur)
        assert relecteur.appels[0]["fiche"]["mois_precedent"]["salaire_brut"] == 2400.0
        assert relecteur.appels[0]["fiche"]["ecarts_avec_mois_precedent"]["salaire_brut"] == 100.0

    def test_janvier_regarde_decembre(self):
        assert service._mois_precedent(2026, 1) == (2025, 12)

    def test_regles_de_la_societe_en_contexte(self):
        base = _base(_bulletin(1))
        base.tables["relecture_ia_regles"].append({"company_id": SOCIETE, "texte": "Règle Alpha."})
        relecteur = FauxRelecteur()
        self._executer(base, relecteur)
        assert "Règle Alpha." in relecteur.appels[0]["systeme"][0]["text"]

    def test_signalement_sans_fondement_ecarte(self):
        base = _base(_bulletin(1))
        code = code_salarie("e1")
        self._executer(base, FauxRelecteur({code: [_point(chiffre="9999")]}))
        ligne = base.ligne("relectures_ia_bulletins", payslip_id="p1")
        assert ligne["signalements"] == []
        assert ligne["ecartes"] == {"chiffre_absent_de_la_fiche": 1}

    def test_echec_d_un_bulletin_n_arrete_pas_le_lot(self):
        base = _base(_bulletin(1))
        relecteur = FauxRelecteur(erreur=RelectureImpossible("L'IA a refusé."))
        relecture = self._executer(base, relecteur)
        assert relecture["statut"] == "echec"
        assert relecture["echecs"] == 1
        assert "relancez" in relecture["message"]
        assert base.ligne("relectures_ia_bulletins", payslip_id="p1")["message"] == "L'IA a refusé."

    def test_erreur_fatale_arrete_et_le_dit(self):
        base = _base(_bulletin(1), _bulletin(2))
        erreur = RelectureImpossible("Clé refusée.", fatale=True)
        relecture = self._executer(base, FauxRelecteur(erreur=erreur))
        assert relecture["statut"] == "echec"
        assert relecture["message"] == "Clé refusée."

    def test_erreur_inattendue_ne_laisse_pas_en_cours(self):
        base = _base(_bulletin(1))
        depot = DepotRelecture(base)
        lance = _lancer(depot)
        depot.bulletins_a_traiter = lambda *_a: 1 / 0
        service.executer(lance["relecture_id"], depot=depot, relecteur=FauxRelecteur())
        assert base.ligne("relectures_ia")["statut"] == "echec"

    def test_bulletin_disparu_dit_pourquoi(self):
        base = _base(_bulletin(1))
        depot = DepotRelecture(base)
        lance = _lancer(depot)
        base.tables["payslips"].clear()
        service.executer(lance["relecture_id"], depot=depot, relecteur=FauxRelecteur())
        assert "supprimé" in base.ligne("relectures_ia_bulletins", payslip_id="p1")["message"]


class TestReprise:
    def _bloquee(self, base, minutes):
        depot = DepotRelecture(base)
        lance = _lancer(depot)
        ancien = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        base.ligne("relectures_ia", id=lance["relecture_id"])["battement_at"] = ancien
        return depot, lance["relecture_id"]

    def test_reprend_apres_deux_minutes_sans_battement(self):
        depot, identifiant = self._bloquee(_base(_bulletin(1)), 3)
        etat = service.lire_etat(depot=depot)
        assert etat["a_executer"] is True
        assert etat["relecture"]["id"] == identifiant

    def test_une_seule_reprise_a_la_fois(self):
        depot, _ = self._bloquee(_base(_bulletin(1)), 3)
        assert service.lire_etat(depot=depot)["a_executer"] is True
        assert service.lire_etat(depot=depot)["a_executer"] is False

    def test_ne_reprend_pas_une_relecture_vivante(self):
        depot, _ = self._bloquee(_base(_bulletin(1)), 1)
        assert service.lire_etat(depot=depot)["a_executer"] is False

    def test_reprise_ne_relit_que_ce_qui_reste(self):
        base = _base(_bulletin(1), _bulletin(2))
        depot, identifiant = self._bloquee(base, 3)
        ligne = base.ligne("relectures_ia_bulletins", payslip_id="p1")
        ligne.update({"statut": "fait", "signalements": []})
        relecteur = FauxRelecteur()
        service.executer(identifiant, depot=depot, relecteur=relecteur)
        assert len(relecteur.appels) == 1
        assert base.ligne("relectures_ia", id=identifiant)["traites"] == 2


class TestARegarder:
    def _relire(self, base, signalements):
        depot = DepotRelecture(base)
        lance = _lancer(depot)
        service.executer(lance["relecture_id"], depot=depot, relecteur=FauxRelecteur(signalements))
        return depot

    def test_points_nommes_et_classes(self):
        base = _base(_bulletin(1), _bulletin(2))
        depot = self._relire(
            base,
            {
                code_salarie("e1"): [_point(gravite="a_verifier")],
                code_salarie("e2"): [_point()],
            },
        )
        vue = service.lire_a_regarder(SOCIETE, 2026, 10, depot=depot)
        assert [p["gravite"] for p in vue["points"]] == ["important", "a_verifier"]
        assert vue["points"][0]["nom"] == "Alix Testeur"
        assert vue["autres_points"] == 0
        assert vue["relecture_faite"] is True

    def test_jamais_relu(self):
        vue = service.lire_a_regarder(SOCIETE, 2026, 10, depot=DepotRelecture(_base(_bulletin(1))))
        assert vue == {"relecture_faite": False, "relu_le": None, "points": [], "autres_points": 0}

    def test_plafond_et_reste_compte(self):
        base = _base(_bulletin(1))
        lignes = [_point(ligne=f"Ligne {c}") for c in "abcde"]
        depot = self._relire(base, {code_salarie("e1"): lignes})
        vue = service.lire_a_regarder(SOCIETE, 2026, 10, depot=depot)
        assert len(vue["points"]) == 3
        assert vue["autres_points"] == 2

    def test_vu_disparait_et_reste_retenu_le_mois_suivant(self):
        base = _base(_bulletin(1))
        depot = self._relire(base, {code_salarie("e1"): [_point()]})
        point = service.lire_a_regarder(SOCIETE, 2026, 10, depot=depot)["points"][0]
        service.marquer_vu(SOCIETE, "u1", point["bulletin_relu_id"], point["ligne"], depot=depot)
        assert service.lire_a_regarder(SOCIETE, 2026, 10, depot=depot)["points"] == []

        base.tables["payslips"].append(_bulletin(1, mois=11))
        base.tables["payslips"][-1]["id"] = "p1-nov"
        lance = service.lancer("u1", SOCIETES, 2026, 11, [SOCIETE], depot=depot)
        service.executer(
            lance["relecture_id"],
            depot=depot,
            relecteur=FauxRelecteur({code_salarie("e1"): [_point()]}),
        )
        ligne = base.ligne("relectures_ia_bulletins", payslip_id="p1-nov")
        assert ligne["signalements"] == []
        assert ligne["ecartes"] == {"deja_vu": 1}

    def test_vu_refuse_si_le_point_n_existe_pas(self):
        base = _base(_bulletin(1))
        depot = self._relire(base, {code_salarie("e1"): [_point()]})
        with pytest.raises(service.PointIntrouvable):
            service.marquer_vu(SOCIETE, "u1", "inconnu", "Salaire de base", depot=depot)
        ligne = base.ligne("relectures_ia_bulletins", payslip_id="p1")
        with pytest.raises(service.PointIntrouvable):
            service.marquer_vu(SOCIETE, "u1", ligne["id"], "Autre ligne", depot=depot)
        with pytest.raises(service.PointIntrouvable):
            service.marquer_vu(AUTRE, "u1", ligne["id"], "Salaire de base", depot=depot)

    def test_bulletin_supprime_ne_montre_plus_ses_points(self):
        base = _base(_bulletin(1))
        depot = self._relire(base, {code_salarie("e1"): [_point()]})
        base.tables["payslips"].clear()
        assert service.lire_a_regarder(SOCIETE, 2026, 10, depot=depot)["points"] == []

    def test_bulletin_modifie_depuis_est_dit(self):
        base = _base(_bulletin(1))
        depot = self._relire(base, {code_salarie("e1"): [_point()]})
        base.ligne("payslips", id="p1")["updated_at"] = "2026-11-03T10:00:00+00:00"
        point = service.lire_a_regarder(SOCIETE, 2026, 10, depot=depot)["points"][0]
        assert point["bulletin_modifie_depuis"] is True

    def test_derniere_relecture_prime(self):
        base = _base(_bulletin(1))
        depot = self._relire(base, {code_salarie("e1"): [_point()]})
        base.ligne("payslips", id="p1")["updated_at"] = "2026-11-03T10:00:00+00:00"
        lance = _lancer(depot)
        service.executer(lance["relecture_id"], depot=depot, relecteur=FauxRelecteur())
        assert service.lire_a_regarder(SOCIETE, 2026, 10, depot=depot)["points"] == []

    def test_societes_du_compte_filtre_les_droits(self):
        user = SimpleNamespace(
            accessible_companies=[
                SimpleNamespace(company_id="a", company_name="A"),
                SimpleNamespace(company_id="b", company_name="B"),
            ],
            has_rh_access_in_company=lambda c: c == "a",
        )
        assert service.societes_du_compte(user) == [{"company_id": "a", "nom": "A"}]
