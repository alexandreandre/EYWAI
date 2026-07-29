"""Le script de resynchro doit refuser d'écrire vers la production."""

import subprocess
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[4] / "scripts" / "test_env" / "refresh_from_prod.sh"
)


def _lancer(env_extra):
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "SUPABASE_PROD_READ_URL": "postgresql://r@db.prodref.supabase.co:5432/postgres",
        "SUPABASE_TEST_DB_URL": "postgresql://postgres@db.testref.supabase.co:5432/postgres",
        "SUPABASE_PROD_REF": "prodref",
        "SUPABASE_TEST_REF": "testref",
        **env_extra,
    }
    return subprocess.run(
        ["bash", str(SCRIPT), "--dry-run"], env=env, capture_output=True, text=True
    )


def test_le_script_existe_et_est_executable():
    assert SCRIPT.is_file(), f"script introuvable : {SCRIPT}"


def test_refuse_si_la_cible_est_la_production():
    r = _lancer({"SUPABASE_TEST_REF": "prodref"})
    assert r.returncode != 0
    assert "production" in (r.stderr + r.stdout).lower()


def test_refuse_si_l_url_cible_contient_la_reference_de_production():
    r = _lancer(
        {
            "SUPABASE_TEST_DB_URL": (
                "postgresql://postgres@db.prodref.supabase.co:5432/postgres"
            )
        }
    )
    assert r.returncode != 0
    assert "production" in (r.stderr + r.stdout).lower()


def test_refuse_si_une_variable_requise_manque():
    r = _lancer({"SUPABASE_TEST_DB_URL": ""})
    assert r.returncode != 0


def test_accepte_une_cible_de_test():
    r = _lancer({})
    assert r.returncode == 0, r.stderr
