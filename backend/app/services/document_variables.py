"""
Variables de fusion pour le module Documents (templates client / EYWAI).

Toutes les valeurs sont des chaînes ; les clés manquantes retournent "".
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _s(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _fmt_date_fr(value: Any) -> str:
    d = _parse_date(value)
    if not d:
        return _s(value) if value else ""
    return d.strftime("%d/%m/%Y")


def _fmt_number_fr(value: Any, decimals: int = 2, suffix: str = "") -> str:
    if value is None or value == "":
        return ""
    try:
        if isinstance(value, Decimal):
            n = float(value)
        elif isinstance(value, (int, float)):
            n = float(value)
        else:
            s = str(value).strip().replace(" ", "").replace(",", ".")
            n = float(s)
    except (ValueError, TypeError, InvalidOperation):
        return _s(value)

    sign = "-" if n < 0 else ""
    n = abs(n)
    if decimals:
        frac_part = f"{n:.{decimals}f}".split(".")[-1]
        int_part = int(f"{n:.{decimals}f}".split(".")[0])
    else:
        frac_part = ""
        int_part = int(round(n))

    int_str = f"{int_part:,}".replace(",", " ")
    if decimals and frac_part:
        return f"{sign}{int_str},{frac_part}{suffix}"
    return f"{sign}{int_str}{suffix}"


def _fmt_euros(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        if isinstance(value, dict):
            inner = value.get("valeur", value.get("amount"))
            return _fmt_euros(inner)
        if isinstance(value, Decimal):
            n = float(value)
        elif isinstance(value, (int, float)):
            n = float(value)
        else:
            s = str(value).strip().replace(" ", "").replace(",", ".")
            n = float(s)
    except (ValueError, TypeError, InvalidOperation):
        return _s(value)

    sign = "-" if n < 0 else ""
    n = abs(n)
    whole, frac = f"{n:.2f}".split(".")
    int_str = f"{int(whole):,}".replace(",", " ")
    return f"{sign}{int_str},{frac} €"


def _employee_address_line(employee: Dict[str, Any]) -> str:
    addr = employee.get("adresse") or employee.get("address") or {}
    if isinstance(addr, str):
        return addr
    if not isinstance(addr, dict):
        return ""
    parts = [
        addr.get("rue") or addr.get("street") or "",
        " ".join(
            filter(
                None,
                [
                    str(addr.get("code_postal") or addr.get("postal_code") or "").strip(),
                    str(addr.get("ville") or addr.get("city") or "").strip(),
                ],
            )
        ).strip(),
    ]
    return ", ".join(p for p in parts if p)


def _nested_classification(employee: Dict[str, Any], key: str) -> str:
    cc = employee.get("classification_conventionnelle") or {}
    if not isinstance(cc, dict):
        return ""
    return _s(cc.get(key) or "")


def _salaire_brut_mensuel(employee: Dict[str, Any]) -> str:
    sb = employee.get("salaire_de_base")
    if isinstance(sb, dict):
        return _fmt_euros(sb.get("valeur", sb.get("amount")))
    return _fmt_euros(sb)


def _salaire_brut_annuel(employee: Dict[str, Any]) -> str:
    sb = employee.get("salaire_de_base")
    val = None
    if isinstance(sb, dict):
        val = sb.get("valeur", sb.get("amount"))
    elif sb is not None:
        val = sb
    if val is None or val == "":
        return ""
    try:
        monthly = float(str(val).replace(",", ".").replace(" ", ""))
        return _fmt_euros(monthly * 12.0)
    except (ValueError, TypeError):
        return ""


def _duree_hebdomadaire(employee: Dict[str, Any]) -> str:
    v = employee.get("duree_hebdomadaire")
    if v is None:
        v = employee.get("weekly_hours")
    if v is None:
        return ""
    try:
        f = float(v)
        s = f"{f:g}".replace(".", ",")
        return f"{s} h"
    except (ValueError, TypeError):
        return _s(v)


def _periode_essai(employee: Dict[str, Any]) -> str:
    for key in (
        "periode_essai_duree",
        "periode_essai",
        "trial_period_duration",
        "duree_periode_essai",
    ):
        if employee.get(key) is not None:
            return _s(employee.get(key))
    return ""


def _lieu_travail(employee: Dict[str, Any]) -> str:
    lt = employee.get("lieu_travail") or employee.get("workplace")
    if isinstance(lt, str):
        return lt
    if isinstance(lt, dict):
        return _s(lt.get("libelle") or lt.get("label") or lt.get("name") or "")
    return _s(lt)


def _company_field(company: Dict[str, Any], *keys: str) -> str:
    for k in keys:
        if company.get(k) is not None and str(company.get(k)).strip() != "":
            return _s(company.get(k))
    return ""


def build_variables(
    employee: Dict[str, Any],
    company: Dict[str, Any],
    context: Dict[str, Any] | None = None,
) -> Dict[str, str]:
    """
    Construit le dictionnaire {nom_variable: valeur_string} pour fusion dans templates.
    """
    ctx = context or {}

    variables: Dict[str, str] = {}

    # --- Salarié ---
    variables["prenom"] = _s(employee.get("first_name") or employee.get("prenom"))
    variables["nom"] = _s(employee.get("last_name") or employee.get("nom"))
    variables["date_naissance"] = _fmt_date_fr(
        employee.get("date_naissance") or employee.get("birth_date")
    )
    variables["adresse_salarie"] = _employee_address_line(employee)
    variables["numero_securite_sociale"] = _s(
        employee.get("nir") or employee.get("numero_securite_sociale")
    )
    variables["poste"] = _s(employee.get("job_title") or employee.get("poste"))
    variables["classification"] = _nested_classification(
        employee, "classe_emploi"
    ) or _nested_classification(employee, "groupe_emploi")
    variables["coefficient"] = _nested_classification(employee, "coefficient")
    variables["salaire_brut_mensuel"] = _salaire_brut_mensuel(employee)
    variables["salaire_brut_annuel"] = _salaire_brut_annuel(employee)
    variables["date_debut_contrat"] = _fmt_date_fr(
        employee.get("hire_date") or employee.get("date_debut_contrat")
    )
    variables["type_contrat"] = _s(
        employee.get("contract_type") or employee.get("type_contrat")
    )
    variables["duree_hebdomadaire"] = _duree_hebdomadaire(employee)
    variables["lieu_travail"] = _lieu_travail(employee)
    variables["periode_essai_duree"] = _periode_essai(employee)

    # --- Avenant (contexte) ---
    variables["date_avenant"] = _fmt_date_fr(ctx.get("date_avenant"))
    variables["date_effet"] = _fmt_date_fr(ctx.get("date_effet"))
    variables["motif_avenant"] = _s(ctx.get("motif_avenant"))
    variables["ancien_salaire"] = _fmt_euros(ctx.get("ancien_salaire"))
    variables["nouveau_salaire"] = _fmt_euros(ctx.get("nouveau_salaire"))
    variables["ancien_poste"] = _s(ctx.get("ancien_poste"))
    variables["nouveau_poste"] = _s(ctx.get("nouveau_poste"))
    variables["ancienne_duree"] = _s(ctx.get("ancienne_duree"))
    variables["nouvelle_duree"] = _s(ctx.get("nouvelle_duree"))
    variables["ancien_lieu"] = _s(ctx.get("ancien_lieu"))
    variables["nouveau_lieu"] = _s(ctx.get("nouveau_lieu"))

    # --- Entreprise ---
    variables["nom_entreprise"] = _company_field(
        company, "company_name", "raison_sociale", "name"
    )
    variables["siret"] = _company_field(company, "siret")
    variables["code_ape"] = _company_field(company, "code_ape", "ape", "naf")
    variables["adresse_entreprise"] = _company_field(
        company, "address", "adresse", "full_address"
    )
    variables["convention_collective"] = _company_field(
        company,
        "convention_collective",
        "collective_agreement_name",
        "ccn_name",
    )
    variables["idcc"] = _s(company.get("idcc") or company.get("code_idcc") or "")
    variables["nom_signataire_rh"] = _s(
        ctx.get("nom_signataire_rh")
        or company.get("nom_signataire_rh")
        or company.get("signatory_name")
    )
    variables["qualite_signataire_rh"] = _s(
        ctx.get("qualite_signataire_rh")
        or company.get("qualite_signataire_rh")
        or company.get("signatory_title")
    )

    # --- Système ---
    today = date.today()
    variables["date_generation"] = today.strftime("%d/%m/%Y")
    variables["signature_lieu"] = _s(
        ctx.get("signature_lieu") or company.get("city") or company.get("ville") or ""
    )
    variables["signature_date"] = _fmt_date_fr(ctx.get("signature_date") or today)

    return variables


def get_unknown_variables(
    template_content: str, known_variables: Dict[str, str]
) -> List[str]:
    """
    Extrait les placeholders {{variable}} présents dans le contenu
    et retourne ceux qui ne sont pas des clés de known_variables.
    """
    found = _PLACEHOLDER_RE.findall(template_content or "")
    known = set(known_variables.keys())
    unknown: List[str] = []
    seen: set[str] = set()
    for name in found:
        if name not in known and name not in seen:
            seen.add(name)
            unknown.append(name)
    return unknown
