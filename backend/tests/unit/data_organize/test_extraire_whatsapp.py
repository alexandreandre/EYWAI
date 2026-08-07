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


def test_ligne_de_media_jamais_telecharge():
    """Sans le fichier, la trace de l'envoi doit rester lisible dans le fil."""
    perdu = message(dt.datetime(2026, 6, 1, 9, 5, 3), media_absent="image absente")

    assert ex.ligne_chat(perdu, None) == "‎[01/06/2026 09:05:03] Elsa: image absente"


def test_ligne_de_document_jamais_telecharge_cite_son_nom():
    perdu = message(
        dt.datetime(2026, 6, 1, 9, 5, 3),
        nom_fichier="PAIE CARTOL",
        media_absent="document absent",
    )

    assert ex.ligne_chat(perdu, None).endswith("Elsa: PAIE CARTOL — document absent")


def test_les_medias_jamais_telecharges_sont_comptes(tmp_path):
    rapport = ex.ecrire_export(
        [message(dt.datetime(2026, 6, 1, 9, 0), media_absent="image absente")],
        tmp_path / "export",
        depuis=None,
    )

    assert rapport.pieces_absentes == 1
    assert rapport.pieces_copiees == 0


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
