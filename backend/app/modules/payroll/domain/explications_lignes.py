"""Explications des lignes qui surprennent sur un bulletin.

Produit à la génération, stockée dans `payslip_data` sur chaque ligne
concernée (`explication`). Aucun montant n'est modifié. Une info-bulle
n'est posée que si le texte dit vraiment d'où vient la ligne.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Mapping, Sequence

CLE_EXPLICATION = "explication"

_RE_DATE = re.compile(r"(\d{1,2})/(\d{2})")
_MOT_HS = "heures suppl"
_MOT_STRUCTURELLES = "structurelle"
_LIBELLE_RGDU = "réduction générale"


def reduction_deja_pour_explication(mois: int, cumuls: Mapping[str, Any] | None) -> float:
    """Réduction déjà appliquée depuis janvier, telle que le moteur la lit.

    En janvier l'année civile recommence : ce n'est pas une régularisation.
    """
    if mois == 1:
        return 0.0
    if not isinstance(cumuls, Mapping):
        return 0.0
    inner = cumuls.get("cumuls")
    source = inner if isinstance(inner, Mapping) else cumuls
    try:
        return abs(float(source.get("reduction_generale_patronale") or 0.0))
    except (TypeError, ValueError):
        return 0.0


#: Clé du point de départ de la réduction posé par une reprise (même nom que
#: `calcul_reduction_generale.CLE_DEPART_REDUCTION`, le domaine n'importe pas le moteur).
_CLE_DEPART_REDUCTION = "reduction_generale_depuis_mois"

_MOIS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def depart_reduction_pour_explication(mois: int, cumuls: Mapping[str, Any] | None) -> int | None:
    """Premier mois de la régularisation posé par une reprise, ou None.

    Lu dans les cumuls du mois précédent, comme le moteur. None en janvier
    (l'année recommence), sans point de départ, ou s'il est en janvier (aucun
    mois laissé hors de la réduction).
    """
    if mois == 1 or not isinstance(cumuls, Mapping):
        return None
    inner = cumuls.get("cumuls")
    source = inner if isinstance(inner, Mapping) else cumuls
    depart = _entier(source.get(_CLE_DEPART_REDUCTION))
    if depart is None or not 2 <= depart <= 12:
        return None
    return depart


def poser_explications(
    bulletin: dict[str, Any],
    *,
    evenements: Sequence[Mapping[str, Any]] | None = None,
    duree_hebdo: float | None = None,
    reduction_deja: float | None = None,
    smic_reference_horaire: float | None = None,
    depart_reduction: int | None = None,
) -> dict[str, Any]:
    """Ajoute `explication` sur les lignes d'heures sup, d'absence et de RGDU.

    `smic_reference_horaire` : le SMIC du 1er janvier que la réduction générale
    retient (RGDU) ; l'explication le nomme à côté de celui du pied du bulletin.
    `depart_reduction` : premier mois de la régularisation posé par une reprise
    (l'ancien logiciel n'a appliqué aucune réduction avant).
    """
    en_tete = bulletin.get("en_tete") if isinstance(bulletin.get("en_tete"), dict) else {}
    annee = _entier(en_tete.get("annee"))
    mois = _entier(en_tete.get("mois"))
    if reduction_deja is None:
        reduction_deja = reduction_deja_pour_explication(mois or 0, bulletin.get("cumuls"))

    _expliquer_heures_sup(bulletin, evenements, duree_hebdo, annee, mois)
    _expliquer_absences(bulletin)
    _expliquer_reduction_generale(
        bulletin,
        annee,
        mois,
        float(reduction_deja or 0.0),
        smic_reference_horaire,
        depart_reduction,
    )
    _expliquer_ijss_deduites(bulletin)
    _expliquer_corrections(bulletin)
    return bulletin


def _expliquer_heures_sup(
    bulletin: dict[str, Any],
    evenements: Sequence[Mapping[str, Any]] | None,
    duree_hebdo: float | None,
    annee: int | None,
    mois: int | None,
) -> None:
    declarees = bulletin.get("heures_sup_declarees")
    compensation = bulletin.get("compensation_semaines")
    saisie_manuelle = isinstance(compensation, Mapping) and bool(
        compensation.get("heures_saisies")
    )
    force_declarees = isinstance(declarees, Mapping) or saisie_manuelle

    semaines_comp = None
    if (
        not force_declarees
        and isinstance(compensation, Mapping)
        and compensation.get("semaines")
    ):
        semaines_comp = list(compensation.get("semaines") or [])

    semaines_evts = None
    if not force_declarees and semaines_comp is None:
        semaines_evts = _semaines_depuis_evenements(evenements, annee, mois)

    for ligne in _lignes_de(bulletin, "calcul_du_brut"):
        palier = _palier_heures_sup(ligne)
        if palier is None:
            continue
        texte = None
        if force_declarees:
            texte = _texte_heures_declarees(palier, declarees, compensation)
        elif semaines_comp is not None:
            texte = _texte_heures_depuis_semaines(
                palier, ligne, semaines_comp, duree_hebdo, cle_heures=f"majo{palier}"
            )
        elif semaines_evts is not None:
            texte = _texte_heures_depuis_semaines(
                palier, ligne, semaines_evts, duree_hebdo, cle_heures=f"hs{palier}"
            )
        _poser(ligne, texte)


def _expliquer_absences(bulletin: dict[str, Any]) -> None:
    for section in ("details_absences", "details_conges"):
        for ligne in _lignes_de(bulletin, section):
            _poser(ligne, _texte_absence(str(ligne.get("libelle") or "")))


def _euros_fr(valeur: float) -> str:
    return f"{valeur:,.2f}".replace(",", " ").replace(".", ",")


def _phrase_smic(
    bulletin: dict[str, Any], annee: int | None, smic_reference: float | None
) -> str | None:
    """Les deux SMIC du bulletin, nommés (relevé I.3 du 12/10/2026).

    La réduction générale (RGDU) retient le SMIC du 1er janvier pour toute
    l'année ; le pied du bulletin imprime celui en vigueur ce mois. Sans
    phrase, 12,02 € et 12,31 € se lisaient comme une erreur.
    """
    if not smic_reference or not annee:
        return None
    phrase = (
        f"Calculée sur le SMIC du 1er janvier {annee} : "
        f"{_euros_fr(smic_reference)} € de l'heure."
    )
    parametres = bulletin.get("parametres") if isinstance(bulletin.get("parametres"), dict) else {}
    try:
        pied = float(parametres.get("smic_horaire") or 0.0)
    except (TypeError, ValueError):
        pied = 0.0
    if pied > 0 and abs(pied - smic_reference) >= 0.005:
        phrase += (
            f" Le SMIC horaire du pied du bulletin ({_euros_fr(pied)} €) est celui "
            "en vigueur ce mois."
        )
    return phrase


def _phrase_depart(depart: int) -> str:
    """La régularisation part de `depart`, comme chez l'ancien logiciel."""
    sans = list(_MOIS_FR[: depart - 1])
    if len(sans) == 1:
        sujet = f"{sans[0]} n'a"
    else:
        sujet = f"{', '.join(sans[:-1])} et {sans[-1]} n'ont"
    return (
        f"Réduction générale : régularisée depuis {_MOIS_FR[depart - 1]}, "
        f"comme l'ancien logiciel ; {sujet} pas eu de réduction."
    )


def _expliquer_reduction_generale(
    bulletin: dict[str, Any],
    annee: int | None,
    mois: int | None,
    reduction_deja: float,
    smic_reference: float | None = None,
    depart: int | None = None,
) -> None:
    regularisation = mois != 1 and reduction_deja > 0
    smic = _phrase_smic(bulletin, annee, smic_reference)
    if mois != 1 and depart and 2 <= depart <= 12:
        texte = _phrase_depart(depart)
        if smic:
            texte = f"{texte} {smic}"
    elif regularisation and smic:
        texte = f"Réduction générale : régularisation depuis janvier. {smic}"
    elif regularisation:
        texte = "Réduction générale : régularisation depuis janvier"
    elif smic:
        texte = f"Réduction générale : {smic[0].lower()}{smic[1:]}"
    else:
        return
    for ligne in _lignes_de(
        bulletin.get("structure_cotisations") or {}, "bloc_allegements"
    ):
        if _est_reduction_generale(ligne):
            _poser(ligne, texte)
    for rubrique in bulletin.get("cotisations_officielles") or []:
        if not isinstance(rubrique, dict):
            continue
        for ligne in rubrique.get("lignes") or []:
            if isinstance(ligne, dict) and _est_reduction_generale(ligne):
                _poser(ligne, texte)


def _texte_heures_declarees(
    palier: int,
    declarees: Mapping[str, Any] | None,
    compensation: Mapping[str, Any] | None,
) -> str | None:
    source = declarees if isinstance(declarees, Mapping) else {}
    saisie = {}
    if isinstance(compensation, Mapping) and isinstance(
        compensation.get("heures_saisies"), Mapping
    ):
        saisie = compensation["heures_saisies"]
    heures = source.get("hs25") if palier == 25 else source.get("hs50")
    if heures is None:
        heures = saisie.get("hs25") if palier == 25 else saisie.get("hs50")
    if heures is None:
        return None
    planning = source.get("planning")
    texte = (
        f"Heures supplémentaires déclarées au bulletin : "
        f"{_heures_fr(heures)} h à {palier} %"
    )
    if planning is not None:
        texte += f" (le planning en donnait {_heures_fr(planning)} h)"
    return texte


def _texte_heures_depuis_semaines(
    palier: int,
    ligne: Mapping[str, Any],
    semaines: Sequence[Mapping[str, Any]],
    duree_hebdo: float | None,
    *,
    cle_heures: str,
) -> str | None:
    retenues: list[tuple[int, float]] = []
    for semaine in semaines:
        if not isinstance(semaine, Mapping):
            continue
        numero = _entier(semaine.get("semaine"))
        heures = _nombre(semaine.get(cle_heures))
        if numero is None or heures is None or heures == 0:
            continue
        retenues.append((numero, heures))
    if not retenues:
        return None
    total = _nombre(ligne.get("quantite"))
    somme = sum(h for _, h in retenues)
    if total is None or abs(somme - total) > 0.01:
        return None
    numeros = [n for n, _ in retenues]
    valeurs = [h for _, h in retenues]
    liste = _liste_semaines(numeros)
    au_dela = _au_dela(palier, duree_hebdo)
    uniforme = len(set(valeurs)) == 1 and valeurs[0] > 0
    if uniforme:
        return (
            f"{_heures_fr(total)} h à {palier} % : "
            f"{_heures_fr(valeurs[0])} h par semaine{au_dela}, {liste}"
        )
    details = ", ".join(
        f"S{numero} {_heures_fr(heures)} h" for numero, heures in retenues
    )
    return f"{_heures_fr(total)} h à {palier} % : {details}{au_dela}"


def _au_dela(palier: int, duree_hebdo: float | None) -> str:
    if palier == 25 and duree_hebdo:
        return f" au-delà de {_heures_fr(duree_hebdo)} h"
    if palier == 50:
        return " au-delà de 43 h"
    return ""


def _semaines_depuis_evenements(
    evenements: Sequence[Mapping[str, Any]] | None,
    annee_defaut: int | None,
    mois_defaut: int | None,
) -> list[dict[str, Any]] | None:
    if not evenements:
        return None
    par_semaine: dict[tuple[int, int], dict[str, float]] = {}
    for ev in evenements:
        if not isinstance(ev, Mapping):
            continue
        type_ev = str(ev.get("type") or "")
        palier = 25 if type_ev == "travail_hs25" else 50 if type_ev == "travail_hs50" else None
        if palier is None:
            continue
        jour = _date_evenement(ev, annee_defaut, mois_defaut)
        if jour is None:
            continue
        heures = _nombre(ev.get("heures"))
        if heures is None or heures == 0:
            continue
        iso = jour.isocalendar()
        cle = (iso[0], iso[1])
        slot = par_semaine.setdefault(cle, {"hs25": 0.0, "hs50": 0.0})
        slot[f"hs{palier}"] = round(slot[f"hs{palier}"] + heures, 2)
    if not par_semaine:
        return None
    return [
        {
            "annee": annee,
            "semaine": semaine,
            "hs25": valeurs["hs25"],
            "hs50": valeurs["hs50"],
        }
        for (annee, semaine), valeurs in sorted(par_semaine.items())
    ]


def _date_evenement(
    ev: Mapping[str, Any], annee_defaut: int | None, mois_defaut: int | None
) -> date | None:
    brut = ev.get("date_complete")
    if brut:
        try:
            return date.fromisoformat(str(brut)[:10])
        except ValueError:
            return None
    jour = _entier(ev.get("jour"))
    if jour is None:
        return None
    annee = _entier(ev.get("annee")) or annee_defaut
    mois = _entier(ev.get("mois")) or mois_defaut
    if annee is None or mois is None:
        return None
    try:
        return date(annee, mois, jour)
    except ValueError:
        return None


def _texte_absence(libelle: str) -> str | None:
    if not libelle.strip():
        return None
    # L'indemnité compensatrice de fin de contrat paie des congés non pris :
    # ce n'est pas une absence du mois.
    if "compensatrice" in libelle.lower():
        return "Congés acquis et non pris, payés à la fin du contrat"
    nature = _nature_absence(libelle)
    dates = _dates_telles_qu_ecrites(libelle)
    if not nature and not dates:
        return None
    if nature and dates:
        return f"Absence : {nature} {dates}"
    if nature:
        return f"Absence : {nature}"
    return f"Absence {dates}"


def _dates_telles_qu_ecrites(libelle: str) -> str:
    """Dates du libellé, sans recomposer une plage continue."""
    apres_deux_points = re.search(r":\s*([^)]+)\)", libelle)
    if apres_deux_points:
        return apres_deux_points.group(1).strip()
    deja_ecrites = re.search(
        r"\bdu\s+\d{1,2}/\d{2}(?:\s+au\s+\d{1,2}/\d{2})?", libelle, flags=re.I
    )
    if deja_ecrites:
        return deja_ecrites.group(0)
    return ""


def _nature_absence(libelle: str) -> str:
    bas = (
        libelle.lower()
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
    )
    paires = (
        ("conges payes", "congés payés"),
        ("arret maladie", "arrêt maladie"),
        ("accident du travail", "accident du travail"),
        ("conge maternite", "congé maternité"),
        ("conge paternite", "congé paternité"),
        ("injustif", "injustifiée"),
        ("evenement familial", "événement familial"),
        ("non remunere", "non rémunérée"),
        ("entree ou sortie", "entrée ou sortie"),
        ("arret de travail", "arrêt de travail"),
    )
    for motif, libelle_fr in paires:
        if motif in bas:
            return libelle_fr
    reste = re.sub(r"^Absence\s+", "", libelle, flags=re.I)
    reste = _RE_DATE.sub("", reste)
    reste = re.sub(r"\bdu\b|\bau\b|[()]", " ", reste)
    return " ".join(reste.split())


def _liste_semaines(numeros: Sequence[int]) -> str:
    uniques = sorted(set(numeros))
    if not uniques:
        return ""
    if len(uniques) == 1:
        return f"semaine {uniques[0]}"
    if uniques == list(range(uniques[0], uniques[-1] + 1)):
        return f"semaines {uniques[0]} à {uniques[-1]}"
    *debut, dernier = uniques
    return "semaines " + ", ".join(str(n) for n in debut) + f" et {dernier}"


def _palier_heures_sup(ligne: Mapping[str, Any]) -> int | None:
    libelle = str(ligne.get("libelle") or "").lower()
    if _MOT_STRUCTURELLES in libelle or _MOT_HS not in libelle:
        return None
    return 50 if "50" in libelle else 25


def _est_reduction_generale(ligne: Mapping[str, Any]) -> bool:
    if ligne.get("coti_id") == "reduction_generale":
        return True
    return _LIBELLE_RGDU in str(ligne.get("libelle") or "").lower()


def _expliquer_ijss_deduites(bulletin: dict[str, Any]) -> None:
    """Sans subrogation, IJSS déduites : la ligne de maintien dit le calcul."""
    from app.modules.payroll.domain.ijss_deduites import explication_ijss_deduites

    bloc = bulletin.get("bloc_maintien")
    texte = explication_ijss_deduites(bloc.get("maintien") if isinstance(bloc, Mapping) else None)
    if not texte:
        return
    for ligne in _lignes_de(bulletin, "calcul_du_brut"):
        if ligne.get("is_maintien_employeur"):
            _poser(ligne, texte)


def _expliquer_corrections(bulletin: dict[str, Any]) -> None:
    """Une ligne corrigée à la main le dit au survol, avec ce que Martine avait
    calculé. Posée en dernier : elle remplace l'explication du calcul (celle de
    la réduction générale ne dit plus « régularisation depuis janvier »)."""
    # Import local : `engine/bulletin.py` importe ce module, et le paquet
    # `engine` importe `bulletin` — un import en tête ferait un cycle quand ce
    # module est chargé le premier.
    from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT, BLOC_COTISATIONS
    from app.modules.payroll.engine.corrections_du_bulletin import (
        BLOCS_DE_GAINS,
        explication_de_correction,
    )

    for bloc in (*BLOCS_DE_GAINS, "details_maintien"):
        for ligne in _lignes_de(bulletin, bloc):
            _poser(ligne, explication_de_correction(ligne, BLOC_BRUT))
    structure = bulletin.get("structure_cotisations")
    if isinstance(structure, dict):
        for cle, valeur in structure.items():
            if isinstance(valeur, list):
                for ligne in _lignes_de(structure, cle):
                    _poser(ligne, explication_de_correction(ligne, BLOC_COTISATIONS))
    for rubrique in bulletin.get("cotisations_officielles") or []:
        if isinstance(rubrique, dict):
            for ligne in _lignes_de(rubrique, "lignes"):
                _poser(ligne, explication_de_correction(ligne, BLOC_COTISATIONS))


def _lignes_de(conteneur: Mapping[str, Any], cle: str) -> list[dict[str, Any]]:
    lignes = conteneur.get(cle) if isinstance(conteneur, Mapping) else None
    if not isinstance(lignes, list):
        return []
    return [ligne for ligne in lignes if isinstance(ligne, dict)]


def _poser(ligne: dict[str, Any], texte: str | None) -> None:
    if not texte or not str(texte).strip():
        return
    ligne[CLE_EXPLICATION] = str(texte).strip()


def _heures_fr(valeur: Any) -> str:
    texte = f"{round(float(valeur), 2):.2f}".rstrip("0").rstrip(".")
    return texte.replace(".", ",")


def _nombre(valeur: Any) -> float | None:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return float(valeur)


def _entier(valeur: Any) -> int | None:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return int(valeur)
