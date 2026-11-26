"""Congé parental d'éducation à temps plein : un congé sans solde qui dit son nom.

Retour d'Elsa du 26/11/2026 : il manquait la possibilité de poser un congé
parental. Sans nouvelle valeur d'enum (migration), il se saisit comme un congé
sans solde (`type = sans_solde`) dont le sous-type (`event_subtype`, texte
libre, lu ailleurs pour les seuls événements familiaux) vaut
`conge_parental_education`. La paie est celle d'un sans solde : aucune
rémunération, aucun congé payé acquis. Seuls changent le libellé (liste,
calendrier, bulletin) et le motif de suspension en DSN (632 au lieu de 501).

Sources, lues le 26/11/2026 :
- C. trav. L1225-47 (code.travail.gouv.fr, version du 11/03/2023) : « le
  bénéfice d'un congé parental d'éducation durant lequel le contrat de travail
  est suspendu » ;
- L1225-48 : « une durée initiale d'un an au plus », prolongeable deux fois ;
- L1225-50 : le salarié « informe son employeur du point de départ et de la
  durée » du congé : la date de fin prévue est connue à la saisie ;
- L1225-54 (modifié par la loi n° 2023-171 du 9 mars 2023, art. 18, version
  en vigueur depuis le 11/03/2023) : « La durée du congé parental d'éducation à
  temps plein est prise en compte pour moitié pour la détermination des droits
  que le salarié tient de son ancienneté. » ; à temps partiel, elle est
  assimilée à du travail effectif (hors de ce module : c'est un horaire réduit) ;
- L3141-5 : le congé parental ne figure pas parmi les périodes assimilées à du
  travail effectif pour les congés payés ;
- service-public.fr F2280 : « Pendant le congé, le salarié n'est pas rémunéré
  par son employeur pour la période non travaillée » ;
- cahier technique NEODeS 2026 (libellés dans dsn_export/domain/
  libelles_rubriques.py) : S21.G00.65.001 = 632 « Congé parental d'éducation ».
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

#: Sous-type (`absence_requests.event_subtype`) d'un congé sans solde qui est
#: un congé parental d'éducation à temps plein.
SOUS_TYPE_CONGE_PARENTAL = "conge_parental_education"

#: Type de demande sous lequel il s'enregistre (aucune valeur d'enum nouvelle).
TYPE_DEMANDE_CONGE_PARENTAL = "sans_solde"

LIBELLE_CONGE_PARENTAL = "Congé parental d'éducation"

#: Motif de suspension DSN (S21.G00.65.001).
MOTIF_DSN_CONGE_PARENTAL = "632"

#: Clés posées sur les jours du planning par la validation (clés serveur, cf.
#: absence_calendar.SERVER_OWNED_ABSENCE_KEYS) et relayées jusqu'au moteur.
CLE_MOTIF_ABSENCE = "motif_absence"
CLE_PERIODE_ABSENCE = "periode_absence"


def est_conge_parental(demande: Mapping[str, Any] | None) -> bool:
    """Vrai pour une demande d'absence qui est un congé parental d'éducation."""
    if not demande:
        return False
    return (
        str(demande.get("type") or "") == TYPE_DEMANDE_CONGE_PARENTAL
        and str(demande.get("event_subtype") or "") == SOUS_TYPE_CONGE_PARENTAL
    )


def est_jour_de_conge_parental(jour: Mapping[str, Any] | None) -> bool:
    """Vrai pour un jour de planning ou un événement de paie de congé parental."""
    return bool(jour) and str(jour.get(CLE_MOTIF_ABSENCE) or "") == SOUS_TYPE_CONGE_PARENTAL


def periode_de_la_demande(selected_days: Any) -> dict[str, str] | None:
    """{"debut", "fin"} en ISO : les bornes de la demande, ou None sans jour."""
    jours = sorted(str(j)[:10] for j in selected_days or [] if j)
    if not jours:
        return None
    return {"debut": jours[0], "fin": jours[-1]}


def periodes_chainees(demandes: Any) -> list[dict[str, str]]:
    """Les congés parentaux validés, une période par suite de demandes qui se
    suivent : une prolongation saisie le lendemain de la fin prévue repousse
    la fin du même congé (un seul bloc 632, fin prévisionnelle repoussée).

    Rend des {"debut", "fin"} en ISO, triés."""
    bornes: list[tuple[date, date]] = []
    for demande in demandes or ():
        if not est_conge_parental(demande):
            continue
        if str(demande.get("status") or "validated") != "validated":
            continue
        periode = periode_de_la_demande(demande.get("selected_days"))
        if periode:
            bornes.append((date.fromisoformat(periode["debut"]), date.fromisoformat(periode["fin"])))
    chaines: list[list[date]] = []
    for debut, fin in sorted(bornes):
        if chaines and debut <= chaines[-1][1] + timedelta(days=1):
            chaines[-1][1] = max(chaines[-1][1], fin)
        else:
            chaines.append([debut, fin])
    return [{"debut": d.isoformat(), "fin": f.isoformat()} for d, f in chaines]


def periode_du_jour(chaines: list[dict[str, str]], jour: str) -> dict[str, str] | None:
    """La période chaînée qui couvre ce jour ISO, ou None."""
    for chaine in chaines:
        if chaine["debut"] <= jour[:10] <= chaine["fin"]:
            return chaine
    return None


def jours_d_anciennete_neutralises(demandes: Any, jusqu_au: date) -> int:
    """Jours d'ancienneté que le congé parental à temps plein ne donne pas.

    C. trav. L1225-54 (version du 11/03/2023, loi n° 2023-171, art. 18 ; le
    texte d'avant le comptait déjà pour moitié) : « La durée du congé parental
    d'éducation à temps plein est prise en compte pour moitié pour la
    détermination des droits que le salarié tient de son ancienneté. » La
    moitié des jours calendaires de congé jusqu'à `jusqu_au` inclus, arrondie
    à l'entier inférieur (au bénéfice du salarié), est retirée."""
    jours: set[str] = set()
    limite = jusqu_au.isoformat()
    for demande in demandes or ():
        if not est_conge_parental(demande):
            continue
        if str(demande.get("status") or "validated") != "validated":
            continue
        jours.update(
            str(j)[:10] for j in demande.get("selected_days") or [] if str(j)[:10] <= limite
        )
    return len(jours) // 2


def decaler_l_anciennete(debut: date | None, jours_neutralises: int) -> date | None:
    """La date d'ancienneté repoussée des jours que le congé ne donne pas."""
    if debut is None or not jours_neutralises:
        return debut
    return debut + timedelta(days=int(jours_neutralises))


def bornes_du_jour(jour: Mapping[str, Any]) -> tuple[date, date] | None:
    """Les bornes du congé parental portées par un jour, ou None."""
    periode = jour.get(CLE_PERIODE_ABSENCE)
    if not isinstance(periode, Mapping):
        return None
    try:
        debut = date.fromisoformat(str(periode.get("debut"))[:10])
        fin = date.fromisoformat(str(periode.get("fin"))[:10])
    except ValueError:
        return None
    return (debut, fin) if debut <= fin else None


__all__ = [
    "decaler_l_anciennete",
    "jours_d_anciennete_neutralises",
    "periode_du_jour",
    "periodes_chainees",
    "CLE_MOTIF_ABSENCE",
    "CLE_PERIODE_ABSENCE",
    "LIBELLE_CONGE_PARENTAL",
    "MOTIF_DSN_CONGE_PARENTAL",
    "SOUS_TYPE_CONGE_PARENTAL",
    "TYPE_DEMANDE_CONGE_PARENTAL",
    "bornes_du_jour",
    "est_conge_parental",
    "est_jour_de_conge_parental",
    "periode_de_la_demande",
]
