"""
Adaptateur de requêtes sécurisées pour le catalogue d'outils Copilot.

Invariants de sécurité (fail-closed) :
- CHAQUE fonction publique exige un ``company_id: str`` serveur non vide
  (positionnel) : il ne provient JAMAIS du LLM ;
- CHAQUE requête directe est filtrée sur ``company_id`` avant exécution : il n'y
  a jamais de requête sans filtre entreprise ;
- les tables réellement utilisées (``employees``, ``absence_requests``,
  ``shifts``) possèdent toutes une colonne ``company_id`` ; le scoping est donc
  direct. Les agrégats paie et indicateurs RH délèguent à des services déjà
  scopés par entreprise ;
- aucune chaîne SQL, nom de table ou identifiant de périmètre issu du LLM n'est
  utilisé : les arguments LLM ne servent qu'à des filtres métier restreints.
"""

from __future__ import annotations

from datetime import date, timedelta
from difflib import SequenceMatcher
from typing import Any

from app.core.database import get_supabase_client
from app.modules.access_control.infrastructure.scoped_repository import (
    filter_allowed_employee_ids_for_user,
    scoped_permission_repository,
)
from app.modules.copilot.domain.filter_values import (
    ABSENCE_STATUTS,
    ABSENCE_TYPES,
    exiger,
)
from app.modules.copilot.domain.tools import TYPES_ECHEANCE
from app.modules.payroll.application.analytics_queries import (
    get_payroll_analytics_summary,
)
from app.modules.dashboard.application.service import build_analytics_avances


def _require_company_id(company_id: Any) -> str:
    """Garantit un company_id serveur exploitable ; sinon échoue (fail-closed)."""
    if not isinstance(company_id, str) or not company_id.strip():
        raise ValueError(
            "company_id serveur obligatoire et non vide pour toute requête Copilot."
        )
    return company_id


def _current_period() -> str:
    today = date.today()
    return f"{today.year}-{today.month:02d}"


def _resolve_period(raw: Any) -> str:
    """Valide une période ``YYYY-MM`` fournie en argument, sinon période courante."""
    if isinstance(raw, str) and len(raw) == 7 and raw[4] == "-":
        year, _, month = raw.partition("-")
        if year.isdigit() and month.isdigit() and 1 <= int(month) <= 12:
            return raw
    return _current_period()


def _resolve_date_range(filters: dict[str, Any]) -> tuple[str, str]:
    """Renvoie une plage ``(date_start, date_end)`` ISO, par défaut la semaine courante.

    Une plage temporelle est TOUJOURS renvoyée : la requête planning n'est jamais
    exécutée sans borne de dates.
    """
    filters = filters or {}
    start = filters.get("date_start")
    end = filters.get("date_end")
    if _is_iso_date(start) and _is_iso_date(end) and str(start) <= str(end):
        return str(start)[:10], str(end)[:10]

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def _is_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value[:10])
        return True
    except ValueError:
        return False


def _valeurs_employees(company_id: str, colonne: str) -> list[str]:
    """Valeurs réellement présentes dans l'entreprise pour une colonne libre.

    ``contract_type`` et ``employment_status`` sont du texte libre : leurs
    valeurs (« Apprentissage », « actif »…) ne sont pas devinables. On rapproche
    donc la valeur proposée de ce qui existe vraiment, plutôt que de filtrer sur
    une chaîne qui ne correspond à rien et de répondre « aucun ».
    """
    lignes = (
        get_supabase_client()
        .table("employees")
        .select(colonne)
        .eq("company_id", company_id)
        .execute()
        .data
        or []
    )
    return sorted({str(ligne[colonne]) for ligne in lignes if ligne.get(colonne)})


