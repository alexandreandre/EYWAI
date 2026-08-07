# Extraction autonome de la conversation WhatsApp — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** produire l'export de la conversation WhatsApp d'Elsa depuis la base locale de WhatsApp Desktop, sans passer par le téléphone, puis le faire classer par la chaîne existante.

**Architecture :** trois modules sous `backend/scripts/data_organize/`. `whatsapp_base` lit la base SQLite de WhatsApp (copie, lecture seule) et rend des messages bruts. `extraire_whatsapp` en écrit un dossier d'export au format que `whatsapp.lire()` sait déjà parser. `actualiser` enchaîne extraction et `ingerer`. Rien n'est modifié dans les modules existants.

**Tech Stack :** Python 3.11+, `sqlite3` et `zoneinfo` de la bibliothèque standard, pytest.

**Spec :** `docs/superpowers/specs/2026-08-07-extraction-whatsapp-design.md`

## Global Constraints

- Le dépôt est **public** et `data/` est gitignoré. Aucun contenu de conversation — texte, nom de salarié, extrait de message — n'entre dans le code, dans un test ou dans un document versionné. Les tests construisent leurs propres bases SQLite miniatures avec des données inventées.
- La base de WhatsApp n'est **jamais** ouverte en place : on copie `ChatStorage.sqlite` avec ses journaux `-wal` et `-shm`, et on interroge la copie en `mode=ro`.
- Les horodatages du fil sont écrits en **heure de Paris** (`ZoneInfo("Europe/Paris")`), jamais en heure locale de la machine. Vérifié le 2026-08-07 : le Mac est en `EDT`, un `datetime.fromtimestamp()` sans fuseau décale le fil de 6 heures par rapport à l'export du téléphone.
- Les horodatages de la base sont en secondes depuis le **1er janvier 2001** (Core Data) : décalage `978_307_200`.
- Tous les modules et commentaires sont en français, comme le reste de `data_organize`.
- Commandes lancées depuis `backend/` : `pytest.ini` y fixe `pythonpath = .`, ce qui rend `scripts.data_organize` importable.

## Repères relevés dans la vraie base (2026-08-07)

| Élément | Valeur |
|---|---|
| Base | `~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite` |
| Racine des médias | le voisin `…/group.net.whatsapp.WhatsApp.shared/Message/`, `ZMEDIALOCALPATH` valant `Media/<jid>/x/y/<uuid>.ext` |
| Conversation Elsa | `ZWACHATSESSION.ZPARTNERNAME = 'Elsa'` |
| Type d'un message | `ZWAMESSAGE.ZMESSAGETYPE` : `0` texte, `1` image, `2` vidéo, `3` audio, `8` document |
| Nom d'origine d'un document | `ZWAMESSAGE.ZTEXT` quand le type vaut `8` |
| Légende d'un média | `ZWAMEDIAITEM.ZTITLE` |
| Lien message → média | `ZWAMEDIAITEM.ZMESSAGE = ZWAMESSAGE.Z_PK` |

Format exact d'une ligne d'export, marques de sens de lecture comprises (relevé dans `data/_inbox/whatsapp-elsa-2026-08-02/_chat.txt`) :

```
‎[24/10/2025 21:54:49] Alexandre: ‎< pièce jointe : -0000186-Ahmadou.vcf >
‎[21/11/2025 16:28:05] Elsa: COLOR 1025.xml ‎< pièce jointe : 00000187-COLOR 1025.xml >
[13/08/2025 15:04:29] Elsa: https://www.linkedin.com/posts/…
```

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `backend/scripts/data_organize/whatsapp_base.py` | Créer, copier et interroger la base WhatsApp. Rend des `MessageBrut`. Ne connaît ni `data/`, ni société, ni format d'export. |
| `backend/scripts/data_organize/extraire_whatsapp.py` | Écrire un dossier d'export depuis une liste de `MessageBrut` : `_chat.txt`, pièces jointes manquantes, état, `nouveautes.md`. |
| `backend/scripts/data_organize/actualiser.py` | Enchaîner extraction et `ingerer`, produire le rapport unique. |
| `backend/tests/unit/data_organize/conftest.py` | Fabrique de bases SQLite miniatures pour les tests. |
| `backend/tests/unit/data_organize/test_whatsapp_base.py` | Tests de lecture de la base. |
| `backend/tests/unit/data_organize/test_extraire_whatsapp.py` | Tests d'écriture de l'export, d'idempotence et de `nouveautes.md`. |

---

### Task 1 : lecture de la base WhatsApp

