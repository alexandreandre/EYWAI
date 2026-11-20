"""PDF d'un export : le classeur Excel de l'export, mis en page (Elsa, 17/11).

Un seul convertisseur pour tous les exports en tableau : chaque feuille du
classeur devient un tableau paysage, l'en-tête répété en haut de chaque page.
Le contenu est celui de l'Excel, au centime ; seuls la police et la largeur
des colonnes s'adaptent à la page.
"""

from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List
from xml.sax.saxutils import escape

from openpyxl import load_workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle

MARGE = 10 * mm
LARGEUR_UTILE = landscape(A4)[0] - 2 * MARGE


def texte_de_cellule(valeur: Any, decimales: bool = False) -> str:
    """La valeur telle qu'on la lit : montants à la française, dates jj/mm/aaaa.

    Excel rend 2 500,00 comme l'entier 2500 : `decimales` (colonne de montants)
    remet les centimes."""
    if valeur is None:
        return ""
    if isinstance(valeur, bool):
        return "Oui" if valeur else "Non"
    if isinstance(valeur, (int, float, Decimal)):
        nombre = float(valeur)
        if nombre.is_integer() and not decimales:
            return f"{int(nombre):,}".replace(",", " ")
        return f"{nombre:,.2f}".replace(",", " ").replace(".", ",")
    if isinstance(valeur, datetime):
        return valeur.strftime("%d/%m/%Y")
    if isinstance(valeur, date):
        return valeur.strftime("%d/%m/%Y")
    return str(valeur)


def _est_un_nombre(valeur: Any) -> bool:
    return isinstance(valeur, (int, float, Decimal)) and not isinstance(valeur, bool)


def _lignes_de_la_feuille(feuille) -> List[List[Any]]:
    lignes = [list(r) for r in feuille.iter_rows(values_only=True)]
    lignes = [r for r in lignes if any(v not in (None, "") for v in r)]
    if not lignes:
        return []
    largeur = max(
        (max((i for i, v in enumerate(r) if v not in (None, "")), default=-1) + 1 for r in lignes),
        default=0,
    )
    return [(r + [None] * largeur)[:largeur] for r in lignes]


def _largeurs(textes: List[List[str]], nombres: List[List[bool]], taille: float) -> List[float]:
    """Une colonne de montants a la largeur de son plus long montant (jamais coupé) ;
    le reste de la page va aux colonnes de texte, au prorata de leur texte.

    Les lignes à une seule case (titre, adresse) ne comptent pas : elles débordent."""
    nb = len(textes[0])
    utiles = [i for i, r in enumerate(textes) if sum(1 for t in r if t) >= 2] or list(range(len(textes)))
    besoin = [0.0] * nb
    souple = [0.0] * nb
    for i in utiles:
        for j, texte in enumerate(textes[i]):
            largeur = stringWidth(texte, "Helvetica", taille) + 6
            if nombres[i][j]:
                besoin[j] = max(besoin[j], largeur)
            else:
                souple[j] = max(souple[j], min(largeur, 60 * taille))
    for j in range(nb):
        besoin[j] = max(besoin[j], 14.0)
    reste = LARGEUR_UTILE - sum(besoin)
    total_souple = sum(souple)
    if reste <= 0 or not total_souple:
        echelle = LARGEUR_UTILE / sum(b + s for b, s in zip(besoin, souple))
        return [(b + s) * echelle for b, s in zip(besoin, souple)]
    return [b + reste * s / total_souple for b, s in zip(besoin, souple)]


