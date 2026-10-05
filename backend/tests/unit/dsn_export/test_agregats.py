"""Blocs de l'établissement qui portent le paiement : versements aux organismes
(S21.G00.20), bordereau (22) et cotisations agrégées Urssaf (23),
assujettissements fiscaux (44).

Règles vérifiées sur les douze DSN 2026 (janvier à juin, deux sociétés) de
l'ancien logiciel : le bordereau reconstruit depuis leurs cotisations
individuelles retombe à l'euro sur le leur, la retraite complémentaire au
centime, le PAS à l'euro. Données des tests inventées.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.agregats import bordereau_urssaf
from app.modules.dsn_export.domain.settings import DsnSettings, depuis_dict, extraire_depuis_dsn, vers_dict
from app.modules.dsn_export.domain.writer import encode_dsn_bytes

URSSAF = "79484650100011"
CAISSE_RETRAITE = "30558637200321"


def _ligne(code: str, base: str, assiette: float, montant: float, taux: str = "0.000", ops: str = URSSAF):
    return {"code": code, "base": base, "assiette": assiette, "montant": montant, "taux": taux, "ops": ops}


SALARIE_A = [
    _ligne("075", "03", 3000.0, 210.0, "7.000"),
    _ligne("074", "03", 3000.0, 103.5, "3.450"),
    _ligne("076", "03", 3000.0, 75.3, "2.510"),
    _ligne("068", "03", 3000.0, 9.0, "0.300"),
    _ligne("045", "03", 3000.0, 94.5, "3.150"),
    _ligne("076", "02", 3000.0, 463.5, "15.450"),
    _ligne("072", "04", 2947.5, 271.17, "9.200"),
    _ligne("079", "04", 2947.5, 14.74, "0.500"),
    _ligne("049", "02", 3000.0, 3.0, "0.100"),
    _ligne("040", "07", 3000.0, 88.5, "2.950"),
    _ligne("048", "07", 3000.0, 7.5, "0.250"),
    _ligne("018", "03", 3000.0, -420.4, "0.000"),
    _ligne("114", "03", 400.0, -45.24, "11.310"),
    _ligne("071", "05", 40.0, 3.2, "8.000"),
    _ligne("071", "05", 90.0, 18.0, "20.000"),
    _ligne("142", "02", 0.0, 180.0, "6.010"),
]
SALARIE_B = [
    _ligne("075", "03", 1900.0, 133.0, "7.000"),
    _ligne("045", "03", 1900.0, 59.85, "3.150"),
    _ligne("076", "02", 1900.0, 293.55, "15.450"),
    # Régularisation annuelle de la réduction : positive, elle part en 669.
    _ligne("018", "03", 1900.0, 120.6, "0.000"),
    _ligne("907", "03", 1900.0, 114.0, "6.000"),
]


def test_bordereau_urssaf_regroupe_par_code_type_de_personnel():
    lignes, total, inconnus = bordereau_urssaf([SALARIE_A, SALARIE_B])
    par_ctp = {(l["ctp"], l["qualifiant"]): l for l in lignes}
    # Régime général déplafonné : assiette = brut, taux AT déclaré à côté.
    assert par_ctp[("100", "920")]["assiette"] == "4900.00"
    assert par_ctp[("100", "920")]["taux"] == "3.15"
    assert par_ctp[("100", "921")]["assiette"] == "4900.00"
    assert par_ctp[("260", "920")]["assiette"] == "2948.00"  # 2 947,50 arrondi à l'euro
    # Chômage à taux modulé (bonus-malus) : CTP 725, le taux en clair.
    assert par_ctp[("725", "920")]["taux"] == "2.95"
    assert ("772", "920") not in par_ctp
    # Réductions : en montant ; la régularisation positive en 669, en assiette.
    assert par_ctp[("668", "921")]["montant"] == "420.00"
    assert par_ctp[("669", "921")]["assiette"] == "121.00"
    assert par_ctp[("003", "921")]["montant"] == "45.00"
    assert par_ctp[("479", "920")]["assiette"] == "40.00"
    assert par_ctp[("012", "920")]["assiette"] == "90.00"
    # La part patronale Agirc-Arrco (142) n'est pas une cotisation Urssaf.
    assert all(l["ctp"] != "142" for l in lignes)
    assert inconnus == []
    # Total : chaque CTP arrondi à l'euro (100 920 : 685,15 → 685 ; 100 921 :
    # 757,05 → 757 ; 260 : 285,91 → 286…), réductions déduites, 669 ajouté.
    assert total == 685 + 757 + 286 + 3 + 89 + 8 + 114 + 3 + 18 - 420 - 45 + 121


def test_taux_absent_retrouve_depuis_montant_et_assiette():
    """Un bulletin repris ne porte pas toujours le taux : 1 849,32 € sur
    62 689,04 € de chômage, c'est 2,95 % (taux modulé), pas un taux nul."""
    lignes, _, _ = bordereau_urssaf(
        [
            [
                _ligne("040", "07", 62689.04, 1849.32, "0.000"),
                _ligne("045", "03", 62689.04, 1974.72, "0.000"),
                _ligne("075", "03", 62689.04, 4388.23, "7.000"),
            ]
        ]
    )
    par_ctp = {(l["ctp"], l["qualifiant"]): l for l in lignes}
    assert par_ctp[("725", "920")]["taux"] == "2.95"
    assert par_ctp[("100", "920")]["taux"] == "3.15"


