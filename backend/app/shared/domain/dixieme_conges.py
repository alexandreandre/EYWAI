"""Base du dixième des congés : domaine pur commun aux bulletins et exports.

Sources ouvertes le 05/11/2026 :
https://code.travail.gouv.fr/code-du-travail/l3141-24
https://www.service-public.gouv.fr/particuliers/vosdroits/F33359
https://www.service-public.gouv.fr/particuliers/vosdroits/F37482

Les codes des lignes sont fournis par l'adaptateur (inventaire du moteur).
Les libellés restent nécessaires aux bulletins repris, sans code Martine.
Ce module ne charge ni le moteur, ni la base, et ne modifie aucune entrée.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any


def texte_normalise(valeur: Any) -> str:
    texte = unicodedata.normalize("NFKD", str(valeur or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", texte.lower())).strip()


def _montant(ligne: Mapping[str, Any], cle: str) -> float:
    try:
        return float(ligne.get(cle) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def part_reconstituee(libelle: Any) -> float:
    """L3141-24 I : maladie ordinaire 80 %, AT/MP et parentalité 100 %.

    Le temps partiel thérapeutique n'est pas une suspension pour arrêt : pas
    de salaire fictif à 80 % (Service public F144, rémunération du travail
    accompli). L'accident de trajet est assimilé à l'AT pour les congés
    (CDTN, fiche ministérielle arrêt AT/MP, Cass. soc. 03/07/2012).
    L'activité partielle compte au salaire normal (F33359, R5122-11).
    """
    texte = texte_normalise(libelle)
    if "therapeutique" in texte:
        return 0.0
    if "non professionnel" in texte or "non professionnelle" in texte:
        return 0.8
    if any(mot in texte for mot in (
        "accident travail", "accident du travail", "accident trajet", "accident de trajet",
        "rechute at", "maladie professionnelle", "maternite", "paternite", "adoption",
        "activite partielle", "chomage partiel",
    )):
        return 1.0
    if "maladie" in texte or "accident" in texte:
        return 0.8
    return 0.0


def _famille(ligne: Mapping[str, Any]) -> str:
    code = str(ligne.get("code_dixieme") or ligne.get("code") or "")
    return code.split("#", 1)[0].split(":")[1] if code.startswith("brut:") else ""


def _complement(texte: str, famille: str) -> bool:
    if "evenement familial" in texte:
        return False
    return famille == "maintien_employeur" or texte.startswith((
        "maintien de salaire", "rappel maintien de salaire", "complement employeur",
        "indemnite complementaire", "garantie nette",
    ))


@dataclass(frozen=True)
class BaseDixieme:
    base: float | None
    reconstitution: float = 0.0
    complement_remplace: float = 0.0
    exclusions: float = 0.0
    regularisation: float = 0.0
    alertes: tuple[str, ...] = ()

    @property
    def ajustement(self) -> float:
        return round(self.reconstitution - self.complement_remplace - self.exclusions - self.regularisation, 2)


def calculer_base_dixieme(brut: float | None, lignes: Iterable[Mapping[str, Any]]) -> BaseDixieme:
    """Brut versé + salaire reconstitué - ce qui le rémunère déjà - exclusions.

    Le complément employeur est remplacé seulement si l'absence correspondante
    est reconstituée : déduction de L3141-24 I, signalée dans le rapport.
    Une régularisation sans affectation exploitable reste incluse et signalée.
    """
    absences: list[tuple[float, float]] = []
    annexes = complement = exclusions = regularisation = 0.0
    alertes: list[str] = []
    for ligne in lignes or []:
        if not isinstance(ligne, Mapping) or ligne.get("is_sous_total") or ligne.get("is_informative"):
            continue
        texte = texte_normalise(ligne.get("libelle"))
        famille = _famille(ligne)
        perte, gain = _montant(ligne, "perte"), _montant(ligne, "gain")
        if famille in {"retenue_absence_integrale", "retenue_absence_mois_complet", "complement_absence_integrale", "reduction_hs_absence"}:
            annexes += perte - gain
            continue
        if not famille and "absence" in texte and not texte.startswith(("absence", "h absence", "jours absence")):
            annexes += perte - gain
            continue
        est_absence = famille in {"arret", "absence_maladie", "absence_ferie_non_paye", "absence_non_remuneree", "absence_injustifiee", "absence_entree_sortie", "absence_conges_payes", "absence_evenement_familial"} or texte.startswith(("absence", "h absence", "jours absence"))
        if est_absence and perte > 0:
            nature = ligne.get("arret_type") or ligne.get("nature_absence") or texte
            part = part_reconstituee(nature)
            if famille in {"arret", "absence_maladie"} and not part and "therapeutique" not in texte_normalise(nature):
                part = 0.8
            absences.append((perte, part))
            continue
        if gain > 0 and _complement(texte, famille):
            complement += gain
            continue
        if gain <= 0 or ligne.get("hors_brut"):
            continue
        exclue = any(mot in texte for mot in ("fin d annee", "prime de bilan", "interessement", "participation", "frais professionnel"))
        # Cass. soc. 06/07/2022, 21-11.118 : seule une gratification dont le
        # montant ET les bénéficiaires sont discrétionnaires est exclue ; le
        # mot « exceptionnelle » ne prouve pas ces conditions.
        exclue = exclue or ligne.get("gratification_discretionnaire") is True
        exclue = exclue or ligne.get("remunere_annee_conges_compris") is True
        if exclue:
            exclusions += gain
        elif "exceptionnel" in texte or "13e mois" in texte or "13eme mois" in texte or "treizieme mois" in texte:
            alertes.append(f"Prime {ligne.get('libelle') or ''} conservée : conditions d'inclusion dans le dixième à vérifier.")
        if "regul" in texte or "rappel salaire" in texte or "rappel de salaire" in texte:
            deja = ligne.get("dixieme_reconstitution_deja_comptee")
            if isinstance(deja, (int, float)) and 0 <= deja <= gain:
                regularisation += float(deja)
            else:
                alertes.append("Régularisation de salaire sans période et absence identifiables : vérifier un double compte dans le dixième.")
    retenues = sum(perte for perte, _ in absences)
    reconstitution = sum(perte * part for perte, part in absences)
    if retenues:
        reconstitution += annexes * reconstitution / retenues
    reconstitution = round(reconstitution, 2)
    if reconstitution <= 0 and complement:
        alertes.append("Complément employeur sans absence reconstituable : conservé dans le dixième, vérifier son affectation.")
        complement = 0.0
    ajustement = round(reconstitution - complement - exclusions - regularisation, 2)
    return BaseDixieme(
        None if brut is None else round(float(brut) + ajustement, 2),
        reconstitution, round(complement, 2), round(exclusions, 2), round(regularisation, 2),
        tuple(dict.fromkeys(alertes)),
    )


def ajustement_dixieme(lignes: Iterable[Mapping[str, Any]]) -> float:
    return calculer_base_dixieme(0.0, lignes).ajustement


def mois_de_periode(debut: date, fin: date) -> list[tuple[int, int]]:
    resultat = []
    annee, mois = debut.year, debut.month
    while (annee, mois) <= (fin.year, fin.month):
        resultat.append((annee, mois))
        annee, mois = (annee + 1, 1) if mois == 12 else (annee, mois + 1)
    return resultat


def calculer_base_periode(
    bulletins: Iterable[Mapping[str, Any]], *, debut: date, fin: date,
    brut_repris: float | None = None,
) -> BaseDixieme:
    """La période, sans inventer le salaire d'un mois absent.

    Un cumul déclaré sert d'ancrage au brut ; seules les corrections lisibles
    dans les bulletins s'y ajoutent. Les lignes manquantes sont signalées.
    Plusieurs contrats dans un même mois s'additionnent, jamais d'écrasement.
    """
    mois = set(mois_de_periode(debut, fin))
    resultats = []
    presents = set()
    alertes = []
    for bulletin in bulletins:
        cle = (int(bulletin["annee"]), int(bulletin["mois"]))
        if cle not in mois:
            continue
        presents.add(cle)
        resultat = calculer_base_dixieme(bulletin.get("brut"), bulletin.get("lignes") or [])
        resultats.append(resultat)
        alertes.extend(resultat.alertes)
    manquants = sorted(mois - presents)
    for annee, numero in manquants:
        alertes.append(f"Bulletin {numero:02d}/{annee} absent : rémunération ou reconstitution du dixième inconnue.")
    if brut_repris is not None:
        base = round(float(brut_repris) + sum(r.ajustement for r in resultats), 2)
    elif manquants or any(r.base is None for r in resultats) or not resultats:
        base = None
    else:
        base = round(sum(r.base or 0.0 for r in resultats), 2)
    return BaseDixieme(
        base, round(sum(r.reconstitution for r in resultats), 2),
        round(sum(r.complement_remplace for r in resultats), 2),
        round(sum(r.exclusions for r in resultats), 2),
        round(sum(r.regularisation for r in resultats), 2), tuple(dict.fromkeys(alertes)),
    )


def montant_dixieme(base: float | None, jours: float, droits: float, *, taux: float = 0.10) -> float | None:
    """L3141-24 I : dixième proportionné aux droits légaux de la période."""
    if base is None or droits <= 0:
        return None
    return round(float(base) * taux * max(float(jours), 0.0) / float(droits), 2)
