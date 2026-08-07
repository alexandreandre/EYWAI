"""Fabrique de bases WhatsApp miniatures.

Reproduit les seules colonnes que `whatsapp_base` interroge. Les données sont
inventées : aucune donnée réelle ne doit entrer dans un test.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

import pytest

EPOCH_APPLE = 978_307_200

_SCHEMA = """
CREATE TABLE ZWACHATSESSION (
    Z_PK INTEGER PRIMARY KEY,
    ZPARTNERNAME VARCHAR,
    ZCONTACTJID VARCHAR
);
CREATE TABLE ZWAMESSAGE (
    Z_PK INTEGER PRIMARY KEY,
    ZCHATSESSION INTEGER,
    ZISFROMME INTEGER,
    ZMESSAGETYPE INTEGER,
    ZMESSAGEDATE TIMESTAMP,
    ZTEXT VARCHAR
);
CREATE TABLE ZWAMEDIAITEM (
    Z_PK INTEGER PRIMARY KEY,
    ZMESSAGE INTEGER,
    ZTITLE VARCHAR,
    ZMEDIALOCALPATH VARCHAR
);
"""


def secondes_apple(horodatage: dt.datetime) -> float:
    """Convertit une heure de Paris en secondes Core Data (UTC)."""
    from zoneinfo import ZoneInfo

    aware = horodatage.replace(tzinfo=ZoneInfo("Europe/Paris"))
    return aware.timestamp() - EPOCH_APPLE


@pytest.fixture
def fabriquer_base(tmp_path: Path):
    """Rend une fonction qui écrit une base miniature et rend son chemin.

    Chaque message est un tuple
    `(horodatage, de_moi, type, texte, legende, chemin_media)`.

    `chemin_media=""` crée la pièce jointe sans chemin local : c'est ainsi que
    la base note un média jamais téléchargé sur cette machine.
    """

    def fabrique(messages, contact: str = "Elsa", nom: str = "ChatStorage.sqlite") -> Path:
        base = tmp_path / nom
        connexion = sqlite3.connect(base)
        connexion.executescript(_SCHEMA)
        connexion.execute(
            "INSERT INTO ZWACHATSESSION (Z_PK, ZPARTNERNAME, ZCONTACTJID) VALUES (?, ?, ?)",
            (7, contact, "33600000000@s.whatsapp.net"),
        )
        for identifiant, (quand, de_moi, type_, texte, legende, media) in enumerate(messages, 1):
            connexion.execute(
                "INSERT INTO ZWAMESSAGE"
                " (Z_PK, ZCHATSESSION, ZISFROMME, ZMESSAGETYPE, ZMESSAGEDATE, ZTEXT)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (identifiant, 7, de_moi, type_, secondes_apple(quand), texte),
            )
            if legende is not None or media is not None:
                connexion.execute(
                    "INSERT INTO ZWAMEDIAITEM (ZMESSAGE, ZTITLE, ZMEDIALOCALPATH)"
                    " VALUES (?, ?, ?)",
                    (identifiant, legende, media or None),
                )
        connexion.commit()
        connexion.close()
        return base

    return fabrique
