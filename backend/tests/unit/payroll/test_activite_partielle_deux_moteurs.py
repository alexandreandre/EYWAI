"""Activité partielle, alertes d'arrêt et paniers : les deux moteurs, même règle.

Constat de Lyon (17/11/2026, LEWIS, octobre) : au forfait jours, l'activité
partielle posée au calendrier n'était pas calculée (jours chômés payés en
entier, sans alerte). La saisie à la main passait comme une prime ordinaire :
indemnité absente du coût employeur, heures chômées gardées dans le Smic de la
réduction générale. Les alertes d'arrêt et la réintégration d'un panier
au-delà du plafond n'existaient qu'en heures.

Les deux moteurs appellent maintenant les mêmes fonctions
(`engine.activite_partielle`, `engine.frais_professionnels`) : chaque test
tourne sur un salarié en heures et sur un salarié au forfait jours, calcul
complet hors ligne (barèmes figés).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import httpx
import pytest

from app.core.paths import payroll_engine_root
from app.modules.payroll.documents import (
    payslip_generator,
    payslip_generator_forfait,
    payslip_run_forfait,
    payslip_run_heures,
)
from app.modules.payroll.engine.activite_partielle import (
    PRIME_ID_INDEMNITE,
    est_l_indemnite,
    heures_chomees_de_la_retenue,
    ligne_d_indemnite,
    lignes_csg_de_l_indemnite,
)
from tests.unit.payroll.test_annee_des_baremes import _baremes, _dossier_calculable

pytestmark = pytest.mark.unit

RETENUE = {
    "prime_id": "Heures_chômées_(act._part.)",
    "libelle": "Heures chômées (act. part.)",
    "montant": -200.0,
    "quantity": 14.0,
    "soumise_a_cotisations": True,
    "soumise_a_impot": True,
}
# Forme du générateur au forfait avant le correctif : identifiant tiré du libellé.
INDEMNITE = {
    "prime_id": "Indemnité_activité_partielle",
    "libelle": "Indemnité activité partielle",
    "montant": 136.36,
    "quantity": 14.0,
    "soumise_a_cotisations": False,
    "soumise_a_impot": True,
}

MOTEURS = {
    "heures": (payslip_run_heures.run_payslip_generation_heures, False),
    "forfait_jours": (payslip_run_forfait.run_payslip_generation_forfait, True),
}


@pytest.fixture(autouse=True)
def _hors_ligne(monkeypatch):
    def reseau_interdit(*_a, **_k):
        raise AssertionError("appel réseau pendant un test unitaire")

    monkeypatch.setattr(httpx.Client, "send", reseau_interdit)


def _bulletin(tmp_path: Path, moteur: str, primes: list[dict]) -> dict:
    calculer, forfait = MOTEURS[moteur]
    dossier = _dossier_calculable(tmp_path, forfait=forfait)
    (dossier / "saisies" / "01.json").write_text(
        json.dumps({"periode": {"mois": 1, "annee": 2026}, "primes": primes}),
        encoding="utf-8",
    )
    baremes = _baremes()
    # Barème Urssaf 2026 du repas sur le lieu de travail (absent du barème figé).
    baremes["frais_pro"]["sections"]["repas"]["sur_lieu_travail"] = 7.5
    return calculer(
        dossier, 2026, 1, payroll_engine_root(), baremes_override=baremes, persister=False
    )


def _cout(b: dict) -> float:
    return float(b["pied_de_page"]["cout_total_employeur"])


def _allegements(b: dict) -> float:
    return float(b["pied_de_page"]["total_allegements_patronaux"])


# --- Fonctions communes ---------------------------------------------------


def test_la_retenue_porte_ses_heures_chomees():
    assert heures_chomees_de_la_retenue("x", "Heures chômées (act. part.)", -200.0, 14) == 14.0
    assert heures_chomees_de_la_retenue("x", "Heures chômées (act. part.)", 200.0, 14) == 0.0
    assert heures_chomees_de_la_retenue("x", "Prime exceptionnelle", -200.0, 14) == 0.0
    assert heures_chomees_de_la_retenue("x", "Heures chômées (act. part.)", -200.0, "?") == 0.0


def test_l_indemnite_est_reconnue_et_rangee_par_son_identifiant():
    assert est_l_indemnite("Indemnité_activité_partielle", "Indemnité activité partielle")
    assert not est_l_indemnite("prime", "Heures chômées (act. part.)")
    assert ligne_d_indemnite("Indemnité activité partielle", 136.364) == {
        "prime_id": PRIME_ID_INDEMNITE,
        "libelle": "Indemnité activité partielle",
        "montant": 136.36,
    }
    assert ligne_d_indemnite("Indemnité activité partielle", 0.0) is None


# --- Calcul complet, heures et forfait jours ------------------------------


@pytest.mark.parametrize("moteur", sorted(MOTEURS))
def test_l_indemnite_est_un_revenu_de_remplacement_avec_heures_et_taux(tmp_path, moteur):
    b = _bulletin(tmp_path, moteur, [RETENUE, INDEMNITE])
    assert b["revenus_hors_brut_imposables"] == [
        {
            "prime_id": PRIME_ID_INDEMNITE,
            "libelle": "Indemnité activité partielle",
            "montant": 136.36,
            "quantite": 14.0,
            "taux": 9.74,
        }
    ]
    retenue = [l for l in b["calcul_du_brut"] if l.get("libelle") == RETENUE["libelle"]]
    assert retenue and retenue[0]["quantite"] == 14.0 and retenue[0]["gain"] == -200.0


@pytest.mark.parametrize("moteur", sorted(MOTEURS))
def test_le_cout_employeur_compte_l_indemnite(tmp_path, moteur):
    avec = _bulletin(tmp_path / "avec", moteur, [RETENUE, INDEMNITE])
    sans = _bulletin(tmp_path / "sans", moteur, [RETENUE])
    assert round(_cout(avec) - _cout(sans), 2) == 136.36


@pytest.mark.parametrize("moteur", sorted(MOTEURS))
def test_les_heures_chomees_sortent_du_smic_de_la_reduction(tmp_path, moteur):
    avec_heures = _bulletin(tmp_path / "h", moteur, [RETENUE, INDEMNITE])
    sans_heures = _bulletin(
        tmp_path / "s", moteur, [{k: v for k, v in RETENUE.items() if k != "quantity"}, INDEMNITE]
    )
    assert avec_heures["salaire_brut"] == sans_heures["salaire_brut"]
    assert _allegements(avec_heures) < _allegements(sans_heures)


PANIER_FRAIS = {
    "prime_id": "panier_repas",
    "libelle": "Panier repas",
    "montant": 30.0,
    "quantity": 2,
    "quantity_kind": "count",
    "situation_repas": "sur_lieu_travail",
    "soumise_a_cotisations": False,
    "soumise_a_impot": False,
    "frais_professionnels": True,
}
PANIER_PRIME = {k: v for k, v in PANIER_FRAIS.items() if k != "frais_professionnels"}


@pytest.mark.parametrize("moteur", sorted(MOTEURS))
@pytest.mark.parametrize("panier", [PANIER_FRAIS, PANIER_PRIME], ids=["frais", "prime"])
def test_un_panier_au_dela_du_plafond_est_reintegre(tmp_path, moteur, panier):
    b = _bulletin(tmp_path, moteur, [panier])
    reint = [l for l in b["calcul_du_brut"] if "Réintégration panier" in str(l.get("libelle"))]
    # 2 paniers à 15 € sur le lieu de travail : 7,50 € exonérés chacun.
    assert [l["gain"] for l in reint] == [15.0]


# --- Le générateur au forfait lit le calendrier comme en heures -----------


@pytest.mark.parametrize("module", [payslip_generator, payslip_generator_forfait])
def test_les_deux_generateurs_tirent_l_activite_partielle_et_les_alertes_du_calendrier(module):
    source = inspect.getsource(module)
    for appel in (
        "lignes_du_calendrier(",
        "alerte_arret_sans_demande(",
        "alerte_arrets_contradictoires(",
    ):
        assert appel in source, f"{module.__name__} n'appelle pas {appel}"


def test_au_forfait_un_jour_chome_vaut_sept_heures_meme_sans_le_libelle():
    """Le générateur au forfait passe la fiche comme forfait jours : le libellé
    du statut (« Cadre », « Non-Cadre ») ne fait pas compter le jour en heures."""
    source = inspect.getsource(payslip_generator_forfait.process_payslip_generation_forfait)
    assert '{**employee_data, "is_forfait_jour": True}' in source


# --- CSG/CRDS de l'indemnité, écrêtée au Smic -----------------------------

SMIC_2026 = 12.31


def test_csg_de_l_indemnite_au_dessus_du_smic_comme_quadra():
    """Bulletin Quadra de LEWIS, juin 2026, forfait jours : 683,61 € d'indemnité,
    base 671,65 €, 25,52 € déductibles et 19,48 € non déductibles."""
    lignes = lignes_csg_de_l_indemnite(
        [{"montant": 683.61}], salaire_brut=2912.08, total_salarial=634.11, smic_horaire=SMIC_2026
    )
    assert [(l["base"], l["montant_salarial"]) for l in lignes] == [(671.65, 25.52), (671.65, 19.48)]
    assert "non déductible" not in lignes[0]["libelle"]
    assert "CSG/CRDS" in lignes[1]["libelle"] and "non déductible" in lignes[1]["libelle"]


def test_sous_le_smic_rien_n_est_preleve():
    """Juin 2026, salarié en heures : brut 1 520,75 €, 533,12 € d'indemnité ;
    Quadra annule la CSG à 100 %."""
    assert lignes_csg_de_l_indemnite(
        [{"montant": 533.12}], salaire_brut=1520.75, total_salarial=330.0, smic_horaire=SMIC_2026
    ) == []


def test_entre_les_deux_le_prelevement_est_reduit_a_l_excedent():
    smic_mensuel = SMIC_2026 * 35 * 52 / 12
    # Salaire net + indemnité = Smic + 10 € : 10 € prélevés, déductible d'abord.
    lignes = lignes_csg_de_l_indemnite(
        [{"montant": 500.0}],
        salaire_brut=round(smic_mensuel - 500.0 + 10.0 + 300.0, 2),
        total_salarial=300.0,
        smic_horaire=SMIC_2026,
    )
    assert round(sum(l["montant_salarial"] for l in lignes), 2) == pytest.approx(10.0, abs=0.01)
    # 18,67 € de CSG déductible dus, réduits à l'excédent ; rien d'autre.
    assert [l["montant_salarial"] for l in lignes] == [pytest.approx(10.0, abs=0.01)]
    assert "non déductible" not in lignes[0]["libelle"]


@pytest.mark.parametrize("moteur", sorted(MOTEURS))
def test_les_deux_moteurs_prelevent_la_csg_de_l_indemnite(tmp_path, moteur):
    b = _bulletin(tmp_path, moteur, [RETENUE, INDEMNITE])
    texte = json.dumps(b["structure_cotisations"], ensure_ascii=False)
    assert "CSG déductible activité partielle" in texte
    assert "CSG/CRDS non déductible activité partielle" in texte
