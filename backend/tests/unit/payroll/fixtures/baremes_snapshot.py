"""Snapshot figé de barèmes pour tests golden (hors réseau)."""

from __future__ import annotations

from typing import Any, Dict

COTISATIONS_MINIMAL: Dict[str, Any] = {
    "cotisations": [
        {
            "id": "csg_deductible",
            "libelle": "CSG déductible",
            "base": "csg_crds_base_normale",
            "salarial": 0.068,
            "patronal": None,
        },
        {
            "id": "csg_non_deductible",
            "libelle": "CSG/CRDS non déductible",
            "base": "csg_crds_base_normale",
            "salarial": 0.024,
            "patronal": None,
        },
        {
            "id": "vieillesse_plafonnee",
            "libelle": "Vieillesse plafonnée",
            "base": "brut_plafonne",
            "salarial": 0.069,
            "patronal": 0.0855,
        },
        {
            "id": "vieillesse_deplafonnee",
            "libelle": "Vieillesse déplafonnée",
            "base": "brut",
            "salarial": 0.004,
            "patronal": 0.0202,
        },
        {
            "id": "vieillesse_deplafonnee",
            "libelle": "Vieillesse déplafonnée",
            "base": "brut",
            "salarial": 0.004,
            "patronal": 0.0202,
        },
        {
            "id": "securite_sociale_maladie",
            "libelle": "Maladie, maternité, invalidité, décès",
            "base": "brut",
            "salarial": 0.0,
            "patronal": 0.07,
            "patronal_plein": 0.07,
            "patronal_reduit": 0.07,
        },
        {
            "id": "allocations_familiales",
            "libelle": "Allocations familiales",
            "base": "brut",
            "salarial": None,
            "patronal": 0.0525,
            "patronal_plein": 0.0525,
            "patronal_reduit": 0.0525,
        },
        {
            "id": "fnal",
            "libelle": "FNAL",
            "base": "brut",
            "salarial": None,
            "patronal": {
                "taux_moins_50": 0.001,
                "taux_50_et_plus": 0.005,
            },
        },
    ]
}


