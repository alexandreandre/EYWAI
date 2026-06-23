"""Constantes protection sociale Comitech Composite (tableaux Quadra)."""

from __future__ import annotations

from typing import Any

MUTUELLE_AMOUNT_TOLERANCE = 0.02

COMITECH_MUTUELLE_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "libelle": "AG2R Isolé 2025 (EMU0)",
        "montant_salarial": 31.58,
        "montant_patronal": 31.58,
        "pack_couverture": "isole",
        "benefits_year": 2025,
        "quadra_code": "EMU0",
    },
    {
        "libelle": "AG2R Famille 2025 (EMU1+SMU1)",
        "montant_salarial": 108.61,
        "montant_patronal": 0.0,
        "pack_couverture": "famille",
        "benefits_year": 2025,
        "quadra_code": "EMU1+SMU1",
    },
    {
        "libelle": "GAN Isolé 2026 (EMU3)",
        "montant_salarial": 29.24,
        "montant_patronal": 29.24,
        "pack_couverture": "isole",
        "benefits_year": 2026,
        "quadra_code": "EMU3",
    },
    {
        "libelle": "GAN Famille 2026 (EMU4+SMU2)",
        "montant_salarial": 98.12,
        "montant_patronal": 0.0,
        "pack_couverture": "famille",
        "benefits_year": 2026,
        "quadra_code": "EMU4+SMU2",
    },
)

PREVOYANCE_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "gan_cadre_2026": [
        {
            "id": "gan_cadre_ta_2026",
            "libelle": "Prévoyance GAN Cadre TA",
            "salarial": 0.00365,
            "patronal": 0.01825,
            "forfait_social": 0.0,
            "base": "brut_plafonne",
        },
        {
            "id": "gan_cadre_tb_2026",
            "libelle": "Prévoyance GAN Cadre TB",
            "salarial": 0.01140,
            "patronal": 0.01710,
            "forfait_social": 0.0,
            "base": "tranche_2",
        },
    ],
    "gan_cadre_2025": [
        {
            "id": "gan_cadre_ta_2025",
            "libelle": "Prévoyance GAN Cadre TA",
            "salarial": 0.00365,
            "patronal": 0.01825,
            "forfait_social": 0.0,
            "base": "brut_plafonne",
        },
        {
            "id": "gan_cadre_tb_2025",
            "libelle": "Prévoyance GAN Cadre TB",
            "salarial": 0.01140,
            "patronal": 0.01710,
            "forfait_social": 0.0,
            "base": "tranche_2",
        },
    ],
    "alptis_cadre_2025": [
        {
            "id": "epca",
            "libelle": "Prévoyance ALPTIS Cadre TA (EPCA)",
            "salarial": 0.00197,
            "patronal": 0.00983,
            "forfait_social": 0.0,
            "base": "brut_plafonne",
        },
        {
            "id": "epcb",
            "libelle": "Prévoyance ALPTIS Cadre TB (EPCB)",
            "salarial": 0.00468,
            "patronal": 0.00702,
            "forfait_social": 0.0,
            "base": "tranche_2",
        },
        {
            "id": "epc1",
            "libelle": "Prévoyance ALPTIS Cadre TA (EPC1)",
            "salarial": 0.00223,
            "patronal": 0.01117,
            "forfait_social": 0.0,
            "base": "brut_plafonne",
        },
        {
            "id": "epc2",
            "libelle": "Prévoyance ALPTIS Cadre TB (EPC2)",
            "salarial": 0.01256,
            "patronal": 0.01884,
            "forfait_social": 0.0,
            "base": "tranche_2",
        },
    ],
    "gan_non_cadre_2026": [
        {
            "id": "epna_2026",
            "libelle": "Prévoyance GAN Non-cadre TA",
            "salarial": 0.00465,
            "patronal": 0.00465,
            "forfait_social": 0.0,
            "base": "brut_plafonne",
        },
        {
            "id": "epnb_2026",
            "libelle": "Prévoyance GAN Non-cadre TB",
            "salarial": 0.00465,
            "patronal": 0.00465,
            "forfait_social": 0.0,
            "base": "tranche_2",
        },
    ],
    "mutex_non_cadre_2025": [
        {
            "id": "epna_2025",
            "libelle": "Prévoyance MUTEX Non-cadre TA",
            "salarial": 0.00400,
            "patronal": 0.00400,
            "forfait_social": 0.0,
            "base": "brut_plafonne",
        },
        {
            "id": "epnb_2025",
            "libelle": "Prévoyance MUTEX Non-cadre TB",
            "salarial": 0.00400,
            "patronal": 0.00400,
            "forfait_social": 0.0,
            "base": "tranche_2",
        },
    ],
}

RETRAITE_SUP_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "ag2r_eres_2026": [
        {
            "id": "eres_ta",
            "libelle": "Retraite sup AG2R La Mondiale TA (ERES)",
            "salarial": 0.025,
            "patronal": 0.025,
            "base": "brut_plafonne",
        },
        {
            "id": "eres_tb",
            "libelle": "Retraite sup AG2R La Mondiale TB",
            "salarial": 0.0,
            "patronal": 0.0,
            "base": "tranche_2",
        },
    ],
}
