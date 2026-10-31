"""Signalement de fin de contrat de travail unique (FCTU, DSN nature 07).

Cahier technique DSN 2026.1, § 5.2 : « transmis dans les cinq jours ouvrés qui
suivent la survenance de la fin du contrat de travail », il porte « l'ensemble
des informations relatives à la fin d'un contrat de travail, y compris les
données du mois en cours calculées dans le cadre du solde de tout compte ».

Son contenu est la DSN du mois de sortie limitée au salarié, passée en nature 07
et filtrée par les rubriques permises, avec les deux rubriques propres au FCTU :
le mois du solde de tout compte (62.020, au 1er du mois) et le rattachement de
chaque versement à ce mois (50.020 = 01). Fonctions pures.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from app.modules.dsn_export.domain.evenements import dsn
from app.modules.dsn_export.domain.signalements import SignalementEnvoye
from app.modules.dsn_export.domain.usages_signalement import NATURE_FCTU, filtrer
from app.modules.dsn_export.domain.writer import ecrire_blocs

#: Les fins à venir s'affichent ce nombre de jours à l'avance, pour prévenir.
JOURS_D_AVANCE = 31

_VERSEMENT_DU_MOIS = "01"
#: Transaction en cours (62.008) : 02 - non. Martine n'en saisit pas ; une
#: transaction se signe après la sortie.
_SANS_TRANSACTION = "02"
#: Base « éléments de cotisation prévoyance, santé, retraite supplémentaire » :
#: refusée dans un FCTU (DSN-VAL, CCH-14), avec ses composants et cotisations.
_BASE_PSC = "31"
_ENFANTS_DE_LA_BASE = ("S21.G00.79", "S21.G00.81")

#: Type réalisation et paiement du préavis (63.001) d'après le dossier de départ.
_PREAVIS_PAR_TYPE = {"executed": "01", "paid": "02", "waived": "03", "not_applicable": "90"}
#: Sorties sans préavis (cahier technique 2026.1, CCH-11/12 de 63.001).
_SORTIES_SANS_PREAVIS = {"fin_cdd", "rupture_conventionnelle", "deces"}
_PREAVIS_DATES = {"01", "02", "03", "60"}


def ajouter_jours_ouvres(jour: date, n: int) -> date:
    """n jours ouvrés après ``jour`` : samedis et dimanches sautés (les fériés
    comptent : c'est la lecture la plus stricte)."""
    while n > 0:
        jour += timedelta(days=1)
        if jour.weekday() < 5:
            n -= 1
    return jour


def _blocs(texte: str) -> List[Dict[str, str]]:
    """Les blocs du fichier, dans l'ordre : un bloc s'arrête quand l'identifiant
    change ou que le numéro de rubrique redescend (bloc répété)."""
    blocs: List[Dict[str, str]] = []
    precedente = ""
    for ligne in texte.splitlines():
        if "," not in ligne:
            continue
        rubrique, valeur = ligne.split(",", 1)
        if rubrique.startswith("S90"):
            continue
        valeur = valeur[1:-1] if valeur.startswith("'") and valeur.endswith("'") else valeur
        if not blocs or rubrique[:10] != precedente[:10] or rubrique <= precedente:
            blocs.append({})
        blocs[-1][rubrique] = valeur
        precedente = rubrique
    return blocs


#: Blocs enfants d'un contrat (40) et d'un versement (50) : arborescence du
#: cahier technique 2026.1, § 8.
_ENFANTS_DU_CONTRAT = tuple(
    f"S21.G00.{n}" for n in ("41", "60", "62", "63", "65", "66", "70", "71", "72", "73")
)
_ENFANTS_DU_VERSEMENT = tuple(
    f"S21.G00.{n}" for n in ("51", "52", "53", "54", "56", "58", "78", "79", "81", "83", "84", "95")
)


def _seul_le_contrat_qui_finit(blocs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Un mois à deux contrats (D3.2) : le contrat qui porte la fin (62), le
    versement qui le rémunère (51.010) et son ancienneté (86.005) ; rien de
    l'autre contrat. Un seul contrat : les blocs tels quels."""
    if sum(1 for b in blocs if "S21.G00.40.001" in b) < 2:
        return blocs
    contrat_de: List[Optional[str]] = [None] * len(blocs)
    courant: Optional[str] = None  # le contrat dont on lit les blocs enfants
    versement: List[int] = []  # les blocs du versement en cours
    for index, bloc in enumerate(blocs):
        prefixe = next(iter(bloc))[:10]
        if prefixe == "S21.G00.50":
            courant, versement = None, [index]
        elif prefixe in _ENFANTS_DU_VERSEMENT and versement:
            versement.append(index)
            # Le versement appartient au contrat de sa rémunération (51, son
            # premier enfant) ; ses blocs suivants aussi.
            numero = bloc.get("S21.G00.51.010") or contrat_de[versement[0]]
            for i in versement:
                contrat_de[i] = numero
        else:
            versement = []
            if prefixe == "S21.G00.40":
                courant = bloc.get("S21.G00.40.009", "")
            elif prefixe == "S21.G00.86":
                courant = None
                contrat_de[index] = bloc.get("S21.G00.86.005", "")
            elif prefixe not in _ENFANTS_DU_CONTRAT:
                courant = None
            if courant is not None:
                contrat_de[index] = courant
    finit = next(
        (contrat_de[i] for i, b in enumerate(blocs) if "S21.G00.62.001" in b), None
    )
    gardes = []
    for bloc, contrat in zip(blocs, contrat_de):
        if contrat is not None and contrat != finit:
            continue
        if "S21.G00.78.006" in bloc:
            # Un seul contrat déclaré : la base ne cite plus son numéro (78.006).
            bloc = {k: v for k, v in bloc.items() if k != "S21.G00.78.006"}
        gardes.append(bloc)
    return gardes


def bloc_preavis(sortie: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    """Le bloc préavis (63), obligatoire dans un FCTU, lu dans le dossier de départ.

    Un CDD à son terme sans dossier, une rupture conventionnelle : « 90 - pas de
    clause de préavis applicable ». Une fin de période d'essai : « 60 - délai de
    prévenance » s'il a des dates, sinon 90. Ailleurs, le type saisi au départ ;
    sans lui, rien ne s'invente.
    """
    sortie = sortie or {}
    type_sortie = str(sortie.get("exit_type") or "fin_cdd")
    debut, fin = _jour(sortie.get("notice_start_date")), _jour(sortie.get("notice_end_date"))
    if type_sortie in _SORTIES_SANS_PREAVIS:
        code = "90"
    elif type_sortie == "fin_periode_essai":
        code = "60" if debut and fin else "90"
    else:
        code = _PREAVIS_PAR_TYPE.get(str(sortie.get("notice_indemnity_type") or ""))
        if not code:
            raise ValueError(
                "Préavis de la sortie à compléter (effectué, payé, dispensé) dans le "
                "dossier de départ : la fin de contrat le déclare."
            )
    bloc = {"S21.G00.63.001": code}
    if code in _PREAVIS_DATES and debut and fin:
        bloc.update({"S21.G00.63.002": dsn(debut), "S21.G00.63.003": dsn(fin)})
    return bloc


def fctu_depuis_mensuelle(
    texte_mensuelle: str, *, mois_solde: date, preavis: Mapping[str, str]
) -> str:
    """Le FCTU tiré de la DSN du mois de sortie, limitée au salarié qui part."""
    blocs = _blocs(texte_mensuelle)
    if sum(1 for bloc in blocs if "S21.G00.30.001" in bloc or "S21.G00.30.002" in bloc) != 1:
        raise ValueError("Une fin de contrat ne porte qu'un seul salarié.")
    if not any("S21.G00.62.001" in bloc for bloc in blocs):
        raise ValueError(
            "Pas de fin de contrat dans le mois : saisissez la sortie du salarié, puis "
            "recalculez son bulletin de sortie."
        )
    blocs = _seul_le_contrat_qui_finit(blocs)
    sortie: List[Dict[str, str]] = []
    base_ecartee = False
    for bloc in blocs:
        if "S21.G00.78.001" in bloc:
            base_ecartee = bloc["S21.G00.78.001"] == _BASE_PSC
        elif not next(iter(bloc)).startswith(_ENFANTS_DE_LA_BASE):
            base_ecartee = False
        if base_ecartee:
            continue
        if "S20.G00.05.001" in bloc:
            bloc = {**bloc, "S20.G00.05.001": NATURE_FCTU}
        if "S21.G00.50.001" in bloc:
            bloc = {**bloc, "S21.G00.50.020": _VERSEMENT_DU_MOIS}
        filtre = filtrer(bloc, NATURE_FCTU)
        if "S21.G00.62.001" in bloc:
            filtre = {
                **filtre,
                "S21.G00.62.020": f"01{mois_solde:%m%Y}",
                "S21.G00.62.008": filtre.get("S21.G00.62.008") or _SANS_TRANSACTION,
            }
            sortie.append(filtre)
            if not any("S21.G00.63.001" in b for b in blocs):
                sortie.append(filtrer(preavis, NATURE_FCTU))
            continue
        if filtre:
            sortie.append(filtre)
    return ecrire_blocs(sortie)


@dataclass(frozen=True)
class FinASignaler:
    employee_id: str
    fin: date
    a_deposer_avant: date
    #: Le bulletin du mois de sortie existe : le solde de tout compte est calculé.
    bulletin_pret: bool


def _jour(valeur: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(valeur or "")[:10])
    except ValueError:
        return None


def fins_a_signaler(
    *,
    sorties: Iterable[Mapping[str, Any]],
    contrats: Iterable[Mapping[str, Any]],
    envoyes: Iterable[SignalementEnvoye],
    bulletins: Set[Tuple[str, int, int]],
    depuis: Optional[date],
    aujourd_hui: date,
) -> List[FinASignaler]:
    """Les fins de contrat à signaler : sorties saisies (hors annulées), sinon
    terme du CDD ; celles des 31 jours à venir comprises, pour prévenir.

    Une sortie d'avant le début du contrat de la fiche est celle d'un contrat
    rangé par « Nouveau contrat » : elle compte à part, sans cacher le terme du
    contrat en cours (D3.2).
    """
    fins: Dict[str, date] = {}
    ranges: Set[Tuple[str, date]] = set()
    debuts: Dict[str, Optional[date]] = {}
    for contrat in contrats:
        employee_id = str(contrat.get("id"))
        debuts[employee_id] = _jour(contrat.get("date_debut_execution") or contrat.get("hire_date"))
        if str(contrat.get("contract_type") or "").upper() == "CDD":
            fin = _jour(contrat.get("contract_end_date"))
            if fin:
                fins[employee_id] = fin
    for sortie in sorties:
        if str(sortie.get("status") or "") == "annulee":
            continue
        fin = _jour(sortie.get("last_working_day"))
        employee_id = str(sortie.get("employee_id"))
        debut = debuts.get(employee_id)
        if fin and debut and fin < debut:
            ranges.add((employee_id, fin))
        elif fin:
            fins[employee_id] = fin
    deja = {
        (e.employee_id, e.debut) for e in envoyes if e.nature == NATURE_FCTU and not e.essai
    }
    horizon = aujourd_hui + timedelta(days=JOURS_D_AVANCE)
    resultat = [
        FinASignaler(
            employee_id,
            fin,
            ajouter_jours_ouvres(fin, 5),
            (employee_id, fin.year, fin.month) in bulletins,
        )
        for employee_id, fin in set(fins.items()) | ranges
        if (not depuis or fin >= depuis) and fin <= horizon and (employee_id, fin) not in deja
    ]
    return sorted(resultat, key=lambda f: (f.a_deposer_avant, f.employee_id))
