"""Tests fallback minima quand les blocs IA ne renvoient que la prime."""

from __future__ import annotations


from app.modules.collective_agreements.rules.extractor import CCRulesExtractor
from app.shared.infrastructure.ai.structured_extractor import StructuredExtractionResult


def _prime_only_partial() -> dict:
    return {
        "idcc": "3248",
        "prime_anciennete": {
            "bareme": [{"annees_min": 3, "taux": 0.03}],
            "base_de_calcul": {"methode": "valeur_du_point", "valeur": 5.83},
        },
        "salaires_minima": [],
        "grilles_salaires": [],
        "confidence": "high",
        "citations": [],
    }


def _minima_partial() -> dict:
    return {
        "idcc": "3248",
        "prime_anciennete": None,
        "salaires_minima": [],
        "grilles_salaires": [
            {
                "zone_type": "national",
                "zone_libelle": "National",
                "departements": [],
                "regions": [],
                "minima": [
                    {"coefficient": 275, "valeur": 1603.25, "libelle": "Position 275"}
                ],
            }
        ],
        "confidence": "medium",
        "citations": [],
    }


class TestExtractorMinimaFallback:
    def test_fallback_minima_when_chunks_return_only_prime(self):
        minima_calls = {"count": 0}

        def extract_fn(**kwargs):
            system = kwargs.get("system_prompt") or ""
            if "UNIQUEMENT les grilles" in system or "minima de CET extrait" in system:
                if "minima de CET extrait" in system:
                    return StructuredExtractionResult(
                        data=_prime_only_partial(), tokens_used=500
                    )
                minima_calls["count"] += 1
                return StructuredExtractionResult(
                    data=_minima_partial(), tokens_used=800
                )
            return StructuredExtractionResult(
                data=_prime_only_partial(), tokens_used=500
            )

        text = (
            "## Texte salarial : Classification\n"
            "Position 275 valeur du point 5,83 €\n" * 20
            + "## Prime d'ancienneté\n3 ans 3%\n" * 5
        )
        extractor = CCRulesExtractor(extract_fn=extract_fn)
        doc, tokens, err = extractor.extract_from_text(text, idcc="3248")

        assert err is None
        assert doc is not None
        assert minima_calls["count"] >= 1
        assert doc.grilles_salaires or doc.salaires_minima
        assert any(g.minima for g in doc.grilles_salaires) or doc.salaires_minima
        assert tokens > 0

    def test_grille_chunk_uses_dedicated_prompt(self):
        seen: list[str] = []

        def extract_fn(**kwargs):
            seen.append(kwargs.get("system_prompt") or "")
            return StructuredExtractionResult(data=_minima_partial(), tokens_used=100)

        extractor = CCRulesExtractor(extract_fn=extract_fn)
        chunk_text = "## Texte salarial : National\nPosition 275 valeur du point 5,83 €\n"
        result, tokens, err = extractor._extract_grille_chunk(chunk_text, idcc="3248")

        assert err is None
        assert result is not None
        assert tokens == 100
        assert len(seen) == 1
        assert "prime_anciennete : null" in seen[0]
