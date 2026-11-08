"""
Attestations remises à la demande du salarié.

Deux lettres :

- l'attestation d'emploi suit le modèle envoyé par la cliente le 06/11/2026
  (« Attestation_emploi », société LEWIS), rien de plus : en-tête (logo,
  adresse, SIRET, code NAF), cinq lignes (nom et prénom, n° de sécurité sociale,
  adresse, emploi occupé, reprise d'ancienneté), la phrase de présence, la
  formule finale, le lieu et la date, le signataire et la mention du pied de
  page, reprise telle quelle ;
- l'attestation de salaire reprend les bulletins remis : la commande de
  génération prépare `mois_de_paie` (documents.domain.attestation_salaire).

Le générateur ne lit pas la base. Rien n'est inventé : une ligne de l'attestation
d'emploi absente de la fiche est dite (« Non renseigné sur la fiche salarié ») ;
ce qui se complète à la main (lieu, signataire) garde des pointillés. Aucun
accord entre parenthèses : la civilité vient de la fiche (sexe), sinon la phrase
reste neutre.
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.modules.documents.domain.attestation_salaire import total
from app.shared.domain.temps_local import aujourd_hui_local
from app.shared.seniority_reference import resolve_seniority_reference_date
from app.shared.infrastructure.pdf.helpers import (
    build_branding_header_reportlab,
    format_date,
    get_company_address,
    get_company_city,
    get_company_name,
    resolve_company_logo,
    setup_custom_styles,
)

A_COMPLETER = "…" * 10

TITRES = {
    "attestation_emploi": "ATTESTATION D'EMPLOI",
    "attestation_salaire": "Attestation de salaire",
}

_MOIS = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]

NON_RENSEIGNE = "Non renseigné sur la fiche salarié"
NON_RENSEIGNEE = "Non renseignée sur la fiche salarié"

# Pied de page du modèle de la cliente, repris mot pour mot.
MENTION_DU_MODELE = (
    "La présente attestation a été établie conformément à l'article L1221-10 du Code du travail."
)

GROUPES_NIR = (1, 2, 2, 2, 3, 3, 2)

_BLEU = colors.HexColor("#1f3a8a")
_GRIS = colors.HexColor("#64748b")
_TRAIT = colors.HexColor("#cbd5e1")
_ENCRE = colors.HexColor("#1e293b")


def _texte(valeur: Any) -> str:
    return "" if valeur is None else str(valeur).strip()


def _ou_a_completer(valeur: str) -> str:
    """Texte prêt pour ReportLab (balisage échappé), ou des pointillés."""
    return escape(valeur) if valeur else A_COMPLETER


def _date(valeur: Any) -> Optional[date]:
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    if isinstance(valeur, str) and valeur.strip():
        try:
            return date.fromisoformat(valeur.strip()[:10])
        except ValueError:
            return None
    return None


def date_fr(jour: date) -> str:
    """« 1er août 2025 », « 5 novembre 2026 »."""
    texte = format_date(jour)
    return "1er" + texte[1:] if jour.day == 1 else texte


def _date_longue(valeur: Any) -> str:
    jour = _date(valeur)
    return date_fr(jour) if jour else ""


def euros(montant: Optional[float]) -> str:
    """« 2 200,00 € » ; un tiret quand le montant est inconnu."""
    if montant is None:
        return "—"
    entier, decimales = f"{abs(montant):.2f}".split(".")
    signe = "-" if montant < 0 else ""
    return f"{signe}{int(entier):,}".replace(",", " ") + f",{decimales} €"


def civilite(employee: Mapping[str, Any]) -> str:
    return {"F": "Madame", "M": "Monsieur"}.get(_texte(employee.get("sexe")).upper(), "")


def nom_complet(employee: Mapping[str, Any]) -> str:
    parties = (
        civilite(employee),
        _texte(employee.get("first_name")),
        _texte(employee.get("last_name")),
    )
    return " ".join(p for p in parties if p)


def adresse_du_salarie(employee: Mapping[str, Any]) -> str:
    adresse = employee.get("adresse")
    if isinstance(adresse, str):
        return adresse.strip()
    if not isinstance(adresse, Mapping):
        return ""
    numero, rue = _texte(adresse.get("numero")), _texte(adresse.get("rue"))
    rue = re.sub(r"^(\d+\w*)\s+\1\b", r"\1", rue)
    # La rue porte souvent déjà son numéro (les 271 fiches du test au 05/11).
    if numero and not re.match(rf"{re.escape(numero)}\b", rue):
        rue = f"{numero} {rue}".strip()
    ville = " ".join(
        p for p in (_texte(adresse.get("code_postal")), _texte(adresse.get("ville"))) if p
    )
    return ", ".join(p for p in (rue, _texte(adresse.get("complement")), ville) if p)


def signataire(company: Mapping[str, Any]) -> Tuple[str, str]:
    """Nom et fonction réglés dans Entreprise > Fiche ; vides s'ils ne le sont pas."""
    nom = _texte(company.get("nom_signataire_rh") or company.get("signatory_name"))
    fonction = _texte(company.get("qualite_signataire_rh") or company.get("signatory_title"))
    return nom, fonction


