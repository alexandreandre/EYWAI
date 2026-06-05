"""Tests découpage texte CC."""

from __future__ import annotations

from app.modules.collective_agreements.rules.chunker import (
    build_fallback_sample,
    build_scout_window,
    extract_article_blocks,
    split_salary_grille_chunks,
    strip_html,
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

    def test_split_salary_grille_chunks_multiple_blocks(self):
        text = """
## Texte salarial : Accord Seine-et-Marne
Coefficient 150 : 1 782 €
Coefficient 170 : 1 850 €

## Texte salarial : Accord Hérault
Coefficient 150 : 1 900 €
Coefficient 170 : 1 980 €
"""
        chunks = split_salary_grille_chunks(text)
        assert len(chunks) == 2
        assert "Seine-et-Marne" in chunks[0]
        assert "Hérault" in chunks[1]

    def test_split_salary_grille_chunks_single_short_block_returns_empty(self):
        text = "## Texte salarial : National\nCoefficient 150 : 1 800 €"
        assert split_salary_grille_chunks(text) == []

    def test_split_salary_grille_chunks_single_large_block_returns_one(self):
        body = "Coefficient 150 : 1 800 €\n" * 200
        text = f"## Texte salarial : Métallurgie nationale\n{body}"
        chunks = split_salary_grille_chunks(text)
        assert len(chunks) == 1
        assert "Métallurgie" in chunks[0]

    def test_split_classification_annexe_block(self):
        text = """
## Annexe I — Classification ETAM
Valeur du point : 6,50 €
Position 275 — Agent de maîtrise
Position 240 — Technicien
""" + ("Position 200 — coefficient associé 1 300 €\n" * 50)
        chunks = split_salary_grille_chunks(text)
        assert len(chunks) == 1

    def test_strip_html_preserves_markdown_headers(self):
        html = "<p>Intro</p><br/>## Texte salarial : Accord 77</p><p>150 1 782 €</p>"
        cleaned = strip_html(html)
        assert "## Texte salarial" in cleaned
        assert "1 782" in cleaned

    def test_split_after_strip_html(self):
        html = (
            "<p>## Texte salarial : Seine-et-Marne</p>"
            "<p>Coefficient 150 : 1 782 €</p>"
            "<p>## Texte salarial : Hérault</p>"
            "<p>Coefficient 150 : 1 900 €</p>"
        )
        chunks = split_salary_grille_chunks(strip_html(html))
        assert len(chunks) == 2

    def test_subsplit_geo_zones_in_single_text(self):
        text = """
Accord national des minima
Pour la Seine-et-Marne, barème :
Coefficient 150 : 1 782 €
Pour la Hérault, barème :
Coefficient 150 : 1 900 €
"""
        chunks = split_salary_grille_chunks(text)
        assert len(chunks) == 2
        assert "Seine-et-Marne" in chunks[0]
        assert "Hérault" in chunks[1]

    def test_dedupe_keeps_latest_zone(self):
        text = """
## Texte salarial : Accord 2021 - Seine-et-Marne
Coefficient 150 : 1 600 €
## Texte salarial : Accord 2023 - Seine-et-Marne
Coefficient 150 : 1 782 €
## Texte salarial : Accord 2023 - Hérault
Coefficient 150 : 1 900 €
"""
        chunks = split_salary_grille_chunks(text)
        assert len(chunks) == 2
        assert any("1 782" in c for c in chunks)
        assert not any("1 600" in c for c in chunks)
