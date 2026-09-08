"""MAJI — répartitions hebdomadaires de Dorothée BOULAY et Claire VERNY.

Retour de la déclarante (07/09/2026) : « La répartition de Dorothée est
7/7/3/7/7 » et « la répartition de Claire = 7h / jour ». Leurs calendriers 2026
sont pourtant à **7,8 h tous les jours** (39 h/semaine) : le parseur du planning
Quadra pose `DEFAULT_DAILY_HOURS = 7.8` quand la feuille ne porte pas d'heures,
sans regarder le contrat. Les fiches, elles, sont justes (BOULAY 31 h temps
partiel, VERNY 35 h) — c'est donc le planning, et lui seul, qu'on corrige.

Chemin retenu : les vrais objets du produit, pas du SQL. On crée deux modèles de
semaine (`company_week_schedule_templates`) et deux plans salarié
(`company_schedule_plans`), puis on régénère 2026 via
`calendar_generation.generate_from_plan`. Modèles et plans restent visibles et
modifiables par la RH dans l'écran Plannings — la déclarante peut les relire.

PIÈGE TRAITÉ : les deux calendriers portent 14 jours typés `conge` (jours posés
par la reprise Quadra) qui ne sont adossés à AUCUNE demande d'absence et ne
portent pas le marqueur `origine` — `is_absence_day` ne les protège donc pas et
une régénération les effacerait en silence. On les relève avant, on les repose
après (aux heures du nouveau modèle) et on les marque `manuel` pour qu'une
prochaine régénération en mode `preserve_manual` les respecte. Exception : un
jour tombé sur un férié (1er janvier) reste `ferie` — c'est la bonne valeur.

Usage : python scripts/maji_repartitions_boulay_verny.py [--apply]
        (sans --apply : simulation, aucune écriture)
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.modulation.infrastructure import repository as mod_repo  # noqa: E402
from app.modules.schedules.application import calendar_generation  # noqa: E402
from app.modules.schedules.domain.calendar_generation_rules import (  # noqa: E402
    OVERWRITE_ALL,
    week_weekly_hours,
)
from app.modules.schedules.infrastructure import (  # noqa: E402
    schedule_plans_repository as plans_repo,
)
from app.modules.schedules.infrastructure.repository import (  # noqa: E402
    schedule_repository,
)
from app.core.database import supabase  # noqa: E402
from app.shared.public_holidays import day_numbers_observed_holidays  # noqa: E402

MAJI_ID = "113b2f33-82ec-4cec-8d3a-f16cda8f74f2"
ANNEE = 2026

#: Répartitions dictées par la déclarante, lundi → vendredi (jour ISO 1 → 5).
REPARTITIONS: Dict[str, Dict[str, Any]] = {
    "a9af19b0-2638-4a66-809c-6708424c1ac8": {
        "nom": "Dorothée BOULAY",
        "duree_attendue": 31.0,
        "heures": {1: 7.0, 2: 7.0, 3: 3.0, 4: 7.0, 5: 7.0},
        "modele": "MAJI — 31 h (7/7/3/7/7)",
        "plan": "Dorothée BOULAY — 31 h (7/7/3/7/7)",
    },
    "36264d03-2f02-4f5b-997e-e97d16ea61eb": {
        "nom": "Claire VERNY",
        "duree_attendue": 35.0,
        "heures": {1: 7.0, 2: 7.0, 3: 7.0, 4: 7.0, 5: 7.0},
        "modele": "MAJI — 35 h (7 h/jour)",
        "plan": "Claire VERNY — 35 h (7 h/jour)",
    },
}

MOIS = list(range(1, 13))


def _day_configs(heures: Dict[int, float]) -> List[Dict[str, Any]]:
    """Semaine type : les jours ouvrés aux heures dictées, samedi/dimanche en
    `weekend` (et non `repos` — `ecart_rules` exonère explicitement ce type sur
    un jour de week-end, un `repos` y lèverait un faux écart)."""
    days: List[Dict[str, Any]] = [
        {
            "day": iso,
            "type": "travail",
            "hours": heures[iso],
            "start": None,
            "end": None,
            "break_minutes": 0,
            "break_paid": False,
            "comment": None,
        }
        for iso in sorted(heures)
    ]
    days += [
        {"day": 6, "type": "weekend", "hours": 0.0},
        {"day": 7, "type": "weekend", "hours": 0.0},
    ]
    return days


def _entrees(planned_calendar: Any) -> List[Dict[str, Any]]:
    if not isinstance(planned_calendar, dict):
        return []
    entries = planned_calendar.get("calendrier_prevu")
    return entries if isinstance(entries, list) else []


def _lire_calendriers(employee_id: str) -> Dict[int, Dict[str, Any]]:
    """Mois → ligne employee_schedules de l'année traitée."""
    rows = schedule_repository.get_schedules_for_months(
        employee_id, [(ANNEE, m) for m in MOIS]
    )
    return {int(r["month"]): r for r in rows if int(r.get("year") or 0) == ANNEE}


