"""La norme DSN se choisit selon le mois principal déclaré (registre R-454).

Cahier technique 2027.1.3 et note différentielle CT2026.1 → CT2027.1 :
S10.G00.00.006 vaut P27V01 ; S21.G00.06.003 et S21.G00.11.002 sont supprimées
(§ 11) ; S21.G00.40.084 se renseigne pour un temps partiel et un forfait jours
réduit (§ 4.5). Une DSN de 2026 reste en P26V01, à l'identique.
"""

from __future__ import annotations

import pytest

from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.norme import norme_de_la_periode
from app.modules.dsn_export.domain.writer import encode_dsn_bytes
from app.modules.dsn_import.domain.parser import parse_dsn_content

pytestmark = pytest.mark.unit

RUB_NORME = "S10.G00.00.006"
RUB_APEN = "S21.G00.06.003"
RUB_APET = "S21.G00.11.002"
RUB_PRORATISATION = "S21.G00.40.084"


def _societe(**champs):
    return {
        "siret": "12345678900015",
        "name": "SOCIETE TEST",
        "code_naf": "2562B",
        "address": {"rue": "1 RUE TEST", "code_postal": "75001", "ville": "PARIS"},
        **champs,
    }


def _ligne(**champs):
    employee = {
        "id": "emp-1",
        "first_name": "Prenom",
        "last_name": "Nom",
        "nir": "1850175123456",
        "sexe": "M",
        "date_naissance": "1985-01-15",
        "lieu_naissance": "PARIS",
        "contract_type": "CDI",
        "hire_date": "2020-01-01",
        "statut": "Non-Cadre",
        "adresse": {"rue": "10 AVENUE TEST", "code_postal": "75010", "ville": "PARIS"},
        "matricule": "TEST",
        "idcc": "1486",
        "pcs": "389a",
        "job_title": "Technicien",
        "specificites_paie": {},
        **champs,
    }
    return {
        "employee": employee,
        "payslip_data": {
            "salaire_brut": 2500.0,
            "heures_remunerees": 151.67,
            "synthese_net": {
                "net_imposable": 2000.0,
                "net_a_payer": 1850.0,
                "impot_prelevement_a_la_source": {
                    "montant": 100.0,
                    "taux": 5.0,
                    "base": 2000.0,
                },
            },
            "structure_cotisations": {
                "total_salarial": 0.0,
                "total_patronal": 0.0,
                "bloc_principales": [],
            },
        },
    }


def _fichier(periode, *lignes, **societe):
    dsn, _ = build_parsed_dsn_from_payroll(
        _societe(**societe), list(lignes) or [_ligne()], periode
    )
    return encode_dsn_bytes(dsn).decode("latin-1")


def _valeurs(texte, rubrique):
    return [
        ligne.split(",", 1)[1].strip("'\r")
        for ligne in texte.splitlines()
        if ligne.startswith(rubrique + ",")
    ]


@pytest.mark.parametrize(
    "periode, norme",
    [
        ("2025-06", "P26V01"),
        ("2026-01", "P26V01"),
        ("2026-12", "P26V01"),
        ("2027-01", "P27V01"),
        ("2027-12", "P27V01"),
    ],
)
def test_la_norme_suit_l_annee_du_mois_principal(periode, norme):
    assert norme_de_la_periode(periode) == norme


def test_une_annee_sans_norme_publiee_est_refusee():
    with pytest.raises(ValueError, match="2028"):
        norme_de_la_periode("2028-01")


def test_la_dsn_de_janvier_2027_sort_en_p27():
    texte = _fichier("2027-01")
    assert _valeurs(texte, RUB_NORME) == ["P27V01"]
    assert parse_dsn_content(texte.encode("latin-1"), file_name="j.dsn").envoi.norme == "P27V01"


def test_la_dsn_de_janvier_2027_ne_porte_plus_les_codes_ape():
    texte = _fichier("2027-01")
    assert _valeurs(texte, RUB_APEN) == []
    assert _valeurs(texte, RUB_APET) == []


def test_en_2027_le_code_naf_manquant_ne_bloque_plus():
    assert _valeurs(_fichier("2027-01", code_naf=""), RUB_NORME) == ["P27V01"]


def test_une_dsn_de_2026_reste_a_l_identique():
    texte = _fichier("2026-12", _ligne(is_temps_partiel=True, duree_hebdomadaire=24))
    assert _valeurs(texte, RUB_NORME) == ["P26V01"]
    assert _valeurs(texte, RUB_APEN) == ["2562B"]
    assert _valeurs(texte, RUB_APET) == ["2562B"]
    assert _valeurs(texte, RUB_PRORATISATION) == []


@pytest.mark.parametrize(
    "champs, attendu",
    [
        # Le bulletin réduit le plafond au prorata de la durée (art. R242-7 CSS).
        ({"is_temps_partiel": True, "duree_hebdomadaire": 24}, ["01"]),
        # Fiche cochée temps partiel à 35 h : le bulletin garde le plafond plein.
        ({"is_temps_partiel": True, "duree_hebdomadaire": 35}, ["02"]),
        # Forfait réduit : le run forfait ne proratise pas le plafond.
        (
            {"is_forfait_jour": True, "specificites_paie": {"forfait_annual_days": 43}},
            ["02"],
        ),
        ({"is_temps_partiel": False, "duree_hebdomadaire": 35}, []),
        ({"is_forfait_jour": True}, []),
        (
            {"is_forfait_jour": True, "specificites_paie": {"forfait_annual_days": 218}},
            [],
        ),
    ],
)
def test_proratisation_du_plafond_en_2027(champs, attendu):
    assert _valeurs(_fichier("2027-01", _ligne(**champs)), RUB_PRORATISATION) == attendu


def test_la_proratisation_se_place_apres_les_rubriques_du_contrat():
    texte = _fichier("2027-01", _ligne(is_temps_partiel=True, duree_hebdomadaire=24))
    rubriques = [
        ligne.split(",", 1)[0]
        for ligne in texte.splitlines()
        if ligne.startswith("S21.G00.40.")
    ]
    assert rubriques == sorted(rubriques)


def _ligne_avec_cet():
    ligne = _ligne()
    ligne["payslip_data"]["structure_cotisations"]["bloc_principales"] = [
        {
            "coti_id": "cet",
            "libelle": "Contribution d'équilibre technique",
            "base": 2500.0,
            "taux_salarial": 0.14,
            "montant_salarial": 3.5,
            "taux_patronal": 0.21,
            "montant_patronal": 5.25,
        }
    ]
    return ligne


def test_en_2027_la_cet_patronale_passe_sur_son_propre_code():
    """Cahier 2027.1 : 146 « hors CET », 148 « CET part patronale » (note, § 8.2)."""
    texte = _fichier("2027-01", _ligne_avec_cet())
    codes = _valeurs(texte, "S21.G00.81.001")
    assert "148" in codes
    assert "146" not in codes


def test_en_2026_la_cet_patronale_reste_sur_146():
    codes = _valeurs(_fichier("2026-12", _ligne_avec_cet()), "S21.G00.81.001")
    assert "146" in codes
    assert "148" not in codes
