"""Tests contrôles convention collective en paie."""

from __future__ import annotations

from types import SimpleNamespace

from app.modules.payroll.engine.controles_convention import (
    controle_convention_collective,
    extraire_alertes_rh_depuis_bulletin,
)


def _contexte(
    *,
    idcc: str = "3248",
    coeff: float | None = 275,
    brut: float = 2500.0,
    regles: dict | None = None,
):
    return SimpleNamespace(
        is_alternant=False,
        contrat={
            "remuneration": {
                "convention_collective": {
                    "idcc": idcc,
                    "libelle": "Métallurgie",
                },
                "classification_conventionnelle": (
                    {"coefficient": coeff} if coeff is not None else None
                ),
            }
        },
        entreprise={"adresse_code_postal": "75001"},
        baremes={
            "conventions_collectives": {
                f"idcc_{idcc}": regles
                or {
                    "salaires_minima": [
                        {"coefficient": 275, "valeur": 2800.0, "libelle": "Agent de maîtrise"}
                    ]
                }
            }
        },
    )


class TestControlesConvention:
    def test_salaire_sous_minimum_alerte_critique(self):
        alertes = controle_convention_collective(_contexte(brut=2500.0), 2500.0)
        assert len(alertes) == 1
        assert alertes[0]["code"] == "cc_salaire_sous_minimum"
        assert alertes[0]["critique"] is True

    def test_salaire_conforme_pas_alerte(self):
        assert controle_convention_collective(_contexte(brut=2900.0), 2900.0) == []

    def test_regles_absentes(self):
        ctx = _contexte(regles={})
        ctx.baremes = {"conventions_collectives": {}}
        alertes = controle_convention_collective(ctx, 3000.0)
        assert alertes[0]["code"] == "cc_regles_absentes"

    def test_extraire_alertes_depuis_bulletin(self):
        data = {
            "alertes_baremes": [
                {
                    "code": "cc_salaire_sous_minimum",
                    "critique": True,
                    "message": "Sous le minimum.",
                }
            ],
            "synthese_net": {"alertes_maintien": ["Règle légale appliquée"]},
        }
        out = extraire_alertes_rh_depuis_bulletin(data)
        assert len(out) == 2
        assert out[0]["severite"] == "bloquant"