def _tableau(lignes: List[List[Any]]) -> LongTable:
    nb_colonnes = len(lignes[0])
    taille = 8 if nb_colonnes <= 8 else 7 if nb_colonnes <= 12 else 6
    style = ParagraphStyle("cellule", fontName="Helvetica", fontSize=taille, leading=taille + 2)
    style_droite = ParagraphStyle("cellule_droite", parent=style, alignment=2)
    style_entete = ParagraphStyle("entete", parent=style, fontName="Helvetica-Bold", textColor=colors.white)

    # Une colonne de montants : au moins un nombre à centimes.
    a_centimes = [
        any(_est_un_nombre(r[i]) and not float(r[i]).is_integer() for r in lignes[1:])
        for i in range(nb_colonnes)
    ]
    textes = [
        [texte_de_cellule(v, a_centimes[j] and k > 0) for j, v in enumerate(ligne)]
        for k, ligne in enumerate(lignes)
    ]
    nombres = [[k > 0 and _est_un_nombre(v) for v in ligne] for k, ligne in enumerate(lignes)]
    largeurs = _largeurs(textes, nombres, taille)

    # Paragraph lit du balisage : « Péage A1<A6 » le faisait planter.
    textes = [[escape(t) for t in ligne] for ligne in textes]
    donnees = [[Paragraph(t, style_entete) for t in textes[0]]]
    for k in range(1, len(lignes)):
        donnees.append(
            [Paragraph(t, style_droite if nombres[k][j] else style) for j, t in enumerate(textes[k])]
        )
    # Ligne de total (« SALAIRE BRUT », « NET A PAYER ») : son libellé en capitales.
    style_total = ParagraphStyle("total", parent=style, fontName="Helvetica-Bold")
    style_total_droite = ParagraphStyle("total_droite", parent=style_total, alignment=2)
    for k in range(1, len(lignes)):
        libelle = next((t for j, t in enumerate(textes[k]) if t and not nombres[k][j]), "")
        # « SALAIRE BRUT », « NET A PAYER » : capitales et plusieurs mots (« URSSAF » seul n'est pas un total).
        if " " in libelle.strip() and libelle.isupper():
            donnees[k] = [
                Paragraph(t, style_total_droite if nombres[k][j] else style_total) for j, t in enumerate(textes[k])
            ]
    tableau = LongTable(donnees, colWidths=largeurs, repeatRows=1)
    tableau.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#366092")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B0B7C3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F5F8")]),
            ]
        )
    )
    return tableau


def xlsx_en_pdf(contenu_xlsx: bytes, titre: str) -> bytes:
    """Le classeur, feuille par feuille, en PDF paysage."""
    classeur = load_workbook(io.BytesIO(contenu_xlsx), data_only=True, read_only=True)
    styles = getSampleStyleSheet()
    elements: list = []
    plusieurs = len(classeur.sheetnames) > 1
    for index, nom in enumerate(classeur.sheetnames):
        lignes = _lignes_de_la_feuille(classeur[nom])
        if index:
            elements.append(PageBreak())
        elements.append(Paragraph(f"{titre} — {nom}" if plusieurs else titre, styles["Heading2"]))
        elements.append(Spacer(1, 4 * mm))
        if lignes:
            elements.append(_tableau(lignes))
        else:
            elements.append(Paragraph("Aucune ligne.", styles["Normal"]))
    sortie = io.BytesIO()
    SimpleDocTemplate(
        sortie,
        pagesize=landscape(A4),
        leftMargin=MARGE,
        rightMargin=MARGE,
        topMargin=MARGE,
        bottomMargin=MARGE,
        title=titre,
    ).build(elements)
    return sortie.getvalue()


def nom_de_la_societe(company_id: str) -> str:
    """Nom de la société (lecture seule) ; vide si introuvable.

    Un titre incomplet ne doit jamais faire échouer l'export."""
    try:
        from app.core.database import supabase

        reponse = (
            supabase.table("companies").select("company_name").eq("id", company_id).limit(1).execute()
        )
        lignes = reponse.data or []
        return str((lignes[0] if lignes else {}).get("company_name") or "").strip()
    except Exception:
        return ""


def titre_du_pdf(titre: str, societe: str = "", periode: str = "") -> str:
    """« Journal de paie — Société — Octobre 2026 » : un groupe a plusieurs
    sociétés, le PDF imprimé dit de laquelle il parle (Elsa, 20/11)."""
    return " — ".join(p for p in (titre, societe.strip(), periode.strip()) if p)


def pdf_depuis_le_classeur(titre: str):
    """Décorateur d'un générateur d'export : `format="pdf"` → son Excel, mis en PDF.

    Le générateur garde ses deux formats (csv, xlsx) ; il reçoit « xlsx » quand
    le PDF est demandé. Le paramètre s'appelle `format` ou `file_format`.
    Le titre porte le nom de la société (`company_id`) et le mois (`period`)
    quand le générateur les reçoit.
    """
    import functools
    import inspect

    from app.shared.utils.export import format_period

    def decorer(generateur):
        signature = inspect.signature(generateur)
        nom = "format" if "format" in signature.parameters else "file_format"

        @functools.wraps(generateur)
        def generer(*args, **kwargs):
            arguments = signature.bind(*args, **kwargs)
            if arguments.arguments.get(nom) != "pdf":
                return generateur(*args, **kwargs)
            arguments.arguments[nom] = "xlsx"
            company_id = arguments.arguments.get("company_id")
            period = arguments.arguments.get("period")
            titre_complet = titre_du_pdf(
                titre,
                nom_de_la_societe(company_id) if company_id else "",
                format_period(period) if isinstance(period, str) and period else "",
            )
            return xlsx_en_pdf(generateur(*arguments.args, **arguments.kwargs), titre_complet)

        return generer

    return decorer
