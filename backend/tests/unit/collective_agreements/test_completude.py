"""Tests évaluation complétude extraction CC."""

from __future__ import annotations

from app.modules.collective_agreements.rules.completude import (
    assess_completude,
    finalize_document,
)
from app.modules.collective_agreements.rules.schema import (
    CCRulesDocument,
    GrilleSalaires,
    SalaireMinimum,
)


class TestCompletude:
    def test_finalize_wraps_legacy_minima(self):
        doc = CCRulesDocument(
            idcc="1486",
            salaires_minima=[SalaireMinimum(coefficient=240, valeur=2500.0)],
        )
        finalized = finalize_document(doc)
        assert len(finalized.grilles_salaires) == 1
        assert finalized.grilles_salaires[0].zone_type == "national"
        assert finalized.completude is not None
        assert finalized.completude.niveau == "complet"

    def test_multi_zone_idcc_warns_single_grille(self):
        doc = CCRulesDocument(
            idcc="1597",
            grilles_salaires=[
                GrilleSalaires(
                    zone_type="departemental",
                    zone_libelle="Seine-et-Marne",
                    departements=["77"],
                    minima=[SalaireMinimum(coefficient=150, valeur=1782.0)],
                )
            ],
        )
        comp = assess_completude(doc)
        assert comp.idcc_multi_zones is True
        assert comp.niveau == "partiel"
        assert any("une seule zone" in w.lower() for w in comp.avertissements)

    def test_multi_zone_many_grilles_complet(self):
        doc = CCRulesDocument(
            idcc="1597",
            grilles_salaires=[
                GrilleSalaires(
                    zone_type="departemental",
                    zone_libelle=f"Zone {i}",
                    departements=[str(10 + i)],
                    minima=[SalaireMinimum(coefficient=150, valeur=1700.0 + i)],
                )
                for i in range(5)
            ],
        )
        comp = assess_completude(doc)
        assert comp.niveau == "complet"
        assert comp.grilles_count == 5

    def test_finalize_drops_empty_grilles(self):
        doc = CCRulesDocument(
            idcc="0547",
            grilles_salaires=[
                GrilleSalaires(zone_type="national", zone_libelle="Zone A", minima=[]),
                GrilleSalaires(
                    zone_type="national",
                    zone_libelle="National",
                    minima=[SalaireMinimum(coefficient=275, valeur=6.5)],
                ),
            ],
        )
        finalized = finalize_document(doc)
        assert len(finalized.grilles_salaires) == 1
        assert finalized.grilles_salaires[0].minima[0].valeur == 1787.5

    def test_finalize_smh_3248_skips_point_materialize(self):
        doc = CCRulesDocument(
            idcc="3248",
            grilles_salaires=[
                GrilleSalaires(
                    zone_type="national",
                    zone_libelle="National — SMH",
                    minima=[SalaireMinimum(coefficient=1, valeur=1808.33)],
                )
            ],
        )
        finalized = finalize_document(doc)
        assert finalized.grilles_salaires[0].minima[0].valeur == 1808.33

    def test_finalize_materialize_from_prime_point(self):
        from app.modules.collective_agreements.rules.schema import (
            BaseCalculPrime,
            PrimeAnciennete,
        )

        doc = CCRulesDocument(
            idcc="0547",
            prime_anciennete=PrimeAnciennete(
                bareme=[],
                base_de_calcul=BaseCalculPrime(methode="valeur_du_point", valeur=6.5),
            ),
            grilles_salaires=[
                GrilleSalaires(
                    zone_type="national",
                    zone_libelle="National",
                    minima=[SalaireMinimum(coefficient=240, valeur=6.5)],
                )
            ],
        )
        finalized = finalize_document(doc)
        assert finalized.grilles_salaires[0].minima[0].valeur == 1560.0
