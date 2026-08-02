"""Classement automatique des pièces jointes d'un export WhatsApp.

Lit le fil de la conversation, identifie les documents de paie parmi les pièces
jointes, en déduit société / rubrique / période — par le nom quand il parle, par
le contexte du fil quand il se tait — puis les range sous `data/`.

Le texte de la conversation ne sort jamais de la mémoire du processus : le
rapport ne contient que des noms de fichiers et la classification retenue.

    python -m scripts.data_organize.ingerer                     # simulation
    python -m scripts.data_organize.ingerer --appliquer         # copie les fichiers
    python -m scripts.data_organize.ingerer --export <dossier>  # export précis
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from scripts.data_organize import convention as cv
from scripts.data_organize import whatsapp
from scripts.data_organize.inventaire import RACINE_DATA, RACINE_DEPOT, empreinte_fichier

INBOX = RACINE_DATA / cv.INBOX

#: Extensions qui portent de la donnée de paie exploitable.
EXTENSIONS_UTILES = {".xlsx", ".xls", ".xlsm", ".dsn", ".pdf", ".csv", ".xml", ".docx"}

#: Extensions ignorées d'office : photos, sons, vidéos, contacts.
EXTENSIONS_IGNOREES = {
    ".jpg", ".jpeg", ".png", ".heic", ".gif", ".webp",
    ".opus", ".m4a", ".mp3", ".ogg", ".wav",
    ".mp4", ".mov", ".3gp",
    ".vcf", ".txt", ".zip", ".pages", ".rtf", ".pptx",
}

#: Documents personnels reconnaissables : ils transitent par la même
#: conversation mais n'ont rien à faire dans les données de paie.
_HORS_PAIE = (
    "cv", "personal_statement", "academic", "columbia", "toefl",
    "plaquette", "proposition_commerciale", "roadmap", "note de cadrage",
    "lm ", "ats_", "billet", "sncf",
)

# États d'une pièce jointe vis-à-vis de l'existant.
NOUVEAU = "nouveau"
IDENTIQUE = "identique"
DIVERGENT = "divergent"
IGNORE = "ignoré"
INCLASSABLE = "inclassable"


@dataclass
class Piece:
    """Une pièce jointe et ce qu'on a pu en déduire."""

    fichier: Path  # chemin réel dans l'export
    nom_origine: str  # nom tel qu'envoyé, sans le préfixe numérique
    auteur: str
    date: str
    societe: str | None = None
    rubrique: str | None = None
    periode: str | None = None
    cible: Path | None = None  # relatif à `data/`
    etat: str = INCLASSABLE
    detail: str = ""


def _sans_prefixe(nom: str) -> str:
    """`00004421-CARTOL_0526_000001 (1).dsn` -> `CARTOL_0526_000001 (1).dsn`."""
    import re

    return re.sub(r"^-?\d{6,10}-", "", nom)


def _est_hors_paie(nom: str) -> bool:
    plat = nom.lower()
    return any(motif in plat for motif in _HORS_PAIE)


def _indexer_existant() -> tuple[set[str], dict[str, str]]:
    """Empreintes déjà présentes sous `data/`, et empreinte par chemin canonique."""
    empreintes: set[str] = set()
    par_chemin: dict[str, str] = {}
    if not RACINE_DATA.exists():
        return empreintes, par_chemin
    for chemin in RACINE_DATA.rglob("*"):
        if not chemin.is_file() or chemin.name == "_manifeste.json":
            continue
        if cv.INBOX in chemin.parts:
            continue
        signature = empreinte_fichier(chemin)
        empreintes.add(signature)
        par_chemin[str(chemin.relative_to(RACINE_DATA))] = signature
    return empreintes, par_chemin


def classer_piece(piece: Piece, contexte: str) -> Piece:
    """Déduit la destination d'une pièce jointe.

    Le nom d'origine prime : quand Elsa envoie `PAIE CARTOL.xlsx`, tout y est.
    Le contexte du fil ne sert qu'à combler ce que le nom tait — typiquement
    `POINTAGE 05-2026.xlsx`, qui ne dit pas de quelle société il s'agit.
    """
    extension = Path(piece.nom_origine).suffix.lower()

    if extension in EXTENSIONS_IGNOREES or extension not in EXTENSIONS_UTILES:
        piece.etat = IGNORE
        piece.detail = f"extension {extension or 'inconnue'}"
        return piece

    if _est_hors_paie(piece.nom_origine):
        piece.etat = IGNORE
        piece.detail = "document personnel, hors paie"
        return piece

    piece.societe = cv.detecter_societe(piece.nom_origine) or cv.detecter_societe(contexte)
    piece.rubrique = cv.detecter_rubrique(piece.nom_origine)
    piece.periode = cv.detecter_periode_explicite(
        piece.nom_origine
    ) or cv.detecter_periode_explicite(contexte)

    if piece.periode is None:
        piece.periode = cv.detecter_periode(piece.nom_origine)

    if not piece.societe:
        piece.etat = INCLASSABLE
        piece.detail = "société introuvable dans le nom et le contexte"
        return piece
    if not piece.rubrique:
        piece.etat = INCLASSABLE
        piece.detail = "rubrique indéterminée"
        return piece

    nom_cible = cv.nom_canonique(piece.rubrique, piece.periode, piece.nom_origine)
    piece.cible = cv.Destination(
        societe=piece.societe,
        rubrique=piece.rubrique,
        periode=piece.periode,
        nom=nom_cible,
    ).chemin_relatif()
    return piece


