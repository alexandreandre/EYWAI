"""
Les rapports de backtest n'atterrissent jamais dans le dépôt.

Ils portent des NOMS de salariés, leurs SALAIRES et leurs NIR. Le dépôt
étant PUBLIC, douze rapports avaient été distribués publiquement avant le
23/08/2026 — dont sept numéros de sécurité sociale et quatorze montants de
paie nominatifs. Ils sont sortis du suivi ; l'historique les conserve.

Ce test garde la porte fermée : il échoue si le dossier de campagne
retombe sous `docs/` ou n'importe où ailleurs dans le dépôt versionné.
"""

from __future__ import annotations

from pathlib import Path

from scripts.backtest.campaign_state import RACINE_RAPPORTS, campaign_dir

RACINE_DEPOT = Path(__file__).resolve().parents[4]


class TestRapportsHorsDepot:
    def test_le_dossier_de_campagne_est_sous_data(self):
        dossier = campaign_dir("Societe Neuve", 2026, 7)
        assert "data" in dossier.parts, (
            f"Les rapports de backtest doivent vivre sous data/ (gitignoré) — "
            f"reçu : {dossier}"
        )
        assert dossier.is_relative_to(RACINE_RAPPORTS)

    def test_le_dossier_de_campagne_n_est_pas_sous_docs(self):
        dossier = campaign_dir("Societe Neuve", 2026, 7)
        assert "docs" not in dossier.parts, (
            "docs/ est versionné dans un dépôt PUBLIC : un rapport de "
            f"backtest n'y a pas sa place. Reçu : {dossier}"
        )

    def test_data_backtests_est_bien_ignore_par_git(self):
        gitignore = (RACINE_DEPOT / ".gitignore").read_text(encoding="utf-8")
        assert "docs/backtest" in gitignore, (
            "docs/backtest/ doit rester ignoré : d'anciens rapports y "
            "subsistent en local."
        )
        # data/ est ignoré en bloc par la convention du projet.
        assert "/data/" in gitignore
