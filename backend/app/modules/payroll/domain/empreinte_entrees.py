"""Empreinte stable des données d'entrée d'un bulletin.

À la génération, le bulletin enregistre `payslip_data.parametres.empreinte_entrees`.
Plus tard, on recalcule la même empreinte sur les lectures actuelles : si elle
diffère, le calendrier, les absences, les saisies ou la fiche ont changé depuis
le calcul.

Les cumuls, l'empreinte elle-même et les sorties du calcul (montants, alertes,
PDF) n'y figurent pas : une empreinte qui se contiendrait changerait à chaque
génération, et `employee_schedules.cumuls` est réécrit par le moteur.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Mapping

CLE_EMPREINTE = "empreinte_entrees"

#: Ce qu'on dit quand on ne sait pas quelle donnée a changé : un bulletin
#: calculé avant l'empreinte complémentaire n'a qu'un hash global.
MESSAGE_A_RECALCULER = (
    "Une donnée du bulletin a changé depuis le calcul (planning, absences, "
    "variables, fiche du salarié ou réglages de la société) : recalculez avant "
    "de valider."
)

#: Les cumuls du mois d'avant ont changé depuis le calcul de ce bulletin.
MESSAGE_A_REGENERER = (
    "Le bulletin du mois précédent a changé depuis le calcul de celui-ci : "
    "leurs cumuls ne se suivent plus. Régénérez ce bulletin."
)


def message_mois_d_avant_a_recalculer(annee: int, mois: int) -> str:
    """Un mois plus ancien de la chaîne est à recalculer d'abord : on le nomme."""
    return (
        f"Le bulletin de {mois:02d}/{annee} doit être recalculé : un mois avant lui a "
        "changé depuis. Recalculez les mois dans l'ordre, celui-ci ensuite."
    )

_CLES_IGNOREES = frozenset(
    {
        "cumuls",
        CLE_EMPREINTE,
        "salaire_brut",
        "net_a_payer",
        "alertes_baremes",
        "pdf_storage_path",
        "payroll_events",
        "annee",
        "mois",
        "created_at",
        "updated_at",
        "id",
        "employee_id",
        "company_id",
    }
)

def _jsonable(valeur: Any) -> Any:
    if isinstance(valeur, Decimal):
        return float(valeur)
    if hasattr(valeur, "isoformat") and callable(valeur.isoformat):
        try:
            return valeur.isoformat()
        except (TypeError, ValueError):
            return str(valeur)
    return valeur


def _sans_volatils(valeur: Any) -> Any:
    if isinstance(valeur, Mapping):
        return {
            str(cle): _sans_volatils(sous)
            for cle, sous in valeur.items()
            if str(cle) not in _CLES_IGNOREES
        }
    if isinstance(valeur, list):
        return [_sans_volatils(sous) for sous in valeur]
    return _jsonable(valeur)


def _cle_de_tri(valeur: Any) -> str:
    return json.dumps(valeur, sort_keys=True, ensure_ascii=False, default=str)


def _liste_stable(valeur: Any) -> list[Any]:
    if not isinstance(valeur, list):
        return []
    return sorted((_sans_volatils(item) for item in valeur), key=_cle_de_tri)


def mois_de_la_fenetre(year: int, month: int) -> tuple[tuple[int, int], ...]:
    """M-1, M, M+1 — même fenêtre que le générateur (`payslip_generator.py`)."""
    out: list[tuple[int, int]] = []
    for i in (-1, 0, 1):
        ancre = date(year, month, 15)
        m_offset, y_offset = ancre.month + i, ancre.year
        if m_offset == 0:
            m_offset, y_offset = 12, y_offset - 1
        elif m_offset == 13:
            m_offset, y_offset = 1, y_offset + 1
        out.append((y_offset, m_offset))
    return tuple(out)


def construire_entrees(brut: Mapping[str, Any] | None) -> dict[str, Any]:
    """Dictionnaire canonique : mêmes clés, listes triées, hors champs volatils."""
    source = _sans_volatils(brut or {})
    if not isinstance(source, dict):
        source = {}
    return {
        "calendriers": source.get("calendriers") or {},
        "absences": _liste_stable(source.get("absences")),
        "saisies": _liste_stable(source.get("saisies")),
        "fiche": source.get("fiche") or {},
        "notes_de_frais": _liste_stable(source.get("notes_de_frais")),
        "parametres_societe": source.get("parametres_societe") or {},
        "fenetre_variables": source.get("fenetre_variables") or {},
    }


