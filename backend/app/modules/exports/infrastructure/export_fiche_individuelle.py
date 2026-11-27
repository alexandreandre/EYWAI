"""Fiche individuelle d'un salarié en Excel (lot L18, 27/11/2026).

Lit la fiche du salarié et ses bulletins enregistrés, construit la fiche
(`fiche_individuelle.construire_fiche`) et l'écrit dans un classeur : identité,
tableau des cumuls mois par mois, salaire de référence de l'indemnité de départ
et notes (mois non payés dans Martine).
"""

from __future__ import annotations

import io
import re
import unicodedata
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.core.database import supabase
from app.modules.exports.infrastructure.fiche_individuelle import (
    MOIS_BROUILLON,
    MOIS_NON_PAYE,
    construire_fiche,
    libelle_court,
    libelle_long,
    lire_periode,
)

_ENTETE = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
_SECTION = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
_NON_PAYE = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
_BROUILLON = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
_EUROS = '#,##0.00'
_TOTAUX = {"SALAIRE BRUT", "NET IMPOSABLE", "NET A PAYER"}
_HEURES = {"Heures du salaire de base", "Heures supplémentaires"}


def _date_fr(valeur: Any) -> str:
    try:
        return date.fromisoformat(str(valeur)[:10]).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return "non renseignée"


def _euros(valeur: Optional[float]) -> str:
    if valeur is None:
        return "—"
    return f"{valeur:,.2f} €".replace(",", " ").replace(".", ",")


def nom_complet(employe: Dict[str, Any]) -> str:
    prenom = str(employe.get("first_name") or "").strip()
    nom = str(employe.get("last_name") or "").strip().upper()
    return f"{prenom} {nom}".strip() or "Salarié"


def nom_du_fichier(employe: Dict[str, Any], debut: Tuple[int, int], fin: Tuple[int, int]) -> str:
    ascii_ = unicodedata.normalize("NFKD", nom_complet(employe)).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9]+", "-", ascii_).strip("-") or "salarie"
    return f"fiche-individuelle-{base}-{debut[0]}-{debut[1]:02d}-{fin[0]}-{fin[1]:02d}.xlsx"


