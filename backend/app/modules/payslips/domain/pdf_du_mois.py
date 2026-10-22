"""PDF de tous les bulletins d'un mois, sans rien recalculer.

On recolle les PDF déjà déposés, dans l'ordre alphabétique, avec un signet
par salarié. La page de garde nomme ceux qui devraient avoir un bulletin
et n'en ont pas, pour que le trou se voie.
"""

from __future__ import annotations

import io
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable
from xml.sax.saxutils import escape

from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

_MOIS = (
    "",
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)
_PARTIS = {"parti", "inactif", "sorti"}


@dataclass(frozen=True)
class SalarieDuMois:
    identifiant: str
    prenom: str
    nom: str
    statut: str
    dernier_jour: str | None
    debut: str | None
    fin_contrat: str | None


@dataclass(frozen=True)
class BulletinRange:
    identifiant: str
    chemin: str | None


def nom_affiche(prenom: str, nom: str) -> str:
    texte = f"{prenom} {nom}".strip()
    return texte or "Sans nom"


def _cle(prenom: str, nom: str) -> tuple[str, str]:
    def plier(valeur: str) -> str:
        decompose = unicodedata.normalize("NFD", valeur.casefold())
        return "".join(c for c in decompose if unicodedata.category(c) != "Mn")

    return (plier(nom), plier(prenom))


def present_sur_le_mois(statut: str | None, dernier_jour: str | None, annee: int, mois: int) -> bool:
    """Même règle que l'écran Paie : un parti n'est là que si son dernier jour tombe dans le mois ou après."""
    if str(statut or "actif").strip().lower() not in _PARTIS:
        return True
    if not dernier_jour:
        return False
    return str(dernier_jour)[:10] >= f"{annee:04d}-{mois:02d}-01"


def _jour(valeur: str | None) -> date | None:
    if not valeur:
        return None
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        return None


def hors_du_mois(debut: str | None, fin_contrat: str | None, annee: int, mois: int) -> bool:
    """Entrée après le mois, ou sortie avant le mois. Une date d'entrée absente n'est pas ce cas."""
    debut_jour = _jour(debut)
    if debut_jour is None:
        return False
    debut_mois = date(annee, mois, 1)
    fin_mois = date(annee + 1, 1, 1) - timedelta(days=1) if mois == 12 else date(annee, mois + 1, 1) - timedelta(days=1)
    if fin_mois < debut_jour:
        return True
    fin = _jour(fin_contrat)
    return bool(fin and debut_mois > fin)