def test_code_sans_correspondance_signale():
    _, _, inconnus = bordereau_urssaf([[_ligne("999", "03", 100.0, 1.0, "1.000")]])
    assert inconnus == ["999"]


CABINET = "\r\n".join(
    [
        "S21.G00.20.001,'30558637200321'",
        "S21.G00.20.003,'CEPAFRPP000'",
        "S21.G00.20.004,'FR7600000000000000000000000'",
        "S21.G00.20.005,'1339.88'",
        "S21.G00.20.010,'05'",
        "S21.G00.20.001,'79484650100011'",
        "S21.G00.20.003,'CEPAFRPP000'",
        "S21.G00.20.004,'FR7600000000000000000000000'",
        "S21.G00.20.005,'6696.00'",
        "S21.G00.20.010,'05'",
        "S21.G00.20.001,'DGFIP'",
        "S21.G00.20.002,'DGFIP_PAS'",
        "S21.G00.20.003,'CEPAFRPP000'",
        "S21.G00.20.004,'FR7600000000000000000000000'",
        "S21.G00.20.005,'244.00'",
        "S21.G00.20.010,'05'",
        "S21.G00.44.001,'001'",
        "S21.G00.44.002,'0.00'",
        "S21.G00.44.003,'2026'",
        "S21.G00.44.001,'013'",
        "S21.G00.44.002,'0.00'",
        "S21.G00.44.003,'2026'",
    ]
).encode("latin-1")


def test_le_parametrage_reprend_versements_et_assujettissements_du_cabinet():
    settings = extraire_depuis_dsn(CABINET)
    assert [v["organisme"] for v in settings.versements] == [CAISSE_RETRAITE, URSSAF, "DGFIP"]
    assert settings.versements[2]["entite"] == "DGFIP_PAS"
    assert settings.versements[1]["iban"] == "FR7600000000000000000000000"
    assert settings.assujettissements_fiscaux == ["001", "013"]
    # Aller-retour par la base.
    relu = depuis_dict(vers_dict(settings))
    assert relu.versements == settings.versements
    assert relu.assujettissements_fiscaux == ["001", "013"]


SOCIETE = {
    "siret": "12345678900011",
    "name": "Société d'essai",
    "address": {"rue": "1 rue de l'Essai", "code_postal": "01000", "ville": "BOURG EN BRESSE"},
    "code_naf": "2229A",
    "urssaf_number": URSSAF,
    "taux_at_mp": 3.15,
}

SALARIE = {
    "id": "e1",
    "first_name": "Paul",
    "last_name": "ESSAI",
    "nir": "177017512345678",
    "sexe": "M",
    "date_naissance": "1977-01-01",
    "lieu_naissance": "PARIS (75)",
    "adresse": {"rue": "1 rue du Test", "code_postal": "01000", "ville": "BOURG EN BRESSE"},
    "hire_date": "2014-09-01",
    "contract_type": "CDI",
    "statut": "Non-Cadre",
    "duree_hebdomadaire": 35.0,
    "classification_conventionnelle": {
        "pcs": "674a",
        "idcc": "0292",
        "position": "200",
        "niveau_dsn": "710",
        "classification_dsn": "252HK",
        "taux_at_individuel_dsn": "3.15",
        "code_statut_dsn": "06",
        "numero_contrat_dsn": "00000",
    },
}

