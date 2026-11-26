"""Retraite progressive en DSN : vieillesse sur un temps plein.

Fiche net-entreprises « salarié à temps partiel cotisant au risque vieillesse
[…] sur la base d'une assiette temps plein » (v2.1, 17/12/2019) : les bases 02
et 03 gardent le réel ; la base 22 porte le différentiel non plafonné, la 24 le
différentiel plafonné (plafond moins la base 02) ; au bordereau, CTP 288
« Vieillesse temps partiel ou Mayotte », 920 et 921. Cahier technique 2026.1 :
S21.G00.40.044 = 01 (vieillesse de base) ou 02 (base et complémentaire).
"""

from __future__ import annotations

import pytest

from app.modules.dsn_export.domain.agregats import bordereau_urssaf, ctp_du_code
from app.modules.dsn_export.domain.cotisation_mapping import build_bases_and_cotisations
from app.modules.dsn_export.domain.temps_plein_reconstitue import salarie_cotisant_a_temps_plein

pytestmark = pytest.mark.unit

BRUT = 2000.0
LIGNES = [
    {"coti_id": "vieillesse_plafonnee", "libelle": "Vieillesse plafonnée", "base": BRUT,
     "montant_salarial": 138.0, "montant_patronal": 171.0, "taux_salarial": 0.069, "taux_patronal": 0.0855},
    {"coti_id": "vieillesse_deplafonnee", "libelle": "Vieillesse déplafonnée", "base": BRUT,
     "montant_salarial": 8.0, "montant_patronal": 42.2, "taux_salarial": 0.004, "taux_patronal": 0.0211},
    {"coti_id": "surcotisation_vieillesse_plafonnee",
     "libelle": "Surcotisation retraite progressive – Vieillesse plafonnée", "base": 1173.93,
     "montant_salarial": 81.0, "montant_patronal": 100.37, "taux_salarial": 0.069, "taux_patronal": 0.0855},
    {"coti_id": "surcotisation_vieillesse_deplafonnee",
     "libelle": "Surcotisation retraite progressive – Vieillesse déplafonnée", "base": 1173.93,
     "montant_salarial": 4.70, "montant_patronal": 24.77, "taux_salarial": 0.004, "taux_patronal": 0.0211},
]
COMPLEMENTAIRE = [
    {"coti_id": "surcotisation_retraite_comp_t1", "libelle": "Surcotisation retraite progressive – T1",
     "base": 1173.93, "montant_salarial": 36.98, "montant_patronal": 55.41,
     "taux_salarial": 0.0315, "taux_patronal": 0.0472},
    {"coti_id": "surcotisation_ceg_t1", "libelle": "Surcotisation retraite progressive – CEG T1",
     "base": 1173.93, "montant_salarial": 10.10, "montant_patronal": 15.14,
     "taux_salarial": 0.0086, "taux_patronal": 0.0129},
]


def _construire(lignes):
    bases, cotisations, avertissements = build_bases_and_cotisations(
        lignes, brut=BRUT, period_start="01112026", period_end="30112026", default_ops="OPS-URSSAF",
    )
    par_base: dict[str, list[dict]] = {}
    for c in cotisations:
        par_base.setdefault(c.rubriques["_base"], []).append(c.rubriques)
    return {b.code: b.montant for b in bases}, par_base, avertissements


def test_bases_22_et_24_portent_le_differentiel():
    bases, par_base, avertissements = _construire(LIGNES)
    assert bases["02"] == 2000.0 and bases["03"] == 2000.0
    assert bases["22"] == 1173.93 and bases["24"] == 1173.93
    assert avertissements == []
    (plaf,) = par_base["24"]
    assert plaf["S21.G00.81.001"] == "076"
    assert plaf["S21.G00.81.003"] == "1173.93"
    assert plaf["S21.G00.81.004"] == "181.37"
    (deplaf,) = par_base["22"]
    assert deplaf["S21.G00.81.004"] == "29.47"
    # Le réel ne bouge pas.
    assert [c["S21.G00.81.004"] for c in par_base["02"]] == ["309.00"]


def test_complementaire_131_montant_seul_sous_la_base_24():
    bases, par_base, _ = _construire(LIGNES + COMPLEMENTAIRE)
    codes_24 = {c["S21.G00.81.001"]: c for c in par_base["24"]}
    assert set(codes_24) == {"076", "131"}
    assert codes_24["131"]["S21.G00.81.004"] == f"{36.98 + 55.41 + 10.10 + 15.14:.2f}"
    assert "S21.G00.81.003" not in codes_24["131"]
    assert "S21.G00.81.002" not in codes_24["131"]


def test_bordereau_ctp_288():
    assert ctp_du_code("076", "22", 2.51) == ("288", "920")
    assert ctp_du_code("076", "24", 15.45) == ("288", "921")
    _, par_base, _ = _construire(LIGNES)
    individuelles = [
        {"code": c["S21.G00.81.001"], "base": base, "assiette": float(c.get("S21.G00.81.003") or 0),
         "montant": float(c["S21.G00.81.004"]), "taux": float(c.get("S21.G00.81.007") or 0)}
        for base, lignes in par_base.items()
        for c in lignes
    ]
    lignes_23, _, inconnus = bordereau_urssaf([individuelles])
    assert inconnus == []
    ctp_288 = {(l["ctp"], l["qualifiant"]): l for l in lignes_23 if l["ctp"] == "288"}
    assert set(ctp_288) == {("288", "920"), ("288", "921")}
    # Assiette arrondie à l'euro (L130-1) : le différentiel, pas le brut.
    assert ctp_288[("288", "921")]["assiette"] == "1174.00"
    assert ctp_288[("288", "920")]["assiette"] == "1174.00"
    # Le réel reste au CTP 100.
    assert {(l["ctp"], l["qualifiant"]) for l in lignes_23 if l["ctp"] == "100"} == {("100", "920"), ("100", "921")}


