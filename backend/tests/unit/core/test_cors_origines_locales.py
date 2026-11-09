"""R-660 : un site déployé n'accepte pas localhost en CORS avec identifiants."""

from __future__ import annotations

import json
import os
import subprocess
import sys

from app.core import settings

ORIGINE_LOCALE = "http://localhost:5173"


def test_poste_de_developpement_garde_localhost():
    assert ORIGINE_LOCALE in settings.origines_locales_cors({})
    assert settings.motif_origines_cors({}) == settings.MOTIF_ORIGINES_LOCALES


def test_service_deploye_refuse_localhost():
    deploye = {"K_SERVICE": "sirh-backend-test"}
    assert settings.origines_locales_cors(deploye) == []
    assert settings.motif_origines_cors(deploye) is None


def test_le_motif_pose_explicitement_reste_lu():
    deploye = {"K_SERVICE": "sirh-backend", "CORS_ALLOW_ORIGIN_REGEX": r"https://a\.example$"}
    assert settings.motif_origines_cors(deploye) == r"https://a\.example$"


def test_le_motif_vide_ferme_aussi_le_poste_de_developpement():
    assert settings.motif_origines_cors({"CORS_ALLOW_ORIGIN_REGEX": "  "}) is None


def test_l_application_deployee_ne_publie_aucune_origine_locale(tmp_path):
    """L'application réelle, importée comme sur Cloud Run (l'import détourne stdout)."""
    fichier = tmp_path / "origines.json"
    script = (
        "import json, sys, app.main as m;"
        "open(sys.argv[1], 'w').write("
        "json.dumps({'origines': m.ALLOWED_ORIGINS, 'motif': m._cors_origin_regex}))"
    )
    env = {**os.environ, "K_SERVICE": "sirh-backend-test"}
    env.pop("CORS_ALLOW_ORIGIN_REGEX", None)
    subprocess.run(
        [sys.executable, "-c", script, str(fichier)],
        env=env,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=120,
        check=True,
    )
    resultat = json.loads(fichier.read_text())
    assert resultat["motif"] is None
    assert not [o for o in resultat["origines"] if "localhost" in o or "127.0.0.1" in o]
    assert resultat["origines"]  # les sites déployés restent listés
