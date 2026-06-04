"""Tests découpage texte CC."""

from __future__ import annotations

from app.modules.collective_agreements.rules.chunker import (
    build_fallback_sample,
    build_scout_window,
    extract_article_blocks,
)

SAMPLE_TEXT = """
Convention collective IDCC 1486

Article 15 - Prime d'ancienneté
Les salariés bénéficient d'une prime d'ancienneté :
- 3 ans : 3 %
- 5 ans : 4 %
- 10 ans : 5 %
La base de calcul est le salaire minimum conventionnel.

Article 16 - Autres dispositions
Texte sans intérêt paie.

Annexe I - Grille des salaires
Coefficient 240 : 2 500 euros
Coefficient 275 : 2 900 euros
"""


class TestChunker:
    def test_scout_window_short_text(self):
        assert build_scout_window(SAMPLE_TEXT) == SAMPLE_TEXT

    def test_scout_window_long_text_with_keywords(self):
        padding = "x" * 100_000
        long_text = padding + SAMPLE_TEXT + padding
        window = build_scout_window(long_text, max_chars=5000)
        assert "ancienneté" in window.lower() or "anciennete" in window.lower()
        assert len(window) <= 5000

    def test_extract_article_blocks_by_ref(self):
        blocks = extract_article_blocks(SAMPLE_TEXT, ["15"])
        assert "3 ans" in blocks
        assert "Article 16" not in blocks or len(blocks) < len(SAMPLE_TEXT)

    def test_extract_fallback_when_no_match(self):
        blocks = extract_article_blocks(SAMPLE_TEXT, ["999"])
        assert len(blocks) > 0

    def test_build_fallback_sample(self):
        sample = build_fallback_sample(SAMPLE_TEXT, max_chars=500)
        assert len(sample) <= 500
        assert "Article 15" in sample
