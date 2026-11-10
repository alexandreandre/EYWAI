"""Retours du 10/11/2026 sur la présentation du bulletin imprimé.

- Autres contributions de l'employeur agrégées en une ligne : C. trav. R3243-2,
  al. 2 (code.travail.gouv.fr, ouvert le 10/11/2026) : « Les contributions autres
  que les contributions sociales mentionnées au a du 8° sont également agrégées
  dans une seule rubrique, qui donne le montant total de cette contribution. »
- Notes de frais : une seule ligne « Remboursement de frais » ; le détail reste
  dans le bulletin enregistré (écran, export comptable).
- Forfait jours : le cumul des jours travaillés de l'année face au volume du
  forfait (R3243-1, 5°, a) et le « Cumul heures » nommé pour ce qu'il est.

Rien ne change aux montants : la vue ne fait que regrouper ce que le moteur a
calculé, et les totaux restent ceux des rubriques.
"""

from __future__ import annotations

import copy

import pytest

from app.modules.payroll.documents.bulletin_view import construire_vue_bulletin
from tests.unit.payroll.test_bulletin_view import (
    bulletin_avec_cotisations,
    bulletin_minimal,
)

pytestmark = pytest.mark.unit


def _coti(coti_id, libelle, patronal, salarial=0.0, base=2000.0, **extra):
    ligne = {
        "coti_id": coti_id,
        "libelle": libelle,
        "base": base,
        "taux_salarial": None,
        "montant_salarial": salarial,
        "taux_patronal": 0.01,
        "montant_patronal": patronal,
    }
    ligne.update(extra)
    return ligne


AUTRES = [
    _coti("cfp", "Formation professionnelle", 11.0),
    _coti("csa", "Contribution solidarité autonomie", 6.0),
    _coti("dialogue_social", "Contribution au dialogue social", 0.32),
    _coti("fnal", "FNAL", 2.0),
    _coti("taxe_apprentissage", "Taxe d'apprentissage (part principale)", 8.7),
    _coti("taxe_apprentissage_solde", "Taxe d'apprentissage (solde)", 1.3),
]


def _bulletin_avec_autres(annee=2026, mois=10, lignes=None):
    bulletin = bulletin_avec_cotisations()
    bulletin["en_tete"].update(annee=annee, mois=mois)
    lignes = copy.deepcopy(lignes if lignes is not None else AUTRES)
    bulletin["cotisations_officielles"].append(
        {
            "code": "autres_contributions_employeur",
            "libelle": "Autres contributions dues par l'employeur",
            "lignes": lignes,
            "total_salarial": round(sum(l["montant_salarial"] for l in lignes), 2),
            "total_patronal": round(sum(l["montant_patronal"] for l in lignes), 2),
        }
    )
    return bulletin


def _libelles(lignes):
    return [ligne["libelle"] for ligne in lignes]


class TestAutresContributionsAgregees:
    def test_une_seule_ligne_au_total_des_six(self):
        lignes = construire_vue_bulletin(_bulletin_avec_autres())["lignes"]
        autres = [l for l in lignes if "AUTRES CONTRIB" in l["libelle"].upper()]
        assert len(autres) == 1
        assert autres[0]["code"] == "Q600"
        assert autres[0]["montant_patronal"] == pytest.approx(29.32)
        assert autres[0]["montant_salarial"] is None
        for detail in ("FNAL", "Formation professionnelle", "Taxe d'apprentissage (solde)"):
            assert detail not in _libelles(lignes)

    def test_le_total_des_retenues_ne_change_pas(self):
        avant = bulletin_avec_cotisations()
        total_avant = next(
            l for l in construire_vue_bulletin(avant)["lignes"] if l["libelle"] == "TOTAL DES RETENUES"
        )
        apres = construire_vue_bulletin(_bulletin_avec_autres())["lignes"]
        total = next(l for l in apres if l["libelle"] == "TOTAL DES RETENUES")
        assert total["montant_patronal"] == pytest.approx(total_avant["montant_patronal"] + 29.32)
        assert total["montant_salarial"] == pytest.approx(total_avant["montant_salarial"])

    def test_le_detail_reste_dans_le_bulletin_enregistre(self):
        bulletin = _bulletin_avec_autres()
        construire_vue_bulletin(bulletin)
        rubrique = bulletin["cotisations_officielles"][-1]
        assert len(rubrique["lignes"]) == 6

    def test_une_ligne_corrigee_a_la_main_garde_son_asterisque(self):
        lignes = copy.deepcopy(AUTRES)
        lignes[3]["correction"] = {"ancien": 1.0, "nouveau": 2.0}
        vue = construire_vue_bulletin(_bulletin_avec_autres(lignes=lignes))["lignes"]
        autres = next(l for l in vue if "AUTRES CONTRIB" in l["libelle"].upper())
        assert autres["libelle"].endswith("*")

    def test_modele_definitif_une_ligne(self):
        lignes = construire_vue_bulletin(_bulletin_avec_autres(annee=2027, mois=1))["lignes"]
        autres = [l for l in lignes if l["libelle"].startswith("Autres charges dues par l'employeur")]
        assert len(autres) == 1
        assert autres[0]["montant_patronal"] == pytest.approx(29.32)
        assert "FNAL" not in _libelles(lignes)
        total = next(
            l for l in lignes if l["libelle"] == "TOTAL DES COTISATIONS ET CONTRIBUTIONS OBLIGATOIRES"
        )
        # 100,53 (santé) + 122,80 (retraite) + 29,32
        assert total["montant_patronal"] == pytest.approx(252.65)


