"""R-394 : abattement « contrats courts » du prélèvement à la source.

BOI-IR-PAS-20-20-30-10 § 230 à 290 (CGI 204 H, III-1-d) : un CDD ou une mission
dont le terme initial n'excède pas deux mois, sans taux transmis, a son assiette
réduite d'un demi-Smic net imposable sur les salaires des deux premiers mois
d'embauche ; le taux de la grille se lit sur la base abattue. Le montant se lit
au BOI-BAREME-000037 § 30 (748 € au 01/01/2026, 766 € au 01/06/2026).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_net import (
    _base_pas_du_mois,
    _calculer_prelevement_a_la_source,
)
from app.shared.pas_taux import terme_de_deux_mois_au_plus

GRILLE = [
    {
        "zone": "metropole",
        "tranches": [
            {"plafond": 1635, "taux": 0.0},
            {"plafond": 1698, "taux": 0.005},
            {"plafond": 1807, "taux": 0.013},
            {"plafond": 1928, "taux": 0.021},
            {"plafond": None, "taux": 0.029},
        ],
    }
]


class _Contexte:
    def __init__(
        self,
        debut="2026-10-05",
        fin="2026-10-30",
        type_contrat="CDD",
        bloc_pas=None,
        date_fin_periode=date(2026, 10, 31),
    ):
        self.contrat = {
            "contrat": {"date_entree": debut, "date_fin_contrat": fin, "type_contrat": type_contrat},
            "specificites_paie": {"prelevement_a_la_source": bloc_pas if bloc_pas is not None else {}},
        }
        self.baremes = {"pas": GRILLE}
        self.entreprise = {"identification": {"adresse": {"code_postal": "79140"}}}
        self.is_alsace_moselle = False
        self.is_apprenti = False
        self.is_cdd = type_contrat == "CDD"
        self.is_interim = type_contrat == "Intérim"
        self.is_professionnalisation = False
        self.is_stagiaire = False
        self.date_fin_periode = date_fin_periode


@pytest.mark.parametrize(
    "debut, fin, attendu",
    [
        (date(2026, 1, 15), date(2026, 3, 14), True),  # § 250 : le dernier jour permis
        (date(2026, 1, 15), date(2026, 3, 15), False),  # § 250 : dépasse d'un jour
        (date(2026, 9, 21), date(2026, 10, 31), True),
        (date(2025, 12, 31), date(2026, 2, 28), True),  # 2 mois de date à date, février court
        (date(2025, 12, 31), date(2026, 3, 1), False),
    ],
)
def test_terme_de_deux_mois_de_date_a_date(debut, fin, attendu):
    assert terme_de_deux_mois_au_plus(debut, fin) is attendu


def test_cas_du_registre_un_mois_sans_taux_ne_paie_rien():
    """1 900 € imposables, sans taux : base 1 134 €, sous la première tranche."""
    assert _calculer_prelevement_a_la_source(_Contexte(), 1900.0) == 0.0


def test_le_taux_et_le_montant_portent_sur_la_base_abattue():
    """§ 270 : 2 600 € - 766 € = 1 834 € → tranche 2,1 %, soit 38,51 €."""
    assert _base_pas_du_mois(_Contexte(), 2600.0) == 1834.0
    assert _calculer_prelevement_a_la_source(_Contexte(), 2600.0) == 38.51


def test_au_dela_de_la_duree_pas_d_abattement():
    """CDD du 15/01 au 15/03 : plus de deux mois, la grille s'applique au net entier."""
    ctx = _Contexte("2026-01-15", "2026-03-15", date_fin_periode=date(2026, 2, 28))
    assert _base_pas_du_mois(ctx, 2600.0) == 2600.0


def test_un_taux_transmis_ecarte_l_abattement():
    ctx = _Contexte(bloc_pas={"taux": 5.0, "type_taux": "01"})
    assert _base_pas_du_mois(ctx, 2600.0) == 2600.0


def test_un_taux_de_bareme_reste_une_absence_de_taux():
    ctx = _Contexte(bloc_pas={"taux": 0.0, "type_taux": "13"})
    assert _base_pas_du_mois(ctx, 2600.0) == 1834.0


def test_cdi_et_terme_inconnu_ne_sont_pas_abattus():
    assert _base_pas_du_mois(_Contexte(type_contrat="CDI"), 2600.0) == 2600.0
    # Terme imprécis : la durée minimale du contrat n'est pas sur la fiche.
    assert _base_pas_du_mois(_Contexte(fin=None), 2600.0) == 2600.0


def test_mission_d_interim_abattue():
    assert _base_pas_du_mois(_Contexte(type_contrat="Intérim"), 2600.0) == 1834.0


@pytest.mark.parametrize(
    "fin_periode, attendu",
    [
        (date(2026, 9, 30), 1834.0),  # M : le mois d'embauche
        (date(2026, 10, 31), 1834.0),  # M+1
        (date(2026, 11, 30), 1834.0),  # M+2 : mois de fin dans les deux premiers mois
        (date(2026, 12, 31), 2600.0),  # hors des deux premiers mois
    ],
)
def test_seuls_les_deux_premiers_mois_civils_sont_abattus(fin_periode, attendu):
    ctx = _Contexte("2026-09-25", "2026-11-20", date_fin_periode=fin_periode)
    assert _base_pas_du_mois(ctx, 2600.0) == attendu


@pytest.mark.parametrize(
    "fin_periode, abattement",
    [
        (date(2026, 5, 31), 748.0),
        (date(2026, 6, 30), 766.0),
    ],
)
def test_le_montant_est_celui_en_vigueur_au_versement(fin_periode, abattement):
    """§ 260 : montant en vigueur au moment du versement (BOI-BAREME-000037)."""
    ctx = _Contexte(
        "2026-05-04", "2026-06-20", date_fin_periode=fin_periode
    )
    assert _base_pas_du_mois(ctx, 2600.0) == round(2600.0 - abattement, 2)


def test_une_annee_sans_montant_publie_garde_le_dernier_et_le_dit():
    ctx = _Contexte("2027-01-04", "2027-01-29", date_fin_periode=date(2027, 1, 31))
    ctx.alertes_baremes = []
    assert _base_pas_du_mois(ctx, 2600.0) == 1834.0
    assert [a["code"] for a in ctx.alertes_baremes] == ["pas_abattement_contrat_court_a_mettre_a_jour"]
    # Une seule alerte par bulletin : le moteur repasse deux fois sur la base.
    _base_pas_du_mois(ctx, 2600.0)
    assert len(ctx.alertes_baremes) == 1


def test_net_inferieur_a_l_abattement_donne_zero():
    assert _base_pas_du_mois(_Contexte(), 500.0) == 0.0
