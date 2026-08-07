"""Écriture d'un dossier d'export WhatsApp depuis des messages bruts.

Produit exactement ce que `whatsapp.lire()` sait déjà parser : un `_chat.txt`
et les pièces jointes préfixées d'un compteur. La chaîne de classement en aval
n'a donc rien à apprendre de la provenance des messages.

Deux choix guident tout le module :

- le fil est **régénéré en entier** à chaque extraction, parce que `ingerer` se
  sert des messages voisins pour lever les ambiguïtés de nommage ;
- les pièces jointes ne sont copiées que si elles manquent, et leur nom est
  déterministe, pour qu'une seconde extraction ne duplique rien.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from scripts.data_organize import convention as cv
from scripts.data_organize.inventaire import RACINE_DATA
from scripts.data_organize.whatsapp_base import (
    BASE_WHATSAPP,
    RACINE_MEDIA,
    MessageBrut,
    copier_base,
    lire_messages,
    ouvrir,
    trouver_conversation,
)

INBOX = RACINE_DATA / cv.INBOX

FICHIER_CONVERSATION = "_chat.txt"
FICHIER_NOUVEAUTES = "nouveautes.md"

#: Marque de sens de lecture, présente dans les exports du téléphone.
_MARQUE = "‎"

#: Familles de médias sans nom d'origine, et le préfixe qu'on leur donne.
_FAMILLES: tuple[tuple[str, frozenset[str]], ...] = (
    ("PHOTO", frozenset({".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif"})),
    ("AUDIO", frozenset({".opus", ".m4a", ".mp3", ".ogg", ".wav"})),
    ("VIDEO", frozenset({".mp4", ".mov", ".3gp"})),
)


@dataclass
class Rapport:
    messages: int = 0
    pieces_copiees: int = 0
    pieces_absentes: int = 0
    nouveaux: list[MessageBrut] = field(default_factory=list)


def nom_origine(message: MessageBrut) -> str:
    """Nom sous lequel la pièce jointe est consignée dans le fil.

    Un document garde le nom qu'Elsa lui a donné — c'est lui qui porte la
    société et la période. Une photo ou un vocal n'en a pas : on en construit
    un à partir de l'horodatage, comme le fait l'export du téléphone.
    """
    if message.nom_fichier:
        return message.nom_fichier

    extension = message.media.suffix.lower() if message.media else ""
    famille = next(
        (nom for nom, extensions in _FAMILLES if extension in extensions), "FICHIER"
    )
    return f"{famille}-{message.horodatage:%Y-%m-%d-%H-%M-%S}{extension}"


def ligne_chat(message: MessageBrut, piece: str | None) -> str:
    """Une ligne de `_chat.txt`, au format des exports du téléphone."""
    if piece is not None:
        corps = f"{_MARQUE}< pièce jointe : {piece} >"
        if message.nom_fichier:
            corps = f"{message.nom_fichier} {corps}"
        if message.legende:
            corps = f"{corps}\n{message.legende}"
    elif message.media_absent:
        # Le fichier est resté sur le téléphone. On ne peut pas le joindre,
        # mais taire l'envoi ferait disparaître un échange du fil.
        corps = message.media_absent
        if message.nom_fichier:
            corps = f"{message.nom_fichier} — {corps}"
        if message.legende:
            corps = f"{corps}\n{message.legende}"
    else:
        corps = message.texte or message.legende or ""

    horodatage = f"{message.horodatage:%d/%m/%Y %H:%M:%S}"
    return f"{_MARQUE}[{horodatage}] {message.auteur}: {corps}"


def _ecrire_nouveautes(nouveaux: list[MessageBrut], chemin: Path) -> None:
    """Le texte des messages arrivés depuis la dernière extraction.

    Destiné à la lecture : c'est là que se trouvent les engagements et les
    décisions qu'aucune pièce jointe ne porte.
    """
    if not nouveaux:
        chemin.write_text("Rien de nouveau depuis la dernière extraction.\n", encoding="utf-8")
        return

    lignes = [f"# Nouveautés — {len(nouveaux)} messages", ""]
    jour_courant = None

    for message in nouveaux:
        jour = message.horodatage.date()
        if jour != jour_courant:
            lignes += ["", f"## {jour:%d/%m/%Y}", ""]
            jour_courant = jour

        if message.porte_un_media:
            detail = f"`{nom_origine(message)}`"
            if message.legende:
                detail += f" — {message.legende}"
        elif message.media_absent:
            detail = f"_{message.nom_fichier or ''} {message.media_absent}_".strip()
            if message.legende:
                detail += f" — {message.legende}"
        else:
            detail = message.texte

        heure = f"{message.horodatage:%H:%M}"
        lignes.append(f"- **{heure}** {message.auteur} : {detail}".replace("\n", " "))

    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def ecrire_export(
    messages: list[MessageBrut], dossier: Path, depuis: dt.datetime | None
) -> Rapport:
    """Écrit `_chat.txt`, les pièces manquantes et `nouveautes.md`."""
    dossier.mkdir(parents=True, exist_ok=True)
    rapport = Rapport(messages=len(messages))
    lignes: list[str] = []
    compteur = 0

    for message in messages:
        piece = None
        if message.media_absent:
            rapport.pieces_absentes += 1
        if message.porte_un_media:
            compteur += 1
            piece = f"{compteur:08d}-{nom_origine(message)}"
            destination = dossier / piece

            if not message.media.exists():
                rapport.pieces_absentes += 1
            elif not destination.exists():
                shutil.copy2(message.media, destination)
                rapport.pieces_copiees += 1

        lignes.append(ligne_chat(message, piece))
        if depuis is None or message.horodatage > depuis:
            rapport.nouveaux.append(message)

    (dossier / FICHIER_CONVERSATION).write_text("\n".join(lignes) + "\n", encoding="utf-8")
    _ecrire_nouveautes(rapport.nouveaux, dossier / FICHIER_NOUVEAUTES)
    return rapport


def chemin_etat(inbox: Path, contact: str) -> Path:
    """Fichier d'état d'un contact, sous l'inbox."""
    plat = re.sub(r"[^a-z0-9]+", "-", contact.lower()).strip("-")
    return inbox / f".whatsapp-{plat}.json"


