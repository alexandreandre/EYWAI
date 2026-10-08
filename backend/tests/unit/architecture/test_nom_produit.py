"""Garde : le produit visible s'appelle Martine, pas EYWAI.

Parcourt backend/app, collecte les chaînes littérales (hors docstrings) et
échoue si l'une contient « EYWAI », sauf cas explicitement autorisés.
"""
from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[3] / "app"

# (fichier relatif à app/, chaîne exacte) : identifiants techniques et
# décisions en attente. Une chaîne vide dans le second champ n'existe pas.
LISTE_BLANCHE: set[tuple[str, str]] = {
    ("modules/exports/infrastructure/export_sepa.py", "EYWAI"),
    ("modules/exports/infrastructure/export_virement_acomptes.py", "EYWAI-ACO"),
    ("modules/dsn_export/application/builder.py", "EYWAI Paie"),
    ("modules/dsn_export/application/builder.py", "EYWAI"),
    ("modules/dsn_export/domain/writer.py", "EYWAI Paie"),
    ("modules/dsn_export/domain/writer.py", "EYWAI"),
    # valeur par défaut du titre d'application envoyé à OpenRouter (identifiant technique)
    ("shared/infrastructure/ai/client.py", "EYWAI"),
    ("shared/infrastructure/ai/client_async.py", "EYWAI"),
    # variables d'environnement et en-tête webhook (contrats techniques)
    ("modules/scraping/infrastructure/scraper_runner.py", "EYWAI_SYNC_COTISATION_IDS"),
    ("modules/scraping/infrastructure/scraper_runner.py", "EYWAI_REVIEWED_BY"),
    ("modules/webhooks/infrastructure/repository.py", "X-EYWAI-Signature"),
    # message de journal serveur, jamais montré à l'écran
    ("services/document_service.py", "ReportLab fallback PDF (EYWAI): %s"),
}


def _docstrings(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


def _violations() -> list[str]:
    out: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        rel = path.relative_to(APP).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        docs = _docstrings(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docs
                and "EYWAI" in node.value
            ):
                s = node.value
                if (rel, s) in LISTE_BLANCHE:
                    continue
                out.append(f"{rel}:{node.lineno}: {s[:90]!r}")
    return out


def test_le_produit_visible_s_appelle_martine():
    v = _violations()
    assert not v, f"{len(v)} chaînes citent encore EYWAI:\n" + "\n".join(v)


def test_les_fichiers_de_donnees_du_serveur_ne_citent_pas_eywai():
    fautifs = [
        p.relative_to(APP).as_posix()
        for ext in ("*.json", "*.md", "*.txt", "*.html")
        for p in APP.rglob(ext)
        if "EYWAI" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not fautifs, f"Fichiers de données citant EYWAI : {fautifs}"
