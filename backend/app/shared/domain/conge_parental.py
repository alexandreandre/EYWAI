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
from datetime import date
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