def empreinte(entrees: dict) -> str:
    """sha256 hex du JSON trié, après canonisation (cumuls et sorties exclus)."""
    texte = json.dumps(
        construire_entrees(entrees),
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def etat_a_recalculer(stockee: str | None, actuelle: str | None) -> bool | None:
    """true = périmé, false = à jour, None = inconnu (pas d'empreinte, ou lecture impossible)."""
    if not stockee or not actuelle:
        return None
    return stockee != actuelle


def empreinte_stockee(payslip_data: Mapping[str, Any] | None) -> str | None:
    if not isinstance(payslip_data, Mapping):
        return None
    parametres = payslip_data.get("parametres")
    if not isinstance(parametres, Mapping):
        return None
    valeur = parametres.get(CLE_EMPREINTE)
    if isinstance(valeur, str) and valeur:
        return valeur
    return None


def poser_empreinte(payslip_data: Mapping[str, Any] | None, valeur: str) -> dict[str, Any]:
    """Copie du bulletin avec l'empreinte dans `parametres`, sans muter l'original."""
    return _poser(payslip_data, CLE_EMPREINTE, valeur)


def _poser(payslip_data: Mapping[str, Any] | None, cle: str, valeur: Any) -> dict[str, Any]:
    data = dict(payslip_data or {})
    parametres = dict(data.get("parametres") or {}) if isinstance(data.get("parametres"), Mapping) else {}
    parametres[cle] = valeur
    data["parametres"] = parametres
    return data


# --- Cumuls du mois précédent ---------------------------------------------------
#
# Le bulletin de M part des cumuls de M-1 (`employee_schedules.cumuls`) : brut et
# heures de l'année pour la réduction générale régularisée, tranches Agirc-Arrco,
# plafond des heures sup, brut de référence du dixième. Régénérer M-1 réécrit ces
# cumuls, et M — calculé sur les anciens — devient faux sans qu'aucune de ses
# entrées ait bougé. Ils restent hors de l'empreinte d'entrée (le moteur réécrit
# ceux du mois qu'il calcule) ; une empreinte à part, posée à la génération, dit
# si M-1 a changé depuis. Un bulletin d'avant cette empreinte n'en a pas : rien
# n'est dit pour lui.

CLE_EMPREINTE_CUMULS = "empreinte_cumuls_precedents"


def empreinte_cumuls(cumuls: Any) -> str:
    """sha256 des cumuls du mois précédent, tels que lus en base ; absents = vides."""
    texte = json.dumps(
        _jsonable_profond(cumuls or {}),
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def _jsonable_profond(valeur: Any) -> Any:
    if isinstance(valeur, Mapping):
        return {str(cle): _jsonable_profond(sous) for cle, sous in valeur.items()}
    if isinstance(valeur, list):
        return [_jsonable_profond(sous) for sous in valeur]
    return _jsonable(valeur)


def empreinte_cumuls_stockee(payslip_data: Mapping[str, Any] | None) -> str | None:
    if not isinstance(payslip_data, Mapping):
        return None
    parametres = payslip_data.get("parametres")
    if not isinstance(parametres, Mapping):
        return None
    valeur = parametres.get(CLE_EMPREINTE_CUMULS)
    if isinstance(valeur, str) and valeur:
        return valeur
    return None


def poser_empreinte_cumuls(payslip_data: Mapping[str, Any] | None, valeur: str) -> dict[str, Any]:
    """Copie du bulletin avec l'empreinte des cumuls d'avant, sans muter l'original."""
    return _poser(payslip_data, CLE_EMPREINTE_CUMULS, valeur)


def a_recalculer(entrees: bool | None, cumuls_precedents: bool | None) -> bool | None:
    """Périmé dès que ses entrées ou les cumuls du mois d'avant ont changé.

    Sinon l'état des entrées : false = à jour, None = inconnu (bulletin d'avant
    l'empreinte).
    """
    if entrees is True or cumuls_precedents is True:
        return True
    return entrees


# --- Empreinte complémentaire ---------------------------------------------------
#
# L'empreinte d'entrée est un seul hash : elle ne dit pas ce qui a changé, et ne
# voit pas tout ce que le moteur lit pour le mois — formules de mutuelle de la
# société, ajustements et réglages de congés, départ du salarié, historique de
# salaire daté, réglages société hors des champs suivis. L'empreinte
# complémentaire, posée à la génération, garde un hash PAR PARTIE : celles de
# l'empreinte d'entrée et ces données-là. Un bulletin d'avant elle n'en a pas :
# rien n'est comparé pour lui, l'empreinte d'entrée seule décide (le
# déploiement ne fait passer aucun bulletin « À recalculer »).

CLE_EMPREINTE_COMPLEMENTAIRE = "empreinte_complementaire"

#: Partie de la fiche du salarié : son changement ne périme que les brouillons
#: du contrat en cours (la fiche est celle d'aujourd'hui, pas celle du mois).
PARTIE_FICHE = "fiche"

#: Phrase quand une seule partie a changé, et nom de la partie dans une liste.
_PARTIES: dict[str, tuple[str, str]] = {
    "calendriers": ("Le planning a changé", "le planning"),
    "absences": ("Une absence a changé", "les absences"),
    "saisies": ("Les variables du mois ont changé", "les variables du mois"),
    PARTIE_FICHE: ("La fiche du salarié a changé", "la fiche du salarié"),
    "notes_de_frais": ("Une note de frais a changé", "les notes de frais"),
    "parametres_societe": (
        "Un réglage de paie de la société a changé",
        "les réglages de paie de la société",
    ),
    "adresse_societe": ("L'adresse de la société a changé", "l'adresse de la société"),
    "fenetre_variables": (
        "La période des variables a changé",
        "la période des variables",
    ),
    "mutuelle": ("La mutuelle a changé", "la mutuelle"),
    "conges_ajustements": (
        "Un compteur de congés a été ajusté",
        "les compteurs de congés",
    ),
    "conges_reglages": ("Les réglages de congés ont changé", "les réglages de congés"),
    "depart": ("Le départ du salarié a changé", "le départ du salarié"),
    "salaire": ("L'historique de salaire a changé", "l'historique de salaire"),
    "reglages_societe": (
        "Un réglage de paie de la société a changé",
        "les réglages de paie de la société",
    ),
}


def empreinte_partie(valeur: Any) -> str:
    """sha256 du JSON trié d'une partie (dates et décimaux rendus en texte)."""
    texte = json.dumps(
        _jsonable_profond(valeur),
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def empreinte_complementaire_valide(valeur: Any) -> dict[str, str] | None:
    """Les hash par partie, ou None (absente, vide ou illisible)."""
    if not isinstance(valeur, Mapping):
        return None
    parties = {str(k): v for k, v in valeur.items() if isinstance(v, str) and v}
    return parties or None


def empreinte_complementaire_stockee(
    payslip_data: Mapping[str, Any] | None,
) -> dict[str, str] | None:
    if not isinstance(payslip_data, Mapping):
        return None
    parametres = payslip_data.get("parametres")
    if not isinstance(parametres, Mapping):
        return None
    return empreinte_complementaire_valide(parametres.get(CLE_EMPREINTE_COMPLEMENTAIRE))


def poser_empreinte_complementaire(
    payslip_data: Mapping[str, Any] | None, parties: Mapping[str, str]
) -> dict[str, Any]:
    """Copie du bulletin avec les hash par partie, sans muter l'original."""
    return _poser(payslip_data, CLE_EMPREINTE_COMPLEMENTAIRE, dict(parties))


def parties_changees(
    stockees: Mapping[str, str], actuelles: Mapping[str, str]
) -> tuple[str, ...]:
    """Les parties dont le hash a changé depuis le calcul.

    Une partie absente d'un côté (lecture ratée, partie ajoutée depuis) ne se
    compare pas : rien n'est dit sur ce qu'on ne sait pas.
    """
    return tuple(
        nom for nom, valeur in stockees.items() if nom in actuelles and actuelles[nom] != valeur
    )


def message_a_recalculer(parties: tuple[str, ...] | list[str] | None) -> str:
    """Ce qui a changé, dit simplement ; sinon le message général, juste."""
    connues = [p for p in (parties or ()) if p in _PARTIES]
    phrases = list(dict.fromkeys(_PARTIES[p][0] for p in connues))
    if not phrases:
        return MESSAGE_A_RECALCULER
    if len(phrases) == 1:
        return f"{phrases[0]} depuis le calcul : recalculez avant de valider."
    noms = list(dict.fromkeys(_PARTIES[p][1] for p in connues))
    liste = f"{', '.join(noms[:-1])} et {noms[-1]}"
    return f"Ont changé depuis le calcul : {liste}. Recalculez avant de valider."


# --- Un bulletin validé recalculé au bac à sable -----------------------------------
#
# Choix du 12/10/2026 (rejeu final A et C2) : poser le calendrier du mois suivant
# change l'empreinte d'un bulletin validé sans que son calcul change. Martine le
# recalcule d'abord au bac à sable, sans rien écrire, et compare au centime ce
# que le moteur calcule : le brut et ses lignes, les cotisations, le net, le coût
# employeur, et les cumuls du mois. Textes, dates, empreintes et soldes de congés
# du pied ne sont pas des montants. Les retenues posées après le moteur (avances,
# saisies, prêts) sont rajoutées au net enregistré : le bac à sable ne les a pas.

#: Ce que le moteur calcule, comparé au centime.
_BLOCS_AU_CENTIME = (
    "salaire_brut",
    "calcul_du_brut",
    "structure_cotisations",
    "synthese_net",
    "primes_non_soumises",
    "revenus_hors_brut_imposables",
    "indemnite_cp_fin_contrat",
    "total_exonerations",
)

#: Retenues posées sur le net après le moteur, et leur total.
_RETENUES_APRES_LE_MOTEUR = (
    ("retenues_saisies", "total_preleve"),
    ("remboursements_avances", "total_rembourse"),
    ("remboursements_prets", "total_rembourse"),
)

_DEBUT_ECART = "Martine l'a recalculé sans rien enregistrer : "


def _centimes(valeur: Any) -> Decimal | None:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float, Decimal)):
        return None
    return Decimal(str(valeur)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _montants(valeur: Any, chemin: str, sortie: Counter) -> None:
    """Chaque montant, au centime, avec son chemin (libellé des lignes compris) :
    l'ordre des lignes ne compte pas, leur contenu si."""
    centimes = _centimes(valeur)
    if centimes is not None:
        sortie[(chemin, centimes)] += 1
        return
    if isinstance(valeur, Mapping):
        libelle = valeur.get("libelle")
        base = f"{chemin}[{libelle}]" if isinstance(libelle, str) else chemin
        for cle, sous in valeur.items():
            _montants(sous, f"{base}.{cle}", sortie)
    elif isinstance(valeur, list):
        for sous in valeur:
            _montants(sous, chemin, sortie)


def _net_du_moteur(payslip_data: Mapping[str, Any]) -> Decimal | None:
    net = _centimes(payslip_data.get("net_a_payer"))
    if net is None:
        return None
    for bloc, total in _RETENUES_APRES_LE_MOTEUR:
        retenue = payslip_data.get(bloc)
        if isinstance(retenue, Mapping):
            net += _centimes(retenue.get(total)) or Decimal("0")
    return net


def _empreinte_au_centime(payslip_data: Mapping[str, Any]) -> Counter:
    sortie: Counter = Counter()
    for bloc in _BLOCS_AU_CENTIME:
        _montants(payslip_data.get(bloc), bloc, sortie)
    pied = payslip_data.get("pied_de_page")
    if isinstance(pied, Mapping):
        _montants(pied.get("cout_total_employeur"), "cout_total_employeur", sortie)
    sortie[("net_du_moteur", _net_du_moteur(payslip_data))] += 1
    return sortie


def _euros(valeur: Decimal) -> str:
    texte = f"{abs(valeur):,.2f}".replace(",", " ").replace(".", ",")
    return f"{'−' if valeur < 0 else ''}{texte} €"


def ecart_au_centime(
    stocke: Mapping[str, Any],
    recalcule: Mapping[str, Any],
    *,
    cumuls_stockes: Any = None,
    cumuls_recalcules: Any = None,
) -> str | None:
    """None si le bulletin recalculé est identique au centime ; sinon ce qui change.

    Les cumuls ne se comparent que si l'appelant donne les deux.
    """
    memes_montants = _empreinte_au_centime(stocke) == _empreinte_au_centime(recalcule)
    memes_cumuls = True
    if cumuls_stockes is not None and cumuls_recalcules is not None:
        avant: Counter = Counter()
        apres: Counter = Counter()
        _montants(cumuls_stockes, "cumuls", avant)
        _montants(cumuls_recalcules, "cumuls", apres)
        memes_cumuls = avant == apres
    if memes_montants and memes_cumuls:
        return None
    brut_avant, brut_apres = _centimes(stocke.get("salaire_brut")), _centimes(recalcule.get("salaire_brut"))
    if brut_avant is not None and brut_apres is not None and brut_avant != brut_apres:
        return f"{_DEBUT_ECART}le brut passerait de {_euros(brut_avant)} à {_euros(brut_apres)}."
    net_avant, net_apres = _net_du_moteur(stocke), _net_du_moteur(recalcule)
    affiche = _centimes(stocke.get("net_a_payer"))
    if net_avant is not None and net_apres is not None and affiche is not None and net_avant != net_apres:
        # Le net affiché, retenues d'après le moteur comprises, bouge comme le net du moteur.
        return (
            f"{_DEBUT_ECART}le net à payer passerait de {_euros(affiche)} "
            f"à {_euros(affiche + net_apres - net_avant)}."
        )
    return f"{_DEBUT_ECART}des cotisations ou des cumuls changent, le brut et le net restent les mêmes."
