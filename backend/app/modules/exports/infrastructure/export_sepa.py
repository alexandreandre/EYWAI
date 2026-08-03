# Export SEPA pain.001.001.03 — virements salaires et acomptes.
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from app.modules.exports.infrastructure.export_paiement_salaires import (
    get_paiement_salaires_data,
    validate_iban,
)
from app.shared.utils.export import format_period

NS = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"


def _sub(parent: ET.Element, tag: str, text: str = "") -> ET.Element:
    el = ET.SubElement(parent, f"{{{NS}}}{tag}")
    if text:
        el.text = text
    return el


def filter_payable_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ne garde que les lignes virables : non bloquantes, IBAN valide, montant > 0."""
    return [
        r for r in rows
        if r.get("Statut_controle") != "Bloquant"
        and validate_iban(str(r.get("IBAN", "")))
        and float(r.get("Montant", 0) or 0) > 0
    ]


def normalize_bic(raw: Any) -> str:
    """BIC prêt pour le XML, chaîne vide s'il n'y en a pas."""
    return str(raw or "").replace(" ", "").replace("-", "").upper().strip()


def _set_financial_institution(parent: ET.Element, bic: str) -> None:
    """
    Renseigne un agent bancaire, avec ou sans BIC.

    La balise BIC n'accepte qu'un BIC : y écrire « NOTPROVIDED » produit un
    fichier que la banque peut rejeter en le confrontant à l'annuaire. Les
    règles SEPA prévoient pour ce cas `Othr/Id` valant « NOTPROVIDED », et cette
    valeur-là uniquement. Le BIC est facultatif depuis le règlement (UE)
    260/2012 : la banque le retrouve à partir de l'IBAN.
    """
    fin = ET.SubElement(parent, f"{{{NS}}}FinInstnId")
    if bic:
        _sub(fin, "BIC", bic)
        return
    othr = ET.SubElement(fin, f"{{{NS}}}Othr")
    _sub(othr, "Id", "NOTPROVIDED")


def count_employees_without_bic(rows: List[Dict[str, Any]]) -> int:
    """Salariés sans BIC parmi les seules lignes qui partiront à la banque."""
    identites = set()
    for row in filter_payable_rows(rows):
        if normalize_bic(row.get("BIC")):
            continue
        identites.add(
            row.get("employee_id")
            or (row.get("Nom", ""), row.get("Prénom", ""), row.get("IBAN", ""))
        )
    return len(identites)


def missing_bic_warning(rows: List[Dict[str, Any]]) -> Optional[str]:
    """Avertissement non bloquant, ou None si tous les BIC sont présents."""
    nb = count_employees_without_bic(rows)
    if nb == 0:
        return None
    pluriel = "s" if nb > 1 else ""
    return (
        f"{nb} salarié{pluriel} sans BIC — le virement reste valide : l'IBAN "
        "suffit depuis 2016 et la banque retrouve le BIC elle-même."
    )


def build_pain001(
    rows: List[Dict[str, Any]],
    period: str,
    label: str,
    execution_date: Optional[str] = None,
    msg_prefix: str = "EYWAI",
    payment_info_id: Optional[str] = None,
    end_to_end_prefix: str = "SAL",
    debtor_name: str = "Entreprise",
    debtor_iban: str = "",
    debtor_bic: str = "",
) -> bytes:
    """
    Construit un pain.001.001.03 à partir de lignes déjà filtrées.

    Les préfixes d'identifiants distinguent les campagnes de paiement : deux
    remises générées le même mois (salaires et acomptes) ne doivent jamais
    porter les mêmes MsgId / PmtInfId / EndToEndId côté banque.
    """
    valid_rows = filter_payable_rows(rows)

    exec_date = execution_date or date.today().isoformat()
    msg_id = f"{msg_prefix}-{period}-{uuid4().hex[:8]}"
    pmt_inf_id = payment_info_id or f"PMT-{period}"
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
    _sub(pmt_inf, "PmtInfId", pmt_inf_id)
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
    # DbtrAgt est exigé par le schéma SEPA, BIC connu ou non : l'omettre rendait
    # la remise invalide dès que l'entreprise n'avait pas renseigné son BIC.
    dbtr_agt = ET.SubElement(pmt_inf, f"{{{NS}}}DbtrAgt")
    _set_financial_institution(dbtr_agt, normalize_bic(debtor_bic))

    for idx, row in enumerate(valid_rows, start=1):
        tx = ET.SubElement(pmt_inf, f"{{{NS}}}CdtTrfTxInf")
        pmt_id = ET.SubElement(tx, f"{{{NS}}}PmtId")
        _sub(pmt_id, "EndToEndId", f"{end_to_end_prefix}-{period}-{idx:04d}")
        amt_el = ET.SubElement(tx, f"{{{NS}}}Amt")
        inst = ET.SubElement(amt_el, f"{{{NS}}}InstdAmt", Ccy="EUR")
        inst.text = f"{float(row.get('Montant', 0)):.2f}"
        cdtr_agt = ET.SubElement(tx, f"{{{NS}}}CdtrAgt")
        _set_financial_institution(cdtr_agt, normalize_bic(row.get("BIC")))
        cdtr = ET.SubElement(tx, f"{{{NS}}}Cdtr")
        name = f"{row.get('Prénom', '')} {row.get('Nom', '')}".strip()
        _sub(cdtr, "Nm", name[:70])
        cdtr_acct = ET.SubElement(tx, f"{{{NS}}}CdtrAcct")
        acct_id = ET.SubElement(cdtr_acct, f"{{{NS}}}Id")
        _sub(acct_id, "IBAN", str(row.get("IBAN", "")).replace(" ", ""))
        rmt = ET.SubElement(tx, f"{{{NS}}}RmtInf")
        _sub(rmt, "Ustrd", str(row.get("Libelle") or label)[:140])

    ET.register_namespace("", NS)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


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
    """Remise SEPA des virements de salaires."""
    data, _, _, _ = get_paiement_salaires_data(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
    )
    return build_pain001(
        data,
        period=period,
        label=payment_label or f"Salaires {format_period(period)}",
        execution_date=execution_date,
        msg_prefix="EYWAI",
        payment_info_id=f"PMT-{period}",
        end_to_end_prefix="SAL",
        debtor_name=debtor_name,
        debtor_iban=debtor_iban,
        debtor_bic=debtor_bic,
    )


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
    employees_count = totals.get("employees_count", totals.get("virements_count", 0))
    bic_warning = missing_bic_warning(data)
    return {
        "employees_count": employees_count,
        "totals": {
            "employees_count": employees_count,
            "total_amount": totals.get("total_amount"),
        },
        "anomalies": anomalies,
        "warnings": warnings
        + ([bic_warning] if bic_warning else [])
        + ["Format SEPA pain.001.001.03 — transmission manuelle à la banque."],
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
