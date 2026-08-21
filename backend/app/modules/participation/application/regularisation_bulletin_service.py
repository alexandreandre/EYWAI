"""Génération d'un bulletin de régularisation « participation » (paie).

Cas d'usage principal : verser la participation/intéressement d'un exercice à un
salarié **déjà parti** l'année suivante. La génération de bulletin mensuel standard
étant (à juste titre) bloquée pour un salarié non actif, on produit ici un bulletin
**dédié, autonome**, qui ne porte que la somme de participation et la CSG/CRDS
correspondante (cf. `participation.domain.regularisation_payslip`).

Le document est enregistré dans la table `payslips` avec
`bulletin_kind = 'regularisation_participation'` :
- il apparaît donc dans la liste des bulletins du salarié et dans l'export DSN ;
- il est **protégé** du nettoyage automatique à l'archivage d'une sortie.
"""

from __future__ import annotations

import html
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.database import supabase
from app.modules.participation.domain.regularisation_payslip import (
    REGULARISATION_KIND,
    build_regularisation_participation_payslip_data,
)
from app.modules.participation.infrastructure.campaign_repository import (
    campaign_repository,
)

logger = logging.getLogger(__name__)


class RegularisationBulletinError(Exception):
    """Erreur fonctionnelle lors de la génération d'un bulletin de régularisation."""


def _fmt_eur(value: Any) -> str:
    try:
        d = float(value or 0)
    except (TypeError, ValueError):
        d = 0.0
    s = f"{d:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} €"


def _resolve_period(
    campaign: Dict[str, Any],
    year: Optional[int],
    month: Optional[int],
) -> tuple[int, int]:
    y = year or campaign.get("payroll_year")
    m = month or campaign.get("payroll_month")
    if not y or not m:
        raise RegularisationBulletinError(
            "Période de versement non définie : renseignez l'année et le mois de paie "
            "de la campagne avant de générer le bulletin de régularisation."
        )
    return int(y), int(m)