def _jj_mm_aaaa(jour: date) -> str:
    return jour.strftime("%d/%m/%Y")


def _feminin(employee: Mapping[str, Any]) -> Optional[bool]:
    """True pour F, False pour M, None si la fiche ne le dit pas."""
    return {"F": True, "M": False}.get(_texte(employee.get("sexe")).upper())


def nom_du_modele(employee: Mapping[str, Any]) -> str:
    """« M. Prénom NOM », « Mme Prénom NOM », sans civilité si la fiche n'a pas le sexe."""
    prenom = _texte(employee.get("first_name"))
    nom = _texte(employee.get("last_name")).upper()
    if not (prenom or nom):
        return ""
    civ = {True: "Mme", False: "M."}.get(_feminin(employee), "")
    return " ".join(p for p in (civ, prenom, nom) if p)


def nir_du_modele(valeur: Any) -> str:
    """« 1 76 09 99 352 859 29 » : les groupes du modèle (et du bulletin) ; tel quel sinon."""
    brut = "".join(c for c in _texte(valeur) if c.isalnum()).upper()
    if len(brut) != sum(GROUPES_NIR):
        return brut
    morceaux, position = [], 0
    for taille in GROUPES_NIR:
        morceaux.append(brut[position : position + taille])
        position += taille
    return " ".join(morceaux)


def siret_du_modele(valeur: Any) -> str:
    """« 991 177 304 00029 » ; tel quel s'il n'a pas 14 chiffres."""
    brut = "".join(c for c in _texte(valeur) if c.isdigit())
    if len(brut) != 14:
        return _texte(valeur)
    return f"{brut[:3]} {brut[3:6]} {brut[6:9]} {brut[9:]}"


def reprise_d_anciennete(employee: Mapping[str, Any]) -> Optional[date]:
    """La date de la fiche, ou celle de la reprise DSN à défaut (même source que le bulletin)."""
    return _date(resolve_seniority_reference_date(dict(employee)))


def lignes_du_modele(employee: Mapping[str, Any]) -> List[Tuple[str, str]]:
    """Les cinq lignes du modèle, dans son ordre ; une ligne absente de la fiche est dite."""
    reprise = reprise_d_anciennete(employee)
    return [
        ("Nom et prénom", nom_du_modele(employee) or NON_RENSEIGNE),
        ("N° de sécurité sociale", nir_du_modele(employee.get("nir")) or NON_RENSEIGNE),
        ("Adresse", adresse_du_salarie(employee) or NON_RENSEIGNEE),
        ("Emploi occupé", _texte(employee.get("job_title")) or NON_RENSEIGNE),
        ("Reprise d'ancienneté", _jj_mm_aaaa(reprise) if reprise else NON_RENSEIGNEE),
    ]


