"""Activité partielle : réglage de la société et heures chômées du mois.

Les jours chômés se posent au calendrier (type « Activité partielle ») : le
bulletin en tire les deux lignes du mois (retenue et indemnité), calculées ici
(`lignes_du_calendrier`). La saisie d'heures du mois à la main reste un repli
pour un salarié sans jour d'activité partielle au calendrier. Un bulletin déjà
fait passe « À recalculer » ; un bulletin remis n'est pas touché.
"""

from __future__ import annotations

import calendar
from datetime import UTC, datetime
from typing import Any

from app.core.database import get_supabase_admin_client
from app.modules.activite_partielle.domain.calendrier import (
    TYPE_JOUR,
    heures_chomees,
    jours_chomes,
)
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
    taux_horaire_forfait_jours,
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
            "hire_date, employment_status, is_forfait_jour, specificites_paie"
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


def _taux_horaire(e: dict[str, Any]) -> float | None:
    """Salaire horaire de référence : contrat en heures, ou forfait en jours."""
    if e.get("is_forfait_jour"):
        from app.modules.payroll.engine.forfait_individuel import (
            jours_du_forfait_de_la_fiche,
        )

        try:
            jours = jours_du_forfait_de_la_fiche(e.get("specificites_paie"))
        except ValueError:
            jours = None
        if jours is None and e.get("company_id"):
            # Sans forfait sur la fiche, celui de la société, comme la
            # réduction générale (`jours_du_forfait_pour_reduction`).
            from app.modules.absences.infrastructure import leave_settings_repository

            jours = float(
                leave_settings_repository.get_leave_policy(str(e["company_id"])).rtt_forfait_annual_days
            )
        return taux_horaire_forfait_jours(e.get("salaire_de_base"), jours)
    return taux_horaire_du_contrat(
        e.get("salaire_de_base"), e.get("duree_hebdomadaire")
    )


