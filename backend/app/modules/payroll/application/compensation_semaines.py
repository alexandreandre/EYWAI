"""Compensation des heures entre semaines — la règle de Gaëlle (Colorplast), en pur.

La règle légale compte les heures supplémentaires par semaine civile et permet
de retenir les heures manquantes d'une semaine courte. Gaëlle fait autrement,
et son classeur (`detail-heures-sup-06-2026-colorplast.xlsx`) l'écrit :

- par jour, l'écart entre les heures faites et l'horaire, positif ou négatif ;
- par semaine, `Majo 25 % = min(total, 4)` — négatif compris — et le reste à
  50 % (les 4 h sont celles entre le contrat de 39 h et 43 h) ;
- par mois de paie, la somme des semaines, **semaines négatives comprises**.

Une semaine courte mange d'abord les heures sup des autres semaines ; le
manque qu'elles ne couvrent pas est **retenu sur les derniers jours manqués**,
à leur vraie date. C'est une option société (spec
`2026-09-21-compensation-heures-entre-semaines-design.md`, corrigée le 22/09
par `2026-09-22-compensation-solde-negatif-retenu-design.md` : la première
version n'en retenait aucun, ce qui éloignait de Quadra de 649 € sur six mois).
Le compteur de récupération entre mois de Gaëlle reste hors périmètre.

Module pur : l'appelant fournit plannings, pointages, contrat et fenêtre.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Mapping, Sequence

from app.modules.payroll.planning_repli import mois_sans_pointage

#: Au-delà de 43 h dans la semaine, les heures sup passent à 50 %.
SEUIL_50_HEBDO = 43.0
#: Événements de la fenêtre que la compensation remplace.
_TYPES_REMPLACES = ("travail_hs25", "travail_hs50", "absence_injustifiee")
CLE_REGLAGE = "compensation_heures_entre_semaines"


def option_active(company_data: Mapping[str, Any] | None) -> bool:
    """L'option se lit dans `companies.settings`, un vrai booléen ; tout le reste vaut faux."""
    reglages = (company_data or {}).get("settings") or {}
    return reglages.get(CLE_REGLAGE) is True


def majorations(total: float, duree_hebdo: float) -> tuple[float, float]:
    """(heures à 25 %, heures à 50 %) d'une semaine dont l'écart total est `total`.

    Les heures à 25 % sont celles entre le contrat et 43 h : 4 h à 39 h, 8 h à
    35 h. Un total négatif reste négatif à 25 % — c'est la formule du classeur.
    """
    seuil25 = max(SEUIL_50_HEBDO - float(duree_hebdo), 0.0)
    majo25 = min(total, seuil25)
    majo50 = max(total - seuil25, 0.0)
    return round(majo25, 2), round(majo50, 2)


@dataclass(frozen=True)
class BilanSemaine:
    annee: int
    semaine: int
    total: float
    majo25: float
    majo50: float


@dataclass(frozen=True)
class Compensation:
    semaines: tuple[BilanSemaine, ...]
    net25: float
    net50: float
    #: Ce qui reste de négatif une fois les 25 % puis les 50 % mangés.
    solde_negatif: float
    #: Heures effectivement retenues sur des jours identifiés (positif ou nul).
    solde_retenu: float = 0.0
    #: Manque qu'aucun jour d'absence ne porte (positif ou nul) — anomalie, dite au bulletin.
    reliquat_sans_jour: float = 0.0

    def resume(self) -> dict[str, Any]:
        return {
            "semaines": [
                {"annee": s.annee, "semaine": s.semaine, "total": s.total, "majo25": s.majo25, "majo50": s.majo50}
                for s in self.semaines
            ],
            "net25": self.net25,
            "net50": self.net50,
            "solde_negatif": self.solde_negatif,
            "solde_retenu": self.solde_retenu,
            "reliquat_sans_jour": self.reliquat_sans_jour,
            "mention": mention(self),
        }


