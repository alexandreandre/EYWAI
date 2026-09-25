"""Le script de resynchro doit refuser d'écrire vers la production, et
d'écraser une base de test qui porte une vraie paie."""

import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[4] / "scripts" / "test_env" / "refresh_from_prod.sh"
)


@pytest.fixture
def faux_psql(tmp_path):
    """Remplace psql : rend ce que la base cible répondrait, sans réseau."""

    def poser(sortie: str = "", code: int = 0) -> str:
        psql = tmp_path / "psql"
        psql.write_text(f"#!/bin/sh\nprintf '%s' '{sortie}'\nexit {code}\n")
        psql.chmod(0o755)
        return str(tmp_path)

    return poser


def _lancer(env_extra, dossier_psql):
    env = {
        "PATH": f"{dossier_psql}:/usr/bin:/bin:/usr/local/bin",
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


def test_refuse_si_la_cible_est_la_production(faux_psql):
    r = _lancer({"SUPABASE_TEST_REF": "prodref"}, faux_psql())
    assert r.returncode != 0
    assert "production" in (r.stderr + r.stdout).lower()


def test_refuse_si_l_url_cible_contient_la_reference_de_production(faux_psql):
    r = _lancer(
        {
            "SUPABASE_TEST_DB_URL": (
                "postgresql://postgres@db.prodref.supabase.co:5432/postgres"
            )
        },
        faux_psql(),
    )
    assert r.returncode != 0
    assert "production" in (r.stderr + r.stdout).lower()


def test_refuse_si_une_variable_requise_manque(faux_psql):
    r = _lancer({"SUPABASE_TEST_DB_URL": ""}, faux_psql())
    assert r.returncode != 0


def test_accepte_une_cible_de_test_sans_paie_reelle(faux_psql):
    r = _lancer({}, faux_psql(sortie=""))
    assert r.returncode == 0, r.stderr


def test_refuse_une_base_de_test_qui_porte_une_vraie_paie(faux_psql):
    """Colorplast fait sa paie sur la base de test (reprise au 31/07/2026) :
    une resynchro effacerait ses bulletins."""
    r = _lancer({}, faux_psql(sortie="Colorplast"))
    assert r.returncode != 0
    sortie = r.stderr + r.stdout
    assert "Colorplast" in sortie
    assert "paie" in sortie.lower()


def test_refuse_si_la_verification_de_paie_reelle_echoue(faux_psql):
    """Base injoignable : on ne sait pas ce qu'elle porte, on n'écrase pas."""
    r = _lancer({}, faux_psql(code=2))
    assert r.returncode != 0


def test_la_levee_explicite_passe_outre_la_paie_reelle(faux_psql):
    r = _lancer({"REFRESH_ECRASER_PAIE_REELLE": "oui"}, faux_psql(sortie="Colorplast"))
    assert r.returncode == 0, r.stderr
