"""Nouveau contrat d'un salarié parti : la fiche repart sur un nouveau contrat.

Règles pures, sans base. Spécification : docs/superpowers/specs/2026-10-03-nouveau-contrat-design.md.

Le contrat précédent est rangé dans les contrats passés ; la fiche porte le
nouveau contrat et redevient active. Les mois qu'il couvre deviennent payables
par la seule date d'entrée de la fiche : aucune autre règle de paie ne change.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

TYPES_DE_CONTRAT = ("CDI", "CDD", "Apprentissage", "Contrat de professionnalisation")
STATUTS_PARTIS = ("parti", "sorti", "inactif")
DUREE_HEBDO_MAX = 48.0
DUREE_LEGALE = 35.0


def _date(valeur: Any) -> date | None:
    if isinstance(valeur, date):
        return valeur
    if isinstance(valeur, str) and valeur.strip():
        try:
            return date.fromisoformat(valeur.strip()[:10])
        except ValueError:
            return None
    return None


def _jj_mm_aaaa(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _mm_aaaa(d: date) -> str:
    return d.strftime("%m/%Y")


def _rang(d: date) -> int:
    return d.year * 12 + d.month


def est_cdd(contract_type: str | None) -> bool:
    t = (contract_type or "").lower()
    return "cdd" in t and "cdi" not in t


def valeur_salaire(salaire_de_base: Any) -> float | None:
    if isinstance(salaire_de_base, Mapping):
        salaire_de_base = salaire_de_base.get("valeur")
    try:
        return float(salaire_de_base) if salaire_de_base is not None else None
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ContratPrecedent:
    """Le contrat que « Nouveau contrat » range dans les contrats passés."""

    contract_type: str
    debut: date
    fin: date


@dataclass(frozen=True)
class Demande:
    date_debut: date
    contract_type: str
    date_fin: date | None
    duree_hebdomadaire: float
    salaire_mensuel: float
    job_title: str | None = None
    reprendre_anciennete: bool = False


def contrat_precedent(
    fiche: Mapping[str, Any], dernier_depart: Mapping[str, Any] | None
) -> ContratPrecedent | None:
    """Début et fin du contrat que porte la fiche d'un salarié parti.

    Début : le début d'exécution, à défaut la date d'entrée (comme la garde de
    présence de la paie). Fin : le dernier jour du départ le plus récent, à
    défaut la date de fin de contrat de la fiche.
    """
    debut = _date(fiche.get("date_debut_execution")) or _date(fiche.get("hire_date"))
    if debut is None:
        return None
    fin = _date((dernier_depart or {}).get("last_working_day")) or _date(
        fiche.get("contract_end_date")
    )
    if fin is None or fin < debut:
        return None
    type_ = str(fiche.get("contract_type") or "").strip() or "Contrat"
    return ContratPrecedent(contract_type=type_, debut=debut, fin=fin)


def raison_indisponible(
    fiche: Mapping[str, Any], precedent: ContratPrecedent | None
) -> str | None:
    """Pourquoi le bouton n'a rien à proposer pour cette fiche, ou None."""
    statut = str(fiche.get("employment_status") or "actif").lower()
    if statut == "en_sortie":
        return (
            "Le départ n'est pas clôturé. Clôturez-le dans Départs, puis revenez ici "
            "pour le nouveau contrat."
        )
    if statut not in STATUTS_PARTIS:
        return "Un nouveau contrat se crée sur la fiche d'un salarié parti."
    if precedent is None:
        return (
            "La fin du contrat précédent est inconnue : ni départ daté, ni date de fin "
            "sur la fiche."
        )
    return None


def premier_jour_possible(precedent: ContratPrecedent) -> date:
    """Le 1er du mois qui suit la fin du contrat précédent : un bulletin par mois."""
    fin = precedent.fin
    return date(fin.year + (fin.month == 12), fin.month % 12 + 1, 1)