def _lundi(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _journee_type_par_jour_de_semaine(
    planned_all: list[dict[str, Any]],
) -> dict[tuple[int, int, int], float]:
    """Les heures d'une journée normale, par (année, mois, jour de semaine) :
    la valeur la plus fréquente des jours de travail prévus. Sert à mesurer ce
    qu'un salarié devait encore faire un jour d'absence déclarée partielle."""
    valeurs: dict[tuple[int, int, int], list[float]] = {}
    for p in planned_all:
        if p.get("type") != "travail":
            continue
        try:
            d = date(int(p["annee"]), int(p["mois"]), int(p["jour"]))
        except (KeyError, TypeError, ValueError):
            continue
        heures = float(p.get("heures_prevues") or 0.0)
        if heures > 0:
            valeurs.setdefault((d.year, d.month, d.weekday()), []).append(heures)
    return {
        cle: max(set(liste), key=lambda h: (liste.count(h), h)) for cle, liste in valeurs.items()
    }


def ecarts_par_semaine(
    planned_all: list[dict[str, Any]],
    actual_all: list[dict[str, Any]],
    fenetre: tuple[date, date],
) -> dict[tuple[int, int], float]:
    """Écart total (faites − prévues) de chaque semaine dont le lundi est dans la fenêtre.

    Comme l'analyseur : un jour prévu sans pointage est neutre, un mois sans
    aucun pointage aussi ; un jour non prévu compte pour ses heures faites.
    Une semaine n'apparaît que si un jour y a contribué.
    """
    debut, fin = fenetre
    reel_par_jour: dict[date, float] = {}
    for j in actual_all:
        try:
            d = date(int(j["annee"]), int(j["mois"]), int(j["jour"]))
        except (KeyError, TypeError, ValueError):
            continue
        reel_par_jour[d] = float(j.get("heures_faites") or 0.0)

    ecarts: dict[tuple[int, int], float] = {}
    vus: set[date] = set()
    journee_type = _journee_type_par_jour_de_semaine(planned_all)

    def ajouter(d: date, ecart: float) -> None:
        cle = (d.isocalendar()[0], d.isocalendar()[1])
        ecarts[cle] = round(ecarts.get(cle, 0.0) + ecart, 2)

    for p in planned_all:
        try:
            d = date(int(p["annee"]), int(p["mois"]), int(p["jour"]))
        except (KeyError, TypeError, ValueError):
            continue
        if not (debut <= _lundi(d) <= fin):
            continue
        type_prevu = str(p.get("type") or "")
        if type_prevu != "travail" and not type_prevu.startswith("absence"):
            continue
        if mois_sans_pointage(actual_all, annee=d.year, mois=d.month):
            continue
        vus.add(d)
        if d not in reel_par_jour:
            continue
        heures_prevues = float(p.get("heures_prevues") or 0.0)
        if type_prevu == "travail":
            ajouter(d, reel_par_jour[d] - heures_prevues)
            continue
        # Absence déclarée de X h : le salarié devait faire la journée moins X.
        # Sans pointage ou à 0 h, le jour est neutre (l'absence est retenue
        # ailleurs) ; s'il a travaillé, l'écart se mesure à ce qui restait dû.
        if reel_par_jour[d] <= 0:
            continue
        journee = journee_type.get((d.year, d.month, d.weekday()), heures_prevues)
        attendu = max(journee - heures_prevues, 0.0)
        ajouter(d, reel_par_jour[d] - attendu)

    for d, faites in reel_par_jour.items():
        if d in vus or not (debut <= _lundi(d) <= fin) or faites <= 0:
            continue
        ajouter(d, faites)
    return ecarts


def compenser(ecarts: Mapping[tuple[int, int], float], duree_hebdo: float) -> Compensation:
    """Somme des majorations de la fenêtre, semaines négatives comprises.

    Un net négatif à 25 % mange d'abord les heures à 50 % ; ce qui reste est le
    `solde_negatif`, que `absences_a_conserver` transforme en retenue.
    """
    semaines: list[BilanSemaine] = []
    for annee, semaine in sorted(ecarts):
        total = round(float(ecarts[(annee, semaine)]), 2)
        majo25, majo50 = majorations(total, duree_hebdo)
        semaines.append(BilanSemaine(annee, semaine, total, majo25, majo50))
    net25 = round(sum(s.majo25 for s in semaines), 2)
    net50 = round(sum(s.majo50 for s in semaines), 2)
    solde = 0.0
    if net25 < 0:
        absorbe = min(net50, -net25)
        net50 = round(net50 - absorbe, 2)
        solde = round(net25 + absorbe, 2)
        net25 = 0.0
    return Compensation(tuple(semaines), net25, net50, solde)


def _rang_de_retenue(cle: tuple[int, int, int, str]) -> tuple[int, str]:
    """Du jour le plus tardif au plus ancien ; à jour égal, la base avant les HS."""
    annee, mois, jour, type_ = cle
    return (-(annee * 10000 + mois * 100 + jour), type_)


def absences_a_conserver(
    absences: list[dict[str, Any]],
    solde_negatif: float,
) -> tuple[list[dict[str, Any]], float]:
    """Les absences injustifiées à garder, et ce qu'aucun jour ne porte.

    Les heures supplémentaires de la fenêtre ont absorbé les manques dans
    l'ordre des jours ; ce qui reste — `solde_negatif`, au signe près — est
    retenu sur les derniers jours manqués. C'est la convention que l'analyseur
    applique déjà à l'intérieur d'une semaine.

    Rend les absences gardées (triées par date, `heures` éventuellement réduit)
    et le reliquat qu'aucun jour ne porte, qui doit rester nul.
    """
    a_retenir = round(-float(solde_negatif or 0.0), 2)
    if a_retenir <= 0:
        return [], 0.0

    groupes: dict[tuple[int, int, int, str], dict[str, Any]] = {}
    for ev in absences:
        try:
            cle = (int(ev["annee"]), int(ev["mois"]), int(ev["jour"]), str(ev.get("type") or ""))
        except (KeyError, TypeError, ValueError):
            continue
        heures = round(float(ev.get("heures") or 0.0), 2)
        if cle in groupes:
            groupes[cle]["heures"] = round(groupes[cle]["heures"] + heures, 2)
        else:
            groupes[cle] = {**ev, "heures": heures}

    gardees: list[dict[str, Any]] = []
    restant = a_retenir
    for cle in sorted(groupes, key=_rang_de_retenue):
        if restant <= 0:
            break
        pris = min(groupes[cle]["heures"], restant)
        if pris > 0:
            gardees.append({**groupes[cle], "heures": round(pris, 2)})
            restant = round(restant - pris, 2)

    gardees.sort(key=lambda a: (int(a["annee"]), int(a["mois"]), int(a["jour"])))
    return gardees, round(max(restant, 0.0), 2)


def _dans_la_fenetre(ev: dict[str, Any], fenetre: tuple[date, date], annee: int, mois: int) -> bool:
    try:
        d = date(int(ev.get("annee") or annee), int(ev.get("mois") or mois), int(ev["jour"]))
    except (KeyError, TypeError, ValueError):
        return False
    return fenetre[0] <= d <= fenetre[1]


def appliquer(
    evenements: list[dict[str, Any]],
    fenetre: tuple[date, date],
    compensation: Compensation,
    *,
    annee: int,
    mois: int,
    absences_gardees: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Les événements d'un mois : heures sup de la fenêtre remplacées par les nets,
    absences injustifiées réduites à celles que l'appelant a décidé de retenir.

    Les nets sont posés au dernier jour de la fenêtre, donc dans le mois qui le
    contient ; les autres mois ne font que perdre leurs événements de la fenêtre.
    """
    gardees = {
        (int(a["annee"]), int(a["mois"]), int(a["jour"]), str(a.get("type") or "")): round(
            float(a.get("heures") or 0.0), 2
        )
        for a in absences_gardees
    }
    conserves: list[dict[str, Any]] = []
    for ev in evenements:
        type_ev = str(ev.get("type") or "")
        if ev.get("is_regularisation_anterieure") or not (
            type_ev.startswith(_TYPES_REMPLACES) and _dans_la_fenetre(ev, fenetre, annee, mois)
        ):
            conserves.append(ev)
            continue
        if not type_ev.startswith("absence_injustifiee"):
            continue  # heures sup : remplacées par les nets
        cle = (
            int(ev.get("annee") or annee),
            int(ev.get("mois") or mois),
            int(ev["jour"]),
            type_ev,
        )
        heures = gardees.pop(cle, None)
        if heures is not None and heures > 0:
            conserves.append({**ev, "heures": heures})

    fin = fenetre[1]
    if (fin.year, fin.month) == (annee, mois):
        for type_ev, heures in (
            ("travail_hs25", compensation.net25),
            ("travail_hs50", compensation.net50),
        ):
            if heures > 0:
                conserves.append(
                    {
                        "annee": fin.year,
                        "mois": fin.month,
                        "jour": fin.day,
                        "type": type_ev,
                        "heures": heures,
                        "compensation_semaines": True,
                    }
                )
    return sorted(conserves, key=lambda ev: int(ev.get("jour", 0)))


def appliquer_aux_mois(
    evenements_par_mois: Mapping[tuple[int, int], list[dict[str, Any]]],
    planned_all: list[dict[str, Any]],
    actual_all: list[dict[str, Any]],
    duree_hebdo: float,
    fenetre: tuple[date, date],
) -> tuple[dict[tuple[int, int], list[dict[str, Any]]], Compensation]:
    """L'orchestration que le générateur appelle : bilan, compensation, application.

    La fenêtre est à cheval sur deux mois : la décision de ce qui est retenu se
    prend **une seule fois**, sur toutes les absences de la fenêtre, avant
    d'appliquer mois par mois.
    """
    compensation = compenser(ecarts_par_semaine(planned_all, actual_all, fenetre), duree_hebdo)

    absences: list[dict[str, Any]] = []
    for (annee_m, mois_m), evts in evenements_par_mois.items():
        for ev in evts:
            if ev.get("is_regularisation_anterieure"):
                continue
            if not str(ev.get("type") or "").startswith("absence_injustifiee"):
                continue
            if not _dans_la_fenetre(ev, fenetre, annee_m, mois_m):
                continue
            absences.append(
                {
                    **ev,
                    "annee": int(ev.get("annee") or annee_m),
                    "mois": int(ev.get("mois") or mois_m),
                }
            )

    gardees, reliquat = absences_a_conserver(absences, compensation.solde_negatif)
    compensation = replace(
        compensation,
        solde_retenu=round(sum(float(a["heures"]) for a in gardees), 2),
        reliquat_sans_jour=reliquat,
    )
    return (
        {
            (annee, mois): appliquer(
                evts, fenetre, compensation, annee=annee, mois=mois, absences_gardees=gardees
            )
            for (annee, mois), evts in evenements_par_mois.items()
        },
        compensation,
    )


def _fr(valeur: float, decimales: int | None = None) -> str:
    texte = f"{valeur:.{decimales}f}" if decimales is not None else f"{valeur:g}"
    return texte.replace("-", "−").replace(".", ",")


def mention(compensation: Compensation) -> str:
    """La phrase du bulletin : les semaines, leurs écarts, les nets."""
    semaines = " · ".join(
        f"S{s.semaine} {'+' if s.total >= 0 else ''}{_fr(s.total, 1)}" for s in compensation.semaines
    )
    texte = (
        f"Heures compensées entre semaines (option société) : {semaines} → "
        f"{_fr(compensation.net25)} h à 25 %, {_fr(compensation.net50)} h à 50 %."
    )
    if compensation.solde_retenu > 0:
        texte += f" Solde retenu : −{_fr(compensation.solde_retenu)} h."
    if compensation.reliquat_sans_jour > 0:
        texte += f" dont {_fr(compensation.reliquat_sans_jour)} h sans jour identifié."
    return texte


def avec_saisie_manuelle(resume: Mapping[str, Any], hs25_saisies: float, hs50_saisies: float) -> dict:
    """Le moteur fait primer les heures sup saisies à la main sur le calendrier.

    Quand une saisie existe et diffère des nets compensés, le résumé la porte
    (`heures_saisies`) et la mention le dit, pour que le bulletin reste vrai.
    Le résumé d'origine n'est pas modifié.
    """
    hs25 = round(float(hs25_saisies or 0.0), 2)
    hs50 = round(float(hs50_saisies or 0.0), 2)
    if hs25 <= 0 and hs50 <= 0:
        return dict(resume)
    nets = (round(float(resume.get("net25") or 0.0), 2), round(float(resume.get("net50") or 0.0), 2))
    if (hs25, hs50) == nets:
        return dict(resume)
    enrichi = dict(resume)
    enrichi["heures_saisies"] = {"hs25": hs25, "hs50": hs50}
    enrichi["mention"] = (
        f"{resume.get('mention') or ''} Heures supplémentaires saisies à la main retenues "
        f"sur le bulletin : {_fr(hs25)} h à 25 %, {_fr(hs50)} h à 50 %."
    ).strip()
    return enrichi


__all__ = [
    "BilanSemaine",
    "Compensation",
    "absences_a_conserver",
    "appliquer",
    "appliquer_aux_mois",
    "avec_saisie_manuelle",
    "compenser",
    "ecarts_par_semaine",
    "majorations",
    "mention",
]