def classer(
    salaries: list[SalarieDuMois],
    bulletins: list[BulletinRange],
    annee: int,
    mois: int,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Rend (nom, chemin) des PDF à coller, et les noms sans bulletin.

    Un bulletin existant est toujours collé, même si le salarié n'est plus
    affiché sur le mois. Quelqu'un hors du mois, sans fichier, n'est pas
    nommé : ce n'est pas un trou de paie.
    """
    chemin_par_personne = {
        bulletin.identifiant: bulletin.chemin
        for bulletin in bulletins
        if bulletin.chemin
    }
    connus = {salarie.identifiant for salarie in salaries}
    morceaux: list[tuple[str, str, tuple[str, str]]] = []
    sans: list[tuple[str, tuple[str, str]]] = []
    for salarie in salaries:
        nom = nom_affiche(salarie.prenom, salarie.nom)
        cle = _cle(salarie.prenom, salarie.nom)
        chemin = chemin_par_personne.get(salarie.identifiant)
        if chemin:
            morceaux.append((nom, chemin, cle))
            continue
        if not present_sur_le_mois(salarie.statut, salarie.dernier_jour, annee, mois):
            continue
        if hors_du_mois(salarie.debut, salarie.fin_contrat, annee, mois):
            continue
        sans.append((nom, cle))
    for bulletin in bulletins:
        if bulletin.identifiant in connus or not bulletin.chemin:
            continue
        morceaux.append(("Sans nom", bulletin.chemin, _cle("", bulletin.identifiant)))
    morceaux.sort(key=lambda ligne: ligne[2])
    sans.sort(key=lambda ligne: ligne[1])
    return [(nom, chemin) for nom, chemin, _cle_ in morceaux], [nom for nom, _cle_ in sans]


def libelle_mois(annee: int, mois: int) -> str:
    return f"{_MOIS[mois]} {annee}"


def nom_de_fichier(annee: int, mois: int) -> str:
    return f"Bulletins {_MOIS[mois]} {annee}.pdf"


def _page_de_garde(societe: str, annee: int, mois: int, colles: list[str], sans: list[str], illisibles: list[str]) -> bytes:
    periode = libelle_mois(annee, mois)
    titre = f"Bulletins d'{periode}" if periode[:1].lower() in "aeiouéèêà" else f"Bulletins de {periode}"
    tampon = io.BytesIO()
    document = SimpleDocTemplate(
        tampon,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2 * cm,
        title=titre,
    )
    titre_style = ParagraphStyle("titre", fontName="Times-Bold", fontSize=18, leading=22, spaceAfter=8)
    corps = ParagraphStyle("corps", fontName="Times-Roman", fontSize=11, leading=15, spaceAfter=6)
    rubrique = ParagraphStyle("rubrique", fontName="Times-Bold", fontSize=12, leading=16, spaceBefore=14, spaceAfter=6)
    ligne = ParagraphStyle("ligne", fontName="Times-Roman", fontSize=11, leading=15, leftIndent=8)
    elements = [
        Paragraph("Martine", ParagraphStyle("marque", fontName="Times-Roman", fontSize=10, textColor="#64748b", spaceAfter=10)),
        Paragraph(escape(titre), titre_style),
    ]
    if societe:
        elements.append(Paragraph(escape(societe), corps))
    elements.append(Paragraph(
        f"{len(colles)} bulletin{'s' if len(colles) != 1 else ''}, dans l'ordre alphabétique. "
        "Le sommaire du PDF ouvre chaque salarié.",
        corps,
    ))
    elements.append(Spacer(1, 0.2 * cm))
    if sans:
        elements.append(Paragraph(f"Sans bulletin ({len(sans)})", rubrique))
        elements.extend(Paragraph(escape(nom), ligne) for nom in sans)
    else:
        elements.append(Paragraph("Chaque salarié de ce mois a un bulletin.", corps))
    if illisibles:
        elements.append(Paragraph(f"Bulletin illisible ({len(illisibles)})", rubrique))
        elements.extend(Paragraph(escape(nom), ligne) for nom in illisibles)
    document.build(elements)
    return tampon.getvalue()


def assembler(
    societe: str,
    annee: int,
    mois: int,
    morceaux: list[tuple[str, str]],
    sans: list[str],
    lire_pdf: Callable[[str], bytes],
) -> bytes:
    """Colle les PDF lus. Un fichier illisible est nommé sur la page de garde, pas inséré."""
    colles: list[tuple[str, bytes]] = []
    illisibles: list[str] = []
    for nom, chemin in morceaux:
        try:
            contenu = lire_pdf(chemin)
            lecteur = PdfReader(io.BytesIO(contenu))
            if len(lecteur.pages) == 0:
                raise ValueError("pdf vide")
        except Exception:
            illisibles.append(nom)
            continue
        colles.append((nom, contenu))
    couverture = _page_de_garde(societe, annee, mois, [nom for nom, _ in colles], sans, illisibles)
    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(couverture)).pages:
        writer.add_page(page)
    for nom, contenu in colles:
        lecteur = PdfReader(io.BytesIO(contenu))
        debut = len(writer.pages)
        for page in lecteur.pages:
            writer.add_page(page)
        writer.add_outline_item(nom, debut)
    sortie = io.BytesIO()
    writer.write(sortie)
    return sortie.getvalue()