def _note(type_, jour, montant):
    return {
        "prime_id": f"remb_{type_}_{jour}",
        "libelle": f"Note de frais : {type_} du {jour[8:10]}/{jour[5:7]}/{jour[0:4]}",
        "montant": montant,
        "frais_professionnels": True,
    }


class TestNotesDeFraisEnUneLigne:
    def test_vingt_cinq_notes_une_ligne(self):
        bulletin = bulletin_avec_cotisations()
        notes = [_note("restaurant", f"2026-10-{j:02d}", 12.5) for j in range(1, 26)]
        bulletin["primes_non_soumises"] = [
            {"libelle": "INDEMNITÉ DE PANIER", "montant": 20.0},
            *notes,
        ]
        lignes = construire_vue_bulletin(bulletin)["lignes"]
        frais = [l for l in lignes if l["libelle"] == "Remboursement de frais"]
        assert len(frais) == 1
        assert frais[0]["montant_salarial"] == pytest.approx(312.5)
        assert not [l for l in lignes if l["libelle"].startswith("Note de frais")]
        # Les autres éléments non soumis restent à leur libellé.
        assert "INDEMNITÉ DE PANIER" in _libelles(lignes)
        # Le bulletin enregistré garde chaque note (export comptable, écran).
        assert len(bulletin["primes_non_soumises"]) == 26

    def test_notes_de_colorplast_dans_le_mns_aussi_regroupees(self):
        bulletin = bulletin_avec_cotisations()
        note = _note("transport", "2026-10-02", 30.0)
        note.pop("frais_professionnels")
        bulletin["primes_non_soumises"] = [note, _note("telephone", "2026-10-03", 20.0)]
        lignes = construire_vue_bulletin(bulletin)["lignes"]
        frais = [l for l in lignes if l["libelle"] == "Remboursement de frais"]
        assert len(frais) == 1
        assert frais[0]["montant_salarial"] == pytest.approx(50.0)

    def test_modele_definitif_dans_les_remboursements(self):
        bulletin = bulletin_avec_cotisations()
        bulletin["en_tete"].update(annee=2027, mois=1)
        bulletin["primes_non_soumises"] = [_note("hotel", "2027-01-05", 80.0), _note("hotel", "2027-01-06", 80.0)]
        pied = construire_vue_bulletin(bulletin)["pied"]
        assert [l["libelle"] for l in pied["remboursements"]] == ["Remboursement de frais"]
        assert pied["remboursements"][0]["montant_salarial"] == pytest.approx(160.0)


def _forfait(cumuls):
    bulletin = bulletin_minimal()
    bulletin["en_tete"].update(annee=2026, mois=10)
    bulletin["forfait_jours_annuel"] = 216.0
    bulletin["cumuls"] = {"cumuls": cumuls}
    return bulletin


def _bloc(vue, titre):
    return next((bloc for bloc in vue["lateral"] if bloc["titre"] == titre), None)


class TestForfaitJours:
    def test_cumul_des_jours_face_au_forfait(self):
        vue = construire_vue_bulletin(
            _forfait({"heures_remunerees": 1188.57, "jours_travailles_forfait": 182.0})
        )
        bloc = _bloc(vue, "FORFAIT JOURS")
        assert bloc is not None
        valeurs = {v["libelle"]: v["valeur"] for v in bloc["valeurs"]}
        assert valeurs["Jours travaillés"] == "182 sur 216"

    def test_decompte_commence_en_cours_d_annee(self):
        vue = construire_vue_bulletin(
            _forfait(
                {
                    "heures_remunerees": 1188.57,
                    "jours_travailles_forfait": 21.5,
                    "jours_travailles_forfait_depuis": 10,
                }
            )
        )
        valeurs = {v["libelle"]: v["valeur"] for v in _bloc(vue, "FORFAIT JOURS")["valeurs"]}
        assert valeurs["Jours travaillés depuis le 01/10/2026"] == "21,5 sur 216"

    def test_sans_cumul_de_jours_rien_n_est_invente(self):
        vue = construire_vue_bulletin(_forfait({"heures_remunerees": 1188.57}))
        assert _bloc(vue, "FORFAIT JOURS") is None

    def test_cumul_heures_nomme_pour_la_reduction_generale(self):
        vue = construire_vue_bulletin(_forfait({"heures_remunerees": 1188.57}))
        valeurs = {v["libelle"]: v["valeur"] for v in _bloc(vue, "HEURES")["valeurs"]}
        assert valeurs["Heures retenues pour la réduction générale"] == "1 188,57"
        assert "Cumul heures" not in valeurs

    def test_salarie_aux_heures_garde_cumul_heures(self):
        bulletin = bulletin_minimal()
        bulletin["cumuls"] = {"cumuls": {"heures_remunerees": 392.49}}
        valeurs = {v["libelle"]: v["valeur"] for v in _bloc(construire_vue_bulletin(bulletin), "HEURES")["valeurs"]}
        assert valeurs["Cumul heures"] == "392,49"
        assert _bloc(construire_vue_bulletin(bulletin), "FORFAIT JOURS") is None
