"""Lecture d'un export de conversation WhatsApp.

Un export est un dossier contenant `_chat.txt` et les pièces jointes, préfixées
d'un compteur : `00004421-CARTOL_0526_000001 (1).dsn`.

Grammaire d'une ligne, marques de sens de lecture (U+200E) comprises :

    [25/06/2026 18:11:07] Elsa: CARTOL_0526_000001 (1).dsn ‎< pièce jointe : 00004421-CARTOL_0526_000001 (1).dsn >

Ce module ne fait que *lire*. Il n'écrit jamais le contenu de la conversation
ailleurs : seuls le nom des pièces jointes et la classification qui en découle
sortent d'ici.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

FICHIER_CONVERSATION = "_chat.txt"

_MARQUES_INVISIBLES = dict.fromkeys(map(ord, "‎‏‪‬"), None)

_RE_ENTETE = re.compile(
    r"^\[(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2})\] ([^:]{1,60}): (.*)$"
)
_RE_PIECE_JOINTE = re.compile(r"<\s*pi[èe]ce\s+jointe\s*:\s*(.+?)\s*>", re.IGNORECASE)
_RE_PIECE_JOINTE_EN = re.compile(r"<\s*attached\s*:\s*(.+?)\s*>", re.IGNORECASE)


@dataclass
class Message:
    horodatage: dt.datetime
    auteur: str
    texte: str
    piece_jointe: str | None = None

    @property
    def porte_un_fichier(self) -> bool:
        return self.piece_jointe is not None


@dataclass
class Conversation:
    dossier: Path
    messages: list[Message] = field(default_factory=list)

    @property
    def pieces_jointes(self) -> list[tuple[int, Message]]:
        return [(i, m) for i, m in enumerate(self.messages) if m.porte_un_fichier]

    def contexte(self, index: int, rayon: int = 5) -> str:
        """Texte des messages voisins, pour lever une ambiguïté de nommage.

        Sert uniquement à deviner la société ou la période d'un fichier au nom
        muet ; ce texte n'est jamais écrit sur disque.
        """
        debut = max(0, index - rayon)
        fin = min(len(self.messages), index + rayon + 1)
        return " \n".join(self.messages[i].texte for i in range(debut, fin))


def _nettoyer(ligne: str) -> str:
    return ligne.translate(_MARQUES_INVISIBLES)


def lire(dossier: Path) -> Conversation:
    """Parse `_chat.txt`. Les messages multilignes sont recollés."""
    chemin = dossier / FICHIER_CONVERSATION
    if not chemin.exists():
        raise FileNotFoundError(f"Pas de {FICHIER_CONVERSATION} dans {dossier}")

    conversation = Conversation(dossier=dossier)
    brut = chemin.read_text(encoding="utf-8", errors="replace")

    for ligne in brut.split("\n"):
        propre = _nettoyer(ligne).rstrip("\r")
        entete = _RE_ENTETE.match(propre)

        if not entete:
            # Suite d'un message multiligne.
            if conversation.messages:
                conversation.messages[-1].texte += "\n" + propre
            continue

        jour, mois, annee, heure, minute, seconde, auteur, texte = entete.groups()
        message = Message(
            horodatage=dt.datetime(
                int(annee), int(mois), int(jour), int(heure), int(minute), int(seconde)
            ),
            auteur=auteur.strip(),
            texte=texte,
        )

        if piece := (_RE_PIECE_JOINTE.search(texte) or _RE_PIECE_JOINTE_EN.search(texte)):
            message.piece_jointe = piece.group(1).strip()

        conversation.messages.append(message)

    return conversation


def trouver_exports(racine: Path) -> list[Path]:
    """Dossiers d'export présents sous `racine` (récursif, 2 niveaux)."""
    exports = []
    if (racine / FICHIER_CONVERSATION).exists():
        exports.append(racine)
    for chemin in racine.glob(f"*/{FICHIER_CONVERSATION}"):
        exports.append(chemin.parent)
    for chemin in racine.glob(f"*/*/{FICHIER_CONVERSATION}"):
        exports.append(chemin.parent)
    return sorted(set(exports))
