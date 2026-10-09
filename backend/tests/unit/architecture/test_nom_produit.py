"""Garde : le produit s'appelle Martine, nulle part EYWAI.

Deux gardes :
- les chaînes littérales de backend/app (hors docstrings) ;
- le texte brut (code, commentaires, docstrings, README, workflows) du dépôt
  hors docs/, supabase/, .cursor/, .claude/.

Seuls trois cas de compatibilité subsistent, listés explicitement.
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]
APP = BACKEND / "app"
DEPOT = BACKEND.parent

# Les noms sont construits pour que ce fichier ne se cite pas lui-même.
ANCIEN = "EY" + "WAI"
ANCIEN_MIN = ANCIEN.lower()

# (fichier relatif à app/, chaîne exacte)
LISTE_BLANCHE: set[tuple[str, str]] = {
    # ancien en-tête de signature des webhooks, encore envoyé (compatibilité)
    ("modules/webhooks/infrastructure/repository.py", "X-" + ANCIEN + "-Signature"),
}

# Fichiers du texte brut autorisés à citer l'ancien nom, et pourquoi.
FICHIERS_COMPATIBILITE: dict[str, str] = {
    "backend/app/modules/webhooks/infrastructure/repository.py": "ancien en-tête webhook",
    "backend/scraping/core/env_produit.py": "repli de lecture EYWAI_*",
    "backend/app/modules/documents/application/commands.py": "sentinelle __eywai__ (ancien front)",
    "backend/tests/unit/architecture/test_nom_produit.py": "ce garde",
    "backend/tests/unit/scraping/test_env_produit.py": "test du repli",
    "backend/tests/unit/webhooks/test_en_tetes_signature.py": "test de l'ancien en-tête",
    "backend/tests/unit/documents/test_sentinelle_modele_standard.py": "test de l'ancienne sentinelle",
    "backend/tests/_garde_base_reelle.py": "repli de lecture EYWAI_*",
    "backend/app/modules/badgeuse/application/badge_tokens.py": "secret par défaut: le changer invaliderait les QR émis",
}
# Chemins de dossiers et dépôt GitHub : le nom du dossier ne change pas.
CHEMINS = ("Desktop/" + ANCIEN + "/" + ANCIEN, "Desktop-" + ANCIEN + "-" + ANCIEN,
           "dev/" + ANCIEN, "alexandreandre/" + ANCIEN, ANCIEN + "/" + ANCIEN)
EXCLUS = ("docs/", "supabase/", ".cursor/", ".claude/", "node_modules/", "data/")
SUFFIXES = {".py", ".ts", ".tsx", ".json", ".md", ".yml", ".yaml", ".html", ".sh", ".toml",
            ".example", ".txt", ".js", ".mjs", ".cfg", ".ini", ".css", ".sql"}


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
                and ANCIEN in node.value
                and (rel, node.value) not in LISTE_BLANCHE
            ):
                out.append(f"{rel}:{node.lineno}: {node.value[:90]!r}")
    return out


def _fichiers_du_depot() -> list[str]:
    res = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=DEPOT, capture_output=True, text=True, check=True,
    )
    return [
        f for f in res.stdout.splitlines()
        if not f.startswith(EXCLUS) and (Path(f).suffix in SUFFIXES or Path(f).name in {"Makefile", ".env.example", ".env.local.example"})
    ]


def _texte_brut() -> list[str]:
    out: list[str] = []
    for f in _fichiers_du_depot():
        if f in FICHIERS_COMPATIBILITE:
            continue
        p = DEPOT / f
        if not p.is_file():
            continue
        try:
            texte = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for i, ligne in enumerate(texte.splitlines(), 1):
            ligne_nue = ligne
            for chemin in CHEMINS:
                ligne_nue = ligne_nue.replace(chemin, "")
            if ANCIEN in ligne_nue or f"__{ANCIEN_MIN}__" in ligne_nue or (
                f.endswith((".ts", ".tsx")) and f"{ANCIEN_MIN}-" in ligne_nue
            ):
                out.append(f"{f}:{i}: {ligne.strip()[:90]}")
    return out


def test_le_produit_visible_s_appelle_martine():
    v = _violations()
    assert not v, f"{len(v)} chaînes citent encore l'ancien nom:\n" + "\n".join(v)


def test_aucun_texte_du_depot_ne_cite_l_ancien_nom():
    v = _texte_brut()
    assert not v, f"{len(v)} lignes citent encore l'ancien nom:\n" + "\n".join(v[:80])


def test_les_fichiers_de_donnees_du_serveur_ne_citent_pas_l_ancien_nom():
    fautifs = [
        p.relative_to(APP).as_posix()
        for ext in ("*.json", "*.md", "*.txt", "*.html")
        for p in APP.rglob(ext)
        if ANCIEN in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not fautifs, f"Fichiers de données citant l'ancien nom : {fautifs}"
