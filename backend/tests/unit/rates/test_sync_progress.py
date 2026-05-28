"""Tests estimation progression sync taux (logs + ETA)."""

from app.modules.rates.application.sync_progress import (
    compute_batch_progress,
    infer_progress_from_logs,
)


class TestInferProgressFromLogs:
    def test_empty_logs_returns_low_fraction(self):
        frac, step = infer_progress_from_logs([])
        assert frac < 0.1
        assert step

    def test_scraping_stage_advances(self):
        logs = [
            "Initialisation du job",
            "Démarrage de l'exécution de /path/script.py",
            "Scraping de l'URL : https://example.com",
            "Extraction réussie et complète.",
        ]
        frac, step = infer_progress_from_logs(logs)
        assert frac >= 0.5
        assert "extraction" in step.lower() or "réussie" in step.lower()

    def test_success_stage_near_complete(self):
        logs = ["Démarrage", "[SUCCÈS] Données extraites avec succès"]
        frac, _ = infer_progress_from_logs(logs)
        assert frac >= 0.85


class TestComputeBatchProgress:
    def test_single_running_job_partial_percent(self):
        jobs = [
            {
                "source_key": "smic",
                "source_name": "SMIC",
                "status": "running",
                "started_at": "2026-05-27T10:00:00+00:00",
                "execution_logs": [
                    "Démarrage de l'exécution",
                    "Scraping de l'URL : https://urssaf.fr",
                ],
            }
        ]
        result = compute_batch_progress(jobs)
        assert 0 < result["percent"] < 100
        assert result["percent_exact"] > 0
        assert result["current_source"] == "SMIC"
        assert result["eta_seconds"] is not None

    def test_mixed_completed_and_running(self):
        jobs = [
            {
                "source_name": "SMIC",
                "status": "completed",
                "success": True,
                "started_at": "2026-05-27T10:00:00+00:00",
                "completed_at": "2026-05-27T10:01:30+00:00",
            },
            {
                "source_name": "PSS",
                "status": "running",
                "started_at": "2026-05-27T10:01:00+00:00",
                "execution_logs": ["Démarrage"],
            },
        ]
        result = compute_batch_progress(jobs)
        assert result["percent"] >= 50
        assert result["done"] == 1
        assert len(result["jobs"]) == 2
        assert result["jobs"][0]["progress_fraction"] == 1.0
