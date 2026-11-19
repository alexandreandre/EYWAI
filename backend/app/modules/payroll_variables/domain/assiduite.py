"""Prime d'assiduité perdue par une absence relevée au calendrier (domaine pur).

Retour d'Elsa du 17/11/2026 :
- Mont Blanc : 50 € par mois (25 € à mi-temps), perdus s'il y a une absence
  injustifiée ou un arrêt dans le mois ; CP, récupération, JTC et repos
  compensateur ne font rien perdre ;
- LEWIS : 6 € par semaine sans absence, mêmes exclusions.

Chez ces sociétés, les absences sont au calendrier (arrêts posés par « Arrêts
& IJ », journées non travaillées), pas dans les demandes d'absence : la règle
lit donc le calendrier prévu et réel de la fenêtre des variables.

Un jour fait perdre la prime quand :
- le prévu ou le réel est un arrêt (`arret…`), une absence non rémunérée
  (le type que la RH donne à une absence injustifiée à l'écran) ou un jour
  « absent, type à donner » ;
- ou un jour « travail » prévu a un réel saisi à 0 (journée non faite), sans
  absence validée ce jour-là (un JTC n'écrit pas le calendrier).
Le congé maternité, paternité ou d'adoption ne fait jamais perdre la prime
(une prime retirée pour ce motif exposerait à une discrimination liée à la
parentalité).
La liste des types peut être remplacée par la règle (`types_qui_font_perdre`).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

from app.modules.payroll_variables.domain.jours_travailles import TYPES_TRAVAIL

#: Types qui font perdre la prime, en plus de tout type qui commence par
#: « arret ».
TYPES_QUI_FONT_PERDRE = frozenset(
    {"absence_injustifiee", "absence_non_remuneree", "absent_a_typer", "maladie"}
)
#: Arrêts qui ne font jamais perdre la prime.
NATURES_PROTEGEES = ("maternite", "paternite", "adoption", "accueil_enfant")

DUREE_LEGALE_HEBDO = 35.0


def _heures(valeur: Any) -> float | None:
    if valeur is None or valeur == "":
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _type(entree: Mapping[str, Any] | None) -> str:
    return str((entree or {}).get("type") or "").strip().lower()


def _protege(entree: Mapping[str, Any] | None) -> bool:
    texte = f"{_type(entree)} {str((entree or {}).get('arret_type') or '').lower()}"
    return any(n in texte for n in NATURES_PROTEGEES)


def motif_de_perte(
    prevu: Mapping[str, Any] | None,
    reel: Mapping[str, Any] | None,
    types: Iterable[str] | None = None,
    absence_validee: bool = False,
) -> str | None:
    """Le motif qui fait perdre la prime ce jour-là, ou None."""
    choisis = {str(t).lower() for t in types} if types else None
    if _protege(prevu) or _protege(reel):
        return None
    for entree in (reel, prevu):
        t = _type(entree)
        if not t:
            continue
        if choisis is not None:
            if t in choisis or ("arret" in choisis and t.startswith("arret")):
                return t
        elif t.startswith("arret") or t in TYPES_QUI_FONT_PERDRE:
            return t
    if (
        not absence_validee
        and _type(prevu) in TYPES_TRAVAIL
        and (_heures((prevu or {}).get("heures_prevues")) or 0) > 0
        and _type(reel) in TYPES_TRAVAIL | {""}
        and _heures((reel or {}).get("heures_faites")) == 0
    ):
        return "journee_non_faite"
    return None


def jours_qui_font_perdre(
    prevu: Mapping[date, Mapping[str, Any]],
    reel: Mapping[date, Mapping[str, Any]],
    debut: date,
    fin: date,
    types: Iterable[str] | None = None,
    jours_absence_validee: set[date] | None = None,
    jours_demandes_qui_font_perdre: set[date] | None = None,
) -> dict[date, str]:
    """Les jours de [debut, fin] qui font perdre la prime, avec leur motif :
    ceux du calendrier, et les demandes d'absence validées des types cochés."""
    validees = jours_absence_validee or set()
    demandes = jours_demandes_qui_font_perdre or set()
    out: dict[date, str] = {}
    jour = debut
    while jour <= fin:
        motif = motif_de_perte(prevu.get(jour), reel.get(jour), types, jour in validees)
        if motif:
            out[jour] = motif
        elif jour in demandes:
            out[jour] = "demande_d_absence"
        jour += timedelta(days=1)
    return out