def confronter(piece: Piece, empreintes: set[str], par_chemin: dict[str, str]) -> Piece:
    """Situe la pièce par rapport à ce qui est déjà rangé."""
    if piece.cible is None:
        return piece

    signature = empreinte_fichier(piece.fichier)
    if signature in empreintes:
        piece.etat = IDENTIQUE
        piece.detail = "contenu déjà présent"
        return piece

    existante = par_chemin.get(str(piece.cible))
    if existante and existante != signature:
        piece.etat = DIVERGENT
        piece.detail = "même emplacement, contenu différent"
        return piece

    piece.etat = NOUVEAU
    return piece


def analyser(export: Path) -> list[Piece]:
    conversation = whatsapp.lire(export)
    empreintes, par_chemin = _indexer_existant()
    pieces: list[Piece] = []

    for index, message in conversation.pieces_jointes:
        fichier = export / message.piece_jointe
        if not fichier.exists():
            continue

        piece = Piece(
            fichier=fichier,
            nom_origine=_sans_prefixe(message.piece_jointe),
            auteur=message.auteur,
            date=message.horodatage.strftime("%Y-%m-%d"),
        )
        piece = classer_piece(piece, conversation.contexte(index))
        if piece.cible is not None:
            piece = confronter(piece, empreintes, par_chemin)
        pieces.append(piece)

    return pieces


def appliquer(pieces: list[Piece]) -> int:
    """Copie les pièces nouvelles. Ne déplace ni ne supprime jamais l'export."""
    copiees = 0
    for piece in pieces:
        if piece.etat != NOUVEAU or piece.cible is None:
            continue
        destination = RACINE_DATA / piece.cible
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            continue
        shutil.copy2(piece.fichier, destination)
        copiees += 1
    return copiees


def afficher(pieces: list[Piece]) -> None:
    compte = Counter(p.etat for p in pieces)
    print(f"Pièces jointes analysées : {len(pieces)}")
    for etat in (NOUVEAU, IDENTIQUE, DIVERGENT, INCLASSABLE, IGNORE):
        print(f"  {etat:<12} {compte.get(etat, 0):>4}")

    nouveaux = [p for p in pieces if p.etat == NOUVEAU]
    if nouveaux:
        print(f"\nÀ ranger ({len(nouveaux)}) :")
        for piece in sorted(nouveaux, key=lambda p: str(p.cible)):
            print(f"  {piece.date}  {piece.nom_origine}")
            print(f"      -> data/{piece.cible}")

    divergents = [p for p in pieces if p.etat == DIVERGENT]
    if divergents:
        print(f"\nConflits ({len(divergents)}) — même emplacement, contenu différent :")
        for piece in divergents:
            print(f"  {piece.date}  {piece.nom_origine}")
            print(f"      data/{piece.cible}")

    inclassables = [p for p in pieces if p.etat == INCLASSABLE]
    if inclassables:
        print(f"\nÀ trier à la main ({len(inclassables)}) :")
        for piece in inclassables[:20]:
            print(f"  {piece.date}  {piece.nom_origine}  ({piece.detail})")
        if len(inclassables) > 20:
            print(f"  ... et {len(inclassables) - 20} autres")


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--export", type=Path, help="dossier d'export WhatsApp")
    analyseur.add_argument("--appliquer", action="store_true", help="copie les nouveautés")
    arguments = analyseur.parse_args(argv)

    if arguments.export:
        exports = [arguments.export]
    else:
        exports = whatsapp.trouver_exports(INBOX) if INBOX.exists() else []
        if not exports:
            exports = whatsapp.trouver_exports(RACINE_DEPOT)

    if not exports:
        print(f"Aucun export trouvé. Déposez le dossier exporté dans {INBOX}/")
        return 1

    total_copie = 0
    for export in exports:
        print(f"\n=== {export.name} ===")
        pieces = analyser(export)
        afficher(pieces)
        if arguments.appliquer:
            copiees = appliquer(pieces)
            total_copie += copiees
            print(f"\n{copiees} fichiers copiés sous data/")

    if not arguments.appliquer:
        print("\nSimulation. Ajouter --appliquer pour ranger les nouveautés.")
    else:
        print(f"\nTotal : {total_copie} fichiers rangés.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
