"""Accès en lecture seule à la base locale de WhatsApp Desktop (macOS).

WhatsApp tient sa conversation dans un SQLite non chiffré, mis à jour en
continu. Ce module en tire ce dont le classement a besoin — horodatage, auteur,
texte, nom d'origine des documents, légende, chemin du média sur disque — et
rien d'autre. Il ne connaît ni société, ni rubrique, ni `data/`.

La base d'origine n'est jamais interrogée en place : on en copie une image, avec
ses journaux `-wal` et `-shm` sans lesquels les derniers messages manquent, puis
on ouvre la copie en lecture seule. WhatsApp peut tourner pendant l'extraction.
"""

from __future__ import annotations

import datetime as dt
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

#: Conteneur de WhatsApp Desktop : la base et les médias y sont voisins.
CONTENEUR = Path.home() / "Library/Group Containers/group.net.whatsapp.WhatsApp.shared"
BASE_WHATSAPP = CONTENEUR / "ChatStorage.sqlite"

#: `ZMEDIALOCALPATH` vaut `Media/<jid>/…` et se lit depuis ce dossier.
RACINE_MEDIA = CONTENEUR / "Message"

#: Core Data compte les secondes depuis le 1er janvier 2001.
EPOCH_APPLE = 978_307_200

#: Le fil s'écrit à l'heure de Paris, comme les exports du téléphone. La machine
#: qui extrait n'est pas forcément dans ce fuseau : ne jamais s'en remettre à
#: l'heure locale, sous peine de décaler tout l'historique.
FUSEAU = ZoneInfo("Europe/Paris")

#: Journaux à copier avec la base.
_JOURNAUX = ("-wal", "-shm")

#: `ZWAMESSAGE.ZMESSAGETYPE` : seul le document porte son nom dans `ZTEXT`.
TYPE_TEXTE = 0
TYPE_IMAGE = 1
TYPE_VIDEO = 2
TYPE_AUDIO = 3
TYPE_DOCUMENT = 8

#: Comment nommer un média que ce Mac n'a jamais téléchargé. Les types absents
#: de cette table — autocollants, événements système, aperçus de lien — ne
#: valent pas une ligne dans le fil.
_MEDIA_ABSENT = {
    TYPE_IMAGE: "image absente",
    TYPE_VIDEO: "vidéo absente",
    TYPE_AUDIO: "audio absent",
    TYPE_DOCUMENT: "document absent",
}


class BaseIntrouvable(RuntimeError):
    """WhatsApp Desktop n'est pas installé, ou sa base a changé de place."""


class ConversationIntrouvable(RuntimeError):
    """Aucune conversation, ou plusieurs, portent ce nom de contact."""


@dataclass
class MessageBrut:
    """Un message tel que la base le connaît, avant toute interprétation."""

    horodatage: dt.datetime
    auteur: str
    texte: str = ""
    nom_fichier: str | None = None  # nom d'origine, pour un document
    legende: str | None = None  # commentaire accompagnant un média
    media: Path | None = None  # fichier sur disque, s'il a été téléchargé
    media_absent: str | None = None  # média resté sur le téléphone, et sa nature

    @property
    def porte_un_media(self) -> bool:
        return self.media is not None


def horodatage(secondes: float) -> dt.datetime:
    """Convertit un horodatage Core Data en heure de Paris, sans fuseau."""
    instant = dt.datetime.fromtimestamp(secondes + EPOCH_APPLE, tz=dt.timezone.utc)
    return instant.astimezone(FUSEAU).replace(tzinfo=None)


def copier_base(destination: Path, source: Path = BASE_WHATSAPP) -> Path:
    """Copie la base et ses journaux sous `destination`, et rend la copie."""
    if not source.exists():
        raise BaseIntrouvable(f"Base WhatsApp absente : {source}")

    destination.mkdir(parents=True, exist_ok=True)
    copie = destination / source.name
    shutil.copy2(source, copie)
    for suffixe in _JOURNAUX:
        journal = source.with_name(source.name + suffixe)
        if journal.exists():
            shutil.copy2(journal, copie.with_name(copie.name + suffixe))
    return copie


def ouvrir(base: Path) -> sqlite3.Connection:
    """Ouvre une base en lecture seule."""
    connexion = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    connexion.row_factory = sqlite3.Row
    return connexion


def trouver_conversation(connexion: sqlite3.Connection, contact: str) -> int:
    """Identifiant de la conversation portant ce nom de contact."""
    lignes = connexion.execute(
        "SELECT Z_PK FROM ZWACHATSESSION WHERE ZPARTNERNAME = ? COLLATE NOCASE",
        (contact,),
    ).fetchall()

    if not lignes:
        raise ConversationIntrouvable(f"Aucune conversation nommée « {contact} »")
    if len(lignes) > 1:
        raise ConversationIntrouvable(
            f"{len(lignes)} conversations nommées « {contact} » : préciser le contact"
        )
    return int(lignes[0]["Z_PK"])


_REQUETE = """
    SELECT m.ZMESSAGEDATE     AS quand,
           m.ZISFROMME        AS de_moi,
           m.ZMESSAGETYPE     AS type,
           m.ZTEXT            AS texte,
           i.Z_PK             AS piece,
           i.ZTITLE           AS legende,
           i.ZMEDIALOCALPATH  AS media
      FROM ZWAMESSAGE m
      LEFT JOIN ZWAMEDIAITEM i ON i.ZMESSAGE = m.Z_PK
     WHERE m.ZCHATSESSION = ? AND m.ZMESSAGEDATE IS NOT NULL
     ORDER BY m.ZMESSAGEDATE
"""


def lire_messages(
    connexion: sqlite3.Connection,
    session: int,
    correspondant: str,
    moi: str = "Alexandre",
    racine_media: Path = RACINE_MEDIA,
) -> list[MessageBrut]:
    """Tous les messages d'une conversation, du plus ancien au plus récent.

    Un média que ce Mac n'a jamais téléchargé n'a pas de chemin local. Le
    message est tout de même conservé, avec la nature de ce qui manque : le
    fichier est resté sur le téléphone, mais l'envoi a bien eu lieu et le fil
    doit pouvoir le dire.

    Les événements système — ni texte, ni légende, ni média — sont écartés :
    ils n'apprennent rien et alourdiraient le fil.
    """
    messages: list[MessageBrut] = []

    for ligne in connexion.execute(_REQUETE, (session,)):
        media = Path(ligne["media"]) if ligne["media"] else None
        est_document = ligne["type"] == TYPE_DOCUMENT
        manquant = (
            _MEDIA_ABSENT.get(ligne["type"])
            if ligne["piece"] is not None and media is None
            else None
        )

        message = MessageBrut(
            horodatage=horodatage(ligne["quand"]),
            auteur=moi if ligne["de_moi"] else correspondant,
            texte=(ligne["texte"] or "") if ligne["type"] == TYPE_TEXTE else "",
            nom_fichier=ligne["texte"] if est_document else None,
            legende=ligne["legende"] or None,
            media=(racine_media / media) if media else None,
            media_absent=manquant,
        )
        if not (message.texte or message.legende or message.media or message.media_absent):
            continue
        messages.append(message)

    return messages
