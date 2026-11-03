"""Feuille « Tableau des charges » au format de Quadra (données : domain/tableau_des_charges)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet

from app.modules.exports.domain.tableau_des_charges import TableauDesCharges, construire_tableau

COLONNES = ("Code", "Libellé", "Base", "Taux", "Montant", "Taux", "Montant", "Taux", "Montant")
GROUPES = (("CHARGES TOTALES", 4, 5), ("CHARGES SALARIALES", 6, 7), ("CHARGES PATRONALES", 8, 9))
FORMAT_MONTANT = "#,##0.00;-#,##0.00;"
FORMAT_TAUX = "0.0000;-0.0000;"
GRIS = PatternFill(start_color="EDEDED", end_color="EDEDED", fill_type="solid")
TRAIT = Side(style="thin", color="999999")


def donnees_du_tableau(company_id: str, period: str, employee_ids: Optional[List[str]] = None) -> TableauDesCharges:
    """Les bulletins du mois, l'impôt à la source par taux et le sexe des salariés."""
    from app.core.database import supabase
    from app.modules.exports.infrastructure.export_ecritures_comptables import get_payslip_data_for_od

    bulletins, _ = get_payslip_data_for_od(company_id, period, employee_ids, "charges_sociales")
    ids = [b["payslip_id"] for b in bulletins if b.get("payslip_id")]
    pas: Dict[Any, Any] = {}
    if ids:
        for r in supabase.table("payslips").select("id, payslip_data").in_("id", ids).execute().data or []:
            synthese = (r.get("payslip_data") or {}).get("synthese_net") or {}
            pas[r["id"]] = synthese.get("impot_prelevement_a_la_source")
    salaries = [b["employee_id"] for b in bulletins if b.get("employee_id")]
    sexes: Dict[Any, Any] = {}
    if salaries:
        for r in supabase.table("employees").select("id, sexe").in_("id", salaries).execute().data or []:
            sexes[r["id"]] = r.get("sexe")
    return construire_tableau(
        {**b, "pas": pas.get(b.get("payslip_id")), "sexe": sexes.get(b.get("employee_id"))} for b in bulletins
    )


def ecrire_tableau_des_charges(
    ws: Worksheet,
    tableau: TableauDesCharges,
    period: str,
    societe: Optional[Dict[str, Any]] = None,
    maintenant: Optional[datetime] = None,
) -> None:
    societe = societe or {}
    maintenant = maintenant or datetime.now()
    annee, mois = period.split("-")
    gras = Font(bold=True)

    ws.cell(row=1, column=1, value=societe.get("company_name") or "").font = gras
    adresse = " ".join(str(v) for v in (societe.get("adresse_code_postal"), societe.get("adresse_ville")) if v)
    ws.cell(row=1, column=9, value=societe.get("adresse_rue") or "").alignment = Alignment(horizontal="right")
    ws.cell(row=2, column=9, value=adresse).alignment = Alignment(horizontal="right")
    ws.cell(row=2, column=1, value=f"Le : {maintenant:%d/%m/%Y à %H:%M}")
    ws.cell(row=3, column=1, value="Dossier tenu en euros")
    ws.cell(row=5, column=1, value=f"TABLEAU DES CHARGES DE {mois}/{annee[2:]} - En Euros").font = Font(bold=True, size=13)
    ws.merge_cells(start_row=5, start_column=1, end_row=5, end_column=9)
    ws.cell(row=5, column=1).alignment = Alignment(horizontal="center")
    ws.cell(row=6, column=1, value="Totaux Généraux").font = gras
    ws.merge_cells(start_row=6, start_column=1, end_row=6, end_column=9)
    ws.cell(row=6, column=1).alignment = Alignment(horizontal="center")

    for titre, debut, fin in GROUPES:
        ws.cell(row=8, column=debut, value=titre).font = gras
        ws.merge_cells(start_row=8, start_column=debut, end_row=8, end_column=fin)
        ws.cell(row=8, column=debut).alignment = Alignment(horizontal="center")
    for col, titre in enumerate(COLONNES, start=1):
        c = ws.cell(row=9, column=col, value=titre)
        c.font = gras
        c.alignment = Alignment(horizontal="center")
        c.border = Border(bottom=TRAIT)

    ligne = 10

    def _montants(row: int, valeurs: List[Any]) -> None:
        for col, valeur in zip(range(3, 10), valeurs):
            c = ws.cell(row=row, column=col, value=valeur)
            c.number_format = FORMAT_TAUX if col in (4, 6, 8) else FORMAT_MONTANT

    for section in tableau.sections:
        for l in section.lignes:
            ws.cell(row=ligne, column=1, value=l.code or None)
            ws.cell(row=ligne, column=2, value=l.libelle)
            _montants(ligne, [l.base or None, l.taux_total, l.montant_total, l.taux_salarial,
                              l.montant_salarial or None, l.taux_patronal, l.montant_patronal or None])
            ligne += 1
        ws.cell(row=ligne, column=1, value=f">>>> {section.libelle}").font = gras
        ws.merge_cells(start_row=ligne, start_column=1, end_row=ligne, end_column=3)
        _montants(ligne, [None, None, section.total, None, section.salarial or None, None, section.patronal or None])
        for col in range(1, 10):
            ws.cell(row=ligne, column=col).fill = GRIS
            ws.cell(row=ligne, column=col).font = gras
        ligne += 2

    ws.cell(row=ligne, column=1, value=">>>> TOTAUX GÉNÉRAUX").font = gras
    ws.merge_cells(start_row=ligne, start_column=1, end_row=ligne, end_column=3)
    _montants(ligne, [None, None, tableau.total, None, tableau.salarial, None, tableau.patronal])
    for col in range(1, 10):
        ws.cell(row=ligne, column=col).fill = GRIS
        ws.cell(row=ligne, column=col).font = gras
    ligne += 2
    ws.cell(row=ligne, column=1,
            value=f"Employés payés sur la période : {tableau.payes} (Femmes : {tableau.femmes} Hommes : {tableau.hommes})")

    for col, largeur in zip("ABCDEFGHI", (10, 38, 13, 10, 13, 10, 13, 10, 13)):
        ws.column_dimensions[col].width = largeur
    ws.freeze_panes = "A10"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