**Files:**
- Create: `backend/scripts/data_organize/whatsapp_base.py`
- Create: `backend/tests/unit/data_organize/__init__.py` (fichier vide)
- Create: `backend/tests/unit/data_organize/conftest.py`
- Test: `backend/tests/unit/data_organize/test_whatsapp_base.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `MessageBrut(horodatage: datetime, auteur: str, texte: str, nom_fichier: str | None, legende: str | None, media: Path | None)` avec la propriété `porte_un_media -> bool`
  - `BASE_WHATSAPP: Path`, `RACINE_MEDIA: Path`, `EPOCH_APPLE: int`, `FUSEAU: ZoneInfo`
  - `BaseIntrouvable(RuntimeError)`, `ConversationIntrouvable(RuntimeError)`
  - `horodatage(secondes: float) -> datetime` (naïf, heure de Paris)
  - `copier_base(destination: Path, source: Path = BASE_WHATSAPP) -> Path`
  - `ouvrir(base: Path) -> sqlite3.Connection`
  - `trouver_conversation(connexion: sqlite3.Connection, contact: str) -> int`
  - `lire_messages(connexion, session: int, correspondant: str, moi: str = "Alexandre", racine_media: Path = RACINE_MEDIA) -> list[MessageBrut]`

- [ ] **Step 1 : écrire la fabrique de bases de test**

Créer `backend/tests/unit/data_organize/__init__.py` vide, puis `backend/tests/unit/data_organize/conftest.py` :

```python
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
                    (identifiant, legende, media),
                )
        connexion.commit()
        connexion.close()
        return base

    return fabrique
```

- [ ] **Step 2 : écrire les tests de lecture**

Créer `backend/tests/unit/data_organize/test_whatsapp_base.py` :

```python
"""Lecture de la base locale de WhatsApp Desktop."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from scripts.data_organize import whatsapp_base as wb


def test_horodatage_est_rendu_en_heure_de_paris():
    """Le Mac peut être dans n'importe quel fuseau : le fil, lui, est à Paris."""
    midi_paris = dt.datetime(2026, 8, 2, 16, 57, 50)
    secondes = midi_paris.replace(tzinfo=wb.FUSEAU).timestamp() - wb.EPOCH_APPLE

    assert wb.horodatage(secondes) == midi_paris


def test_trouver_conversation_par_nom_de_contact(fabriquer_base):
    base = fabriquer_base([(dt.datetime(2026, 6, 1, 9, 0), 0, 0, "bonjour", None, None)])
    connexion = wb.ouvrir(base)

    assert wb.trouver_conversation(connexion, "Elsa") == 7


def test_trouver_conversation_ignore_la_casse(fabriquer_base):
    base = fabriquer_base([(dt.datetime(2026, 6, 1, 9, 0), 0, 0, "bonjour", None, None)])
    connexion = wb.ouvrir(base)

    assert wb.trouver_conversation(connexion, "elsa") == 7


def test_conversation_absente_leve_une_erreur(fabriquer_base):
    base = fabriquer_base([(dt.datetime(2026, 6, 1, 9, 0), 0, 0, "bonjour", None, None)])
    connexion = wb.ouvrir(base)

    with pytest.raises(wb.ConversationIntrouvable):
        wb.trouver_conversation(connexion, "Personne")


def test_message_texte(fabriquer_base):
    base = fabriquer_base([(dt.datetime(2026, 6, 1, 9, 0), 0, 0, "bonjour", None, None)])
    connexion = wb.ouvrir(base)

    messages = wb.lire_messages(connexion, 7, correspondant="Elsa")

    assert len(messages) == 1
    assert messages[0].auteur == "Elsa"
    assert messages[0].texte == "bonjour"
    assert messages[0].media is None


def test_message_envoye_porte_mon_nom(fabriquer_base):
    base = fabriquer_base([(dt.datetime(2026, 6, 1, 9, 0), 1, 0, "reçu", None, None)])
    connexion = wb.ouvrir(base)

    messages = wb.lire_messages(connexion, 7, correspondant="Elsa", moi="Alexandre")

    assert messages[0].auteur == "Alexandre"


def test_document_expose_son_nom_dorigine_et_sa_legende(fabriquer_base):
    """C'est ce couple qui permettra à `ingerer` de classer le fichier."""
    base = fabriquer_base(
        [
            (
                dt.datetime(2026, 6, 1, 9, 0),
                0,
                wb.TYPE_DOCUMENT,
                "POINTAGE 05-2026.xlsx",
                "les pointages de mai",
                "Media/33600000000@s.whatsapp.net/a/b/uuid.xlsx",
            )
        ]
    )
    connexion = wb.ouvrir(base)

    message = wb.lire_messages(connexion, 7, correspondant="Elsa", racine_media=Path("/racine"))[0]

    assert message.nom_fichier == "POINTAGE 05-2026.xlsx"
    assert message.legende == "les pointages de mai"
    assert message.media == Path("/racine/Media/33600000000@s.whatsapp.net/a/b/uuid.xlsx")
    assert message.texte == ""


