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
    ZTEXT VARCHAR,
    ZGROUPMEMBER INTEGER
);
CREATE TABLE ZWAGROUPMEMBER (
    Z_PK INTEGER PRIMARY KEY,
    ZCHATSESSION INTEGER,
    ZCONTACTNAME VARCHAR,
    ZFIRSTNAME VARCHAR,
    ZMEMBERJID VARCHAR
);
CREATE TABLE ZWAPROFILEPUSHNAME (
    Z_PK INTEGER PRIMARY KEY,
    ZJID VARCHAR,
    ZPUSHNAME VARCHAR
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
    `(horodatage, de_moi, type, texte, legende, chemin_media)`, avec un
    septième champ facultatif `(nom_contact, jid[, prenom, nom_profil])` : le
    membre du groupe qui l'a envoyé. Absent, le message est celui d'une
    conversation à deux.

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
        membres: dict[tuple[str | None, str], int] = {}

        for identifiant, message in enumerate(messages, 1):
            quand, de_moi, type_, texte, legende, media = message[:6]
            membre = message[6] if len(message) > 6 else None

            if membre is not None and membre not in membres:
                membres[membre] = len(membres) + 1
                nom_contact, jid = membre[:2]
                prenom = membre[2] if len(membre) > 2 else None
                nom_profil = membre[3] if len(membre) > 3 else None
                connexion.execute(
                    "INSERT INTO ZWAGROUPMEMBER"
                    " (Z_PK, ZCHATSESSION, ZCONTACTNAME, ZFIRSTNAME, ZMEMBERJID)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (membres[membre], 7, nom_contact, prenom, jid),
                )
                if nom_profil is not None:
                    connexion.execute(
                        "INSERT INTO ZWAPROFILEPUSHNAME (ZJID, ZPUSHNAME) VALUES (?, ?)",
                        (jid, nom_profil),
                    )

            connexion.execute(
                "INSERT INTO ZWAMESSAGE"
                " (Z_PK, ZCHATSESSION, ZISFROMME, ZMESSAGETYPE, ZMESSAGEDATE, ZTEXT,"
                " ZGROUPMEMBER) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    identifiant,
                    7,
                    de_moi,
                    type_,
                    secondes_apple(quand),
                    texte,
                    membres.get(membre) if membre is not None else None,
                ),
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
