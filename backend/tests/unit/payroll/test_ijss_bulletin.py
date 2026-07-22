"""Tests calcul CSG IJSS bulletin."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.ijss_bulletin import (
    build_rappel_ijss_net_prime,
    compute_ijss_csg_lines,
)


class TestComputeIjssCsgLines:
    def test_brut_448(self):
        lignes, total_csg, net = compute_ijss_csg_lines(
            448.0,
            {"csg_ijss": {"taux_deductible": 0.038, "taux_non_deductible": 0.029}},
        )
        assert len(lignes) == 2
        assert total_csg == pytest.approx(30.01, abs=0.02)
        assert net == pytest.approx(448 - total_csg, 2)

    def test_zero_brut(self):
        lignes, total, net = compute_ijss_csg_lines(0, {})
        assert lignes == []
        assert total == 0
        assert net == 0


class TestBuildRappelIjssNetPrime:
    def test_negative_rappel_creates_net_counterpart(self):
        prime = build_rappel_ijss_net_prime(
            prime_id="rappel_ijss",
            libelle="Rappel IJSS (régularisation janvier)",
            montant=-40.89,
            baremes_maladie={
                "csg_ijss": {
                    "taux_deductible": 0.038,
                    "taux_non_deductible": 0.029,
                }
            },
        )

        assert prime == {
            "prime_id": "rappel_ijss_net",
            "libelle": "IJSS nettes (rappel)",
            "montant": 38.15,
            "is_rappel_ijss": True,
        }

    @pytest.mark.parametrize(
        ("libelle", "montant"),
        [
            ("Prime exceptionnelle", -40.89),
            ("Rappel IJSS", 40.89),
        ],
    )
    def test_unrelated_or_positive_input_is_ignored(self, libelle, montant):
        assert (
            build_rappel_ijss_net_prime(
                prime_id=libelle.lower().replace(" ", "_"),
                libelle=libelle,
                montant=montant,
                baremes_maladie={},
            )
            is None
        )