def test_photo_na_pas_de_nom_dorigine(fabriquer_base):
    base = fabriquer_base(
        [
            (
                dt.datetime(2026, 6, 1, 9, 0),
                0,
                1,
                None,
                "regarde",
                "Media/33600000000@s.whatsapp.net/c/d/uuid.jpg",
            )
        ]
    )
    connexion = wb.ouvrir(base)

    message = wb.lire_messages(connexion, 7, correspondant="Elsa", racine_media=Path("/racine"))[0]

    assert message.nom_fichier is None
    assert message.legende == "regarde"
    assert message.porte_un_media


def test_les_messages_muets_sont_ecartes(fabriquer_base):
    """Événements système : ni texte, ni légende, ni média. Rien à consigner."""
    base = fabriquer_base(
        [
            (dt.datetime(2026, 6, 1, 9, 0), 0, 59, None, None, None),
            (dt.datetime(2026, 6, 1, 9, 1), 0, 0, "bonjour", None, None),
        ]
    )
    connexion = wb.ouvrir(base)

    messages = wb.lire_messages(connexion, 7, correspondant="Elsa")

    assert [m.texte for m in messages] == ["bonjour"]


def test_les_messages_sortent_dans_lordre_chronologique(fabriquer_base):
    base = fabriquer_base(
        [
            (dt.datetime(2026, 6, 2, 9, 0), 0, 0, "second", None, None),
            (dt.datetime(2026, 6, 1, 9, 0), 0, 0, "premier", None, None),
        ]
    )
    connexion = wb.ouvrir(base)

    messages = wb.lire_messages(connexion, 7, correspondant="Elsa")

    assert [m.texte for m in messages] == ["premier", "second"]


def test_copier_base_emporte_les_journaux(fabriquer_base, tmp_path):
    """Sans le `-wal`, les derniers messages manquent à l'appel."""
    base = fabriquer_base([(dt.datetime(2026, 6, 1, 9, 0), 0, 0, "bonjour", None, None)])
    base.with_name(base.name + "-wal").write_bytes(b"journal")

    copie = wb.copier_base(tmp_path / "copie", source=base)

    assert copie.exists()
    assert copie.with_name(copie.name + "-wal").read_bytes() == b"journal"


def test_base_absente_leve_une_erreur(tmp_path):
    with pytest.raises(wb.BaseIntrouvable):
        wb.copier_base(tmp_path / "copie", source=tmp_path / "nulle-part.sqlite")
```

- [ ] **Step 3 : lancer les tests pour les voir échouer**

```bash
cd backend && pytest tests/unit/data_organize/test_whatsapp_base.py -v
```

Attendu : collection error, `ModuleNotFoundError: No module named 'scripts.data_organize.whatsapp_base'`.

- [ ] **Step 4 : écrire le module**

Créer `backend/scripts/data_organize/whatsapp_base.py` :

```python
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
TYPE_DOCUMENT = 8


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

    Les événements système — ni texte, ni légende, ni média — sont écartés :
    ils n'apprennent rien et alourdiraient le fil.
    """
    messages: list[MessageBrut] = []

    for ligne in connexion.execute(_REQUETE, (session,)):
        media = Path(ligne["media"]) if ligne["media"] else None
        est_document = ligne["type"] == TYPE_DOCUMENT

        message = MessageBrut(
            horodatage=horodatage(ligne["quand"]),
            auteur=moi if ligne["de_moi"] else correspondant,
            texte=(ligne["texte"] or "") if ligne["type"] == TYPE_TEXTE else "",
            nom_fichier=ligne["texte"] if est_document else None,
            legende=ligne["legende"] or None,
            media=(racine_media / media) if media else None,
        )
        if not (message.texte or message.legende or message.media):
            continue
        messages.append(message)

    return messages
```

- [ ] **Step 5 : lancer les tests pour les voir passer**

```bash
cd backend && pytest tests/unit/data_organize/test_whatsapp_base.py -v
```

Attendu : 12 passed.

- [ ] **Step 6 : commiter**

```bash
git add backend/scripts/data_organize/whatsapp_base.py backend/tests/unit/data_organize/
git commit -m "feat(whatsapp): lecture de la base locale de WhatsApp Desktop"
```

---

### Task 2 : écriture du dossier d'export

**Files:**
- Create: `backend/scripts/data_organize/extraire_whatsapp.py`
- Test: `backend/tests/unit/data_organize/test_extraire_whatsapp.py`

**Interfaces:**
- Consumes: `whatsapp_base.MessageBrut`
- Produces:
  - `nom_origine(message: MessageBrut) -> str`
  - `ligne_chat(message: MessageBrut, piece: str | None) -> str`
  - `Rapport(messages: int, pieces_copiees: int, pieces_absentes: int, nouveaux: list[MessageBrut])`
  - `ecrire_export(messages: list[MessageBrut], dossier: Path, depuis: datetime | None) -> Rapport`
  - `FICHIER_CONVERSATION = "_chat.txt"`, `FICHIER_NOUVEAUTES = "nouveautes.md"`

Le compteur de pièce jointe est **l'ordre chronologique du message porteur de média**, sur huit chiffres. Il est déterministe : deux extractions successives donnent les mêmes noms, donc aucune copie en double. Une pièce supprimée dans WhatsApp après coup laisse un fichier orphelin dans l'export ; c'est sans conséquence, `ingerer` ne range que ce que `_chat.txt` cite.

- [ ] **Step 1 : écrire les tests de format**

Créer `backend/tests/unit/data_organize/test_extraire_whatsapp.py` :

```python
"""Écriture d'un dossier d'export à partir de messages bruts."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from scripts.data_organize import extraire_whatsapp as ex
from scripts.data_organize import whatsapp as wa
from scripts.data_organize.whatsapp_base import MessageBrut


