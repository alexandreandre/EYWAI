# Export SEPA pain.001.001.03 — virements salaires.
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from app.modules.exports.infrastructure.export_paiement_salaires import (
    get_paiement_salaires_data,
    validate_iban,
)
from app.shared.utils.export import format_period, generate_csv

NS = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"


def _sub(parent: ET.Element, tag: str, text: str = "") -> ET.Element:
    el = ET.SubElement(parent, f"{{{NS}}}{tag}")
    if text:
        el.text = text
    return el


def generate_sepa_pain001(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    excluded_employee_ids: Optional[List[str]] = None,
    execution_date: Optional[str] = None,
    payment_label: Optional[str] = None,
    debtor_name: str = "Entreprise",
    debtor_iban: str = "",
    debtor_bic: str = "",
) -> bytes:
    data, _, _, _ = get_paiement_salaires_data(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
    )
    valid_rows = [
        r for r in data
        if r.get("Statut_controle") != "Bloquant"
        and validate_iban(str(r.get("IBAN", "")))
        and float(r.get("Montant", 0) or 0) > 0
    ]

    exec_date = execution_date or date.today().isoformat()
    msg_id = f"EYWAI-{period}-{uuid4().hex[:8]}"
    label = payment_label or f"Salaires {format_period(period)}"
    total = sum(float(r.get("Montant", 0) or 0) for r in valid_rows)
    nb_tx = len(valid_rows)

    root = ET.Element(f"{{{NS}}}Document")
    cstmr = ET.SubElement(root, f"{{{NS}}}CstmrCdtTrfInitn")

    grp_hdr = ET.SubElement(cstmr, f"{{{NS}}}GrpHdr")
    _sub(grp_hdr, "MsgId", msg_id)
    _sub(grp_hdr, "CreDtTm", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    _sub(grp_hdr, "NbOfTxs", str(nb_tx))
    _sub(grp_hdr, "CtrlSum", f"{total:.2f}")
    initg = ET.SubElement(grp_hdr, f"{{{NS}}}InitgPty")
    _sub(initg, "Nm", debtor_name[:70])

    pmt_inf = ET.SubElement(cstmr, f"{{{NS}}}PmtInf")
    _sub(pmt_inf, "PmtInfId", f"PMT-{period}")
    _sub(pmt_inf, "PmtMtd", "TRF")
    _sub(pmt_inf, "NbOfTxs", str(nb_tx))
    _sub(pmt_inf, "CtrlSum", f"{total:.2f}")
    pmt_tp = ET.SubElement(pmt_inf, f"{{{NS}}}PmtTpInf")
    svc = ET.SubElement(pmt_tp, f"{{{NS}}}SvcLvl")
    _sub(svc, "Cd", "SEPA")
    _sub(pmt_inf, "ReqdExctnDt", exec_date)
    dbtr = ET.SubElement(pmt_inf, f"{{{NS}}}Dbtr")
    _sub(dbtr, "Nm", debtor_name[:70])
    if debtor_iban:
        dbtr_acct = ET.SubElement(pmt_inf, f"{{{NS}}}DbtrAcct")
        acct_id = ET.SubElement(dbtr_acct, f"{{{NS}}}Id")
        _sub(acct_id, "IBAN", debtor_iban.replace(" ", ""))
    if debtor_bic:
        dbtr_agt = ET.SubElement(pmt_inf, f"{{{NS}}}DbtrAgt")
        fin = ET.SubElement(dbtr_agt, f"{{{NS}}}FinInstnId")
        _sub(fin, "BIC", debtor_bic)

    for idx, row in enumerate(valid_rows, start=1):
        tx = ET.SubElement(pmt_inf, f"{{{NS}}}CdtTrfTxInf")
        pmt_id = ET.SubElement(tx, f"{{{NS}}}PmtId")
        _sub(pmt_id, "EndToEndId", f"SAL-{period}-{idx:04d}")
        amt_el = ET.SubElement(tx, f"{{{NS}}}Amt")
        inst = ET.SubElement(amt_el, f"{{{NS}}}InstdAmt", Ccy="EUR")
        inst.text = f"{float(row.get('Montant', 0)):.2f}"
        cdtr_agt = ET.SubElement(tx, f"{{{NS}}}CdtrAgt")
        fin = ET.SubElement(cdtr_agt, f"{{{NS}}}FinInstnId")
        bic = str(row.get("BIC", "") or "NOTPROVIDED")
        _sub(fin, "BIC", bic)
        cdtr = ET.SubElement(tx, f"{{{NS}}}Cdtr")
        name = f"{row.get('Prénom', '')} {row.get('Nom', '')}".strip()
        _sub(cdtr, "Nm", name[:70])
        cdtr_acct = ET.SubElement(tx, f"{{{NS}}}CdtrAcct")
        acct_id = ET.SubElement(cdtr_acct, f"{{{NS}}}Id")
        _sub(acct_id, "IBAN", str(row.get("IBAN", "")).replace(" ", ""))
        rmt = ET.SubElement(tx, f"{{{NS}}}RmtInf")
        _sub(rmt, "Ustrd", label[:140])

    ET.register_namespace("", NS)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def preview_sepa(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    excluded_employee_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    data, totals, anomalies, warnings = get_paiement_salaires_data(
        company_id, period, employee_ids, excluded_employee_ids
    )
    blocking = [a for a in anomalies if a.get("severity") == "blocking"]
    return {
        "employees_count": totals.get("employees_count", 0),
        "totals": totals,
        "anomalies": anomalies,
        "warnings": warnings + ["Format SEPA pain.001.001.03 — transmission manuelle à la banque."],
        "can_generate": len(blocking) == 0,
    }


def generate_sepa_or_csv_bank_file(
    company_id: str,
    period: str,
    file_format: str,
    **kwargs: Any,
) -> Tuple[bytes, str]:
    """Retourne (contenu, extension)."""
    if file_format == "sepa" or file_format == "xml":
        return generate_sepa_pain001(company_id, period, **kwargs), "xml"
    from app.modules.exports.infrastructure.export_paiement_salaires import (
        generate_bank_file,
    )
    return (
        generate_bank_file(company_id, period, **kwargs),
        "csv",
    )
