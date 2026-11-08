"""Exonération JEI en DSN (registre R-444).

Comme les DSN de juillet à septembre 2026 de l'ancien logiciel pour Zone 404 :
- `014` sur les bases 02 et 03, assiette de la base, montant 0,00, au taux
  salarial de vieillesse restant dû (6,90 % et 0,40 %) ;
- plus de `075`, `074` ni `076` : la part patronale exonérée disparaît ;
- au bordereau, le CTP 734 remplace le CTP 100 (921 sur la base plafonnée,
  920 sur le déplafonné avec le taux d'accident du travail déclaré).
Le CTP 734 n'est pas nul : le total du bordereau de juillet (4 296 €) ne
retombe que si l'on y compte 6,90 %, 0,40 %, l'AT et la CSA de 0,30 %.
"""

from __future__ import annotations

import pytest

from app.modules.dsn_export.domain.agregats import bordereau_urssaf
from app.modules.dsn_export.domain.cotisation_mapping import build_bases_and_cotisations

pytestmark = pytest.mark.unit

BRUT = 3608.0


def _ligne(coti_id, sal=0.0, pat=0.0, taux_sal=None, taux_pat=None, base=BRUT):
    return {
        "coti_id": coti_id,
        "libelle": coti_id,
        "base": base,
        "montant_salarial": sal,
        "montant_patronal": pat,
        "taux_salarial": taux_sal,
        "taux_patronal": taux_pat,
    }


def _lignes(exoneration=-(252.56 + 124.48 + 308.48 + 76.13)):
    return [
        _ligne("securite_sociale_maladie", pat=252.56, taux_pat=0.07),
        _ligne("allocations_familiales", pat=124.48, taux_pat=0.0345),
        _ligne("retraite_secu_plafond", sal=248.95, pat=308.48, taux_sal=0.069, taux_pat=0.0855),
        _ligne("retraite_secu_deplafond", sal=14.43, pat=76.13, taux_sal=0.004, taux_pat=0.0211),
        _ligne("at_mp", pat=31.03, taux_pat=0.0086),
        _ligne("csa", pat=10.82, taux_pat=0.003),
        _ligne("assurance_chomage", pat=144.32, taux_pat=0.04),
        _ligne("exoneration_jei", pat=exoneration),
    ]


def _construire(lignes):
    return build_bases_and_cotisations(
        lignes, brut=BRUT, period_start="01102026", period_end="31102026", default_ops="OPS-URSSAF"
    )


def _par_base(cotisations):
    par_base: dict[str, dict[str, object]] = {}
    for bloc in cotisations:
        par_base.setdefault(bloc.rubriques["_base"], {})[bloc.code] = bloc
    return par_base


def test_les_cotisations_exonerees_cedent_la_place_au_014():
    _bases, cotisations, avertissements = _construire(_lignes())
    par_base = _par_base(cotisations)

    assert "014" in par_base["02"] and "014" in par_base["03"]
    for code in ("075", "074", "076", "907", "102"):
        assert code not in par_base["02"] and code not in par_base["03"]
    assert not [a for a in avertissements if "JEI" in a or "exoneration_jei" in a]


def test_le_014_porte_l_assiette_de_la_base_un_montant_nul_et_le_taux_salarial():
    _bases, cotisations, _ = _construire(_lignes())
    par_base = _par_base(cotisations)

    plafonnee = par_base["02"]["014"].rubriques
    deplafonnee = par_base["03"]["014"].rubriques
    assert plafonnee["S21.G00.81.003"] == "3608.00"
    assert plafonnee["S21.G00.81.004"] == "0.00"
    assert plafonnee["S21.G00.81.007"] == "6.900"
    assert deplafonnee["S21.G00.81.003"] == "3608.00"
    assert deplafonnee["S21.G00.81.004"] == "0.00"
    assert deplafonnee["S21.G00.81.007"] == "0.400"


