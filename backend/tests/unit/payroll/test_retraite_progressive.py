"""Retraite progressive : vieillesse sur un temps plein, surcotisation au bulletin.

Cas d'origine : un cadre au forfait jours (Cartol, D.G.) à 50 % depuis le
01/10/2026, cotisations vieillesse sur un temps plein, part patronale du
supplément à l'employeur, part salariale au salarié (gestionnaire, 26/11/2026).
Les deux générateurs passent par `calculer_cotisations` ; les tests de bulletin
tournent sur le profil heures (temps partiel) et sur le forfait jours.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.retraite_progressive import (
    COTI_IDS_SURCOTISATION,
    ReglageRetraiteProgressive,
    assiettes_dsn,
    lignes_de_surcotisation,
    lire_reglage,
    salaires_temps_plein,
)
from app.modules.payroll.engine.calcul_cotisations import _calculer_une_ligne
from tests.unit.payroll.profils_salaries import alertes, banc  # noqa: F401

pytestmark = pytest.mark.unit

SMIC_HORAIRE = 12.31  # au 01/06/2026, comme les barèmes figés des tests


def _reglage(**k) -> ReglageRetraiteProgressive:
    valeurs = dict(
        actif=True,
        quotite=0.5,
        date_debut=None,
        date_fin=None,
        vieillesse_temps_plein=True,
        complementaire_temps_plein=False,
        prise_en_charge_part_salariale=False,
        salaire_temps_plein=None,
    )
    valeurs.update(k)
    return ReglageRetraiteProgressive(**valeurs)


# --- Lecture du réglage ---------------------------------------------------


def test_sans_reglage_ou_inactif_rien():
    assert lire_reglage(None) is None
    assert lire_reglage({}) is None
    assert lire_reglage({"retraite_progressive": {"actif": False, "quotite": 0.5}}) is None


def test_quotite_en_pourcentage_ramenee_a_une_fraction():
    reglage = lire_reglage(
        {"retraite_progressive": {"actif": True, "quotite": "50", "date_debut": "2026-10-01",
                                  "vieillesse_temps_plein": True}}
    )
    assert reglage is not None and reglage.quotite == 0.5
    assert reglage.couvre(2026, 10) and reglage.couvre(2026, 11) and not reglage.couvre(2026, 9)


def test_quotite_illisible_arrete_le_calcul():
    with pytest.raises(ValueError, match="quotité"):
        lire_reglage({"retraite_progressive": {"actif": True, "quotite": "moitié"}})


# --- Salaire temps plein --------------------------------------------------


def test_heures_rapport_des_heures():
    """R241-0-2, I : brut × durée temps plein / heures rémunérées."""
    heures = 17.5 * 52 / 12
    s = salaires_temps_plein(
        _reglage(complementaire_temps_plein=True), brut=1250.0, au_forfait_jours=False,
        jours_forfait=None, heures_contrat_mois=heures, heures_complementaires_mois=0.0,
        smic_horaire=SMIC_HORAIRE,
    )
    assert s.base == 2500.0 and s.complementaire == 2500.0
    assert s.alertes == ()


def test_forfait_sous_1_7_smic_base_a_1_7_smic_et_complementaire_au_prorata_des_jours():
    s = salaires_temps_plein(
        _reglage(complementaire_temps_plein=True), brut=2000.0, au_forfait_jours=True,
        jours_forfait=109, heures_contrat_mois=151.67, heures_complementaires_mois=0.0,
        smic_horaire=SMIC_HORAIRE,
    )
    # brut × 151,67 / (brut / (1,7 × SMIC)) = 1,7 SMIC mensuel.
    assert s.base == round(1.7 * SMIC_HORAIRE * 35 * 52 / 12, 2) == 3173.93
    # Agirc-Arrco, avenant 23 : brut × 218 / jours du forfait.
    assert s.complementaire == 4000.0
    assert s.alertes == ()


def test_forfait_au_dela_de_1_7_smic_pas_de_base_et_une_alerte():
    s = salaires_temps_plein(
        _reglage(complementaire_temps_plein=True), brut=3244.48, au_forfait_jours=True,
        jours_forfait=109, heures_contrat_mois=151.67, heures_complementaires_mois=0.0,
        smic_horaire=SMIC_HORAIRE,
    )
    assert s.base is None
    assert s.complementaire == round(3244.48 * 2, 2)
    assert [a["code"] for a in s.alertes] == ["retraite_progressive_forfait_au_dela_1_7_smic"]


def test_forfait_de_la_fiche_qui_ne_suit_pas_la_quotite():
    s = salaires_temps_plein(
        _reglage(), brut=2000.0, au_forfait_jours=True, jours_forfait=171,
        heures_contrat_mois=151.67, heures_complementaires_mois=0.0, smic_horaire=SMIC_HORAIRE,
    )
    codes = [a["code"] for a in s.alertes]
    assert codes == ["retraite_progressive_quotite_fiche"]
    assert "109 jours" in s.alertes[0]["message"]


def test_salaire_temps_plein_saisi_prime():
    s = salaires_temps_plein(
        _reglage(salaire_temps_plein=4100.0), brut=2050.0, au_forfait_jours=True,
        jours_forfait=109, heures_contrat_mois=151.67, heures_complementaires_mois=0.0,
        smic_horaire=SMIC_HORAIRE,
    )
    assert s.base == 4100.0 and s.complementaire is None


# --- Lignes ---------------------------------------------------------------

BAREME = [
    {"id": "vieillesse_plafonnee", "libelle": "Vieillesse plafonnée", "base": "brut_plafonne",
     "salarial": 0.069, "patronal": 0.0855},
    {"id": "vieillesse_deplafonnee", "libelle": "Vieillesse déplafonnée", "base": "brut",
     "salarial": 0.004, "patronal": 0.0211},
    {"id": "retraite_comp_t1", "libelle": "Retraite complémentaire T1", "base": "brut_plafonne",
     "salarial": 0.0315, "patronal": 0.0472},
    {"id": "ceg_t1", "libelle": "CEG T1", "base": "brut_plafonne", "salarial": 0.0086, "patronal": 0.0129},
]


def _lignes(reglage, salaires, brut=2000.0, plafond=4005.0):
    return lignes_de_surcotisation(
        reglage, salaires, cotisations_du_bareme=BAREME, brut=brut, plafond=plafond,
        assiette_plafonnee=min(brut, plafond), assiette_tranche_2=0.0, assiette_cet=0.0,
        calculer_ligne=_calculer_une_ligne,
    )


def test_lignes_de_surcotisation_parts_patronale_et_salariale():
    s = salaires_temps_plein(
        _reglage(), brut=2000.0, au_forfait_jours=True, jours_forfait=109,
        heures_contrat_mois=151.67, heures_complementaires_mois=0.0, smic_horaire=SMIC_HORAIRE,
    )
    lignes = {l["coti_id"]: l for l in _lignes(_reglage(), s)}
    assert set(lignes) == {"surcotisation_vieillesse_plafonnee", "surcotisation_vieillesse_deplafonnee"}
    plaf = lignes["surcotisation_vieillesse_plafonnee"]
    assert plaf["base"] == 1173.93
    assert plaf["montant_salarial"] == round(1173.93 * 0.069, 2) == 81.0
    assert plaf["montant_patronal"] == round(1173.93 * 0.0855, 2) == 100.37
    assert plaf["libelle"].startswith("Surcotisation retraite progressive")
    assert plaf["rubrique"] == "retraite"
    assert assiettes_dsn(list(lignes.values())) == {"24": 1173.93, "22": 1173.93}


def test_prise_en_charge_de_la_part_salariale():
    reglage = _reglage(prise_en_charge_part_salariale=True)
    s = salaires_temps_plein(
        reglage, brut=2000.0, au_forfait_jours=True, jours_forfait=109,
        heures_contrat_mois=151.67, heures_complementaires_mois=0.0, smic_horaire=SMIC_HORAIRE,
    )
    plaf = next(l for l in _lignes(reglage, s) if l["coti_id"] == "surcotisation_vieillesse_plafonnee")
    assert plaf["montant_salarial"] == 0.0
    assert plaf["montant_patronal"] == round(100.37 + 81.0, 2)
    assert plaf["prise_en_charge_part_salariale"] == 81.0


def test_plafond_atteint_seule_la_deplafonnee_bouge():
    s = salaires_temps_plein(
        _reglage(), brut=4500.0, au_forfait_jours=False, jours_forfait=None,
        heures_contrat_mois=17.5 * 52 / 12, heures_complementaires_mois=0.0, smic_horaire=SMIC_HORAIRE,
    )
    lignes = {l["coti_id"]: l for l in _lignes(_reglage(), s, brut=4500.0)}
    assert set(lignes) == {"surcotisation_vieillesse_deplafonnee"}
    assert lignes["surcotisation_vieillesse_deplafonnee"]["base"] == 4500.0


# --- Bulletin complet, deux générateurs ------------------------------------

REGLAGE_FICHE = {
    "actif": True,
    "quotite": 0.5,
    "date_debut": "2026-10-01",
    "vieillesse_temps_plein": True,
    "complementaire_temps_plein": False,
    "prise_en_charge_part_salariale": False,
}
#: Un salarié par générateur, à 50 % : temps partiel 17 h 30 et forfait de 109 jours.
FICHES = {
    "temps_partiel": {"duree_hebdomadaire": 17.5, "is_temps_partiel": True, "salaire_de_base": {"valeur": 1250.0}},
    "forfait_jours": {"salaire_de_base": {"valeur": 2000.0}},
}
FORFAIT_109 = {"forfait_annual_days": 109}


def _fiche(profil: str, reglage: dict | None) -> dict:
    fiche = dict(FICHES[profil])
    specificites = {"prelevement_a_la_source": {"taux": 0.0, "is_personnalise": True}}
    if profil == "forfait_jours":
        specificites.update(FORFAIT_109)
    if reglage is not None:
        specificites["retraite_progressive"] = reglage
    fiche["specificites_paie"] = specificites
    return fiche


def _cotisations(donnees: dict) -> list[dict]:
    structure = donnees.get("structure_cotisations") or {}
    autres = (structure.get("bloc_autres_contributions") or {}).get("lignes") or []
    return [
        *(structure.get("bloc_principales") or []),
        *(structure.get("bloc_allegements") or []),
        *autres,
        *(structure.get("bloc_csg_non_deductible") or []),
    ]


def _surcotisations(donnees: dict) -> list[dict]:
    return [l for l in _cotisations(donnees) if l.get("coti_id") in COTI_IDS_SURCOTISATION]


def _sans_surcotisation(donnees: dict) -> list[tuple]:
    return [
        (l.get("libelle"), l.get("base"), l.get("montant_salarial"), l.get("montant_patronal"))
        for l in _cotisations(donnees)
        if l.get("coti_id") not in COTI_IDS_SURCOTISATION
    ]


@pytest.mark.parametrize("profil", ["temps_partiel", "forfait_jours"])
def test_sans_reglage_bulletin_inchange_au_centime(banc, profil):  # noqa: F811
    """Un réglage absent ou décoché ne change rien, au centime près."""
    sans = banc.generer(profil, fiche_en_plus=_fiche(profil, None))
    decoche = banc.generer(profil, fiche_en_plus=_fiche(profil, {**REGLAGE_FICHE, "actif": False}))
    assert _surcotisations(sans) == []
    for cle in ("salaire_brut", "net_a_payer"):
        assert sans.get(cle) == decoche.get(cle), cle
    assert sans["structure_cotisations"] == decoche["structure_cotisations"]
    assert sans["pied_de_page"]["cout_total_employeur"] == decoche["pied_de_page"]["cout_total_employeur"]
    assert sans["synthese_net"] == decoche["synthese_net"]
    assert _sans_surcotisation(sans) == _sans_surcotisation(decoche)


@pytest.mark.parametrize("profil", ["temps_partiel", "forfait_jours"])
def test_bulletin_porte_la_surcotisation_et_le_reste_ne_bouge_pas(banc, profil):  # noqa: F811
    sans = banc.generer(profil, fiche_en_plus=_fiche(profil, None))
    avec = banc.generer(profil, fiche_en_plus=_fiche(profil, REGLAGE_FICHE))
    lignes = {l["coti_id"]: l for l in _surcotisations(avec)}
    assert set(lignes) == {"surcotisation_vieillesse_plafonnee", "surcotisation_vieillesse_deplafonnee"}
    brut = float(avec["salaire_brut"])
    assert brut == float(sans["salaire_brut"])
    # Temps partiel : le double du brut ; forfait (sous 1,7 SMIC) : 1,7 SMIC mensuel.
    attendu = round(brut * 2, 2) if profil == "temps_partiel" else round(1.7 * SMIC_HORAIRE * 35 * 52 / 12, 2)
    assert lignes["surcotisation_vieillesse_deplafonnee"]["base"] == round(attendu - brut, 2)
    # Le reste du bulletin est identique ; le net baisse de la seule part salariale.
    assert _sans_surcotisation(avec) == _sans_surcotisation(sans)
    salariale = round(sum(l["montant_salarial"] for l in lignes.values()), 2)
    assert salariale > 0
    assert round(float(sans["net_a_payer"]) - float(avec["net_a_payer"]), 2) == salariale
    assert all(l["montant_patronal"] > 0 for l in lignes.values())
    assert "retraite_progressive_quotite_fiche" not in alertes(avec)


@pytest.mark.parametrize("profil", ["temps_partiel", "forfait_jours"])
def test_prise_en_charge_net_inchange(banc, profil):  # noqa: F811
    sans = banc.generer(profil, fiche_en_plus=_fiche(profil, None))
    avec = banc.generer(
        profil, fiche_en_plus=_fiche(profil, {**REGLAGE_FICHE, "prise_en_charge_part_salariale": True})
    )
    assert _surcotisations(avec)
    assert avec["net_a_payer"] == sans["net_a_payer"]
    assert avec["synthese_net"]["net_imposable"] == sans["synthese_net"]["net_imposable"]


def test_forfait_de_la_fiche_non_reduit_alerte(banc):  # noqa: F811
    fiche = _fiche("forfait_jours", REGLAGE_FICHE)
    fiche["specificites_paie"]["forfait_annual_days"] = 171
    donnees = banc.generer("forfait_jours", fiche_en_plus=fiche)
    assert "retraite_progressive_quotite_fiche" in alertes(donnees)


def test_pas_avant_la_date_de_debut(banc):  # noqa: F811
    donnees = banc.generer(
        "forfait_jours", fiche_en_plus=_fiche("forfait_jours", {**REGLAGE_FICHE, "date_debut": "2026-11-01"})
    )
    assert _surcotisations(donnees) == []


def test_complementaire_au_dela_du_plafond_tranche_2_et_cet():
    """Forfait de 109 jours à 2 068,12 € : Agirc-Arrco sur 4 136,24 € (218 / 109)."""
    bareme = BAREME + [
        {"id": "retraite_comp_t2", "libelle": "Retraite complémentaire T2", "base": "tranche_2",
         "salarial": 0.0864, "patronal": 0.1295},
        {"id": "cet", "libelle": "CET", "base": "assiette_cet", "salarial": 0.0014, "patronal": 0.0021},
    ]
    reglage = _reglage(vieillesse_temps_plein=False, complementaire_temps_plein=True)
    s = salaires_temps_plein(
        reglage, brut=2068.12, au_forfait_jours=True, jours_forfait=109,
        heures_contrat_mois=151.67, heures_complementaires_mois=0.0, smic_horaire=SMIC_HORAIRE,
    )
    assert s.base is None and s.complementaire == 4136.24
    lignes = {
        l["coti_id"]: l
        for l in lignes_de_surcotisation(
            reglage, s, cotisations_du_bareme=bareme, brut=2068.12, plafond=4005.0,
            assiette_plafonnee=2068.12, assiette_tranche_2=0.0, assiette_cet=0.0,
            calculer_ligne=_calculer_une_ligne,
        )
    }
    assert lignes["surcotisation_retraite_comp_t1"]["base"] == 1936.88
    assert lignes["surcotisation_retraite_comp_t2"]["base"] == 131.24
    assert lignes["surcotisation_cet"]["base"] == 4136.24
    # Base DSN : 24 = plafond − base 02 ; 22 = temps plein − réel.
    assert lignes["surcotisation_retraite_comp_t1"]["assiette_base_dsn"] == 1936.88
    assert lignes["surcotisation_retraite_comp_t2"]["assiette_base_dsn"] == 2068.12
    assert lignes["surcotisation_cet"]["assiette_base_dsn"] == 2068.12