def message(quand, auteur="Elsa", **reste) -> MessageBrut:
    return MessageBrut(horodatage=quand, auteur=auteur, **reste)


def test_ligne_de_texte_simple():
    ligne = ex.ligne_chat(message(dt.datetime(2026, 6, 1, 9, 5, 3), texte="bonjour"), None)

    assert ligne == "‎[01/06/2026 09:05:03] Elsa: bonjour"


def test_ligne_de_document_cite_son_nom_dorigine():
    """`ingerer` classe sur ce nom : il doit apparaître tel quel."""
    doc = message(
        dt.datetime(2026, 6, 1, 9, 5, 3),
        nom_fichier="POINTAGE 05-2026.xlsx",
        media=Path("/racine/Media/a/b/uuid.xlsx"),
    )

    ligne = ex.ligne_chat(doc, "00000001-POINTAGE 05-2026.xlsx")

    assert ligne == (
        "‎[01/06/2026 09:05:03] Elsa: POINTAGE 05-2026.xlsx"
        " ‎< pièce jointe : 00000001-POINTAGE 05-2026.xlsx >"
    )


def test_la_legende_suit_la_piece_jointe():
    """La légende porte le contexte : elle doit rester collée au message."""
    doc = message(
        dt.datetime(2026, 6, 1, 9, 5, 3),
        nom_fichier="POINTAGE.xlsx",
        legende="les pointages de Cartol",
        media=Path("/racine/Media/a/b/uuid.xlsx"),
    )

    ligne = ex.ligne_chat(doc, "00000001-POINTAGE.xlsx")

    assert ligne.endswith(" >\nles pointages de Cartol")


def test_media_sans_nom_prend_un_nom_construit():
    photo = message(dt.datetime(2026, 6, 1, 9, 5, 3), media=Path("/racine/Media/a/b/uuid.jpg"))

    assert ex.nom_origine(photo) == "PHOTO-2026-06-01-09-05-03.jpg"


def test_les_lignes_produites_sont_relues_par_le_parseur_existant(tmp_path):
    """Le format d'export est un contrat avec `whatsapp.lire()`."""
    fichier = tmp_path / "Media" / "a" / "b" / "uuid.xlsx"
    fichier.parent.mkdir(parents=True)
    fichier.write_bytes(b"contenu")

    messages = [
        message(dt.datetime(2026, 6, 1, 9, 0, 0), texte="je t'envoie ça"),
        message(dt.datetime(2026, 6, 1, 9, 1, 0), nom_fichier="PAIE CARTOL.xlsx", media=fichier),
    ]
    ex.ecrire_export(messages, tmp_path / "export", depuis=None)

    conversation = wa.lire(tmp_path / "export")

    assert len(conversation.messages) == 2
    assert conversation.messages[0].texte == "je t'envoie ça"
    assert conversation.pieces_jointes[0][1].piece_jointe == "00000001-PAIE CARTOL.xlsx"


def test_la_piece_jointe_est_copiee(tmp_path):
    fichier = tmp_path / "Media" / "a" / "b" / "uuid.xlsx"
    fichier.parent.mkdir(parents=True)
    fichier.write_bytes(b"contenu")

    rapport = ex.ecrire_export(
        [message(dt.datetime(2026, 6, 1, 9, 0), nom_fichier="PAIE.xlsx", media=fichier)],
        tmp_path / "export",
        depuis=None,
    )

    assert rapport.pieces_copiees == 1
    assert (tmp_path / "export" / "00000001-PAIE.xlsx").read_bytes() == b"contenu"