def baremes_snapshot() -> Dict[str, Any]:
    return {
        "cotisations": COTISATIONS_MINIMAL,
        "pas": [
            {
                "zone": "metropole",
                "periode": "mensuel_2026",
                "tranches": [
                    {"plafond": 1591.0, "taux": 0.0},
                    {"plafond": 1658.0, "taux": 0.5},
                    {"plafond": 1760.0, "taux": 1.3},
                    {"plafond": 1871.0, "taux": 2.1},
                    {"plafond": None, "taux": 11.0},
                ],
            }
        ],
        "smic": {
            "cas_general": 12.31,
            "smic_horaire_brut": 12.31,
            "smic_mensuel_brut": 1867.02,
        },
        "pss": {"mensuel": 4005.0, "annuel": 48060.0},
        "frais_pro": {
            "sections": {
                "repas": {
                    "repas": 21.1,
                    "hebergement": 0.0,
                }
            }
        },
        "heures_supp": {
            "regles_calcul_communes": {
                "taux_majoration_par_defaut": {
                    "heures_supplementaires": [
                        {"taux": 0.25},
                        {"taux": 0.50},
                    ],
                    "heures_complementaires": [
                        {"taux": 0.10},
                        {"taux": 0.25},
                    ],
                }
            }
        },
        "primes": [
            {
                "id": "prime_exceptionnelle",
                "libelle": "Prime exceptionnelle",
                "soumise_a_cotisations": True,
                "soumise_a_impot": True,
            },
            {
                "id": "prime_partage_valeur",
                "libelle": "Prime de partage de la valeur",
                "soumise_a_cotisations": False,
                "soumise_a_impot": False,
            },
            {
                "id": "prime_13eme_mois",
                "libelle": "13e mois",
                "soumise_a_cotisations": True,
                "soumise_a_impot": True,
            },
            {
                "id": "indemnite_panier_repas",
                "libelle": "Indemnité panier repas",
                "soumise_a_cotisations": False,
                "soumise_a_impot": False,
            },
        ],
        "conventions_collectives": {},
        "ij_plafonds": {
            "maladie": 51.0,
            "maternite_paternite": 95.22,
            "at_mp": 205.47,
            "at_mp_majoree": 274.0,
            "unite": "EUR/jour",
        },
        "baremes_km": {
            "annee": 2026,
            "vehicules": {
                "voitures": {
                    "segments": [
                        {"d_min": 0, "d_max": 5000},
                        {"d_min": 5001, "d_max": 20000},
                        {"d_min": 20001, "d_max": None},
                    ],
                    "tranches_cv": [
                        {
                            "cv_min": None,
                            "cv_max": 3,
                            "formules": [
                                {"segment": 1, "a": 0.529, "b": 0.0},
                                {"segment": 2, "a": 0.316, "b": 1065.0},
                                {"segment": 3, "a": 0.370, "b": 1295.0},
                            ],
                        }
                    ],
                }
            },
        },
        "taux_vmrr": [
            {"commune": "Paris", "taux": 0.025},
            {"commune": "Lyon", "taux": 0.021},
        ],
        "alternance": {
            "apprenti": {
                "regimes": [
                    {
                        "date_execution_min": None,
                        "date_execution_max": "2025-02-28",
                        "plafond_exoneration_pct_smic": 0.79,
                        "csg_crds_assujettie_au_dela_plafond": False,
                        "libelle": "Apprenti - exécution avant le 01/03/2025",
                    },
                    {
                        "date_execution_min": "2025-03-01",
                        "date_execution_max": None,
                        "plafond_exoneration_pct_smic": 0.50,
                        "csg_crds_assujettie_au_dela_plafond": True,
                        "libelle": "Apprenti - exécution à partir du 01/03/2025",
                    },
                ],
                "abattement_csg_frais_pro": 0.0175,
                "cotisations_exclues_exoneration": [
                    "mutuelle",
                    "prevoyance_cadre",
                    "prevoyance_non_cadre",
                    "apec",
                ],
                "exoneration_ir": {
                    "actif": True,
                    "plafond_annuel_pct_smic": 1.0,
                },
            },
            "professionnalisation": {"exonerations_patronales": []},
            "dsn": {
                "codes_dispositif_politique_publique": {
                    "Apprentissage": "64",
                    "Contrat de professionnalisation": "61",
                }
            },
        },
        "reduction_generale": {
            "actif": True,
            "type": "RGDU",
            "annee": 2026,
            "point_sortie_smic": 3.0,
            "p": 1.75,
            "tmin": 0.0200,
            "tdelta": {
                "fnal_moins_50": 0.3781,
                "fnal_50_et_plus": 0.3821,
            },
        },
        "stage": {
            "actif": True,
            "pct_plafond_horaire_ss": 0.15,
        },
        "jei": {
            "actif": True,
            "facteur_smic_plafond": 4.5,
            "facteur_pass_plafond_annuel": 5,
            "duree_annees": 7,
            "cotisations_exonerees_patronales": [
                "securite_sociale_maladie",
                "retraite_secu_plafond",
                "retraite_secu_deplafond",
                "allocations_familiales",
                "vieillesse_plafonnee",
                "vieillesse_deplafonnee",
            ],
        },
        "conges": {
            "taux_journalier_diviseur": 21.67,
            "taux_dixieme": 0.10,
            "jours_reference_dixieme": 30.0,
        },
        "cdd": {
            "precarite": {
                "actif": True,
                "taux": 0.10,
            },
            "indemnite_conges": {
                "actif": True,
                "taux": 0.10,
            },
        },
        "interim": {
            "ifm": {
                "actif": True,
                "taux": 0.10,
            },
            "indemnite_conges": {
                "actif": True,
                "taux": 0.10,
            },
        },
        "mandataire": {
            "cotisations_exclues": [
                "assurance_chomage",
                "ags",
                "chomage",
                "apec",
            ],
        },
        "maladie": {
            "csg_ijss": {
                "taux_deductible": 0.038,
                "taux_non_deductible": 0.029,
            },
        },
    }


def baremes_snapshot_csg_unifie() -> Dict[str, Any]:
    """Variante du snapshot avec la CSG au format production (entrée 'csg' dict).

    En production, la CSG/CRDS est une seule ligne `id='csg'` avec
    `salarial = {deductible, non_deductible}`. Cette variante sert aux tests
    apprenti dont la logique CSG repose sur ce format.
    """
    import copy

    b = copy.deepcopy(baremes_snapshot())
    cots = [
        c
        for c in b["cotisations"]["cotisations"]
        if c["id"] not in ("csg_deductible", "csg_non_deductible")
    ]
    cots.append(
        {
            "id": "csg",
            "libelle": "CSG/CRDS",
            "base": "brut",
            "salarial": {"deductible": 0.068, "non_deductible": 0.029},
            "patronal": None,
        }
    )
    b["cotisations"]["cotisations"] = cots
    return b


def entreprise_snapshot(
    effectif: int = 10,
    *,
    jei_enabled: bool = False,
    date_creation_etablissement: str | None = None,
    taux_exoneration: float = 1.0,
) -> Dict[str, Any]:
    return {
        "identification": {
            "raison_sociale": "Test SARL",
            "siret": "12345678901234",
            "adresse": "1 rue Test",
        },
        "parametres_paie": {
            "effectif": effectif,
            "periode_de_paie": {"jour_de_fin": 4, "occurrence": -2},
            "taux_specifiques": {
                "taux_versement_mobilite": 0.025,
                "taux_at_mp": 0.01,
            },
            "jei": {
                "enabled": jei_enabled,
                "date_creation_etablissement": date_creation_etablissement,
                "taux_exoneration": taux_exoneration,
            },
        },
    }
