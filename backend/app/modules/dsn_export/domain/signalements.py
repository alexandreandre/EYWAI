"""Arrêts à signaler (DSN 04) et reprises anticipées (DSN 05), avec leur date limite.

Cahier technique DSN 2026.1 : § 5.3 (arrêt : « dans les 5 jours après la prise
de connaissance », ou avec la DSN mensuelle en subrogation) ; § 5.4 (reprise :
« qu'en cas de reprise anticipée », « dans les cinq jours ouvrables qui suivent
la reprise »). Guide net-entreprises des arrêts : une prolongation ne se signale
pas, elle passe dans la DSN mensuelle. Fonctions pures.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional

from app.modules.dsn_export.domain.evenements import _jours, periodes_d_arret
from app.modules.dsn_export.domain.usages_signalement import NATURE_ARRET, NATURE_REPRISE

#: À partir de 50 salariés, la DSN du mois M est due le 5 de M+1, sinon le 15.
SEUIL_ECHEANCE = 50


@dataclass(frozen=True)
class SignalementEnvoye:
    employee_id: str
    nature: str
    motif: str
    debut: date
    fin_prevue: date
    essai: bool
    genere_le: date


@dataclass(frozen=True)
class SignalementAFaire:
    employee_id: str
    nature: str
    motif: str
    debut: date
    #: Fin de l'arrêt (04) ; fin déclarée au signalement d'arrêt (05).
    fin_prevue: date
    subrogation: bool
    connu_le: date
    a_deposer_avant: date
    date_reprise: Optional[date] = None


def echeance_mensuelle(jour: date, effectif: int) -> date:
    annee, mois = (jour.year + 1, 1) if jour.month == 12 else (jour.year, jour.month + 1)
    return date(annee, mois, 5 if effectif >= SEUIL_ECHEANCE else 15)


def ajouter_jours_ouvrables(jour: date, n: int) -> date:
    """n jours ouvrables après ``jour`` : les dimanches ne comptent pas (les
    fériés comptent : c'est la lecture la plus stricte)."""
    while n > 0:
        jour += timedelta(days=1)
        if jour.weekday() != 6:
            n -= 1
    return jour


def _saisie(absence: Dict[str, Any]) -> Optional[date]:
    try:
        return date.fromisoformat(str(absence.get("created_at") or "")[:10])
    except ValueError:
        return None


def _connu_le(absences: Iterable[Dict[str, Any]], debut: date, fin: date) -> date:
    """La saisie de la première demande de la période, jamais avant son premier
    jour : un arrêt connu d'avance se signale quand il commence."""
    saisies = [
        saisie
        for absence in absences
        if (jours := _jours(absence)) and debut <= jours[0] <= fin
        and (saisie := _saisie(absence))
    ]
    return max(min(saisies), debut) if saisies else debut


def signalements_a_faire(
    arrets: Mapping[str, List[Dict[str, Any]]],
    envoyes: Iterable[SignalementEnvoye],
    *,
    depuis: Optional[date],
    effectif: int,
) -> List[SignalementAFaire]:
    """Les signalements à déposer, du plus pressé au moins pressé.

    ``depuis`` : le premier jour dont les arrêts reviennent à Martine (avant,
    l'ancien logiciel les signalait). Un fichier d'essai ne vaut pas signalement.
    """
    reels = [e for e in envoyes if not e.essai]
    resultat: List[SignalementAFaire] = []
    for employee_id, absences in arrets.items():
        for periode in periodes_d_arret(absences):
            if depuis and periode.debut < depuis:
                continue
            les_siens = [
                e for e in reels
                if e.employee_id == employee_id
                and e.motif == periode.motif
                and e.debut == periode.debut
            ]
            arrets_envoyes = [e for e in les_siens if e.nature == NATURE_ARRET]
            connu = _connu_le(absences, periode.debut, periode.fin)
            if not arrets_envoyes:
                limite = (
                    echeance_mensuelle(connu, effectif)
                    if periode.subrogation
                    else connu + timedelta(days=5)
                )
                resultat.append(SignalementAFaire(
                    employee_id, NATURE_ARRET, periode.motif, periode.debut, periode.fin,
                    periode.subrogation, connu, limite,
                ))
                continue
            declaree = max(arrets_envoyes, key=lambda e: e.genere_le).fin_prevue
            reprise_envoyee = any(e.nature == NATURE_REPRISE for e in les_siens)
            if periode.fin < declaree and not reprise_envoyee:
                reprise = periode.fin + timedelta(days=1)
                resultat.append(SignalementAFaire(
                    employee_id, NATURE_REPRISE, periode.motif, periode.debut, declaree,
                    periode.subrogation, connu, ajouter_jours_ouvrables(reprise, 5), reprise,
                ))
    return sorted(resultat, key=lambda s: (s.a_deposer_avant, s.employee_id))