def _render_pdf_html(payslip_data: Dict[str, Any]) -> str:
    """Construit un HTML autonome (rendu WeasyPrint) pour le bulletin de régularisation."""
    en_tete = payslip_data.get("en_tete", {})
    reg = payslip_data.get("regularisation", {})
    salarie = en_tete.get("salarie", {})
    entreprise = en_tete.get("entreprise", {})

    def esc(value: Any) -> str:
        return html.escape(str(value)) if value is not None else ""

    lignes_csg = "".join(
        f"<tr><td>{esc(c['libelle'])}</td>"
        f"<td class='r'>{_fmt_eur(c['base'])}</td>"
        f"<td class='r'>{c['taux_salarial']:.3f} %</td>"
        f"<td class='r'>{_fmt_eur(c['montant_salarial'])}</td></tr>"
        for c in payslip_data.get("structure_cotisations", {}).get("cotisations", [])
    )

    mention = (
        payslip_data.get("pied_de_page", {})
        .get("mentions_legales", {})
        .get("participation", "")
    )

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><style>
  @page {{ size: A4; margin: 18mm 16mm; }}
  body {{ font-family: 'Helvetica', 'Arial', sans-serif; font-size: 11px; color: #1a1a1a; }}
  h1 {{ font-size: 16px; margin: 0 0 2px; }}
  .sub {{ color: #555; font-size: 11px; margin-bottom: 14px; }}
  .grid {{ display: flex; justify-content: space-between; margin-bottom: 16px; }}
  .box {{ width: 48%; border: 1px solid #ddd; border-radius: 6px; padding: 8px 10px; }}
  .box .lbl {{ color: #888; font-size: 9px; text-transform: uppercase; letter-spacing: .04em; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 12px; }}
  th, td {{ padding: 5px 7px; border-bottom: 1px solid #eee; text-align: left; }}
  th {{ background: #f5f6f8; font-size: 9px; text-transform: uppercase; color: #555; }}
  td.r, th.r {{ text-align: right; }}
  .total {{ font-weight: bold; }}
  .net {{ margin-top: 10px; padding: 10px 12px; background: #0f172a; color: #fff;
          border-radius: 6px; display: flex; justify-content: space-between; font-size: 14px; }}
  .mention {{ margin-top: 16px; font-size: 9px; color: #666; border-top: 1px solid #eee; padding-top: 8px; }}
</style></head><body>
  <h1>Bulletin de régularisation</h1>
  <div class="sub">{esc(reg.get('dispositif_label'))} — exercice {esc(reg.get('exercise_label'))} · Période de paie : {esc(en_tete.get('periode'))}</div>
  <div class="grid">
    <div class="box"><div class="lbl">Employeur</div><div>{esc(entreprise.get('raison_sociale'))}</div><div>SIRET {esc(entreprise.get('siret'))}</div></div>
    <div class="box"><div class="lbl">Salarié</div><div>{esc(salarie.get('nom_complet'))}</div><div>{esc(salarie.get('emploi') or '')}</div></div>
  </div>
  <table>
    <thead><tr><th>Élément</th><th class="r">Base</th><th class="r">Taux</th><th class="r">Montant</th></tr></thead>
    <tbody>
      <tr><td>{esc(reg.get('dispositif_label'))} {esc(reg.get('exercise_label'))} (brut)</td>
          <td class="r"></td><td class="r"></td><td class="r">{_fmt_eur(reg.get('brut'))}</td></tr>
      {lignes_csg}
      <tr class="total"><td>Total CSG/CRDS (9,7 %)</td><td class="r"></td><td class="r"></td>
          <td class="r">- {_fmt_eur(reg.get('csg_total'))}</td></tr>
    </tbody>
  </table>
  <table>
    <tbody>
      <tr><td>Part numéraire (versée — imposable IR)</td><td class="r">{_fmt_eur(reg.get('part_numeraire'))}</td></tr>
      <tr><td>Part placée sur plan d'épargne (PEE — exonérée IR)</td><td class="r">{_fmt_eur(reg.get('part_pee'))}</td></tr>
      {('<tr><td>Dont acompte déjà versé (' + esc(reg.get('acompte_label') or '') + ')</td><td class="r">' + _fmt_eur(reg.get('acompte')) + '</td></tr>') if (reg.get('acompte') or 0) > 0 else ''}
    </tbody>
  </table>
  <div class="net"><span>Net à payer</span><span>{_fmt_eur(payslip_data.get('net_a_payer'))}</span></div>
  <div class="mention">{esc(mention)}</div>
</body></html>"""


def generate_regularisation_participation_payslip(
    bulletin_id: str,
    company_id: str,
    *,
    year: Optional[int] = None,
    month: Optional[int] = None,
    notify: bool = True,
) -> Dict[str, Any]:
    """Génère (ou régénère) le bulletin de régularisation participation d'un salarié.

    Fonctionne quel que soit le statut du salarié (y compris « parti »).
    Retourne {payslip_id, download_url, year, month, employee_id}.
    """
    bulletin = campaign_repository.get_bulletin(bulletin_id, company_id=company_id)
    if not bulletin:
        raise RegularisationBulletinError("Bulletin de participation introuvable.")

    campaign = campaign_repository.get_campaign(
        str(bulletin["campaign_id"]), company_id
    ) or {}
    year_paie, month_paie = _resolve_period(campaign, year, month)

    employee_id = str(bulletin["employee_id"])
    emp_res = (
        supabase.table("employees")
        .select("*")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    employee = emp_res.data if emp_res else None
    if not employee:
        raise RegularisationBulletinError("Salarié introuvable pour ce bulletin.")

    # Lot 3 : ce bulletin partage la clé d'unicité (company, employee, year,
    # month) avec le bulletin MENSUEL et s'upsert en statut « valide ». Sans
    # ces gardes, un clic sur la route manuelle écraserait le bulletin du
    # mois d'un salarié actif — même validé — en le remplaçant par une
    # régularisation auto-validée hors circuit.
    if str(employee.get("employment_status") or "") == "actif":
        raise RegularisationBulletinError(
            "Ce salarié est actif : la régularisation de participation "
            "s'intègre à son bulletin mensuel, pas en bulletin séparé "
            "(réservé aux salariés sortis)."
        )
    bulletin_periode = (
        supabase.table("payslips")
        .select("id, bulletin_kind, status")
        .match(
            {
                "company_id": company_id,
                "employee_id": employee_id,
                "year": year_paie,
                "month": month_paie,
            }
        )
        .maybe_single()
        .execute()
    )
    existant = bulletin_periode.data if bulletin_periode else None
    if existant and existant.get("bulletin_kind") != REGULARISATION_KIND:
        raise RegularisationBulletinError(
            f"Un bulletin existe déjà pour {month_paie:02d}/{year_paie} : "
            "générer la régularisation l'écraserait. Choisissez une autre "
            "période de rattachement."
        )

    comp_res = (
        supabase.table("companies")
        .select("*")
        .eq("id", company_id)
        .maybe_single()
        .execute()
    )
    company = (comp_res.data if comp_res else None) or {}

    payslip_data = build_regularisation_participation_payslip_data(
        bulletin=bulletin,
        employee=employee,
        company=company,
        year=year_paie,
        month=month_paie,
        exercise_label=campaign.get("exercise_label"),
    )

    folder = employee.get("employee_folder_name") or employee_id
    pdf_name = f"Regularisation_participation_{folder}_{month_paie:02d}-{year_paie}.pdf"
    storage_path = f"{company_id}/{employee_id}/bulletins/{pdf_name}"

    html_doc = _render_pdf_html(payslip_data)
    from weasyprint import HTML

    with tempfile.TemporaryDirectory(prefix="regul_part_") as tmp:
        pdf_path = Path(tmp) / pdf_name
        HTML(string=html_doc).write_pdf(str(pdf_path))
        with open(pdf_path, "rb") as fh:
            supabase.storage.from_("payslips").upload(
                path=storage_path,
                file=fh.read(),
                file_options={"x-upsert": "true"},
            )

    signed = supabase.storage.from_("payslips").create_signed_url(
        storage_path, 3600, options={"download": True}
    )
    pdf_url = signed["signedURL"]

    upsert = (
        supabase.table("payslips")
        .upsert(
            {
                "employee_id": employee_id,
                "company_id": company_id,
                "year": year_paie,
                "month": month_paie,
                "name": pdf_name,
                "payslip_data": payslip_data,
                "pdf_storage_path": storage_path,
                "url": pdf_url,
                "status": "valide",
                "bulletin_kind": REGULARISATION_KIND,
            },
            on_conflict="company_id,employee_id,year,month",
        )
        .execute()
    )
    payslip_id = upsert.data[0].get("id") if upsert.data else None

    if notify:
        try:
            from app.modules.notifications.application.employee_document_alerts import (
                NOTIFICATION_TYPE_PAYSLIP,
                notify_employee_new_document,
            )

            notify_employee_new_document(
                employee_id,
                company_id,
                f"Bulletin de régularisation participation — {month_paie:02d}/{year_paie}",
                page_path="payslips",
                notification_type=NOTIFICATION_TYPE_PAYSLIP,
            )
        except Exception as exc:  # pragma: no cover - notification best effort
            logger.info("[regul_part] notification ignorée (%s): %s", employee_id, exc)

    return {
        "payslip_id": payslip_id,
        "download_url": pdf_url,
        "year": year_paie,
        "month": month_paie,
        "employee_id": employee_id,
    }