def lire_etat(chemin: Path) -> dt.datetime | None:
    """Horodatage du dernier message déjà extrait, ou None.

    Un état absent ou illisible vaut première extraction : tout est neuf. Mieux
    vaut resignaler du déjà-vu que taire une nouveauté.
    """
    if not chemin.exists():
        return None
    try:
        etat = json.loads(chemin.read_text(encoding="utf-8"))
        return dt.datetime.fromisoformat(etat["dernier_message"])
    except (ValueError, KeyError, OSError):
        return None


def ecrire_etat(chemin: Path, dernier: dt.datetime | None, rapport: Rapport) -> None:
    """Consigne l'extraction qui vient d'avoir lieu."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        json.dumps(
            {
                "dernier_message": dernier.isoformat() if dernier else None,
                "messages": rapport.messages,
                "pieces_copiees": rapport.pieces_copiees,
                "pieces_absentes": rapport.pieces_absentes,
                "extrait_le": dt.datetime.now().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _dossier_export(inbox: Path, contact: str) -> Path:
    """`data/_inbox/whatsapp-elsa/`, distinct des exports manuels datés."""
    plat = re.sub(r"[^a-z0-9]+", "-", contact.lower()).strip("-")
    return inbox / f"whatsapp-{plat}"


def extraire(
    contact: str,
    inbox: Path = INBOX,
    base: Path = BASE_WHATSAPP,
    racine_media: Path = RACINE_MEDIA,
) -> tuple[Path, Rapport]:
    """Extrait la conversation dans un dossier d'export, et rend le rapport."""
    with tempfile.TemporaryDirectory(prefix="whatsapp-") as tampon:
        connexion = ouvrir(copier_base(Path(tampon), source=base))
        session = trouver_conversation(connexion, contact)
        messages = lire_messages(
            connexion, session, correspondant=contact, racine_media=racine_media
        )
        connexion.close()

    dossier = _dossier_export(inbox, contact)
    etat = chemin_etat(inbox, contact)
    rapport = ecrire_export(messages, dossier, depuis=lire_etat(etat))
    dernier = messages[-1].horodatage if messages else None
    ecrire_etat(etat, dernier, rapport)
    return dossier, rapport


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--contact", default="Elsa", help="nom du contact WhatsApp")
    arguments = analyseur.parse_args(argv)

    dossier, rapport = extraire(arguments.contact)

    print(f"{rapport.messages} messages écrits dans {dossier}")
    print(f"  pièces copiées   {rapport.pieces_copiees:>4}")
    print(f"  pièces absentes  {rapport.pieces_absentes:>4}  (restées sur le téléphone)")
    print(f"  nouveautés       {len(rapport.nouveaux):>4}  -> {FICHIER_NOUVEAUTES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