def raison_du_refus(
    fiche: Mapping[str, Any],
    precedent: ContratPrecedent | None,
    demande: Demande,
    *,
    bulletin_du_dernier_mois: bool,
    rang_de_bascule: int | None,
) -> str | None:
    """Pourquoi la demande ne peut pas être enregistrée, ou None."""
    indisponible = raison_indisponible(fiche, precedent)
    if indisponible:
        return indisponible
    assert precedent is not None
    if demande.contract_type not in TYPES_DE_CONTRAT:
        return f"Type de contrat inconnu : « {demande.contract_type} »."
    if not (0 < demande.duree_hebdomadaire <= DUREE_HEBDO_MAX):
        return (
            f"Durée hebdomadaire invalide : {demande.duree_hebdomadaire:g} h "
            "(plus de 0 h, 48 h au plus)."
        )
    if demande.salaire_mensuel <= 0:
        return "Indiquez le salaire de base mensuel du nouveau contrat."
    if est_cdd(demande.contract_type) and demande.date_fin is None:
        return "Indiquez la date de fin du CDD."
    if demande.contract_type == "CDI" and demande.date_fin is not None:
        return "Un CDI n'a pas de date de fin."
    if demande.date_fin is not None and demande.date_fin < demande.date_debut:
        return "La date de fin est avant la date de début."
    if demande.date_debut <= precedent.fin:
        return (
            "Le nouveau contrat doit commencer après la fin du précédent "
            f"({_jj_mm_aaaa(precedent.fin)})."
        )
    if _rang(demande.date_debut) <= _rang(precedent.fin):
        return (
            f"Le nouveau contrat commencerait en {_mm_aaaa(demande.date_debut)}, le mois "
            "où le précédent se termine : Martine ne fait qu'un bulletin par mois. Il peut "
            f"commencer le {_jj_mm_aaaa(premier_jour_possible(precedent))} au plus tôt."
        )
    avant_bascule = rang_de_bascule is not None and _rang(precedent.fin) <= rang_de_bascule
    if not bulletin_du_dernier_mois and not avant_bascule:
        return (
            f"Générez d'abord le bulletin de {_mm_aaaa(precedent.fin)}, dernier mois du "
            "contrat précédent : il ne pourra plus l'être ensuite."
        )
    return None


def date_anciennete(
    fiche: Mapping[str, Any], precedent: ContratPrecedent, demande: Demande
) -> date:
    """La date d'ancienneté posée sur la fiche, sans calcul : la case de la RH décide.

    Cochée : la date d'ancienneté du contrat précédent est gardée (à défaut, son
    début). Décochée : l'ancienneté part du nouveau contrat. Dans les deux cas
    la date est écrite : la date d'entrée change, et un champ vide retomberait
    sur elle sans que personne l'ait décidé.
    """
    if demande.reprendre_anciennete:
        return _date(fiche.get("seniority_reference_date")) or precedent.debut
    return demande.date_debut


def ecritures(
    fiche: Mapping[str, Any], precedent: ContratPrecedent, demande: Demande
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """Le contrat rangé, la nouvelle fiche, et le salaire à historiser (ou None).

    Dates en ISO. `date_debut_execution` et `date_conclusion_contrat` étaient
    celles du contrat précédent : elles sont vidées, sinon la garde de présence
    lirait encore l'ancien début.
    """
    periode = {
        "contract_type": precedent.contract_type,
        "date_debut": precedent.debut.isoformat(),
        "date_fin": precedent.fin.isoformat(),
    }
    nouvelle_fiche: dict[str, Any] = {
        "hire_date": demande.date_debut.isoformat(),
        "date_debut_execution": None,
        "date_conclusion_contrat": None,
        "contract_type": demande.contract_type,
        "contract_end_date": demande.date_fin.isoformat() if demande.date_fin else None,
        "duree_hebdomadaire": demande.duree_hebdomadaire,
        "is_temps_partiel": demande.duree_hebdomadaire < DUREE_LEGALE,
        "job_title": (demande.job_title or "").strip() or fiche.get("job_title"),
        "employment_status": "actif",
        "current_exit_id": None,
        "seniority_reference_date": date_anciennete(fiche, precedent, demande).isoformat(),
    }
    ancien = fiche.get("salaire_de_base")
    ancien_montant = valeur_salaire(ancien)
    salaire = None
    if ancien_montant is None or abs(ancien_montant - demande.salaire_mensuel) > 0.004:
        ancien_bloc = dict(ancien) if isinstance(ancien, Mapping) else {"type": "mensuel", "valeur": ancien_montant}
        salaire = {
            "ancien_salaire": ancien_bloc,
            "nouveau_salaire": {**ancien_bloc, "valeur": round(demande.salaire_mensuel, 2)},
            "motif": f"Nouveau contrat du {_jj_mm_aaaa(demande.date_debut)}",
            "effective_date": demande.date_debut.isoformat(),
        }
    return periode, nouvelle_fiche, salaire


def message_de_succes(precedent: ContratPrecedent, demande: Demande) -> str:
    debut = _jj_mm_aaaa(demande.date_debut)
    contrat = demande.contract_type + (
        f" du {debut} au {_jj_mm_aaaa(demande.date_fin)}"
        if demande.date_fin
        else f" à partir du {debut}"
    )
    return (
        f"Nouveau contrat enregistré : {contrat}. Le contrat précédent "
        f"({precedent.contract_type} du {_jj_mm_aaaa(precedent.debut)} au "
        f"{_jj_mm_aaaa(precedent.fin)}) est dans les contrats passés. Le bulletin de "
        f"{_mm_aaaa(demande.date_debut)} peut être généré."
    )
