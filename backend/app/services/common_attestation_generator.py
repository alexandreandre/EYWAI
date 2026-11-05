"""
Attestations remises à la demande du salarié (modèle Martine, sans modèle client).

Deux lettres (décision du 05/11/2026) :

- l'attestation de travail suit le « Modèle de lettre - Attestation d'emploi »
  du ministère du Travail (https://code.travail.gouv.fr/modeles-de-courriers/attestation-de-travail,
  mis à jour le 05/06/2023), plus la rémunération et la période d'essai que le
  décret n° 2015-1437 demande pour un bailleur (service-public F1169) ;
- l'attestation de salaire reprend les bulletins remis : la commande de
  génération prépare `mois_de_paie` (documents.domain.attestation_salaire).

Le générateur ne lit pas la base. Une donnée absente laisse des pointillés à
compléter à la main : rien n'est inventé. Aucun accord entre parenthèses : la
civilité vient de la fiche (sexe), sinon la phrase reste neutre.
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
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.documents.domain.attestation_salaire import total
from app.shared.domain.pluriel import pluriel
from app.shared.domain.temps_local import aujourd_hui_local
from app.shared.infrastructure.pdf.helpers import (
    build_branding_header_reportlab,
    format_date,
    get_company_address,
    get_company_city,
    get_company_name,
    setup_custom_styles,
)

A_COMPLETER = "…" * 10

TITRES = {
    "attestation_emploi": "Attestation de travail",
    "attestation_salaire": "Attestation de salaire",
}

_MOIS = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]

_CONTRATS = {
    "cdd": "Contrat à durée déterminée (CDD)",
    "apprentissage": "Contrat d'apprentissage",
    "professionnalisation": "Contrat de professionnalisation",
    "alternance": "Contrat d'alternance",
    "stage": "Convention de stage",
}


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


def anciennete(debut: Optional[date], jour: date) -> str:
    """« 1 an et 3 mois », « 8 mois », « 3 ans » ; vide si l'entrée est inconnue."""
    if not debut or debut > jour:
        return ""
    mois = (jour.year - debut.year) * 12 + (jour.month - debut.month)
    if jour.day < debut.day:
        mois -= 1
    ans, reste = divmod(max(mois, 0), 12)
    parties = []
    if ans:
        parties.append(pluriel(ans, "an"))
    if reste or not ans:
        parties.append(f"{reste} mois")
    return " et ".join(parties)


def nature_du_contrat(employee: Mapping[str, Any]) -> str:
    brut = _texte(employee.get("contract_type"))
    cle = brut.lower()
    if cle == "cdi":
        return "Contrat à durée indéterminée (CDI)"
    libelle = _CONTRATS.get(cle)
    if not libelle:
        return brut
    fin = _date_longue(employee.get("contract_end_date"))
    return f"{libelle} jusqu'au {fin}" if fin else libelle


def naissance(employee: Mapping[str, Any]) -> str:
    le = _date_longue(employee.get("date_naissance"))
    lieu = _texte(employee.get("lieu_naissance"))
    if not le:
        return ""
    return f"{le} à {lieu}" if lieu else le


def adresse_du_salarie(employee: Mapping[str, Any]) -> str:
    adresse = employee.get("adresse")
    if isinstance(adresse, str):
        return adresse.strip()
    if not isinstance(adresse, Mapping):
        return ""
    numero, rue = _texte(adresse.get("numero")), _texte(adresse.get("rue"))
    # La rue porte souvent déjà son numéro (les 271 fiches du test au 05/11).
    if numero and not re.match(rf"{re.escape(numero)}\b", rue):
        rue = f"{numero} {rue}".strip()
    ville = " ".join(
        p for p in (_texte(adresse.get("code_postal")), _texte(adresse.get("ville"))) if p
    )
    return ", ".join(p for p in (rue, _texte(adresse.get("complement")), ville) if p)


