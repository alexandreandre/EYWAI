"""Les erreurs laissent leur pile dans les journaux (audit du 25/09/2026, A7).

`traceback.print_exc()` écrit sur la sortie d'erreur, que le filtre de
`app/core/logging.py` classe en DEBUG faute de mot-clé d'erreur : en
production, la pile disparaissait. On journalise avec `logger.exception(...)`.
"""

from __future__ import annotations

from pathlib import Path

APP = Path(__file__).resolve().parents[3] / "app"


def test_aucun_print_exc_dans_l_application():
    fautifs = [
        str(f.relative_to(APP))
        for f in APP.rglob("*.py")
        if "traceback.print_exc()" in f.read_text(encoding="utf-8")
    ]
    assert fautifs == [], f"Remplacer par logger.exception(...) : {fautifs}"