def fiche_en_xlsx(fiche: Dict[str, Any]) -> bytes:
    employe = fiche["employe"]
    mois = fiche["mois"]
    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Fiche individuelle"
    gras = Font(bold=True)

    feuille.cell(row=1, column=1, value=f"Fiche individuelle — {nom_complet(employe)}").font = Font(bold=True, size=14)
    identite = [
        ("Matricule", employe.get("matricule") or "non renseigné"),
        ("Date d'entrée", _date_fr(employe.get("hire_date"))),
        ("Emploi", employe.get("job_title") or "non renseigné"),
        ("Statut", employe.get("statut") or "non renseigné"),
        ("Contrat", employe.get("contract_type") or "non renseigné"),
        ("Période", f"de {libelle_long(fiche['debut'])} à {libelle_long(fiche['fin'])}"),
    ]
    ligne = 2
    for libelle, valeur in identite:
        feuille.cell(row=ligne, column=1, value=libelle).font = gras
        feuille.cell(row=ligne, column=2, value=str(valeur))
        ligne += 1

    ligne += 1
    entetes = ["Rubrique", *(libelle_court(m) for m in mois), "Total"]
    for colonne, texte in enumerate(entetes, start=1):
        cellule = feuille.cell(row=ligne, column=colonne, value=texte)
        cellule.fill = _ENTETE
        cellule.font = Font(bold=True, color="FFFFFF")
        cellule.alignment = Alignment(horizontal="center")
    feuille.freeze_panes = feuille.cell(row=ligne + 1, column=2)
    ligne += 1

    section_precedente = None
    for donnees in fiche["lignes"]:
        if donnees["section"] != section_precedente and donnees["section"] in ("brut", "synthese"):
            titre = "Éléments du brut" if donnees["section"] == "brut" else "Synthèse du mois"
            cellule = feuille.cell(row=ligne, column=1, value=titre)
            cellule.font = gras
            for colonne in range(1, len(entetes) + 1):
                feuille.cell(row=ligne, column=colonne).fill = _SECTION
            ligne += 1
        section_precedente = donnees["section"]
        feuille.cell(row=ligne, column=1, value=donnees["libelle"]).font = (
            gras if donnees["libelle"] in _TOTAUX else Font()
        )
        for colonne, m in enumerate(mois, start=2):
            valeur = donnees["valeurs"].get(m)
            cellule = feuille.cell(row=ligne, column=colonne, value=valeur)
            if isinstance(valeur, float) and donnees["libelle"] not in _HEURES:
                cellule.number_format = _EUROS
            etat = str(fiche["lignes"][0]["valeurs"].get(m) or "")
            if etat == MOIS_NON_PAYE:
                cellule.fill = _NON_PAYE
            elif etat.startswith(MOIS_BROUILLON):
                cellule.fill = _BROUILLON
        total = feuille.cell(row=ligne, column=len(entetes), value=donnees["total"])
        total.font = gras
        if isinstance(donnees["total"], float) and donnees["libelle"] not in _HEURES:
            total.number_format = _EUROS
        ligne += 1

    reference = fiche["reference"]
    ligne += 1
    feuille.cell(
        row=ligne,
        column=1,
        value=(
            f"Salaire de référence de l'indemnité de départ, calculé sur les {fiche['mois_reference']}"
            if fiche.get("mois_reference")
            else "Salaire de référence de l'indemnité de départ : aucun bulletin dans Martine "
            f"jusqu'à {libelle_long(fiche['fin'])}"
        ),
    ).font = Font(bold=True, size=12)
    ligne += 1
    if reference.formule == "contrat":
        lignes_reference: List[Tuple[str, Any]] = [
            ("Salaire de référence retenu", reference.retenu),
            ("Calcul", reference.phrase()),
        ]
    else:
        lignes_reference = [
            (f"Moyenne des 12 derniers mois ({reference.mois_lus} bulletins lus)", reference.moyenne_douze_mois),
            ("Tiers des 3 derniers mois (primes annuelles à due proportion)", reference.tiers_trois_mois),
            ("Salaire de référence retenu (le plus favorable, C. trav. R1234-4)", reference.retenu),
        ]
    if reference.arret:
        lignes_reference.append(("Arrêt maladie", reference.arret))
    lignes_reference += [("À vérifier", alerte) for alerte in reference.alertes]
    lignes_reference += [("Note", note) for note in fiche.get("notes_reference", [])]
    for libelle, valeur in lignes_reference:
        feuille.cell(row=ligne, column=1, value=libelle).font = gras
        cellule = feuille.cell(row=ligne, column=2, value=valeur)
        if isinstance(valeur, float):
            cellule.number_format = _EUROS
        ligne += 1

    ligne += 1
    feuille.cell(row=ligne, column=1, value="Notes").font = gras
    ligne += 1
    for note in fiche["notes"]:
        feuille.cell(row=ligne, column=1, value=note)
        ligne += 1

    feuille.column_dimensions["A"].width = 58
    for colonne in range(2, len(entetes) + 1):
        feuille.column_dimensions[get_column_letter(colonne)].width = 14

    sortie = io.BytesIO()
    classeur.save(sortie)
    return sortie.getvalue()


_COLONNES_EMPLOYE = (
    "id, company_id, first_name, last_name, matricule, hire_date, job_title, statut, "
    "contract_type, salaire_de_base, duree_hebdomadaire, specificites_paie"
)


def generer_fiche_individuelle(
    company_id: str,
    employee_id: str,
    debut: Optional[str] = None,
    fin: Optional[str] = None,
    *,
    aujourd_hui: Optional[date] = None,
) -> Tuple[bytes, str]:
    """(contenu du classeur, nom du fichier). ValueError si le salarié n'est
    pas de la société ou si la période est illisible."""
    aujourd_hui = aujourd_hui or date.today()
    premier, dernier = lire_periode(debut, fin, aujourd_hui)
    employes = (
        supabase.table("employees")
        .select(_COLONNES_EMPLOYE)
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
        .data
    ) or []
    if not employes:
        raise ValueError("Salarié non trouvé dans cette société.")
    employe = employes[0]
    # Deux ans avant la fin : le salaire de référence remonte avant un arrêt.
    annee_min = min(premier[0], dernier[0] - 2)
    bulletins = (
        supabase.table("payslips")
        .select("year, month, status, origine, payslip_data")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .gte("year", annee_min)
        .lte("year", dernier[0])
        .execute()
        .data
    ) or []
    fiche = construire_fiche(employe, bulletins, premier, dernier, aujourd_hui=aujourd_hui)
    return fiche_en_xlsx(fiche), nom_du_fichier(employe, premier, dernier)