def test_une_seconde_extraction_ne_recopie_rien(tmp_path):
    """« Garder seulement ce qu'on n'a pas » : la copie est idempotente."""
    fichier = tmp_path / "Media" / "a" / "b" / "uuid.xlsx"
    fichier.parent.mkdir(parents=True)
    fichier.write_bytes(b"contenu")
    messages = [message(dt.datetime(2026, 6, 1, 9, 0), nom_fichier="PAIE.xlsx", media=fichier)]

    ex.ecrire_export(messages, tmp_path / "export", depuis=None)
    second = ex.ecrire_export(messages, tmp_path / "export", depuis=None)

    assert second.pieces_copiees == 0


def test_media_absent_du_disque_reste_cite_dans_le_fil(tmp_path):
    """Le fichier est resté sur le téléphone ; le fil doit en garder la trace."""
    manquant = tmp_path / "Media" / "a" / "b" / "jamais-telecharge.pdf"

    rapport = ex.ecrire_export(
        [message(dt.datetime(2026, 6, 1, 9, 0), nom_fichier="BULLETIN.pdf", media=manquant)],
        tmp_path / "export",
        depuis=None,
    )

    assert rapport.pieces_absentes == 1
    assert rapport.pieces_copiees == 0
    assert "BULLETIN.pdf" in (tmp_path / "export" / "_chat.txt").read_text(encoding="utf-8")


def test_le_fil_est_regenere_en_entier(tmp_path):
    """Le contexte des messages voisins sert à classer : on ne tronque pas."""
    messages = [
        message(dt.datetime(2026, 5, 1, 9, 0), texte="ancien"),
        message(dt.datetime(2026, 6, 1, 9, 0), texte="récent"),
    ]

    ex.ecrire_export(messages, tmp_path / "export", depuis=dt.datetime(2026, 5, 15))
    fil = (tmp_path / "export" / "_chat.txt").read_text(encoding="utf-8")

    assert "ancien" in fil and "récent" in fil


def test_les_nouveautes_se_limitent_a_ce_qui_suit_la_derniere_extraction(tmp_path):
    messages = [
        message(dt.datetime(2026, 5, 1, 9, 0), texte="ancien"),
        message(dt.datetime(2026, 6, 1, 9, 0), texte="récent"),
    ]

    rapport = ex.ecrire_export(messages, tmp_path / "export", depuis=dt.datetime(2026, 5, 15))
    nouveautes = (tmp_path / "export" / "nouveautes.md").read_text(encoding="utf-8")

    assert [m.texte for m in rapport.nouveaux] == ["récent"]
    assert "récent" in nouveautes
    assert "ancien" not in nouveautes


def test_sans_extraction_anterieure_tout_est_nouveau(tmp_path):
    messages = [message(dt.datetime(2026, 5, 1, 9, 0), texte="ancien")]

    rapport = ex.ecrire_export(messages, tmp_path / "export", depuis=None)

    assert len(rapport.nouveaux) == 1
```

- [ ] **Step 2 : lancer les tests pour les voir échouer**

```bash
cd backend && pytest tests/unit/data_organize/test_extraire_whatsapp.py -v
```

Attendu : collection error, `ModuleNotFoundError: No module named 'scripts.data_organize.extraire_whatsapp'`.

- [ ] **Step 3 : écrire le module**

Créer `backend/scripts/data_organize/extraire_whatsapp.py` :

```python
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

import datetime as dt
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from scripts.data_organize.whatsapp_base import MessageBrut

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
```

- [ ] **Step 4 : lancer les tests pour les voir passer**

```bash
cd backend && pytest tests/unit/data_organize/test_extraire_whatsapp.py -v
```

Attendu : 11 passed.

- [ ] **Step 5 : commiter**

```bash
git add backend/scripts/data_organize/extraire_whatsapp.py backend/tests/unit/data_organize/test_extraire_whatsapp.py
git commit -m "feat(whatsapp): écriture d'un export au format attendu par la chaîne de classement"
```

---

### Task 3 : état d'une extraction à l'autre

**Files:**
- Modify: `backend/scripts/data_organize/extraire_whatsapp.py`
- Modify: `backend/tests/unit/data_organize/test_extraire_whatsapp.py`

**Interfaces:**
- Consumes: `Rapport`, `ecrire_export` de la tâche 2.
- Produces:
  - `chemin_etat(inbox: Path, contact: str) -> Path`
  - `lire_etat(chemin: Path) -> datetime | None`
  - `ecrire_etat(chemin: Path, dernier: datetime | None, rapport: Rapport) -> None`

- [ ] **Step 1 : écrire les tests**

Ajouter à la fin de `backend/tests/unit/data_organize/test_extraire_whatsapp.py` :

```python
def test_letat_est_absent_a_la_premiere_extraction(tmp_path):
    assert ex.lire_etat(tmp_path / ".whatsapp-elsa.json") is None