def test_les_cotisations_non_exonerees_restent_declarees():
    _bases, cotisations, _ = _construire(_lignes())
    par_base = _par_base(cotisations)

    assert par_base["03"]["045"].rubriques["S21.G00.81.004"] == "31.03"
    assert par_base["03"]["068"].rubriques["S21.G00.81.004"] == "10.82"
    assert par_base["07"]["040"].rubriques["S21.G00.81.004"] == "144.32"


def test_sans_ligne_jei_rien_ne_change():
    lignes = [l for l in _lignes() if l["coti_id"] != "exoneration_jei"]
    _bases, cotisations, _ = _construire(lignes)
    par_base = _par_base(cotisations)

    assert "014" not in par_base["02"] and "014" not in par_base["03"]
    assert "076" in par_base["02"] and "075" in par_base["03"]


def test_une_exoneration_partielle_ne_se_declare_pas_en_silence():
    """Part au-delà de 4,5 SMIC ou plafond annuel atteint : aucune DSN réelle ne
    montre comment la ventiler. La déclaration reste pleine et le dit."""
    _bases, cotisations, avertissements = _construire(_lignes(exoneration=-400.0))
    par_base = _par_base(cotisations)

    assert "014" not in par_base["02"]
    assert "076" in par_base["02"]
    assert any("JEI" in a for a in avertissements)


def _salarie_jei(assiette, plafonnee):
    return [
        {"code": "014", "base": "02", "assiette": plafonnee, "montant": 0.0, "taux": 6.9},
        {"code": "014", "base": "03", "assiette": assiette, "montant": 0.0, "taux": 0.4},
        {"code": "045", "base": "03", "assiette": assiette, "montant": round(assiette * 0.0086, 2), "taux": 0.86},
    ]


def test_le_bordereau_passe_du_ctp_100_au_734_comme_le_cabinet():
    """Assiettes de juillet 2026 : 19 133 au 734-920 (taux 0,86), 18 138 au 734-921."""
    salaries = [
        _salarie_jei(3608.00, 3608.00),
        _salarie_jei(3608.00, 3608.00),
        _salarie_jei(5000.00, 4005.00),
        _salarie_jei(3166.66, 3166.66),
        _salarie_jei(3750.00, 3750.00),
    ]
    lignes, _total, inconnus = bordereau_urssaf(salaries)
    par_cle = {(l["ctp"], l["qualifiant"]): l for l in lignes}

    assert inconnus == []
    assert ("100", "920") not in par_cle and ("100", "921") not in par_cle
    assert par_cle[("734", "920")]["assiette"] == "19133.00"
    assert par_cle[("734", "920")]["taux"] == "0.86"
    assert par_cle[("734", "921")]["assiette"] == "18138.00"
    assert par_cle[("734", "921")]["taux"] == ""


def test_le_montant_du_734_compte_la_part_salariale_de_vieillesse():
    """Le 014 porte 0,00 mais la vieillesse salariale reste due : 6,90 % + 0,40 %."""
    _lignes_23, total, _ = bordereau_urssaf([_salarie_jei(3608.00, 3608.00)])

    assert total == round(3608 * 0.069) + round(3608 * 0.004 + 31.03)


def test_la_csa_d_un_salarie_jei_rejoint_le_734():
    """La CSA reste due mais le CTP 100 n'existe plus pour ce salarié."""
    salarie = _salarie_jei(3608.00, 3608.00) + [
        {"code": "068", "base": "03", "assiette": 3608.00, "montant": 10.82, "taux": 0.3}
    ]
    lignes, total, _ = bordereau_urssaf([salarie])
    cles = {(l["ctp"], l["qualifiant"]) for l in lignes}

    assert ("100", "920") not in cles
    assert total == round(3608 * 0.069) + round(3608 * 0.004 + 31.03 + 10.82)


def test_un_salarie_sans_jei_reste_au_ctp_100():
    lignes, _total, _ = bordereau_urssaf(
        [[{"code": "045", "base": "03", "assiette": 3000.0, "montant": 25.8, "taux": 0.86}]]
    )

    assert {(l["ctp"], l["qualifiant"]) for l in lignes} == {("100", "920")}