REGLAGE_BASE = {"actif": True, "date_debut": "2026-10-01", "vieillesse_temps_plein": True}
REGLAGE_BASE_ET_COMP = {**REGLAGE_BASE, "complementaire_temps_plein": True}


@pytest.mark.parametrize(
    "reglage,periode,lignes,attendu",
    [
        (None, "2026-11", LIGNES, None),
        (REGLAGE_BASE, "2026-11", LIGNES, "01"),
        (REGLAGE_BASE_ET_COMP, "2026-11", LIGNES + COMPLEMENTAIRE, "02"),
        (REGLAGE_BASE, "2026-09", LIGNES, None),
        ({**REGLAGE_BASE, "actif": False}, "2026-11", LIGNES, None),
        # Le bulletin prime : la complémentaire cochée mais non posée ne fait pas « 02 ».
        (REGLAGE_BASE_ET_COMP, "2026-11", LIGNES, "01"),
    ],
)
def test_rubrique_40_044(reglage, periode, lignes, attendu):
    specificites = {"retraite_progressive": reglage} if reglage is not None else {}
    assert salarie_cotisant_a_temps_plein(specificites, periode, lignes).code == attendu


@pytest.mark.parametrize("lignes", [LIGNES[:2], []], ids=["forfait_au_dela_1_7_smic", "brut_nul"])
def test_rubrique_40_044_absente_sans_surcotisation_au_bulletin(lignes):
    """Réglage actif, mais le moteur n'a rien posé (forfait au-delà de 1,7 SMIC,
    brut nul) : pas de S21.G00.40.044, et l'aperçu le dit."""
    resultat = salarie_cotisant_a_temps_plein({"retraite_progressive": REGLAGE_BASE}, "2026-11", lignes)
    assert resultat.code is None
    assert "aucune surcotisation au bulletin" in (resultat.avertissement or "")


def test_complementaire_seule_rubrique_vide_et_avertie():
    resultat = salarie_cotisant_a_temps_plein(
        {"retraite_progressive": {"actif": True, "complementaire_temps_plein": True}},
        "2026-11",
        LIGNES[:2] + COMPLEMENTAIRE,
    )
    assert resultat.code is None and "complémentaire seule" in (resultat.avertissement or "")


def test_forfait_social_de_la_prise_en_charge_071_a_20_pourcent_ctp_012():
    """Prise en charge de la part salariale complémentaire : forfait social
    (CSS L137-15) au code 071, base 05, taux 20 %, CTP 012 du bordereau."""
    forfait_social = {
        "coti_id": "forfait_social", "libelle": "Forfait social 20% sur prise en charge retraite progressive",
        "base": 47.08, "montant_salarial": 0.0, "montant_patronal": 9.42,
        "taux_salarial": None, "taux_patronal": 0.20,
    }
    _, par_base, avertissements = _construire(LIGNES + COMPLEMENTAIRE + [forfait_social])
    assert avertissements == []
    (fs,) = par_base["05"]
    assert fs["S21.G00.81.001"] == "071"
    assert fs["S21.G00.81.003"] == "47.08" and fs["S21.G00.81.004"] == "9.42"
    assert ctp_du_code("071", "05", 20.0) == ("012", "920")


def test_forfait_vieillesse_et_complementaire_differentes_base_de_la_vieillesse_et_avertie():
    """Forfait jours : vieillesse à 1,7 SMIC, Agirc-Arrco à 218 / jours ; la base 22
    porte la vieillesse (temps plein − réel), jamais une part de tranche 2."""
    lignes = [dict(l) for l in LIGNES] + [
        {"coti_id": "surcotisation_retraite_comp_t2", "libelle": "Surcotisation retraite progressive – T2",
         "base": 131.24, "assiette_base_dsn": 2068.12, "montant_salarial": 11.34, "montant_patronal": 17.0},
        {"coti_id": "surcotisation_cet", "libelle": "Surcotisation retraite progressive – CET",
         "base": 4136.24, "assiette_base_dsn": 2068.12, "montant_salarial": 5.79, "montant_patronal": 8.69},
    ]
    bases, par_base, avertissements = _construire(lignes)
    assert bases["22"] == 1173.93
    assert [c["S21.G00.81.001"] for c in par_base["22"]] == ["076", "131"]
    assert any("base 22" in a and "2068.12" in a for a in avertissements)


def test_complementaire_seule_porte_sa_base():
    lignes = [dict(l) for l in LIGNES[:2]] + [
        {"coti_id": "surcotisation_retraite_comp_t1", "libelle": "Surcotisation retraite progressive – T1",
         "base": 1936.88, "assiette_base_dsn": 1936.88, "montant_salarial": 61.01, "montant_patronal": 91.42},
    ]
    bases, par_base, avertissements = _construire(lignes)
    assert bases["24"] == 1936.88 and "22" not in bases
    assert avertissements == []