def remuneration_mensuelle(employee: Mapping[str, Any]) -> str:
    salaire = employee.get("salaire_de_base")
    valeur = salaire.get("valeur") if isinstance(salaire, Mapping) else salaire
    try:
        montant = float(str(valeur).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return ""
    return euros(montant) if montant > 0 else ""


def signataire(company: Mapping[str, Any]) -> Tuple[str, str]:
    """Nom et fonction réglés dans Entreprise > Fiche ; vides s'ils ne le sont pas."""
    nom = _texte(company.get("nom_signataire_rh") or company.get("signatory_name"))
    fonction = _texte(company.get("qualite_signataire_rh") or company.get("signatory_title"))
    return nom, fonction


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
        build_branding_header_reportlab(story, styles, company)
        story.append(Paragraph(TITRES[attestation_type], styles["AttTitre"]))
        story.append(Spacer(1, 0.4 * cm))
        if attestation_type == "attestation_emploi":
            self._corps_travail(story, styles, employee, company, ctx, jour)
        else:
            self._corps_salaire(story, styles, employee, company, ctx)
        self._cloture(story, styles, company, jour)
        tampon = io.BytesIO()
        SimpleDocTemplate(
            tampon,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        ).build(story)
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

    def _corps_travail(self, story, styles, employee, company, ctx, jour: date) -> None:
        story.append(Paragraph(self._ouverture(company) + " :", styles["AttCorps"]))
        story.append(Spacer(1, 0.3 * cm))
        lignes = [
            ("Nom et prénom", nom_complet(employee)),
            ("Date et lieu de naissance", naissance(employee)),
            ("Adresse", adresse_du_salarie(employee)),
            ("Emploi occupé", _texte(employee.get("job_title"))),
            ("Nature du contrat", nature_du_contrat(employee)),
            ("Date d'entrée", _date_longue(employee.get("hire_date"))),
            ("Ancienneté", anciennete(_date(employee.get("hire_date")), jour)),
            ("Rémunération brute mensuelle", remuneration_mensuelle(employee)),
        ]
        fin_essai = _date_longue(ctx.get("periode_essai_fin"))
        if fin_essai:
            lignes.append(("Période d'essai", f"en cours jusqu'au {fin_essai}"))
        tableau = Table(
            [
                [Paragraph(f"<b>{escape(libelle)}</b>", styles["AttCorps"]),
                 Paragraph(_ou_a_completer(valeur), styles["AttCorps"])]
                for libelle, valeur in lignes
            ],
            colWidths=[5.5 * cm, 11 * cm],
        )
        tableau.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(tableau)
        story.append(Spacer(1, 0.5 * cm))
        story.append(
            Paragraph(
                f"<b>{_ou_a_completer(nom_complet(employee))}</b> fait toujours partie de nos "
                f"effectifs à la date du {date_fr(jour)}.",
                styles["AttCorps"],
            )
        )

    def _corps_salaire(self, story, styles, employee, company, ctx) -> None:
        mois = list(ctx.get("mois_de_paie") or [])
        if not mois:
            raise ValueError("Aucun mois de paie à attester.")
        periode = (
            "son dernier mois de paie" if len(mois) == 1 else f"ses {len(mois)} derniers mois de paie"
        )
        story.append(
            Paragraph(
                f"{self._ouverture(company)} <b>{_ou_a_completer(nom_complet(employee))}</b>, "
                f"qui occupe l'emploi « {_ou_a_completer(_texte(employee.get('job_title')))} » "
                f"depuis le {_ou_a_completer(_date_longue(employee.get('hire_date')))}, a perçu "
                f"les rémunérations suivantes au cours de {periode} :",
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
            name="AttPetit",
            parent=styles["AttCorps"],
            fontSize=9,
            textColor=colors.HexColor("#64748b"),
        )
    )
    return styles


common_attestation_generator = CommonAttestationGenerator()