def test_letat_retient_le_dernier_message(tmp_path):
    chemin = tmp_path / ".whatsapp-elsa.json"
    rapport = ex.Rapport(messages=3, pieces_copiees=1)

    ex.ecrire_etat(chemin, dt.datetime(2026, 6, 1, 9, 0), rapport)

    assert ex.lire_etat(chemin) == dt.datetime(2026, 6, 1, 9, 0)


def test_le_nom_du_fichier_detat_depend_du_contact(tmp_path):
    assert ex.chemin_etat(tmp_path, "Elsa").name == ".whatsapp-elsa.json"


def test_un_etat_illisible_vaut_absence(tmp_path):
    """Un fichier tronqué ne doit pas empêcher l'extraction : tout est neuf."""
    chemin = tmp_path / ".whatsapp-elsa.json"
    chemin.write_text("{ceci n'est pas du json", encoding="utf-8")

    assert ex.lire_etat(chemin) is None
```

- [ ] **Step 2 : lancer les tests pour les voir échouer**

```bash
cd backend && pytest tests/unit/data_organize/test_extraire_whatsapp.py -k etat -v
```

Attendu : `AttributeError: module 'scripts.data_organize.extraire_whatsapp' has no attribute 'lire_etat'`.

- [ ] **Step 3 : implémenter l'état**

Dans `backend/scripts/data_organize/extraire_whatsapp.py`, ajouter `import json` et `import re` en tête, puis ces fonctions après `ecrire_export` :

```python
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
```

- [ ] **Step 4 : lancer les tests pour les voir passer**

```bash
cd backend && pytest tests/unit/data_organize/test_extraire_whatsapp.py -v
```

Attendu : 15 passed.

- [ ] **Step 5 : commiter**

```bash
git add backend/scripts/data_organize/extraire_whatsapp.py backend/tests/unit/data_organize/test_extraire_whatsapp.py
git commit -m "feat(whatsapp): état d'une extraction à l'autre, pour ne signaler que les nouveautés"
```

---

### Task 4 : commande d'extraction, et essai sur la vraie base

**Files:**
- Modify: `backend/scripts/data_organize/extraire_whatsapp.py`

**Interfaces:**
- Consumes: `whatsapp_base.copier_base/ouvrir/trouver_conversation/lire_messages`, `chemin_etat`, `lire_etat`, `ecrire_etat`, `ecrire_export`.
- Produces:
  - `extraire(contact: str, inbox: Path, base: Path = BASE_WHATSAPP, racine_media: Path = RACINE_MEDIA) -> tuple[Path, Rapport]`
  - `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1 : écrire l'orchestration et la CLI**

Ajouter en tête de `backend/scripts/data_organize/extraire_whatsapp.py` :

```python
import argparse
import sys
import tempfile

from scripts.data_organize import convention as cv
from scripts.data_organize.inventaire import RACINE_DATA
from scripts.data_organize.whatsapp_base import (
    BASE_WHATSAPP,
    RACINE_MEDIA,
    copier_base,
    lire_messages,
    ouvrir,
    trouver_conversation,
)

INBOX = RACINE_DATA / cv.INBOX
```