def _releve_conges(employee_id: str) -> List[Tuple[int, int]]:
    """(mois, jour) des jours typés `conge` — à reposer après régénération."""
    out: List[Tuple[int, int]] = []
    for mois, row in _lire_calendriers(employee_id).items():
        for e in _entrees(row.get("planned_calendar")):
            if e.get("type") == "conge":
                try:
                    out.append((mois, int(e["jour"])))
                except (KeyError, TypeError, ValueError):
                    continue
    return sorted(out)


def _totaux_par_type(employee_id: str) -> Dict[str, int]:
    compte: Dict[str, int] = {}
    for row in _lire_calendriers(employee_id).values():
        for e in _entrees(row.get("planned_calendar")):
            t = str(e.get("type"))
            compte[t] = compte.get(t, 0) + 1
    return compte


def _heures_ouvrees_vues(employee_id: str) -> Dict[str, int]:
    """Heures distinctes rencontrées sur les jours `travail` (photo avant/après)."""
    vues: Dict[str, int] = {}
    for row in _lire_calendriers(employee_id).values():
        for e in _entrees(row.get("planned_calendar")):
            if e.get("type") == "travail":
                k = str(e.get("heures_prevues"))
                vues[k] = vues.get(k, 0) + 1
    return vues


def _upsert_modele(nom: str, days: List[Dict[str, Any]]) -> str:
    existing = plans_repo.find_template_by_name(MAJI_ID, nom)
    payload = {
        "name": nom,
        "description": "Répartition transmise par la déclarante (07/09/2026).",
        "weekly_hours": week_weekly_hours(days),
        "day_configs": days,
        "modulation_tier": "neutral",
        "is_active": True,
    }
    row = mod_repo.upsert_week_template(
        MAJI_ID, payload, template_id=str(existing["id"]) if existing else None
    )
    return str(row["id"])


def _upsert_plan(nom: str, employee_id: str, template_id: str) -> str:
    payload = {
        "name": nom,
        "scope_type": "employees",
        "scope_ref": {"employee_ids": [employee_id]},
        "template_cycle": [template_id],
        "cycle_anchor": f"{ANNEE}-01-05",  # un lundi : cycle d'une seule semaine
        "start_date": f"{ANNEE}-01-01",
        "end_date": f"{ANNEE}-12-31",
        "overwrite_mode": OVERWRITE_ALL,
        "needs_confirmation": False,
        "notes": "Répartition dictée par la déclarante MAJI le 07/09/2026.",
        "is_active": True,
    }
    existing = plans_repo.find_plan_by_name(MAJI_ID, nom)
    if existing:
        row = plans_repo.update_plan(MAJI_ID, str(existing["id"]), payload)
    else:
        row = plans_repo.create_plan(MAJI_ID, {**payload, "status": "draft"})
    return str(row["id"])


def _reposer_conges(
    employee_id: str, conges: List[Tuple[int, int]], heures: Dict[int, float]
) -> Tuple[int, int]:
    """Repose les jours `conge` effacés par la régénération.

    Renvoie (reposés, laissés en férié). Les heures reprennent celles du nouveau
    modèle pour ce jour de semaine — un congé vaut la journée qu'il remplace.
    """
    par_mois: Dict[int, List[int]] = {}
    for mois, jour in conges:
        par_mois.setdefault(mois, []).append(jour)

    reposes = feries = 0
    for mois, jours in sorted(par_mois.items()):
        row = _lire_calendriers(employee_id).get(mois)
        if not row:
            print(f"    ⚠ mois {mois:02d} absent après régénération, congés non reposés")
            continue
        planned = row["planned_calendar"]
        entrees = _entrees(planned)
        index = {int(e["jour"]): e for e in entrees if e.get("jour") is not None}
        touche = False
        for jour in sorted(jours):
            entree = index.get(jour)
            if entree is None:
                continue
            if entree.get("type") == "ferie":
                feries += 1
                continue
            iso = date(ANNEE, mois, jour).isoweekday()
            entree["type"] = "conge"
            entree["heures_prevues"] = float(heures.get(iso, 0.0))
            entree["manuel"] = True
            reposes += 1
            touche = True
        if touche:
            planned["calendrier_prevu"] = entrees
            schedule_repository.upsert_schedule(
                employee_id, MAJI_ID, ANNEE, mois, planned_calendar=planned
            )
    return reposes, feries