def _a_un_calendrier(
    prevu: Mapping[date, Mapping[str, Any]],
    reel: Mapping[date, Mapping[str, Any]],
    debut: date,
    fin: date,
) -> bool:
    """Un jour au moins du calendrier est renseigné : sans calendrier, rien ne
    dit si le salarié a été absent. Un mois tout en congés payés garde la
    prime (les CP ne font rien perdre)."""
    jour = debut
    while jour <= fin:
        if prevu.get(jour) or reel.get(jour):
            return True
        jour += timedelta(days=1)
    return False


def evaluer_assiduite_du_mois(
    prevu: Mapping[date, Mapping[str, Any]],
    reel: Mapping[date, Mapping[str, Any]],
    jours_absence: set[date],
    debut: date,
    fin: date,
    *,
    montant: float,
    duree_hebdomadaire: float | None = None,
    proratiser_temps_partiel: bool = True,
    types: Iterable[str] | None = None,
    jours_demandes_qui_font_perdre: set[date] | None = None,
) -> dict[str, Any]:
    """`{amount, quantity, details}` pour la fenêtre [debut, fin].

    `jours_absence` : les jours couverts par une absence validée (ils ne sont
    jamais une « journée non faite ») ; `jours_demandes_qui_font_perdre` :
    ceux des demandes d'absence des types cochés sur la règle.

    À temps partiel, le montant suit la durée du contrat (17,5 h → la moitié).
    """
    perdus = jours_qui_font_perdre(
        prevu, reel, debut, fin, types, jours_absence, jours_demandes_qui_font_perdre
    )
    details: dict[str, Any] = {"du": debut.isoformat(), "au": fin.isoformat()}
    if perdus:
        details["perdue"] = [
            {"jour": j.isoformat(), "motif": m} for j, m in sorted(perdus.items())
        ]
        return {"amount": 0.0, "quantity": 0.0, "details": details}
    if not _a_un_calendrier(prevu, reel, debut, fin):
        details["perdue"] = "aucun calendrier saisi"
        return {"amount": 0.0, "quantity": 0.0, "details": details}
    facteur = 1.0
    duree = _heures(duree_hebdomadaire)
    if proratiser_temps_partiel and duree and 0 < duree < DUREE_LEGALE_HEBDO:
        facteur = duree / DUREE_LEGALE_HEBDO
        details["prorata_temps_partiel"] = round(facteur, 4)
    return {"amount": round(float(montant or 0) * facteur, 2), "quantity": 1.0, "details": details}


def lundis_de_la_fenetre(debut: date, fin: date) -> list[date]:
    """Les semaines dont le dimanche tombe dans la fenêtre : chaque semaine est
    payée une fois, dans le mois où elle se termine, quand elle a été vécue
    en entier."""
    dimanche = debut + timedelta(days=(6 - debut.weekday()) % 7)
    out: list[date] = []
    while dimanche <= fin:
        out.append(dimanche - timedelta(days=6))
        dimanche += timedelta(days=7)
    return out


def evaluer_assiduite_des_semaines(
    prevu: Mapping[date, Mapping[str, Any]],
    reel: Mapping[date, Mapping[str, Any]],
    jours_absence_validee: set[date],
    debut: date,
    fin: date,
    *,
    montant_par_semaine: float,
    types: Iterable[str] | None = None,
    jours_demandes_qui_font_perdre: set[date] | None = None,
    debut_contrat: date | None = None,
) -> dict[str, Any]:
    """Semaines sans absence, payées dans le mois de leur dimanche.

    Le calendrier doit couvrir la semaine entière (lundi compris, même s'il
    tombe le mois d'avant). Une semaine compte si un jour au moins est
    renseigné au calendrier, depuis l'entrée, et qu'aucun jour ne fait perdre
    la prime. Une semaine toute en congés payés est payée.
    """
    semaines: list[dict[str, Any]] = []
    eligibles = 0
    for lundi in lundis_de_la_fenetre(debut, fin):
        dimanche = lundi + timedelta(days=6)
        perdus = jours_qui_font_perdre(
            prevu, reel, lundi, dimanche, types, jours_absence_validee, jours_demandes_qui_font_perdre
        )
        if perdus:
            semaines.append(
                {
                    "monday": lundi.isoformat(),
                    "eligible": False,
                    "reason": "absence",
                    "jours": [d.isoformat() for d in sorted(perdus)],
                }
            )
            continue
        depuis = max(lundi, debut_contrat) if debut_contrat else lundi
        if not _a_un_calendrier(prevu, reel, depuis, dimanche):
            semaines.append({"monday": lundi.isoformat(), "eligible": False, "reason": "no_work"})
            continue
        eligibles += 1
        semaines.append({"monday": lundi.isoformat(), "eligible": True})
    return {
        "quantity": float(eligibles),
        "amount": round(float(montant_par_semaine or 0) * eligibles, 2),
        "details": {"weeks": semaines},
    }