BULLETIN = {
    "salaire_brut": 3000.0,
    "synthese_net": {
        "net_imposable": 2300.0,
        "montant_net_social": 2350.0,
        "impot_prelevement_a_la_source": {"base": 2300.0, "taux": 2.0, "montant": 46.47},
    },
    "calcul_du_brut": [{"libelle": "Salaire de base", "quantite": 151.67, "gain": 3000.0}],
    "structure_cotisations": {
        "bloc_principales": [
            {"coti_id": "securite_sociale_maladie", "base": 3000.0, "taux_patronal": 0.07, "montant_patronal": 210.0},
            {"coti_id": "retraite_secu_plafond", "base": 3000.0, "taux_salarial": 0.069, "montant_salarial": 207.0, "taux_patronal": 0.0855, "montant_patronal": 256.5},
            {"coti_id": "retraite_comp_t1", "base": 3000.0, "taux_salarial": 0.0315, "montant_salarial": 94.5, "taux_patronal": 0.0472, "montant_patronal": 141.6},
            {"coti_id": "at_mp", "base": 3000.0, "taux_patronal": 0.0315, "montant_patronal": 94.5},
        ],
        "bloc_allegements": [
            {"coti_id": "reduction_generale", "base": 3000.0, "montant_patronal": -400.0, "smic_reference_mois": 1867.06},
        ],
    },
}

PARAMETRES = DsnSettings(
    idcc="0292",
    versements=[
        {"organisme": CAISSE_RETRAITE, "bic": "CEPAFRPP000", "iban": "FR7600000000000000000000000", "mode": "05"},
        {"organisme": URSSAF, "bic": "CEPAFRPP000", "iban": "FR7600000000000000000000000", "mode": "05"},
        {"organisme": "DGFIP", "entite": "DGFIP_PAS", "bic": "CEPAFRPP000", "iban": "FR7600000000000000000000000", "mode": "05"},
    ],
    assujettissements_fiscaux=["001", "013"],
)


def _lignes() -> List[Tuple[str, str]]:
    fichier, _ = build_parsed_dsn_from_payroll(
        SOCIETE, [{"employee": SALARIE, "payslip_data": BULLETIN}], "2026-06", settings=PARAMETRES
    )
    texte = encode_dsn_bytes(fichier).decode("iso-8859-15")
    return [(l.split(",", 1)[0], l.split(",", 1)[1].strip("'")) for l in texte.splitlines()]


def _blocs(lignes, bloc: str) -> List[Dict[str, str]]:
    sortie: List[Dict[str, str]] = []
    precedent = None
    for rubrique, valeur in lignes:
        if not rubrique.startswith(bloc + "."):
            precedent = None
            continue
        numero = rubrique.rsplit(".", 1)[1]
        if precedent is None or numero <= precedent:
            sortie.append({})
        sortie[-1][numero] = valeur
        precedent = numero
    return sortie


def test_les_versements_portent_urssaf_retraite_complementaire_et_pas():
    versements = {v["001"]: v for v in _blocs(_lignes(), "S21.G00.20")}
    # Retraite complémentaire : 131 (+ 132, 106) au centime.
    retraite = round(94.5 + 141.6 - round(400.0 * 6.01 / 39.81, 2), 2)
    assert versements[CAISSE_RETRAITE]["005"] == f"{retraite:.2f}"
    # PAS arrondi à l'euro, entité DGFIP_PAS.
    assert versements["DGFIP"]["005"] == "46.00"
    assert versements["DGFIP"]["002"] == "DGFIP_PAS"
    assert versements[URSSAF]["006"] == "01062026"
    assert versements[URSSAF]["007"] == "30062026"
    assert versements[URSSAF]["010"] == "05"
    bordereau = _blocs(_lignes(), "S21.G00.22")[0]
    assert bordereau["001"] == URSSAF
    assert versements[URSSAF]["005"] == bordereau["005"]


def test_ordre_des_blocs_de_l_etablissement():
    ordre = []
    for rubrique, _ in _lignes():
        bloc = rubrique.rsplit(".", 1)[0]
        if not ordre or ordre[-1] != bloc:
            ordre.append(bloc)
    entete = ordre[: ordre.index("S21.G00.30")]
    assert entete.index("S21.G00.11") < entete.index("S21.G00.20") < entete.index("S21.G00.22")
    assert entete.index("S21.G00.22") < entete.index("S21.G00.23") < entete.index("S21.G00.44")


def test_assujettissements_fiscaux_du_millesime():
    assert _blocs(_lignes(), "S21.G00.44") == [
        {"001": "001", "002": "0.00", "003": "2026"},
        {"001": "013", "002": "0.00", "003": "2026"},
    ]
