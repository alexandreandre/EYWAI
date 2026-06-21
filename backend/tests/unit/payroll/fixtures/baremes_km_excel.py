"""Fixture barème km — cas recette Excel Elsa (4 CV / 7 CV)."""

from __future__ import annotations

from typing import Any, Dict


def baremes_km_excel_fixture() -> Dict[str, Any]:
    return {
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
                        "cv_min": 4,
                        "cv_max": 4,
                        "formules": [
                            {"segment": 1, "a": 0.606, "b": 0.0},
                            {"segment": 2, "a": 0.340, "b": 1065.0},
                            {"segment": 3, "a": 0.370, "b": 1295.0},
                        ],
                    },
                    {
                        "cv_min": 5,
                        "cv_max": 5,
                        "formules": [
                            {"segment": 1, "a": 0.636, "b": 0.0},
                            {"segment": 2, "a": 0.357, "b": 1065.0},
                            {"segment": 3, "a": 0.394, "b": 1295.0},
                        ],
                    },
                    {
                        "cv_min": 7,
                        "cv_max": None,
                        "formules": [
                            {"segment": 1, "a": 0.697, "b": 0.0},
                            {"segment": 2, "a": 0.401, "b": 1065.0},
                            {"segment": 3, "a": 0.443, "b": 1295.0},
                        ],
                    },
                ],
            }
        },
    }