def _controle(employee_id: str, conf: Dict[str, Any], conges_attendus: int) -> List[str]:
    """Contrôle après écriture — un écart ici fait échouer le script."""
    erreurs: List[str] = []
    heures = conf["heures"]
    calendriers = _lire_calendriers(employee_id)

    manquants = [m for m in MOIS if m not in calendriers]
    if manquants:
        erreurs.append(f"mois sans calendrier : {manquants}")

    conges_vus = 0
    for mois, row in calendriers.items():
        feries = day_numbers_observed_holidays(ANNEE, mois, MAJI_ID)
        for e in _entrees(row.get("planned_calendar")):
            jour = int(e["jour"])
            iso = date(ANNEE, mois, jour).isoweekday()
            typ, h = e.get("type"), e.get("heures_prevues")
            if typ == "conge":
                conges_vus += 1
                if float(h or 0) != float(heures.get(iso, 0.0)):
                    erreurs.append(f"{jour:02d}/{mois:02d} congé à {h} h au lieu de "
                                   f"{heures.get(iso)} h")
            elif typ == "travail":
                if jour in feries:
                    erreurs.append(f"{jour:02d}/{mois:02d} férié typé travail")
                elif iso > 5:
                    erreurs.append(f"{jour:02d}/{mois:02d} week-end typé travail")
                elif float(h or 0) != float(heures[iso]):
                    erreurs.append(f"{jour:02d}/{mois:02d} à {h} h au lieu de {heures[iso]} h")
            elif typ == "weekend" and iso <= 5:
                erreurs.append(f"{jour:02d}/{mois:02d} jour ouvré typé week-end")

    if conges_vus != conges_attendus:
        erreurs.append(f"{conges_vus} jours de congé retrouvés sur {conges_attendus} attendus")
    return erreurs


def main() -> int:
    apply = "--apply" in sys.argv
    print(f"MAJI — répartitions {ANNEE} ({'ÉCRITURE' if apply else 'SIMULATION'})\n")

    # Garde : les fiches doivent porter la durée contractuelle attendue, sinon la
    # répartition serait posée contre un contrat faux (et le bulletin suivrait).
    fiches = (
        supabase.table("employees")
        .select("id, first_name, last_name, company_id, duree_hebdomadaire")
        .in_("id", list(REPARTITIONS))
        .execute()
    ).data or []
    if len(fiches) != len(REPARTITIONS):
        print("REFUS : fiche(s) introuvable(s).")
        return 1
    for fiche in fiches:
        conf = REPARTITIONS[str(fiche["id"])]
        if str(fiche["company_id"]) != MAJI_ID:
            print(f"REFUS : {conf['nom']} n'est pas chez MAJI.")
            return 1
        duree = float(fiche.get("duree_hebdomadaire") or 0)
        if duree != conf["duree_attendue"]:
            print(f"REFUS : {conf['nom']} — fiche à {duree} h, "
                  f"répartition à {conf['duree_attendue']} h. Corriger la fiche d'abord.")
            return 1
        semaine = sum(conf["heures"].values())
        if semaine != conf["duree_attendue"]:
            print(f"REFUS : répartition {conf['nom']} = {semaine} h ≠ {duree} h contractuelles.")
            return 1

    plan_de_travail: List[Tuple[str, Dict[str, Any], List[Tuple[int, int]]]] = []
    for employee_id, conf in REPARTITIONS.items():
        conges = _releve_conges(employee_id)
        print(f"{conf['nom']} — {conf['duree_attendue']} h contractuelles")
        print(f"  avant : heures des jours travaillés {_heures_ouvrees_vues(employee_id)}")
        print(f"          types {_totaux_par_type(employee_id)}")
        print(f"  {len(conges)} jour(s) `conge` à préserver : "
              + ", ".join(f"{j:02d}/{m:02d}" for m, j in conges))
        plan_de_travail.append((employee_id, conf, conges))

    if not apply:
        print("\nSimulation — rien n'a été écrit. Relancer avec --apply.")
        return 0

    echecs: List[str] = []
    for employee_id, conf, conges in plan_de_travail:
        print(f"\n→ {conf['nom']}")
        template_id = _upsert_modele(conf["modele"], _day_configs(conf["heures"]))
        plan_id = _upsert_plan(conf["plan"], employee_id, template_id)
        print(f"  modèle {template_id} · plan {plan_id}")

        resultat = calendar_generation.generate_from_plan(
            MAJI_ID, plan_id, year=ANNEE, dry_run=False
        )
        mois_ecrits = sum(len(e["months"]) for e in resultat.get("employees") or [])
        print(f"  calendriers régénérés : {mois_ecrits} mois")

        reposes, feries = _reposer_conges(employee_id, conges, conf["heures"])
        print(f"  congés reposés : {reposes} (dont {feries} laissé(s) en férié)")

        erreurs = _controle(employee_id, conf, len(conges) - feries)
        if erreurs:
            echecs.extend(f"{conf['nom']} : {e}" for e in erreurs)
        else:
            print(f"  après : heures des jours travaillés {_heures_ouvrees_vues(employee_id)}")
            print(f"          types {_totaux_par_type(employee_id)}")
            print("  contrôle OK")

    if echecs:
        print("\nCONTRÔLE EN ÉCHEC :")
        for e in echecs[:40]:
            print(f"  - {e}")
        return 1

    print("\nTerminé : répartitions appliquées et contrôlées.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