def phrase_de_presence(employee: Mapping[str, Any], jour: date) -> str:
    """La phrase du modèle, accordée selon la fiche ; neutre si la fiche n'a pas le sexe."""
    feminin = _feminin(employee)
    entree = _date(employee.get("hire_date"))
    if entree and entree > jour:
        if feminin is None:
            return f"rejoindra notre entreprise le {_jj_mm_aaaa(entree)}."
        employe = "employée" if feminin else "employé"
        return f"sera {employe} au sein de notre entreprise à compter du {_jj_mm_aaaa(entree)}."
    depuis = (
        f"le {_jj_mm_aaaa(entree)}"
        if entree
        else "le (date d'entrée non renseignée sur la fiche salarié)"
    )
    debut = (
        "travaille"
        if feminin is None
        else ("est employée" if feminin else "est employé")
    )
    return (
        f"{debut} au sein de notre entreprise depuis {depuis} et fait toujours partie "
        "de nos effectifs à la date de la présente attestation."
    )


def _a_l_interesse(employee: Mapping[str, Any]) -> str:
    return {True: "à l'intéressée", False: "à l'intéressé"}.get(
        _feminin(employee), "à la personne intéressée"
    )


def code_naf(company: Mapping[str, Any]) -> str:
    for cle in ("code_naf", "naf_ape", "naf_code", "ape_code", "naf"):
        valeur = _texte(company.get(cle))
        if valeur:
            return valeur
    return ""


def _en_tete_du_modele(company: Mapping[str, Any], styles) -> Table:
    """Logo à gauche ; adresse, SIRET et code NAF à droite ; un trait dessous."""
    gauche: Any = Paragraph(f"<b>{escape(get_company_name(company))}</b>", styles["AttCorps"])
    logo = resolve_company_logo(dict(company))
    if logo:
        try:
            gauche = Image(io.BytesIO(logo), width=4.5 * cm, height=1.6 * cm, kind="proportional")
        except Exception:  # un logo illisible laisse le nom de la société
            pass
    adresse = get_company_address(company)
    siret = siret_du_modele(company.get("siret"))
    naf = code_naf(company)
    droite = Paragraph(
        "<br/>".join(
            (
                escape(adresse) if adresse else "Adresse : non renseignée",
                f"SIRET : {escape(siret) if siret else 'non renseigné'}",
                f"Code NAF : {escape(naf) if naf else 'non renseigné'}",
            )
        ),
        styles["EmpEnTete"],
    )
    tableau = Table([[gauche, droite]], colWidths=[7 * cm, 10 * cm])
    tableau.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, _TRAIT),
            ]
        )
    )
    return tableau


def _signature_du_modele(company: Mapping[str, Any], styles) -> Table:
    """« Nom, qualité et signature de l'employeur », le signataire, un cadre pour signer."""
    nom, qualite = signataire(company)
    lignes: List[List[Any]] = [
        [Paragraph("Nom, qualité et signature de l'employeur", styles["EmpPetit"])]
    ]
    if nom:
        lignes.append([Paragraph(escape(nom), styles["AttCorps"])])
        lignes.append([Paragraph(escape(qualite) if qualite else A_COMPLETER, styles["AttCorps"])])
    else:
        lignes.append([Paragraph(A_COMPLETER, styles["AttCorps"])])
    lignes.append([""])
    tableau = Table(lignes, colWidths=[7.5 * cm], rowHeights=[None] * (len(lignes) - 1) + [2.5 * cm])
    tableau.hAlign = "RIGHT"
    tableau.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("BOX", (0, -1), (-1, -1), 0.6, _GRIS, None, (2, 2)),
            ]
        )
    )
    return tableau


