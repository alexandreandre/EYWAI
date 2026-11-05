"""Règles métier compte d'heures modulation — domaine pur."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

MovementType = Literal[
    "credit_hs",
    "debit_recovery",
    "debit_payout",
    "adjustment",
    "opening_balance",
]

_CREDIT_TYPES = frozenset({"credit_hs", "opening_balance"})
_DEBIT_TYPES = frozenset({"debit_recovery", "debit_payout"})
_ACTIVE_STATUSES = frozenset({"validated", "applied_payroll"})

_HS_EVENT_TYPES = ("travail_hs25", "travail_hs50")


@dataclass(frozen=True)
class SplitHsResult:
    to_account: float
    to_pay: float


def split_hs_for_period(
    total_hs: float,
    franchise_hours: float,
    franchise_consumed_in_period: float,
    current_balance: float,
    max_balance: float | None = None,
) -> SplitHsResult:
    """
    Répartit les HS d'une période entre compte modulation et paie.

    franchise_hours : plafond de crédit compte sur la période (ex. 14 h/mois).
    """
    total_hs = max(0.0, round(float(total_hs), 2))
    if total_hs <= 0:
        return SplitHsResult(to_account=0.0, to_pay=0.0)

    franchise = max(0.0, float(franchise_hours or 0))
    consumed = max(0.0, float(franchise_consumed_in_period or 0))
    franchise_remaining = max(0.0, round(franchise - consumed, 2))

    to_account_raw = min(total_hs, franchise_remaining)

    if max_balance is not None:
        room = max(0.0, round(float(max_balance) - float(current_balance), 2))
        to_account = min(to_account_raw, room)
    else:
        to_account = to_account_raw

    to_account = round(max(0.0, to_account), 2)
    to_pay = round(max(0.0, total_hs - to_account), 2)
    return SplitHsResult(to_account=to_account, to_pay=to_pay)


def route_hs_for_period(
    total_hs: float,
    policy: str,
    franchise_hours: float,
    franchise_consumed_in_period: float,
    current_balance: float,
    max_balance: float | None = None,
    *,
    manual_to_account: float | None = None,
    manual_to_pay: float | None = None,
) -> SplitHsResult:
    """Routage HS selon politique entreprise."""
    total_hs = max(0.0, round(float(total_hs), 2))
    if total_hs <= 0:
        return SplitHsResult(to_account=0.0, to_pay=0.0)

    if policy == "pay_all":
        return SplitHsResult(to_account=0.0, to_pay=total_hs)

    if policy == "account_all":
        return SplitHsResult(to_account=total_hs, to_pay=0.0)

    if policy == "manual":
        to_account = round(max(0.0, float(manual_to_account or 0)), 2)
        to_pay = round(max(0.0, float(manual_to_pay or 0)), 2)
        if round(to_account + to_pay, 2) != total_hs:
            return SplitHsResult(to_account=0.0, to_pay=total_hs)
        return SplitHsResult(to_account=to_account, to_pay=to_pay)

    cap = None if policy == "account_all" else max_balance
    return split_hs_for_period(
        total_hs,
        franchise_hours,
        franchise_consumed_in_period,
        current_balance,
        cap,
    )


def _movement_signed_hours(movement_type: str, hours: float) -> float:
    h = abs(float(hours))
    if movement_type in _CREDIT_TYPES:
        return h
    if movement_type in _DEBIT_TYPES:
        return -h
    if movement_type == "adjustment":
        return float(hours)
    return 0.0


def compute_balance_from_movements(movements: list[dict[str, Any]]) -> float:
    """Solde compte = somme des mouvements validés ou appliqués en paie."""
    total = 0.0
    for m in movements:
        status = str(m.get("status") or "")
        if status not in _ACTIVE_STATUSES:
            continue
        mtype = str(m.get("movement_type") or "")
        hours = float(m.get("hours") or 0)
        total += _movement_signed_hours(mtype, hours)
    return round(total, 2)


def compute_acquired_and_taken(movements: list[dict[str, Any]]) -> tuple[float, float]:
    """Retourne (heures créditées, heures consommées en récup)."""
    acquired = 0.0
    taken = 0.0
    for m in movements:
        if str(m.get("status") or "") not in _ACTIVE_STATUSES:
            continue
        mtype = str(m.get("movement_type") or "")
        hours = abs(float(m.get("hours") or 0))
        if mtype in _CREDIT_TYPES or (mtype == "adjustment" and float(m.get("hours") or 0) > 0):
            acquired += hours
        elif mtype == "debit_recovery":
            taken += hours
    return round(acquired, 2), round(taken, 2)


def can_debit_recovery(balance: float, hours: float) -> bool:
    return round(float(balance), 2) >= round(max(0.0, float(hours)), 2)


def sum_hs_from_payroll_events(events: list[dict[str, Any]]) -> float:
    total = 0.0
    for ev in events:
        ev_type = str(ev.get("type") or "")
        if ev_type in _HS_EVENT_TYPES or "hs" in ev_type:
            if ev_type.startswith("travail_hs"):
                total += float(ev.get("heures") or 0)
    return round(total, 2)


def reduce_payroll_hs_events(
    events: list[dict[str, Any]],
    hours_to_defer: float,
) -> tuple[list[dict[str, Any]], float]:
    """
    Retire des heures HS des événements de paie (HS25 puis HS50) pour crédit compte.
    Retourne (événements modifiés, heures effectivement différées).
    """
    remaining = round(max(0.0, float(hours_to_defer)), 2)
    if remaining <= 0:
        return events, 0.0

    def _hs_sort_key(ev: dict[str, Any]) -> tuple[int, Any]:
        t = str(ev.get("type") or "")
        order = 0 if t == "travail_hs25" else 1 if t == "travail_hs50" else 2
        return (order, ev.get("jour"), ev.get("mois"))

    sorted_indices = sorted(range(len(events)), key=lambda i: _hs_sort_key(events[i]))
    mutable = [dict(e) for e in events]
    deferred = 0.0

    for idx in sorted_indices:
        if remaining <= 0:
            break
        ev = mutable[idx]
        ev_type = str(ev.get("type") or "")
        if ev_type not in _HS_EVENT_TYPES:
            continue
        heures = float(ev.get("heures") or 0)
        if heures <= 0:
            continue
        take = min(heures, remaining)
        ev["heures"] = round(heures - take, 2)
        remaining = round(remaining - take, 2)
        deferred = round(deferred + take, 2)

    out = [ev for ev in mutable if not (
        str(ev.get("type") or "") in _HS_EVENT_TYPES and float(ev.get("heures") or 0) <= 0
    )]
    return out, deferred


def reduce_hs_in_calendar(
    calendrier: list[dict[str, Any]],
    hours_to_defer: float,
) -> tuple[list[dict[str, Any]], float]:
    """Réduit les heures HS dans le calendrier étendu bulletin (comme hook CET)."""
    remaining = round(max(0.0, float(hours_to_defer)), 2)
    if remaining <= 0:
        return calendrier, 0.0

    deferred = 0.0
    updated: list[dict[str, Any]] = []

    for jour in reversed(calendrier):
        if remaining <= 0:
            updated.append(jour)
            continue
        entry = dict(jour)
        ev_type = str(entry.get("type") or "")
        if ev_type not in _HS_EVENT_TYPES:
            updated.append(entry)
            continue
        heures = float(entry.get("heures") or 0)
        if heures <= 0:
            updated.append(entry)
            continue
        deduct = min(heures, remaining)
        entry["heures"] = round(heures - deduct, 2)
        remaining = round(remaining - deduct, 2)
        deferred = round(deferred + deduct, 2)
        if entry["heures"] > 0:
            updated.append(entry)

    updated.reverse()
    return updated, deferred


# ---------------------------------------------------------------------------
# Heures de récupération (repos compensateur de remplacement) — 05/11/2026.
# Spec : docs/superpowers/specs/2026-11-05-heures-de-recuperation-design.md
# ---------------------------------------------------------------------------

#: Taux légaux à défaut d'accord (C. trav. L3121-36) : repli quand le barème
#: de la société ne donne pas le sien.
MAJORATIONS_LEGALES: dict[str, float] = {"travail_hs25": 0.25, "travail_hs50": 0.5}


@dataclass(frozen=True)
class MiseAuCompteur:
    calendrier: list[dict[str, Any]]
    heures_sup_au_compteur: float
    heures_sup_payees: float
    repos_credite: float
    heures_par_type: dict[str, float]


def _date_de(ev: dict[str, Any]) -> Any:
    from datetime import date as _date

    brut = ev.get("date_complete")
    if not brut:
        return None
    try:
        return _date.fromisoformat(str(brut)[:10])
    except ValueError:
        return None


def mettre_hs_au_compteur(
    calendrier: list[dict[str, Any]],
    *,
    majorations: dict[str, float] | None = None,
    bornes: tuple[Any, Any] | None = None,
    solde: float = 0.0,
    plafond: float | None = None,
    heures_a_payer: float = 0.0,
) -> MiseAuCompteur:
    """Retire du calendrier de paie les heures sup qui vont au compteur et
    calcule le repos crédité, à l'équivalent majoré (L3121-28, L3121-33 II 2° :
    « paiement des heures supplémentaires, ainsi que des majorations » remplacé
    par un repos équivalent — 1 h à 25 % = 1 h 15).

    - `bornes` : la fenêtre des variables ; les heures sup hors fenêtre ne
      sont pas de ce bulletin et ne bougent pas.
    - `plafond` : solde maximal du compteur, en heures de repos ; au-delà, les
      heures restent payées.
    - `heures_a_payer` : heures sup que la RH a choisi de payer ce mois-ci.
    Les derniers jours partent au compteur en premier.
    """
    taux = {**MAJORATIONS_LEGALES, **(majorations or {})}
    eligibles: list[int] = []
    for i, ev in enumerate(calendrier):
        if str(ev.get("type") or "") not in taux:
            continue
        if float(ev.get("heures") or 0) <= 0:
            continue
        if bornes is not None:
            d = _date_de(ev)
            if d is None or not (bornes[0] <= d <= bornes[1]):
                continue
        eligibles.append(i)

    total = round(sum(float(calendrier[i].get("heures") or 0) for i in eligibles), 2)
    a_mettre = round(max(0.0, total - max(0.0, float(heures_a_payer or 0))), 2)
    place = (
        None
        if plafond is None
        else round(max(0.0, float(plafond) - float(solde or 0)), 2)
    )

    def _cle(i: int) -> tuple:
        d = _date_de(calendrier[i])
        return (d.toordinal() if d else 0, i)

    nouveau = [dict(ev) for ev in calendrier]
    repos = 0.0
    mises = 0.0
    par_type: dict[str, float] = {}
    for i in sorted(eligibles, key=_cle, reverse=True):
        if a_mettre <= 0 or (place is not None and place <= 0):
            break
        ev = nouveau[i]
        t = str(ev["type"])
        coef = 1.0 + float(taux[t])
        heures = float(ev.get("heures") or 0)
        prise = min(heures, a_mettre)
        if place is not None:
            prise = min(prise, round(place / coef, 2))
        prise = round(prise, 2)
        if prise <= 0:
            break
        ev["heures"] = round(heures - prise, 2)
        a_mettre = round(a_mettre - prise, 2)
        mises = round(mises + prise, 2)
        credit = round(prise * coef, 2)
        repos = round(repos + credit, 2)
        if place is not None:
            place = round(place - credit, 2)
        par_type[t] = round(par_type.get(t, 0.0) + prise, 2)

    if mises <= 0:
        sortie = list(calendrier)
    else:
        vides = {i for i in eligibles if float(nouveau[i].get("heures") or 0) <= 0}
        sortie = [ev for i, ev in enumerate(nouveau) if i not in vides]
    return MiseAuCompteur(
        calendrier=sortie,
        heures_sup_au_compteur=mises,
        heures_sup_payees=round(total - mises, 2),
        repos_credite=repos,
        heures_par_type=par_type,
    )


def _avant_ou_egal(m: dict[str, Any], annee: int, mois: int) -> bool:
    a = int(m.get("year") or 0)
    mm = m.get("month")
    # Un mouvement sans mois (ancien solde d'ouverture) vaut pour janvier.
    mm = int(mm) if mm is not None else 1
    return (a, mm) <= (annee, mois)


def solde_au(movements: list[dict[str, Any]], annee: int, mois: int) -> float:
    """Solde du compteur à la fin du mois : tous les mouvements actifs jusqu'au
    mois inclus, toutes années confondues. Un repos non pris ne se perd pas au
    1er janvier ; il reste dû jusqu'à ce qu'il soit pris ou payé."""
    return compute_balance_from_movements(
        [m for m in movements if _avant_ou_egal(m, annee, mois)]
    )


def mouvements_hors_paie_du_mois(
    movements: list[dict[str, Any]], annee: int, mois: int
) -> list[dict[str, Any]]:
    """Les mouvements sans les crédits que la paie du mois a déjà posés : un
    recalcul (ou le bac à sable) refait ce crédit, il ne doit pas compter deux
    fois dans le solde ni dans le plafond."""
    return [
        m
        for m in movements
        if not (
            str(m.get("movement_type") or "") == "credit_hs"
            and str(m.get("source") or "") == "payroll_auto"
            and int(m.get("year") or 0) == annee
            and m.get("month") is not None
            and int(m["month"]) == mois
        )
    ]


def etat_du_mois(
    movements: list[dict[str, Any]],
    annee: int,
    mois: int,
    *,
    credit_du_calcul: float | None = None,
) -> dict[str, Any]:
    """Ce que le bulletin imprime : heures acquises du mois, heures prises (avec
    leur date), heures payées, solde à la fin du mois (C. trav. D3171-11).

    `credit_du_calcul` : le crédit que le calcul en cours pose pour ce mois ;
    il remplace celui d'une génération précédente."""
    base = movements
    if credit_du_calcul is not None:
        base = mouvements_hors_paie_du_mois(movements, annee, mois)
        if credit_du_calcul > 0:
            base = [
                *base,
                {
                    "movement_type": "credit_hs",
                    "hours": float(credit_du_calcul),
                    "year": annee,
                    "month": mois,
                    "status": "validated",
                    "source": "payroll_auto",
                },
            ]
    acquis = pris = paye = 0.0
    acquis_annee = pris_annee = 0.0
    prises: list[dict[str, Any]] = []
    for m in base:
        if str(m.get("status") or "") not in _ACTIVE_STATUSES:
            continue
        if int(m.get("year") or 0) == annee and m.get("month") is not None and int(m["month"]) <= mois:
            t_ = str(m.get("movement_type") or "")
            h_ = float(m.get("hours") or 0)
            if t_ == "credit_hs" or (t_ == "adjustment" and h_ > 0):
                acquis_annee += abs(h_)
            elif t_ in ("debit_recovery", "debit_payout") or (t_ == "adjustment" and h_ < 0):
                pris_annee += abs(h_)
        if int(m.get("year") or 0) != annee or m.get("month") is None or int(m["month"]) != mois:
            continue
        t = str(m.get("movement_type") or "")
        h = float(m.get("hours") or 0)
        if t == "credit_hs" or (t == "adjustment" and h > 0):
            acquis += abs(h)
        elif t == "adjustment" and h < 0:
            pris += abs(h)
        elif t == "debit_recovery":
            pris += abs(h)
            jours = (m.get("metadata") or {}).get("jours") or {}
            for jour, heures in sorted(jours.items()):
                prises.append({"date": str(jour)[:10], "heures": round(float(heures), 2)})
        elif t == "debit_payout":
            paye += abs(h)
    return {
        "acquis": round(acquis, 2),
        "pris": round(pris, 2),
        "paye": round(paye, 2),
        "solde": solde_au(base, annee, mois),
        "acquis_annee": round(acquis_annee, 2),
        "pris_annee": round(pris_annee, 2),
        "prises": prises,
    }