def _filtre_employees(query: Any, company_id: str, filters: dict[str, Any]) -> Any:
    """Applique les filtres statut / contrat après rapprochement des valeurs."""
    for argument, colonne in (
        ("employment_status", "employment_status"),
        ("contract_type", "contract_type"),
    ):
        demande = filters.get(argument)
        if not demande:
            continue
        valeurs = _valeurs_employees(company_id, colonne)
        if not valeurs:
            # Entreprise sans salarié : le filtre ne peut se rapprocher de rien,
            # mais la bonne réponse est « zéro », pas « valeur inconnue ».
            query = query.eq(colonne, str(demande))
            continue
        query = query.eq(colonne, exiger(str(demande), valeurs, champ=argument))
    return query


def _coerce_limit(raw: Any, *, default: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value < 1:
        return default
    return min(value, maximum)


# --- employees (company_id présent) ---


def count_employees(company_id: str, filters: dict[str, Any]) -> dict[str, Any]:
    """Compte les salariés de l'entreprise ; filtres optionnels statut / contrat."""
    company_id = _require_company_id(company_id)
    filters = filters or {}
    query = (
        get_supabase_client()
        .table("employees")
        .select("id", count="exact")
        .eq("company_id", company_id)
    )
    query = _filtre_employees(query, company_id, filters)
    response = query.execute()
    return {"count": int(response.count or 0)}


def search_employees(company_id: str, filters: dict[str, Any]) -> dict[str, Any]:
    """Recherche des salariés par nom, strictement dans l'entreprise active."""
    company_id = _require_company_id(company_id)
    filters = filters or {}
    name = str(filters.get("name") or "").strip().lower()
    limit = _coerce_limit(filters.get("limit"), default=10, maximum=25)

    query = (
        get_supabase_client()
        .table("employees")
        .select(
            "id, first_name, last_name, job_title, employment_status, contract_type"
        )
        .eq("company_id", company_id)
    )
    query = _filtre_employees(query, company_id, filters)
    rows = query.execute().data or []

    if name:
        rows = _rank_by_name(rows, name)

    matches = rows[:limit]
    return {"employees": matches, "count": len(matches)}


def _rank_by_name(rows: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        first = str(row.get("first_name") or "").lower()
        last = str(row.get("last_name") or "").lower()
        full = f"{first} {last}".strip()
        candidates = [full, first, last, f"{last} {first}".strip()]
        substring = any(name in c for c in candidates if c)
        ratio = max(
            (SequenceMatcher(None, name, c).ratio() for c in candidates if c),
            default=0.0,
        )
        score = 1.0 if substring else ratio
        if score >= 0.6:
            scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored]


# --- absence_requests (company_id présent) ---


def absence_summary(company_id: str, filters: dict[str, Any]) -> dict[str, Any]:
    """Synthèse des demandes d'absence de l'entreprise (comptes par statut / type).

    Si ``date_start`` et ``date_end`` sont fournis (ISO), ne compte que les
    demandes dont au moins un jour de ``selected_days`` croise la plage.
    """
    company_id = _require_company_id(company_id)
    filters = filters or {}
    query = (
        get_supabase_client()
        .table("absence_requests")
        .select("id, employee_id, type, status, selected_days")
        .eq("company_id", company_id)
    )
    # ``type`` et ``status`` sont des énumérations Postgres : une valeur hors
    # énumération fait échouer la requête entière. On rapproche donc « maladie »
    # de « arret_maladie » et « validé » de « validated ».
    status = filters.get("status")
    if status:
        query = query.eq("status", exiger(str(status), ABSENCE_STATUTS, champ="status"))
    atype = filters.get("type")
    if atype:
        query = query.eq("type", exiger(str(atype), ABSENCE_TYPES, champ="type"))
    rows = query.execute().data or []

    date_start = filters.get("date_start")
    date_end = filters.get("date_end")
    range_applied = False
    if _is_iso_date(date_start) and _is_iso_date(date_end) and str(date_start) <= str(date_end):
        start_s, end_s = str(date_start)[:10], str(date_end)[:10]
        filtered: list[dict[str, Any]] = []
        for row in rows:
            selected = row.get("selected_days") or []
            if not isinstance(selected, list):
                continue
            if any(
                isinstance(d, str) and start_s <= d[:10] <= end_s for d in selected
            ):
                filtered.append(row)
        rows = filtered
        range_applied = True

    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    total_selected_days = 0
    salaries: set[str] = set()
    aujourdhui = date.today().isoformat()
    en_cours_aujourdhui: set[str] = set()
    for row in rows:
        st = str(row.get("status") or "inconnu")
        ty = str(row.get("type") or "inconnu")
        by_status[st] = by_status.get(st, 0) + 1
        by_type[ty] = by_type.get(ty, 0) + 1
        if row.get("employee_id"):
            salaries.add(str(row["employee_id"]))
        selected = row.get("selected_days") or []
        if isinstance(selected, list):
            if any(isinstance(d, str) and d[:10] == aujourdhui for d in selected):
                if row.get("employee_id"):
                    en_cours_aujourdhui.add(str(row["employee_id"]))
            if range_applied:
                start_s, end_s = str(date_start)[:10], str(date_end)[:10]
                total_selected_days += sum(
                    1
                    for d in selected
                    if isinstance(d, str) and start_s <= d[:10] <= end_s
                )
            else:
                total_selected_days += len(selected)

    # La période est explicitée dans la réponse : sans elle, un décompte
    # historique se lit comme une situation du jour (« 4 salariés en arrêt
    # actuellement » alors qu'il s'agissait de 4 demandes depuis toujours).
    result: dict[str, Any] = {
        "periode": (
            f"du {str(date_start)[:10]} au {str(date_end)[:10]}"
            if range_applied
            else "tout l'historique (aucune période demandée)"
        ),
        "total_demandes": len(rows),
        "salaries_concernes": len(salaries),
        "salaries_absents_aujourdhui": len(en_cours_aujourdhui),
        "by_status": by_status,
        "by_type": by_type,
        "total_selected_days": total_selected_days,
    }
    if range_applied:
        result["date_start"] = str(date_start)[:10]
        result["date_end"] = str(date_end)[:10]
    return result


# --- shifts (company_id présent) ---


def planning_summary(company_id: str, filters: dict[str, Any]) -> dict[str, Any]:
    """Synthèse du planning (shifts) de l'entreprise sur une plage de dates."""
    company_id = _require_company_id(company_id)
    filters = filters or {}
    date_start, date_end = _resolve_date_range(filters)

    rows = (
        get_supabase_client()
        .table("shifts")
        .select("id, employee_id, shift_date, is_locked, transverse_category")
        .eq("company_id", company_id)
        .gte("shift_date", date_start)
        .lte("shift_date", date_end)
        .execute()
        .data
        or []
    )

    employees = {
        str(r.get("employee_id")) for r in rows if r.get("employee_id")
    }
    locked = sum(1 for r in rows if r.get("is_locked"))
    return {
        "date_start": date_start,
        "date_end": date_end,
        "total_shifts": len(rows),
        "employees_scheduled": len(employees),
        "locked_shifts": locked,
    }


# --- Agrégats délégués à des services déjà scopés par entreprise ---


def payroll_summary(company_id: str, filters: dict[str, Any]) -> dict[str, Any]:
    """Synthèse paie : délègue à l'analytics paie scopée par entreprise."""
    company_id = _require_company_id(company_id)
    filters = filters or {}
    period = _resolve_period(filters.get("period"))
    return get_payroll_analytics_summary(
        company_id=company_id, period=period, team_ids=None
    )


def hr_indicators(company_id: str, filters: dict[str, Any]) -> dict[str, Any]:
    """Indicateurs RH synthétiques : délègue au dashboard et sérialise un sous-ensemble."""
    company_id = _require_company_id(company_id)
    analytics = build_analytics_avances(company_id)
    return {
        "effectif_actif": analytics.effectif_actif,
        "age_moyen": analytics.age_moyen,
        "anciennete_moyenne_annees": analytics.anciennete_moyenne_annees,
        "masse_salariale_brute_totale": analytics.masse_salariale_brute_totale,
        "turnover": {
            "taux_turnover_annuel": analytics.turnover.taux_turnover_annuel,
            "nb_departs_12_mois": analytics.turnover.nb_departs_12_mois,
            "nb_embauches_12_mois": analytics.turnover.nb_embauches_12_mois,
        },
        "absenteisme": {
            "taux_global": analytics.absenteisme.taux_global,
            "taux_maladie": analytics.absenteisme.taux_maladie,
            "taux_at": analytics.absenteisme.taux_at,
        },
    }


# ----------------------------------------------------------------------------
# Outils nominatifs — ils désignent des personnes.
#
# Deux bornes cumulées, dans cet ordre :
#   1. le ``company_id`` serveur, comme partout ailleurs ;
#   2. le périmètre scopé de l'utilisateur (``access_control``), qui est
#      fail-closed : sans grant, la liste des salariés autorisés est vide et la
#      requête ne renvoie rien.
#
# Un RH restreint à une équipe ne voit donc que la sienne, dans l'assistant
# comme dans le reste de l'application. Le ``user_id`` vient du serveur, jamais
# du LLM.
# ----------------------------------------------------------------------------


# Rôles dont les droits viennent du nom, et non de grants : eux seuls peuvent
# se voir attribuer le périmètre entreprise en l'absence de grant explicite.
ROLES_PERIMETRE_ENTREPRISE: frozenset[str] = frozenset(
    {"admin", "rh", "collaborateur_rh"}
)


def _tous_les_salaries(company_id: str) -> list[str]:
    lignes = (
        get_supabase_client()
        .table("employees")
        .select("id")
        .eq("company_id", company_id)
        .execute()
        .data
        or []
    )
    return [str(ligne["id"]) for ligne in lignes]


def _employes_autorises(
    company_id: str, user_id: str, permission: str, role: str = ""
) -> list[str] | None:
    """Identifiants des salariés visibles par l'utilisateur pour une permission.

    Reprend la règle déjà appliquée par ``access_control`` dans le reste de
    l'application (``require_employee_access``) :

    1. un grant scopé existe -> on applique son périmètre, équipes et exceptions
       comprises. C'est le cas d'un RH restreint à une équipe ;
    2. aucun grant, rôle **nommé** (admin / rh / collaborateur_rh) -> périmètre
       entreprise. Ces rôles n'ont pas de ligne ``user_permissions`` : leurs
       droits viennent du rôle. Vérifié en production : aucun d'eux n'a de grant
       explicite. Sans cette branche, l'assistant ne renverrait rien à personne ;
    3. aucun grant, rôle **custom** -> AUCUN salarié. Un rôle custom ne tient
       ses droits que de ses grants : l'absence de grant pour cette permission
       est un refus, pas un silence à combler.

    La distinction entre 2 et 3 n'est pas théorique. DROZ-VINCENT (Mont Blanc
    Composite) a quinze permissions en périmètre « équipes », mais pas
    ``employees.view_all`` : le repli de la branche 2 lui ouvrait les 89
    salariés de l'entreprise, soit exactement l'inverse de son paramétrage.

    Deux retours à ne pas confondre, car ils donnent des réponses opposées :

    - ``None`` : l'utilisateur n'a AUCUN droit sur cette donnée. L'appelant doit
      dire « hors de votre périmètre », jamais « il n'y en a pas » ;
    - liste vide : l'utilisateur a le droit, mais la population est réellement
      vide (entreprise sans salarié). Là, « aucun » est la bonne réponse.
    """
    if not isinstance(user_id, str) or not user_id.strip():
        return None
    grant = scoped_permission_repository.get_grant(user_id, company_id, permission)
    if grant is not None:
        autorises = filter_allowed_employee_ids_for_user(
            user_id, company_id, permission
        )
        # Le périmètre du grant est renvoyé tel quel : s'il ne couvre personne,
        # c'est bien « aucun salarié », pas « accès refusé ». L'utilisateur a le
        # droit ; c'est la population qui est vide.
        return autorises
    if role in ROLES_PERIMETRE_ENTREPRISE:
        return _tous_les_salaries(company_id)
    return None


def _index_salaries(company_id: str, ids: list[str]) -> dict[str, dict[str, Any]]:
    """Nom et équipe des salariés autorisés, en une requête."""
    if not ids:
        return {}
    lignes = (
        get_supabase_client()
        .table("employees")
        .select("id, first_name, last_name, job_title, team_id")
        .eq("company_id", company_id)
        .in_("id", ids)
        .execute()
        .data
        or []
    )
    return {str(ligne["id"]): ligne for ligne in lignes}


def _nom(ligne: dict[str, Any]) -> str:
    return f"{ligne.get('first_name') or ''} {ligne.get('last_name') or ''}".strip()


def absences_en_cours(
    company_id: str, filters: dict[str, Any], user_id: str = "", role: str = ""
) -> dict[str, Any]:
    """Qui est absent sur une période, nommément.

    Répond à « qui est en arrêt maladie en ce moment ? », que la synthèse
    agrégée ne pouvait pas traiter : elle ne renvoyait que des comptes, et
    l'assistant finissait par dire qu'il n'avait pas accès à l'information.
    """
    company_id = _require_company_id(company_id)
    filters = filters or {}
    autorises = _employes_autorises(company_id, user_id, "absences.view_all", role)
    if autorises is None:
        return {"absences": [], "count": 0, "hors_perimetre": True}
    if not autorises:
        return {"absences": [], "count": 0}

    date_start, date_end = _resolve_date_range(filters)
    query = (
        get_supabase_client()
        .table("absence_requests")
        .select("employee_id, type, status, selected_days")
        .eq("company_id", company_id)
        .in_("employee_id", autorises)
    )
    demande_type = filters.get("type")
    if demande_type:
        query = query.eq(
            "type", exiger(str(demande_type), ABSENCE_TYPES, champ="type")
        )
    lignes = query.execute().data or []

    salaries = _index_salaries(company_id, autorises)
    absences: list[dict[str, Any]] = []
    for ligne in lignes:
        jours = ligne.get("selected_days") or []
        if not isinstance(jours, list):
            continue
        concernes = [
            j for j in jours
            if isinstance(j, str) and date_start <= j[:10] <= date_end
        ]
        if not concernes:
            continue
        salarie = salaries.get(str(ligne.get("employee_id")))
        if not salarie:
            continue
        absences.append(
            {
                "salarie": _nom(salarie),
                "poste": salarie.get("job_title"),
                "type": ligne.get("type"),
                "statut": ligne.get("status"),
                "premier_jour": min(concernes)[:10],
                "dernier_jour": max(concernes)[:10],
                "jours_sur_la_periode": len(concernes),
            }
        )
    absences.sort(key=lambda a: a["premier_jour"])
    return {
        "date_start": date_start,
        "date_end": date_end,
        "absences": absences,
        "count": len(absences),
    }


def echeances_rh(
    company_id: str, filters: dict[str, Any], user_id: str = "", role: str = ""
) -> dict[str, Any]:
    """Échéances RH à venir ou dépassées, nommément.

    Couvre les quatre suivis à date : titre de séjour, visite médicale,
    période d'essai et fin de contrat. Les échéances **dépassées** sont
    incluses volontairement — ce sont les plus urgentes, et les exclure est
    exactement ce qui rendait les relances d'échéances muettes.
    """
    company_id = _require_company_id(company_id)
    filters = filters or {}
    horizon = _coerce_limit(filters.get("jours"), default=90, maximum=365)
    aujourdhui = date.today()
    limite = (aujourdhui + timedelta(days=horizon)).isoformat()
    demande = filters.get("type")
    voulus = {str(demande)} if demande else set(TYPES_ECHEANCE)

    echeances: list[dict[str, Any]] = []
    client = get_supabase_client()

    hors_perimetre: list[str] = []
    if voulus & {"titre_sejour", "periode_essai", "fin_contrat"}:
        autorises = _employes_autorises(company_id, user_id, "employees.view_all", role)
        if autorises is None:
            # Aucun salarié visible : « aucune échéance » serait un mensonge.
            # L'utilisateur doit savoir qu'il regarde à travers une fenêtre
            # fermée, pas une pièce vide.
            hors_perimetre.extend(
                sorted(voulus & {"titre_sejour", "periode_essai", "fin_contrat"})
            )
            autorises = []
        salaries = _index_salaries(company_id, autorises)

        if "titre_sejour" in voulus and autorises:
            lignes = (
                client.table("employees")
                .select("id, residence_permit_expiry_date, residence_permit_type")
                .eq("company_id", company_id)
                .in_("id", autorises)
                .not_.is_("residence_permit_expiry_date", "null")
                .lte("residence_permit_expiry_date", limite)
                .execute()
                .data
                or []
            )
            for ligne in lignes:
                salarie = salaries.get(str(ligne["id"]))
                if salarie:
                    echeances.append(
                        _echeance(
                            "titre_sejour",
                            salarie,
                            ligne.get("residence_permit_expiry_date"),
                            aujourdhui,
                            detail=ligne.get("residence_permit_type"),
                        )
                    )

        if "fin_contrat" in voulus and autorises:
            lignes = (
                client.table("employees")
                .select("id, contract_end_date, contract_type")
                .eq("company_id", company_id)
                .in_("id", autorises)
                .not_.is_("contract_end_date", "null")
                .lte("contract_end_date", limite)
                .execute()
                .data
                or []
            )
            for ligne in lignes:
                salarie = salaries.get(str(ligne["id"]))
                if salarie:
                    echeances.append(
                        _echeance(
                            "fin_contrat",
                            salarie,
                            ligne.get("contract_end_date"),
                            aujourdhui,
                            detail=ligne.get("contract_type"),
                        )
                    )

        if "periode_essai" in voulus and autorises:
            lignes = (
                client.table("trial_periods")
                .select("employee_id, end_date, status")
                .eq("company_id", company_id)
                .in_("employee_id", autorises)
                .lte("end_date", limite)
                .execute()
                .data
                or []
            )
            for ligne in lignes:
                if str(ligne.get("status") or "").lower() in ("confirmed", "confirmee"):
                    continue
                salarie = salaries.get(str(ligne.get("employee_id")))
                if salarie:
                    echeances.append(
                        _echeance(
                            "periode_essai",
                            salarie,
                            ligne.get("end_date"),
                            aujourdhui,
                            detail=ligne.get("status"),
                        )
                    )

    if "visite_medicale" in voulus:
        # Le suivi médical a sa propre permission : un RH peut gérer les
        # contrats sans avoir à connaître les visites de santé.
        autorises_med = _employes_autorises(
            company_id, user_id, "medical_follow_up.view_all", role
        )
        if autorises_med is None:
            hors_perimetre.append("visite_medicale")
            autorises_med = []
        if autorises_med:
            salaries_med = _index_salaries(company_id, autorises_med)
            lignes = (
                client.table("medical_follow_up_obligations")
                .select("employee_id, due_date, visit_type, status")
                .eq("company_id", company_id)
                .in_("employee_id", autorises_med)
                .lte("due_date", limite)
                .execute()
                .data
                or []
            )
            for ligne in lignes:
                if str(ligne.get("status") or "").lower() in ("completed", "done"):
                    continue
                salarie = salaries_med.get(str(ligne.get("employee_id")))
                if salarie:
                    echeances.append(
                        _echeance(
                            "visite_medicale",
                            salarie,
                            ligne.get("due_date"),
                            aujourdhui,
                            detail=ligne.get("visit_type"),
                        )
                    )

    echeances.sort(key=lambda e: e["date"] or "9999")
    return {
        "horizon_jours": horizon,
        "echeances": echeances,
        "count": len(echeances),
        "depassees": sum(1 for e in echeances if e["jours_restants"] is not None
                         and e["jours_restants"] < 0),
        # Types que l'utilisateur n'a pas le droit de consulter. Distinguer
        # « rien à signaler » de « pas visible pour vous » évite de faire dire à
        # l'assistant qu'une échéance n'existe pas alors qu'elle est seulement
        # hors de son périmètre.
        "types_hors_perimetre": sorted(set(hors_perimetre)),
    }


def _echeance(
    type_echeance: str,
    salarie: dict[str, Any],
    echeance: Any,
    aujourdhui: date,
    *,
    detail: Any = None,
) -> dict[str, Any]:
    jours = None
    if _is_iso_date(echeance):
        jours = (date.fromisoformat(str(echeance)[:10]) - aujourdhui).days
    return {
        "type": type_echeance,
        "salarie": _nom(salarie),
        "poste": salarie.get("job_title"),
        "date": str(echeance)[:10] if echeance else None,
        "jours_restants": jours,
        "depassee": jours is not None and jours < 0,
        "detail": detail,
    }


def employee_detail(
    company_id: str, filters: dict[str, Any], user_id: str = "", role: str = ""
) -> dict[str, Any]:
    """Fiche d'un salarié : contrat, ancienneté, et rémunération si autorisée.

    La rémunération a sa propre permission (``payroll.view_all``) : un RH peut
    consulter un dossier sans voir le salaire. Le champ est alors simplement
    absent, et la réponse le dit — plutôt que de laisser croire à une donnée
    manquante.
    """
    company_id = _require_company_id(company_id)
    filters = filters or {}
    nom_cherche = str(filters.get("name") or "").strip().lower()
    if not nom_cherche:
        return {"employees": [], "count": 0}

    autorises = _employes_autorises(company_id, user_id, "employees.view_all", role)
    if autorises is None:
        return {"employees": [], "count": 0, "hors_perimetre": True}
    if not autorises:
        return {"employees": [], "count": 0}

    lignes = (
        get_supabase_client()
        .table("employees")
        .select(
            "id, first_name, last_name, job_title, contract_type, "
            "employment_status, hire_date, date_debut_execution, "
            "contract_end_date, salaire_de_base, team_id"
        )
        .eq("company_id", company_id)
        .in_("id", autorises)
        .execute()
        .data
        or []
    )
    correspondances = _rank_by_name(lignes, nom_cherche)[:3]
    if not correspondances:
        return {"employees": [], "count": 0}

    # Le droit de voir un salaire s'évalue SALARIÉ PAR SALARIÉ, pas globalement.
    # Un utilisateur peut consulter les dossiers des équipes A et B et n'avoir
    # accès à la paie que de l'équipe A : un booléen unique lui montrerait le
    # salaire d'un salarié de l'équipe B.
    salaires_autorises = set(
        _employes_autorises(company_id, user_id, "payroll.view_all", role) or []
    )
    aujourdhui = date.today()
    fiches = []
    for ligne in correspondances:
        entree = ligne.get("date_debut_execution") or ligne.get("hire_date")
        anciennete = None
        if _is_iso_date(entree):
            anciennete = round(
                (aujourdhui - date.fromisoformat(str(entree)[:10])).days / 365.25, 1
            )
        fiche = {
            "salarie": _nom(ligne),
            "poste": ligne.get("job_title"),
            "type_contrat": ligne.get("contract_type"),
            "statut": ligne.get("employment_status"),
            "date_entree": str(entree)[:10] if entree else None,
            "anciennete_annees": anciennete,
            "fin_contrat": ligne.get("contract_end_date"),
        }
        if str(ligne.get("id")) in salaires_autorises:
            fiche["salaire_de_base"] = ligne.get("salaire_de_base")
        else:
            fiche["salaire_de_base"] = None
            fiche["salaire_non_autorise"] = True
        fiches.append(fiche)
    return {"employees": fiches, "count": len(fiches)}