def _pied_du_modele(canvas, document) -> None:
    canvas.saveState()
    largeur, _ = A4
    canvas.setStrokeColor(_TRAIT)
    canvas.setLineWidth(0.5)
    canvas.line(2 * cm, 1.9 * cm, largeur - 2 * cm, 1.9 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(_GRIS)
    canvas.drawCentredString(largeur / 2, 1.4 * cm, MENTION_DU_MODELE)
    canvas.restoreState()


class CommonAttestationGenerator:
    """Les deux lettres Martine (ReportLab)."""

    ATTESTATION_TYPES: List[str] = ["attestation_emploi", "attestation_salaire"]

    def generate(
        self,
        attestation_type: str,
        employee: Dict[str, Any],
        company: Dict[str, Any],
        context: Dict[str, Any] | None = None,
    ) -> bytes:
        if attestation_type not in self.ATTESTATION_TYPES:
            raise ValueError(f"Type d'attestation non pris en charge : {attestation_type}")
        ctx = context or {}
        jour = _date(ctx.get("date_generation")) or aujourd_hui_local()
        styles = _styles()
        story: List[Any] = []
        pied = None
        if attestation_type == "attestation_emploi":
            self._lettre_emploi(story, styles, employee, company, jour)
            pied = _pied_du_modele
        else:
            build_branding_header_reportlab(story, styles, company)
            story.append(Paragraph(TITRES[attestation_type], styles["AttTitre"]))
            story.append(Spacer(1, 0.4 * cm))
            self._corps_salaire(story, styles, employee, company, ctx)
            self._cloture(story, styles, company, jour)
        tampon = io.BytesIO()
        document = SimpleDocTemplate(
            tampon,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        if pied:
            document.build(story, onFirstPage=pied, onLaterPages=pied)
        else:
            document.build(story)
        return tampon.getvalue()

    @staticmethod
    def _ouverture(company: Mapping[str, Any]) -> str:
        nom, fonction = signataire(company)
        qui = escape(", ".join(p for p in (nom, fonction) if p)) if nom else A_COMPLETER
        return (
            f"<b>{qui}</b>, agissant pour le compte de la société "
            f"<b>{_ou_a_completer(get_company_name(company))}</b>, dont le siège est situé "
            f"{_ou_a_completer(get_company_address(company))}, immatriculée sous le numéro "
            f"SIRET {_ou_a_completer(_texte(company.get('siret')))}, atteste que"
        )

    # --- Attestation d'emploi : le modèle de la cliente (06/11/2026) -------------

    def _lettre_emploi(self, story, styles, employee, company, jour: date) -> None:
        story.append(_en_tete_du_modele(company, styles))
        story.append(Spacer(1, 1.2 * cm))
        story.append(Paragraph(TITRES["attestation_emploi"], styles["EmpTitre"]))
        story.append(
            HRFlowable(width=3.5 * cm, thickness=1, color=_BLEU, hAlign="CENTER", spaceBefore=2)
        )
        story.append(Spacer(1, 1 * cm))
        societe = escape(get_company_name(company))
        story.append(
            Paragraph(f"Nous soussignés, la société {societe}, certifions que :", styles["AttCorps"])
        )
        story.append(Spacer(1, 0.3 * cm))
        tableau = Table(
            [
                [Paragraph(escape(libelle), styles["EmpLibelle"]),
                 Paragraph(escape(valeur), styles["AttCorps"])]
                for libelle, valeur in lignes_du_modele(employee)
            ],
            colWidths=[5 * cm, 12 * cm],
        )
        tableau.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, _TRAIT),
                ]
            )
        )
        story.append(tableau)
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(escape(phrase_de_presence(employee, jour)), styles["AttCorps"]))
        story.append(Spacer(1, 0.3 * cm))
        story.append(
            Paragraph(
                f"Cette attestation est délivrée {_a_l_interesse(employee)} pour servir et "
                "valoir ce que de droit.",
                styles["AttCorps"],
            )
        )
        story.append(Spacer(1, 1 * cm))
        lieu = _ou_a_completer(get_company_city(company))
        story.append(Paragraph(f"Fait à {lieu}, le {_jj_mm_aaaa(jour)}", styles["AttDroite"]))
        story.append(Spacer(1, 0.8 * cm))
        story.append(_signature_du_modele(company, styles))

    def _corps_salaire(self, story, styles, employee, company, ctx) -> None:
        mois = list(ctx.get("mois_de_paie") or [])
        if not mois:
            raise ValueError("Aucun mois de paie à attester.")
        periode = (
            "son dernier mois de paie" if len(mois) == 1 else f"ses {len(mois)} derniers mois de paie"
        )
        emploi = _ou_a_completer(_texte(employee.get("job_title")))
        entree = _ou_a_completer(_date_longue(employee.get("hire_date")))
        sortie = _date_longue(ctx.get("date_de_sortie"))
        if not ctx.get("a_quitte"):
            poste = f"qui occupe l'emploi « {emploi} » depuis le {entree}"
        elif sortie:
            poste = f"qui a occupé l'emploi « {emploi} » du {entree} au {sortie}"
        else:
            poste = f"qui a occupé l'emploi « {emploi} » à partir du {entree}"
        story.append(
            Paragraph(
                f"{self._ouverture(company)} <b>{_ou_a_completer(nom_complet(employee))}</b>, "
                f"{poste}, a perçu les rémunérations suivantes au cours de {periode} :",
                styles["AttCorps"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))
        donnees = [["Mois", "Salaire brut", "Net à payer avant impôt sur le revenu"]]
        for ligne in mois:
            donnees.append(
                [
                    f"{_MOIS[int(ligne['month']) - 1]} {int(ligne['year'])}",
                    euros(ligne.get("brut")),
                    euros(ligne.get("net_avant_impot")),
                ]
            )
        donnees.append(["Total", euros(total(mois, "brut")), euros(total(mois, "net_avant_impot"))])
        tableau = Table(donnees, colWidths=[4.5 * cm, 4.5 * cm, 7.5 * cm])
        tableau.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#94a3b8")),
                    ("LINEABOVE", (0, -1), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(tableau)
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("Montants repris de ses bulletins de paie.", styles["AttPetit"]))

    @staticmethod
    def _cloture(story, styles, company, jour: date) -> None:
        story.append(Spacer(1, 0.6 * cm))
        story.append(
            Paragraph(
                "La présente attestation lui est délivrée à sa demande, pour servir et "
                "valoir ce que de droit.",
                styles["AttCorps"],
            )
        )
        story.append(Spacer(1, 0.6 * cm))
        lieu = _ou_a_completer(get_company_city(company))
        story.append(Paragraph(f"Fait à {lieu}, le {date_fr(jour)}.", styles["AttDroite"]))
        story.append(Spacer(1, 1.2 * cm))
        nom, fonction = signataire(company)
        if nom:
            bloc = f"<b>{escape(nom)}</b>" + (f"<br/>{escape(fonction)}" if fonction else "")
        else:
            bloc = f"Nom et fonction du signataire : {A_COMPLETER}"
        story.append(Paragraph(bloc, styles["AttDroite"]))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph("<i>Signature et cachet de l'employeur</i>", styles["AttDroite"]))