def _heures_par_jour(e: dict[str, Any], reglage: dict[str, Any]) -> float:
    if e.get("is_forfait_jour"):
        return 7.0  # une journée de forfait vaut 7 h (fiche du ministère du Travail)
    return float(
        reglage.get("heures_par_jour")
        or round(float(e.get("duree_hebdomadaire") or 35) / 5, 2)
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
    du_mois = _salaries_du_mois(company_id, year, month)
    recap = recap_du_calendrier(company_id, year, month, du_mois, reglage)
    salaries = []
    for e in sorted(du_mois, key=lambda r: _nom(r).lower()):
        eid = str(e["id"])
        heures_jour = _heures_par_jour(e, reglage)
        deja = par_salarie.get(eid)
        salaries.append(
            {
                "employee_id": eid,
                "nom": _nom(e),
                "statut": e.get("statut"),
                "taux_horaire": _taux_horaire(e),
                "forfait_jours": bool(e.get("is_forfait_jour")),
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
                # Jours posés au calendrier : ils font foi au bulletin.
                "calendrier": recap.get(eid),
            }
        )
    return {
        "reglage": reglage,
        "refus": refus_periode(reglage, year, month),
        "salaries": salaries,
    }


def _deux_lignes(c: Any) -> list[dict[str, Any]]:
    """Les deux variables du mois que le moteur paie (forme de la saisie)."""
    return [
        {
            "name": LIBELLE_RETENUE,
            "description": f"{c.heures_chomees:g} h × {c.taux_horaire:.2f} €",
            "amount": -c.retenue,
            "payroll_quantity": c.heures_chomees,
            "is_socially_taxed": True,
            "is_taxable": True,
        },
        {
            "name": LIBELLE_INDEMNITE,
            "description": f"{c.heures_chomees:g} h × {c.indemnite_horaire:.2f} € ({c.regle})",
            "amount": c.indemnite,
            "payroll_quantity": c.heures_chomees,
            "is_socially_taxed": False,
            "is_taxable": True,
        },
    ]


def _calcul(heures: float, taux: float, reglage: dict[str, Any]) -> Any:
    return calculer(
        heures,
        taux,
        taux_indemnite=float(reglage["taux_indemnite"]),
        plancher=float(reglage["plancher_horaire"]),
        plafond=float(reglage["plafond_horaire"]),
    )


def _jours_du_calendrier(
    e: dict[str, Any], reglage: dict[str, Any], prevu: list, reel: list
) -> list:
    return jours_chomes(
        prevu,
        reel,
        forfait_jours=bool(e.get("is_forfait_jour")),
        heures_par_jour=_heures_par_jour(e, reglage),
    )


def lignes_du_calendrier(
    company_id: str,
    employee: dict[str, Any],
    year: int,
    month: int,
    prevu_du_mois: list[dict[str, Any]],
    reel_du_mois: list[dict[str, Any]],
    saisies: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Saisies du bulletin, avec l'activité partielle lue dans le calendrier.

    Sans jour « Activité partielle » au calendrier du mois, rien ne change (la
    saisie à la main, s'il y en a une, compte). Sinon les deux lignes sont
    calculées depuis les jours chômés et remplacent celles saisies à la main :
    le calendrier fait foi. Rien n'est écrit en base. Rend aussi l'alerte du
    bulletin quand le calcul n'a pas pu se faire ou sort du réglage.
    """
    if not any(str(j.get("type") or "") == TYPE_JOUR for j in prevu_du_mois):
        return saisies, None
    reglage = lire_reglage(company_id)
    jours = _jours_du_calendrier(employee, reglage, prevu_du_mois, reel_du_mois)
    heures = heures_chomees(jours)
    if heures <= 0:
        return saisies, None
    taux = _taux_horaire(employee)
    if not taux:
        return saisies, {
            "code": "activite_partielle_sans_taux",
            "severity": "warning",
            "critique": True,
            "message": (
                f"Activité partielle au calendrier ({heures:g} h) non payée : "
                "le salaire de base manque sur la fiche. Complétez-le, puis "
                "recalculez ce bulletin."
            ),
        }
    c = _calcul(heures, taux, reglage)
    gardees = [r for r in saisies if r.get("name") not in LIBELLES]
    commun = {
        "company_id": company_id,
        "employee_id": str(employee.get("id") or ""),
        "year": year,
        "month": month,
        "source": "calendrier_activite_partielle",
    }
    lignes = [{**commun, **ligne} for ligne in _deux_lignes(c)]
    refus = refus_periode(reglage, year, month)
    alerte = (
        {
            "code": "activite_partielle_hors_reglage",
            "severity": "warning",
            "critique": False,
            "message": (
                f"Jours d'activité partielle au calendrier, payés ({heures:g} h), "
                f"mais : {refus} Vérifiez le réglage de la société."
            ),
        }
        if refus
        else None
    )
    return gardees + lignes, alerte


def recap_du_calendrier(
    company_id: str, year: int, month: int, salaries: list[dict[str, Any]], reglage: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Par salarié : jours et heures chômés au calendrier du mois, et leur effet."""
    ids = [str(e["id"]) for e in salaries]
    if not ids:
        return {}
    rows = (
        _db()
        .table("employee_schedules")
        .select("employee_id, planned_calendar, actual_hours")
        .in_("employee_id", ids)
        .eq("year", year)
        .eq("month", month)
        .execute()
        .data
        or []
    )
    par_id = {str(e["id"]): e for e in salaries}
    recap: dict[str, dict[str, Any]] = {}
    for row in rows:
        e = par_id.get(str(row.get("employee_id")))
        if e is None:
            continue
        prevu = (row.get("planned_calendar") or {}).get("calendrier_prevu") or []
        reel = (row.get("actual_hours") or {}).get("calendrier_reel") or []
        jours = _jours_du_calendrier(e, reglage, prevu, reel)
        heures = heures_chomees(jours)
        if heures <= 0:
            continue
        taux = _taux_horaire(e)
        c = _calcul(heures, taux, reglage) if taux else None
        recap[str(e["id"])] = {
            "jours": [j.jour for j in jours],
            "heures": heures,
            "retenue": c.retenue if c else None,
            "indemnite": c.indemnite if c else None,
        }
    return recap


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
        taux = _taux_horaire(e)
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
        c = _calcul(heures, taux, reglage)
        commun = {
            "company_id": company_id,
            "employee_id": eid,
            "year": year,
            "month": month,
            "manual_override": True,
        }
        _db().table("monthly_inputs").insert(
            [{**commun, **ligne} for ligne in _deux_lignes(c)]
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