def heures_payees_du_mois(
    movements: list[dict[str, Any]], annee: int, mois: int
) -> float:
    """Heures du compteur que la RH a choisi de payer sur le bulletin du mois."""
    total = 0.0
    for m in movements:
        if str(m.get("movement_type") or "") != "debit_payout":
            continue
        if str(m.get("status") or "") not in _ACTIVE_STATUSES:
            continue
        if int(m.get("year") or 0) != annee or m.get("month") is None or int(m["month"]) != mois:
            continue
        total += abs(float(m.get("hours") or 0))
    return round(total, 2)


def saisie_paiement_solde(heures: float, taux_horaire_base: float) -> dict[str, Any]:
    """La ligne du bulletin qui paie un solde de récupération : une prime au
    taux horaire de base (le repos est déjà l'équivalent majoré), soumise
    comme un salaire, SANS les régimes des heures sup — une heure mise en
    repos puis payée les a perdus (BOSS heures sup ; BOFiP
    BOI-RSA-CHAMP-20-50-20-40 ; spec 2026-11-03 « Tranché le 03/11 »)."""
    return {
        "prime_id": "paiement_solde_recuperation",
        "libelle": "Paiement solde heures de récupération",
        "montant": round(float(heures) * float(taux_horaire_base), 2),
        "quantity": round(float(heures), 2),
        "soumise_a_cotisations": True,
        "soumise_a_impot": True,
    }