def _styles():
    styles = setup_custom_styles(getSampleStyleSheet())
    styles.add(
        ParagraphStyle(
            name="AttTitre",
            parent=styles["Heading1"],
            fontSize=15,
            alignment=TA_CENTER,
            spaceAfter=12,
            textColor=colors.HexColor("#1e293b"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="AttCorps",
            parent=styles["Normal"],
            fontSize=11,
            leading=16,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#1e293b"),
        )
    )
    styles.add(ParagraphStyle(name="AttDroite", parent=styles["AttCorps"], alignment=TA_RIGHT))
    styles.add(
        ParagraphStyle(
            name="EmpTitre",
            parent=styles["AttCorps"],
            fontSize=17,
            leading=22,
            alignment=TA_CENTER,
            textColor=_BLEU,
        )
    )
    styles.add(ParagraphStyle(name="EmpLibelle", parent=styles["AttCorps"], textColor=_GRIS))
    styles.add(
        ParagraphStyle(
            name="EmpEnTete",
            parent=styles["AttCorps"],
            fontSize=9,
            leading=13,
            alignment=TA_RIGHT,
            textColor=_GRIS,
        )
    )
    styles.add(ParagraphStyle(name="EmpPetit", parent=styles["AttCorps"], fontSize=9, textColor=_GRIS))
    styles.add(
        ParagraphStyle(
            name="AttPetit",
            parent=styles["AttCorps"],
            fontSize=9,
            textColor=colors.HexColor("#64748b"),
        )
    )
    return styles


common_attestation_generator = CommonAttestationGenerator()
