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


def test_media_jamais_telecharge_reste_dans_le_fil(fabriquer_base):
    """Le fichier est resté sur le téléphone ; l'envoi, lui, a bien eu lieu."""
    base = fabriquer_base([(dt.datetime(2026, 6, 1, 9, 0), 0, wb.TYPE_IMAGE, None, None, "")])
    connexion = wb.ouvrir(base)

    message = wb.lire_messages(connexion, 7, correspondant="Elsa")[0]

    assert message.media is None
    assert message.media_absent == "image absente"


def test_document_jamais_telecharge_garde_son_nom(fabriquer_base):
    """La base retient le nom même quand le fichier n'est pas là."""
    base = fabriquer_base(
        [(dt.datetime(2026, 6, 1, 9, 0), 0, wb.TYPE_DOCUMENT, "PAIE CARTOL", None, "")]
    )
    connexion = wb.ouvrir(base)

    message = wb.lire_messages(connexion, 7, correspondant="Elsa")[0]

    assert message.nom_fichier == "PAIE CARTOL"
    assert message.media_absent == "document absent"


def test_apercu_de_lien_nest_pas_un_media_absent(fabriquer_base):
    """Un lien partagé porte une vignette : c'est du texte, pas une pièce perdue."""
    base = fabriquer_base(
        [(dt.datetime(2026, 6, 1, 9, 0), 0, wb.TYPE_TEXTE, "https://exemple.fr", None, "")]
    )
    connexion = wb.ouvrir(base)

    message = wb.lire_messages(connexion, 7, correspondant="Elsa")[0]

    assert message.texte == "https://exemple.fr"
    assert message.media_absent is None


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
