"""
Variables de fusion pour le module Documents (templates client / EYWAI).

Toutes les valeurs sont des chaînes ; les clés manquantes retournent "".
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, TypedDict


class DocumentVariableMeta(TypedDict):
    key: str
    label: str
    category: str
    example: str


DOCUMENT_VARIABLE_CATALOG: List[DocumentVariableMeta] = [
    {"key": "nom", "label": "Nom de famille", "category": "Salarié", "example": "Dupont"},
    {"key": "prenom", "label": "Prénom", "category": "Salarié", "example": "Marie"},
    {"key": "date_naissance", "label": "Date de naissance", "category": "Salarié", "example": "15/03/1990"},
    {"key": "lieu_naissance", "label": "Lieu de naissance", "category": "Salarié", "example": "Lyon (69)"},
    {"key": "nationalite", "label": "Nationalité", "category": "Salarié", "example": "Française"},
    {"key": "adresse_salarie", "label": "Adresse du salarié", "category": "Salarié", "example": "12 rue de la Paix, 75002 Paris"},
    {"key": "numero_titre_sejour", "label": "N° titre de séjour", "category": "Salarié", "example": "1234567890"},
    {"key": "titre_sejour_fin", "label": "Fin validité titre de séjour", "category": "Salarié", "example": "31/12/2028"},
    {"key": "date_fin_contrat", "label": "Date de fin de contrat (CDD)", "category": "Salarié", "example": "30/04/2026"},
    {"key": "fin_periode_essai", "label": "Fin de période d'essai", "category": "Salarié", "example": "04/04/2026"},
    {"key": "numero_securite_sociale", "label": "N° sécurité sociale", "category": "Salarié", "example": "1 85 03 75 123 456 78"},
    {"key": "poste", "label": "Intitulé de poste", "category": "Salarié", "example": "Responsable commercial"},
    {"key": "classification", "label": "Classification conventionnelle", "category": "Salarié", "example": "Cadre"},
    {"key": "coefficient", "label": "Coefficient", "category": "Salarié", "example": "250"},
    {"key": "salaire_brut_mensuel", "label": "Salaire brut mensuel", "category": "Salarié", "example": "3 200,00 €"},
    {"key": "salaire_brut_annuel", "label": "Salaire brut annuel", "category": "Salarié", "example": "38 400,00 €"},
    {"key": "date_debut_contrat", "label": "Date d'embauche", "category": "Salarié", "example": "01/09/2023"},
    {"key": "type_contrat", "label": "Type de contrat", "category": "Salarié", "example": "CDI"},
    {"key": "duree_hebdomadaire", "label": "Durée hebdomadaire", "category": "Salarié", "example": "35 h"},
    {"key": "lieu_travail", "label": "Lieu de travail", "category": "Salarié", "example": "Siège social"},
    {"key": "periode_essai_duree", "label": "Durée période d'essai", "category": "Salarié", "example": "2 mois"},
    {"key": "service", "label": "Service / département", "category": "Salarié", "example": "Commercial"},
    {"key": "manager", "label": "Manager / responsable hiérarchique", "category": "Salarié", "example": "Jean Martin"},
    {"key": "missions", "label": "Missions du poste", "category": "Fiche de poste", "example": "Prospection et fidélisation client"},
    {"key": "description_poste", "label": "Description du poste", "category": "Fiche de poste", "example": "Pilotage de l'activité commerciale"},
    {"key": "localisation_poste", "label": "Localisation du poste", "category": "Fiche de poste", "example": "Paris"},
    {"key": "date_avenant", "label": "Date de l'avenant", "category": "Avenant", "example": "01/01/2026"},
    {"key": "date_effet", "label": "Date d'effet", "category": "Avenant", "example": "01/01/2026"},
    {"key": "motif_avenant", "label": "Motif de l'avenant", "category": "Avenant", "example": "Évolution de poste"},
    {"key": "ancien_salaire", "label": "Ancien salaire", "category": "Avenant", "example": "2 800,00 €"},
    {"key": "nouveau_salaire", "label": "Nouveau salaire", "category": "Avenant", "example": "3 000,00 €"},
    {"key": "ancien_poste", "label": "Ancien poste", "category": "Avenant", "example": "Commercial junior"},
    {"key": "nouveau_poste", "label": "Nouveau poste", "category": "Avenant", "example": "Commercial senior"},
    {"key": "nom_entreprise", "label": "Raison sociale", "category": "Entreprise", "example": "ACME SAS"},
    {"key": "siret", "label": "SIRET", "category": "Entreprise", "example": "123 456 789 00012"},
    {"key": "urssaf_number", "label": "N° URSSAF", "category": "Entreprise", "example": "827000002161193744"},
    {"key": "code_ape", "label": "Code APE", "category": "Entreprise", "example": "6201Z"},
    {"key": "adresse_entreprise", "label": "Adresse entreprise", "category": "Entreprise", "example": "10 avenue de la République, 44000 Nantes"},
    {"key": "convention_collective", "label": "Convention collective", "category": "Entreprise", "example": "Bureaux d'études techniques"},
    {"key": "idcc", "label": "IDCC", "category": "Entreprise", "example": "1486"},
    {"key": "nom_signataire_rh", "label": "Nom du signataire RH", "category": "Entreprise", "example": "Sophie Leroy"},
    {"key": "qualite_signataire_rh", "label": "Qualité du signataire", "category": "Entreprise", "example": "Directrice RH"},
    {"key": "date_generation", "label": "Date du jour", "category": "Système", "example": "18/04/2026"},
    {"key": "signature_lieu", "label": "Lieu de signature", "category": "Système", "example": "Nantes"},
    {"key": "signature_date", "label": "Date de signature", "category": "Système", "example": "18/04/2026"},
    {"key": "exercice", "label": "Année d'exercice", "category": "Participation", "example": "2025"},
    {"key": "exercice_debut", "label": "Début d'exercice", "category": "Participation", "example": "01/01/2025"},
    {"key": "exercice_fin", "label": "Fin d'exercice", "category": "Participation", "example": "31/12/2025"},
    {"key": "date_emission", "label": "Date d'émission du bulletin", "category": "Participation", "example": "12/05/2025"},
    {"key": "montant_brut", "label": "Montant brut participation/intéressement", "category": "Participation", "example": "3 225,33 €"},
    {"key": "csg_non_deductible", "label": "CSG + CRDS non déductibles", "category": "Participation", "example": "93,53 €"},
    {"key": "csg_deductible", "label": "CSG déductible des revenus", "category": "Participation", "example": "219,32 €"},
    {"key": "acompte", "label": "Acompte déjà versé", "category": "Participation", "example": "1 000,00 €"},
    {"key": "acompte_libelle", "label": "Libellé acompte", "category": "Participation", "example": "décembre 2025"},
    {"key": "net_a_payer", "label": "Net à payer", "category": "Participation", "example": "1 912,47 €"},
    {"key": "net_a_payer_final", "label": "Net à payer final", "category": "Participation", "example": "1 912,47 €"},
    {"key": "type_dispositif", "label": "Type (Participation / Intéressement)", "category": "Participation", "example": "Participation"},
    {"key": "clause_defaut_15j", "label": "Clause défaut 15 jours PEE", "category": "Participation", "example": "À défaut de réponse dans les 15 jours…"},
]


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
    for key in ("periode_essai_duree", "trial_period_duration", "duree_periode_essai"):
        if employee.get(key) is not None:
            return _s(employee.get(key))
    # Sinon, la période d'essai active jointe depuis trial_periods.
    trial = employee.get("trial_period")
    if isinstance(trial, dict) and trial.get("duration_value"):
        return f"{trial['duration_value']} {trial.get('duration_unit') or 'mois'}"
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


def _company_address_line(company: Dict[str, Any]) -> str:
    for key in ("address", "adresse", "full_address"):
        val = company.get(key)
        if val is not None and str(val).strip():
            return _s(val)
    rue = _s(company.get("adresse_rue") or "")
    cp = _s(company.get("adresse_code_postal") or "")
    ville = _s(company.get("adresse_ville") or "")
    city_line = " ".join(p for p in (cp, ville) if p).strip()
    parts = [p for p in (rue, city_line) if p]
    return ", ".join(parts)


def _employee_service(employee: Dict[str, Any]) -> str:
    svc = employee.get("service") or employee.get("department")
    if isinstance(svc, dict):
        return _s(svc.get("name") or svc.get("label") or svc.get("libelle") or "")
    return _s(svc)


def enrich_context_from_recruitment_job(
    ctx: Dict[str, Any], job: Dict[str, Any]
) -> Dict[str, Any]:
    """Préremplit le contexte de génération depuis une offre de recrutement."""
    out = dict(ctx)
    title = _s(job.get("title"))
    description = _s(job.get("description"))
    location = _s(job.get("location"))
    contract_type = _s(job.get("contract_type"))
    if title:
        out.setdefault("poste", title)
        out.setdefault("nouveau_poste", title)
    if description:
        out.setdefault("missions", description)
        out.setdefault("description_poste", description)
    if location:
        out.setdefault("localisation_poste", location)
    if contract_type:
        out.setdefault("type_contrat", contract_type)
    out["recruitment_job_id"] = str(job.get("id") or "")
    return out


def list_document_variables() -> List[DocumentVariableMeta]:
    return list(DOCUMENT_VARIABLE_CATALOG)


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
    variables["lieu_naissance"] = _s(employee.get("lieu_naissance"))
    variables["nationalite"] = _s(employee.get("nationalite"))
    variables["adresse_salarie"] = _employee_address_line(employee)
    variables["numero_titre_sejour"] = _s(employee.get("residence_permit_number"))
    variables["titre_sejour_fin"] = _fmt_date_fr(
        employee.get("residence_permit_expiry_date")
    )
    variables["date_fin_contrat"] = _fmt_date_fr(
        employee.get("contract_end_date") or ctx.get("date_fin_contrat")
    )
    variables["fin_periode_essai"] = _fmt_date_fr(
        employee.get("trial_period_end_date") or ctx.get("fin_periode_essai")
    )
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
    variables["service"] = _employee_service(employee)
    variables["manager"] = _s(
        ctx.get("manager")
        or employee.get("manager_name")
        or employee.get("manager")
    )

    # --- Fiche de poste / recrutement (contexte) ---
    missions = _s(ctx.get("missions") or ctx.get("description_poste"))
    variables["missions"] = missions
    variables["description_poste"] = _s(ctx.get("description_poste") or missions)
    variables["localisation_poste"] = _s(
        ctx.get("localisation_poste") or ctx.get("location") or variables["lieu_travail"]
    )
    if ctx.get("poste") and not variables["poste"]:
        variables["poste"] = _s(ctx.get("poste"))
    if ctx.get("type_contrat") and not variables["type_contrat"]:
        variables["type_contrat"] = _s(ctx.get("type_contrat"))

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
    variables["urssaf_number"] = _company_field(company, "urssaf_number")
    variables["code_ape"] = _company_field(
        company, "code_ape", "ape", "naf", "naf_ape"
    )
    variables["adresse_entreprise"] = _company_address_line(company)
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

    custom_fields = ctx.get("custom_fields")
    if isinstance(custom_fields, dict):
        for key, val in custom_fields.items():
            k = str(key).strip()
            if k:
                variables[k] = _s(val)

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
