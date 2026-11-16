"""Activité partielle : réglage de la société et heures chômées du mois.

La RH saisit les heures (ou jours) chômées de chaque salarié ; Martine pose les
deux variables du mois que le moteur paie déjà. Un bulletin déjà fait passe
« À recalculer » ; un bulletin remis n'est pas touché.
"""

from __future__ import annotations

import calendar
from datetime import UTC, datetime
from typing import Any

from app.core.database import get_supabase_admin_client
from app.modules.activite_partielle.domain.calcul import (
    LIBELLE_INDEMNITE,
    LIBELLE_RETENUE,
    LIBELLES,
    PLAFOND_LEGAL,
    PLANCHER_LEGAL,
    TAUX_LEGAL,
    calculer,
    refus_periode,
    taux_horaire_du_contrat,
)

CHAMPS_REGLAGE = (
    "active",
    "date_debut",
    "date_fin",
    "taux_indemnite",
    "plancher_horaire",
    "plafond_horaire",
    "heures_par_jour",
    "reference_decision",
    "note",
)


def _db():
    return get_supabase_admin_client()


def _reglage_par_defaut(company_id: str) -> dict[str, Any]:
    return {
        "company_id": company_id,
        "active": False,
        "date_debut": None,
        "date_fin": None,
        "taux_indemnite": TAUX_LEGAL,
        "plancher_horaire": PLANCHER_LEGAL,
        "plafond_horaire": PLAFOND_LEGAL,
        "heures_par_jour": None,
        "reference_decision": None,
        "note": None,
        "updated_at": None,
    }


def _nombres(r: dict[str, Any]) -> dict[str, Any]:
    out = dict(r)
    for cle in (
        "taux_indemnite",
        "plancher_horaire",
        "plafond_horaire",
        "heures_par_jour",
    ):
        if out.get(cle) is not None:
            out[cle] = float(out[cle])
    return out


def lire_reglage(company_id: str) -> dict[str, Any]:
    rows = (
        _db()
        .table("company_activite_partielle")
        .select("*")
        .eq("company_id", company_id)
        .execute()
        .data
        or []
    )
    return _nombres(rows[0]) if rows else _reglage_par_defaut(company_id)