(l'import existant `from scripts.data_organize.whatsapp_base import MessageBrut` fusionne dans ce bloc)

Puis, à la fin du module :

```python
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
```

- [ ] **Step 2 : vérifier que les tests unitaires tiennent toujours**

```bash
cd backend && pytest tests/unit/data_organize/ -v
```

Attendu : 27 passed.

- [ ] **Step 3 : essai sur la vraie base**

```bash
cd backend && python -m scripts.data_organize.extraire_whatsapp --contact Elsa
```

Attendu : un compte de messages supérieur à 6 700, quelques centaines de pièces copiées, et des pièces absentes (les médias jamais téléchargés sur le Mac). Le dossier `data/_inbox/whatsapp-elsa/` existe.

- [ ] **Step 4 : vérifier la cohérence avec l'export manuel**

```bash
cd backend && python - <<'PY'
import io, re
from pathlib import Path

RACINE = Path("../data/_inbox")
RE_ENTETE = re.compile(r"^\[(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\] ([^:]{1,60}): ")
MARQUES = dict.fromkeys(map(ord, "‎‏‪‬"), None)

def entetes(chemin):
    texte = io.open(chemin, encoding="utf-8", errors="replace").read().translate(MARQUES)
    return [m.group(1) for l in texte.split("\n") if (m := RE_ENTETE.match(l))]

manuel = entetes(RACINE / "whatsapp-elsa-2026-08-02/_chat.txt")
auto = set(entetes(RACINE / "whatsapp-elsa/_chat.txt"))
manquants = [h for h in manuel if h not in auto]
print(f"manuel {len(manuel)} messages, auto {len(auto)} horodatages")
print(f"horodatages du manuel absents de l'auto : {len(manquants)}")
print(manquants[:5])
PY
```

Attendu : « horodatages du manuel absents de l'auto » proche de zéro. Un écart non nul et systématique de plusieurs heures signale une erreur de fuseau — reprendre `whatsapp_base.horodatage`. Quelques manquants isolés sont normaux : messages supprimés depuis.

- [ ] **Step 5 : vérifier l'idempotence sur la vraie base**

```bash
cd backend && python -m scripts.data_organize.extraire_whatsapp --contact Elsa
```

Attendu : `pièces copiées 0` et `nouveautés 0` — le second passage ne recopie rien.

- [ ] **Step 6 : commiter**

```bash
git add backend/scripts/data_organize/extraire_whatsapp.py
git commit -m "feat(whatsapp): commande d'extraction de la conversation depuis la base locale"
```

---

### Task 5 : chaînage avec le classement

**Files:**
- Create: `backend/scripts/data_organize/actualiser.py`

**Interfaces:**
- Consumes: `extraire_whatsapp.extraire`, `ingerer.analyser/appliquer/afficher`, `ingerer.NOUVEAU`.
- Produces: `main(argv: list[str] | None = None) -> int`

`ingerer.analyser(export)` rend une `list[Piece]`, `ingerer.appliquer(pieces)` rend le nombre de fichiers copiés, `ingerer.afficher(pieces)` imprime le détail par état. Ces trois signatures existent déjà dans `backend/scripts/data_organize/ingerer.py`.

- [ ] **Step 1 : écrire le module**

Créer `backend/scripts/data_organize/actualiser.py` :

```python
"""Extraction puis classement de la conversation WhatsApp, en une commande.

    python -m scripts.data_organize.actualiser              # simulation
    python -m scripts.data_organize.actualiser --appliquer  # range sous data/

L'extraction a lieu dans les deux cas : elle est sans effet de bord hors de
`data/_inbox/`, et il faut bien lire le fil pour savoir ce qui a changé. Seul
le rangement sous `data/<societe>/…` est conditionné par `--appliquer`.
"""

from __future__ import annotations

import argparse
import sys

from scripts.data_organize import extraire_whatsapp, ingerer


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--contact", default="Elsa", help="nom du contact WhatsApp")
    analyseur.add_argument("--appliquer", action="store_true", help="range les nouveautés")
    arguments = analyseur.parse_args(argv)

    dossier, rapport = extraire_whatsapp.extraire(arguments.contact)
    print(f"=== conversation {arguments.contact} ===")
    print(f"{rapport.messages} messages, {rapport.pieces_copiees} pièces récupérées, "
          f"{rapport.pieces_absentes} restées sur le téléphone")

    pieces = ingerer.analyser(dossier)
    ingerer.afficher(pieces)

    if arguments.appliquer:
        copiees = ingerer.appliquer(pieces)
        print(f"\n{copiees} fichiers rangés sous data/")
    else:
        a_ranger = sum(1 for piece in pieces if piece.etat == ingerer.NOUVEAU)
        print(f"\nSimulation. {a_ranger} fichiers à ranger : relancer avec --appliquer.")

    if rapport.nouveaux:
        chemin = dossier / extraire_whatsapp.FICHIER_NOUVEAUTES
        print(f"\n{len(rapport.nouveaux)} messages nouveaux depuis la dernière fois : {chemin}")
        print("Les lire : ils portent ce qu'aucune pièce jointe ne dit.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2 : essai en simulation**

```bash
cd backend && python -m scripts.data_organize.actualiser
```

Attendu : le rapport d'extraction, puis le décompte de `ingerer` par état (`nouveau`, `identique`, `divergent`, `inclassable`, `ignoré`), puis « Simulation ». Rien n'est écrit sous `data/<societe>/`.

- [ ] **Step 3 : vérifier qu'aucun fichier n'a été rangé**

```bash
cd /Users/alex/Desktop/EYWAI/EYWAI && git status --short data/ | head
```

Attendu : aucune sortie — `data/` est gitignoré, et de toute façon la simulation n'y touche pas.

- [ ] **Step 4 : ranger pour de bon**

```bash
cd backend && python -m scripts.data_organize.actualiser --appliquer
```

Attendu : « N fichiers rangés sous data/ ». Relancer la même commande : le second passage doit annoncer `0` (les empreintes marquent les pièces comme `identique`).

- [ ] **Step 5 : commiter**

```bash
git add backend/scripts/data_organize/actualiser.py
git commit -m "feat(whatsapp): commande unique extraction + classement"
```

---

### Task 6 : mémoire, pour que Claude s'en serve seul

**Files:**
- Create: `/Users/alex/.claude/projects/-Users-alex-Desktop-EYWAI-EYWAI/memory/whatsapp-elsa-extraction.md`
- Modify: `/Users/alex/.claude/projects/-Users-alex-Desktop-EYWAI-EYWAI/memory/MEMORY.md`

Ces fichiers vivent hors du dépôt : rien à commiter.

- [ ] **Step 1 : écrire la mémoire**

```markdown
---
name: whatsapp-elsa-extraction
description: Extraire soi-même la conversation WhatsApp d'Elsa depuis la base locale, sans export manuel du téléphone
metadata:
  type: project
---

La conversation WhatsApp d'Elsa s'extrait sans intervention d'Alexandre :
`cd backend && python -m scripts.data_organize.actualiser --appliquer` copie la
base locale de WhatsApp Desktop, régénère `data/_inbox/whatsapp-elsa/`, range les
pièces jointes sous `data/<societe>/<rubrique>/<période>/` et écrit
`nouveautes.md` — le texte des messages arrivés depuis la dernière fois.

**Why:** les données de paie arrivent par WhatsApp. Avant, il fallait attendre
qu'Alexandre déclenche un export depuis son téléphone ; entre deux exports, tout
ce qu'Elsa envoyait était invisible.

**How to apply:** lancer la commande dès qu'un échange avec Elsa est évoqué,
qu'un document est censé être arrivé, ou qu'une donnée manque et pourrait être
passée par WhatsApp. Puis lire `nouveautes.md` : les engagements et les décisions
n'ont pas de pièce jointe. Deux limites : seuls les médias téléchargés sur le Mac
sont récupérables (les autres restent sur le téléphone, l'export manuel du
2026-08-02 sert de socle), et le fil s'écrit en heure de Paris alors que le Mac
peut être ailleurs. Voir [[ou-trouver-les-donnees]] et
[[fuites-donnees-personnelles-github]] — rien de tout cela ne quitte `data/`.
```

- [ ] **Step 2 : ajouter la ligne d'index**

Ajouter à `MEMORY.md`, à la suite de la ligne « Où trouver les données » :

```markdown
- [Extraction WhatsApp Elsa](whatsapp-elsa-extraction.md) — `python -m scripts.data_organize.actualiser --appliquer` extrait la conv **sans export manuel** ; lire `nouveautes.md` ; médias limités à ceux téléchargés sur le Mac
```

- [ ] **Step 3 : vérifier**

```bash
grep -c "whatsapp-elsa-extraction" /Users/alex/.claude/projects/-Users-alex-Desktop-EYWAI-EYWAI/memory/MEMORY.md
```

Attendu : `1`.

---

### Task 7 : vérification d'ensemble

**Files:** aucun. Cette tâche ne fait que vérifier ce que les précédentes ont produit.

- [ ] **Step 1 : lancer toute la suite unitaire**

```bash
cd backend && pytest tests/unit/data_organize/ -v
```

Attendu : 27 passed.

- [ ] **Step 2 : vérifier qu'aucun test existant n'a bougé**

```bash
cd backend && pytest tests/unit -q -x
```

Attendu : la suite passe comme avant l'implémentation. Aucun module existant n'a été modifié.

- [ ] **Step 3 : vérifier qu'aucune donnée réelle n'a fui dans le code**

```bash
cd /Users/alex/Desktop/EYWAI/EYWAI && git diff main --stat && git diff main -- backend/ | grep -iE "33XXXXXXXXX|elsa:" | head
```

Attendu : la liste des fichiers ajoutés, et **aucune** ligne trouvée par le `grep` — ni numéro de téléphone, ni extrait de conversation.

- [ ] **Step 4 : vérifier que rien de `data/` n'est suivi par git**

```bash
cd /Users/alex/Desktop/EYWAI/EYWAI && git status --short && git check-ignore -q data/_inbox/whatsapp-elsa/_chat.txt && echo "data/ bien ignoré"
```

Attendu : `data/ bien ignoré`, et aucun fichier de `data/` dans la sortie de `git status`.

- [ ] **Step 5 : lire les nouveautés**

```bash
cat /Users/alex/Desktop/EYWAI/EYWAI/data/_inbox/whatsapp-elsa/nouveautes.md
```

Attendu : les messages arrivés depuis le 2026-08-02. Les lire et signaler à Alexandre ce qui appelle une action — un document promis, une consigne de paie, une donnée manquante. C'est la finalité du chantier ; ne pas s'arrêter au « tests verts ».