def enregistrer_reglage(
    company_id: str, body: dict[str, Any], user_id: str
) -> dict[str, Any]:
    ligne = {k: body.get(k) for k in CHAMPS_REGLAGE if k in body}
    for cle in ("date_debut", "date_fin"):
        if ligne.get(cle) is not None:
            ligne[cle] = str(ligne[cle])[:10]
    if (
        ligne.get("date_debut")
        and ligne.get("date_fin")
        and ligne["date_fin"] < ligne["date_debut"]
    ):
        raise ValueError("La fin de l'activité partielle est avant son début.")
    ligne.update(
        {
            "company_id": company_id,
            "updated_by": user_id,
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    _db().table("company_activite_partielle").upsert(
        ligne, on_conflict="company_id"
    ).execute()
    return lire_reglage(company_id)


def _salaries_du_mois(company_id: str, year: int, month: int) -> list[dict[str, Any]]:
    fin = f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
    rows = (
        _db()
        .table("employees")
        .select(
            "id, first_name, last_name, nom_usage, statut, salaire_de_base, duree_hebdomadaire, "
            "hire_date, employment_status"
        )
        .eq("company_id", company_id)
        .execute()
        .data
        or []
    )
    return [
        r
        for r in rows
        if str(r.get("hire_date") or "0000")[:10] <= fin
        and str(r.get("employment_status") or "actif") == "actif"
    ]


def _lignes_ap_du_mois(company_id: str, year: int, month: int) -> list[dict[str, Any]]:
    return (
        _db()
        .table("monthly_inputs")
        .select("id, employee_id, name, amount, payroll_quantity")
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("month", month)
        .in_("name", list(LIBELLES))
        .execute()
        .data
        or []
    )


def _nom(r: dict[str, Any]) -> str:
    nom = r.get("nom_usage") or r.get("last_name") or ""
    return f"{r.get('first_name') or ''} {nom}".strip()


def lister_mois(company_id: str, year: int, month: int) -> dict[str, Any]:
    reglage = lire_reglage(company_id)
    lignes = _lignes_ap_du_mois(company_id, year, month)
    par_salarie: dict[str, dict[str, Any]] = {}
    for ligne in lignes:
        p = par_salarie.setdefault(
            str(ligne["employee_id"]),
            {"heures": None, "retenue": 0.0, "indemnite": 0.0},
        )
        if ligne["name"] == LIBELLE_RETENUE:
            p["retenue"] += -float(ligne.get("amount") or 0)
            if ligne.get("payroll_quantity") is not None:
                p["heures"] = (p["heures"] or 0.0) + abs(
                    float(ligne["payroll_quantity"])
                )
        else:
            p["indemnite"] += float(ligne.get("amount") or 0)
    salaries = []
    for e in sorted(
        _salaries_du_mois(company_id, year, month), key=lambda r: _nom(r).lower()
    ):
        eid = str(e["id"])
        heures_jour = reglage.get("heures_par_jour") or round(
            float(e.get("duree_hebdomadaire") or 35) / 5, 2
        )
        deja = par_salarie.get(eid)
        salaries.append(
            {
                "employee_id": eid,
                "nom": _nom(e),
                "statut": e.get("statut"),
                "taux_horaire": taux_horaire_du_contrat(
                    e.get("salaire_de_base"), e.get("duree_hebdomadaire")
                ),
                "heures_par_jour": float(heures_jour),
                "deja": (
                    {
                        "heures": round(deja["heures"], 2)
                        if deja["heures"] is not None
                        else None,
                        "retenue": round(deja["retenue"], 2),
                        "indemnite": round(deja["indemnite"], 2),
                    }
                    if deja
                    else None
                ),
            }
        )
    return {
        "reglage": reglage,
        "refus": refus_periode(reglage, year, month),
        "salaries": salaries,
    }


def _bulletin_remis(employee_id: str, year: int, month: int) -> bool:
    from app.modules.payslips.application import commands as payslip_cmds
    from app.modules.payslips.application.dto import PayslipBadRequestError

    existant = payslip_cmds._fetch_existing_payslip(employee_id, year, month)
    if not existant:
        return False
    try:
        payslip_cmds.refuser_si_remis(existant, year, month)
    except PayslipBadRequestError:
        return True
    return False


def poser_heures_du_mois(
    company_id: str,
    year: int,
    month: int,
    saisies: list[dict[str, Any]],
    user_id: str,
) -> dict[str, Any]:
    """Pose (ou remplace) les deux lignes d'activité partielle de chaque salarié.

    0 heure retire les lignes. Un bulletin remis n'est pas touché : la
    correction se fait le mois suivant.
    """
    reglage = lire_reglage(company_id)
    refus = refus_periode(reglage, year, month)
    if refus:
        raise ValueError(refus)
    salaries = {str(e["id"]): e for e in _salaries_du_mois(company_id, year, month)}
    existantes = _lignes_ap_du_mois(company_id, year, month)
    resultats: list[dict[str, Any]] = []
    cibles: list[tuple[str, int, int]] = []
    for saisie in saisies:
        eid = str(saisie["employee_id"])
        e = salaries.get(eid)
        if e is None:
            resultats.append(
                {
                    "employee_id": eid,
                    "statut": "refuse",
                    "message": "Salarié introuvable dans la société ce mois-ci.",
                }
            )
            continue
        heures = float(saisie.get("heures") or 0)
        if heures < 0 or heures > 250:
            resultats.append(
                {
                    "employee_id": eid,
                    "nom": _nom(e),
                    "statut": "refuse",
                    "message": "Nombre d'heures impossible.",
                }
            )
            continue
        if _bulletin_remis(eid, year, month):
            resultats.append(
                {
                    "employee_id": eid,
                    "nom": _nom(e),
                    "statut": "bulletin_remis",
                    "message": "Bulletin déjà remis : rien n'est changé ; régularisez le mois suivant.",
                }
            )
            continue
        taux = taux_horaire_du_contrat(
            e.get("salaire_de_base"), e.get("duree_hebdomadaire")
        )
        if heures > 0 and not taux:
            resultats.append(
                {
                    "employee_id": eid,
                    "nom": _nom(e),
                    "statut": "refuse",
                    "message": "Salaire de base absent de la fiche : taux horaire inconnu.",
                }
            )
            continue
        anciennes = [
            str(ligne["id"]) for ligne in existantes if str(ligne["employee_id"]) == eid
        ]
        if anciennes:
            _db().table("monthly_inputs").delete().in_("id", anciennes).eq(
                "company_id", company_id
            ).execute()
        if heures <= 0:
            resultats.append(
                {
                    "employee_id": eid,
                    "nom": _nom(e),
                    "statut": "retire" if anciennes else "rien",
                }
            )
            if anciennes:
                cibles.append((eid, year, month))
            continue
        c = calculer(
            heures,
            taux,
            taux_indemnite=float(reglage["taux_indemnite"]),
            plancher=float(reglage["plancher_horaire"]),
            plafond=float(reglage["plafond_horaire"]),
        )
        commun = {
            "company_id": company_id,
            "employee_id": eid,
            "year": year,
            "month": month,
            "manual_override": True,
        }
        _db().table("monthly_inputs").insert(
            [
                {
                    **commun,
                    "name": LIBELLE_RETENUE,
                    "description": f"{c.heures_chomees:g} h × {c.taux_horaire:.2f} €",
                    "amount": -c.retenue,
                    "payroll_quantity": c.heures_chomees,
                    "is_socially_taxed": True,
                    "is_taxable": True,
                },
                {
                    **commun,
                    "name": LIBELLE_INDEMNITE,
                    "description": f"{c.heures_chomees:g} h × {c.indemnite_horaire:.2f} € ({c.regle})",
                    "amount": c.indemnite,
                    "payroll_quantity": c.heures_chomees,
                    "is_socially_taxed": False,
                    "is_taxable": True,
                },
            ]
        ).execute()
        cibles.append((eid, year, month))
        resultats.append(
            {
                "employee_id": eid,
                "nom": _nom(e),
                "statut": "pose",
                "heures": c.heures_chomees,
                "taux_horaire": c.taux_horaire,
                "indemnite_horaire": c.indemnite_horaire,
                "retenue": c.retenue,
                "indemnite": c.indemnite,
                "regle": c.regle,
            }
        )
    from app.modules.monthly_inputs.application.queries import bulletins_a_recalculer

    return {
        "resultats": resultats,
        "bulletins_a_recalculer": bulletins_a_recalculer(company_id, cibles)
        if cibles
        else [],
    }
