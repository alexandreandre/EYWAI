"""Le code stable de chaque ligne d'un bulletin, et ce qui s'y corrige.

Théorème de la correction à la main, étape 2 (spec 2026-10-18, règle 3 et
§ 10). Une correction vise une ligne par son code. Le code se lit sur la ligne
elle-même, au calcul comme sur un bulletin enregistré : il n'est jamais
stocké. Un bulletin sans correction reste donc identique, clé pour clé, et un
bulletin calculé avant cette étape se corrige comme les autres.

- Gain : « brut:<famille>[:<discriminant>] ». La famille vient d'un drapeau
  posé par le moteur ou du libellé, qu'une correction ne change jamais ; le
  discriminant (une date, un palier) distingue les lignes d'une même famille.
- Cotisation : « cotisation:<coti_id>[:<libellé>] ». Le libellé n'entre que
  pour les organismes qui portent plusieurs lignes.
- Impôt : « impot ».

Deux lignes de même code sont numérotées dans leur ordre (« #2 », « #3 ») :
elles restent dans le même bloc et dans le même ordre, au calcul comme une
fois enregistrées.

Une ligne que l'inventaire ne connaît pas n'a pas de code : le test du
théorème échoue sur elle. Un nouveau type de ligne n'entre pas sans sa
correction.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any, Iterable, Mapping

BLOC_BRUT = "brut"
BLOC_COTISATIONS = "cotisations"
BLOC_IMPOT = "impot"

MODE_BASE_OU_TAUX = "base_ou_taux"
MODE_MONTANT = "montant"
MODE_TAUX = "taux"

CODE_IMPOT = "impot"

RAISON_SAISIE = "Une prime saisie se corrige dans « Primes du mois »."
RAISON_SOUS_TOTAL = "Un sous-total ne se corrige pas : corrigez les lignes qui le composent."
RAISON_INFORMATION = "Ligne d'information : elle ne compte pas dans le brut."
RAISON_REGULARISATION = (
    "Une régularisation se retire ou se refait dans « Régularisations de cotisation »."
)
RAISON_HORS_SALAIRE = (
    "Cotisation de la participation ou de la prime de partage de la valeur : "
    "corrigez-la par une régularisation de cotisation."
)
RAISON_INCONNUE = (
    "Martine ne connaît pas cette ligne : corrigez-la à sa source ou par une régularisation."
)

#: Organismes qui portent plusieurs lignes sur un même bulletin : CSG sur le
#: salaire et sur les heures sup, forfait social sur prévoyance et sur retraite
#: supplémentaire, une ligne par mutuelle et par tranche de prévoyance.
COTI_IDS_A_PLUSIEURS_LIGNES = frozenset(
    {
        "csg_deductible",
        "csg_non_deductible",
        "crds",
        "forfait_social",
        "mutuelle",
        "prevoyance_cadre",
        "prevoyance_non_cadre",
        "retraite_sup",
    }
)

#: Cotisations dont le montant n'est pas base × taux : elles se corrigent par
#: leur montant (règle 3). La réduction générale porte un coefficient cumulé.
COTI_IDS_AU_MONTANT = frozenset(
    {
        "reduction_generale",
        "mutuelle",
        "reduction_hs_salariale",
        "deduction_hs_patronale",
        "exoneration_apprenti_salariale",
        "exoneration_stage",
    }
)

#: (famille, motif du libellé). Le premier motif qui reconnaît le libellé donne
#: la famille ; le groupe « d », s'il existe, le discriminant.
_MOTIFS_DE_GAIN: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (famille, re.compile(motif))
    for famille, motif in (
        ("salaire_base", r"^Salaire de base( \(forfait jour\))?$"),
        ("hs_structurelles", r"^Heures suppl\. structurelles majorées à .+%$"),
        ("heures_sup", r"^Heures suppl\. majorées à (?P<d>.+)%$"),
        ("heures_complementaires", r"^Heures complémentaires majorées à (?P<d>.+)%$"),
        ("absence_entree_sortie", r"^Absence pour entrée ou sortie$"),
        ("absence_injustifiee", r"^Absence injustifiée (?P<d>.+)$"),
        ("absence_non_remuneree", r"^Absence non rémunérée du (?P<d>.+)$"),
        ("absence_evenement_familial", r"^Absence événement familial du (?P<d>.+)$"),
        ("absence_ferie_non_paye", r"^Abs\. jour férié non payé du (?P<d>.+)$"),
        ("absence_maladie", r"^Absence maladie du (?P<d>.+)$"),
        ("reduction_hs_absence", r"^Réduction HS structurelles \(jours d'absence\)$"),
        ("reduction_hs_evenement_familial", r"^Réduction HS structurelles \(événement familial\)$"),
        ("maintien_evenement_familial", r"^Maintien de salaire \(événement familial\)$"),
        ("maintien_employeur", r"^Maintien de salaire employeur$"),
        ("complement_absence_integrale", r"^Complément retenue absence intégrale du mois"),
        ("retenue_absence_integrale", r"^Retenue absence intégrale du mois limitée au salaire mensuel$"),
        ("retenue_absence_mois_complet", r"^Absence sur tout le mois : retenue ramenée au salaire du mois$"),
        ("lissage_modulation", r"^Lissage modulation$"),
        ("absence_conges_payes", r"^Absence congés payés"),
        ("indemnite_conges_payes", r"^Indemnité de congés payés \((?P<d>.+)\)$"),
        ("iccp", r"^Indemnité compensatrice de congés payés(?P<d>.*)$"),
        ("precarite", r"^Prime de précarité \(CDD\)$"),
        ("ifm", r"^Indemnité de fin de mission \(intérim\)$"),
        ("avantages_en_nature", r"^Avantages en nature$"),
        ("rappel_salaire", r"^Rappel de salaire(?P<d>.*)$"),
        ("reintegration", r"^Réintégration (?P<d>.+)$"),
        ("heures_nuit", r"^Heures de nuit majorées à .+%$"),
        ("pause_remuneree", r"^Pause rémunérée \(planning\)$"),
    )
)


def slug(texte: Any) -> str:
    """« Absence du 12/09/26 (règle) » → « absence-du-12-09-26-regle »."""
    ascii_ = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")


def famille_du_code(code: str | None) -> str:
    """« brut:heures_sup:25#2 » → « brut:heures_sup » ; « impot » → « impot »."""
    if not code:
        return ""
    return ":".join(code.split("#", 1)[0].split(":")[:2])


def _avec_discriminant(prefixe: str, discriminant: Any) -> str:
    morceau = slug(discriminant)
    return f"{prefixe}:{morceau}" if morceau else prefixe


def _montant_seul(ligne: Mapping[str, Any]) -> bool:
    return (
        ligne.get("quantite") is None
        and ligne.get("taux") is None
        and ligne.get("gain") is not None
        and ligne.get("perte") is None
    )


def code_de_ligne_de_gain(ligne: Mapping[str, Any]) -> str | None:
    libelle = str(ligne.get("libelle") or "")
    if ligne.get("is_sous_total"):
        return "brut:sous_total"
    if ligne.get("is_informative"):
        return _avec_discriminant("brut:information", libelle)
    if ligne.get("saisie_id"):
        return f"brut:saisie:{ligne['saisie_id']}"
    if ligne.get("is_arret_maladie"):
        return _avec_discriminant("brut:arret", libelle)
    if ligne.get("is_maintien_employeur"):
        return "brut:maintien_employeur"
    if ligne.get("is_indemnite_sortie"):
        return _avec_discriminant("brut:indemnite_sortie", libelle)
    meta = ligne.get("meta")
    if isinstance(meta, Mapping) and "plein_mois" in meta:
        return "brut:prime_anciennete"
    for famille, motif in _MOTIFS_DE_GAIN:
        trouve = motif.match(libelle)
        if trouve:
            return _avec_discriminant(f"brut:{famille}", trouve.groupdict().get("d"))
    # Un gain au forfait, sans quantité ni taux (prime d'une règle, rappel
    # d'IJSS…) : il se corrige toujours par son montant.
    if libelle and _montant_seul(ligne):
        return _avec_discriminant("brut:prime", libelle)
    return None


def code_de_ligne_de_cotisation(ligne: Mapping[str, Any]) -> str | None:
    regularisation = ligne.get("regularisation")
    if isinstance(regularisation, Mapping):
        return f"cotisation:regularisation:{regularisation.get('saisie_id') or slug(ligne.get('libelle'))}"
    coti_id = str(ligne.get("coti_id") or "")
    libelle = ligne.get("libelle")
    if not coti_id:
        return _avec_discriminant("cotisation:sans_organisme", libelle) if slug(libelle) else None
    if coti_id in COTI_IDS_A_PLUSIEURS_LIGNES or ligne.get("is_participation") or ligne.get("is_ppv"):
        return _avec_discriminant(f"cotisation:{coti_id}", libelle)
    return f"cotisation:{coti_id}"


def code_de_ligne(bloc: str, ligne: Mapping[str, Any]) -> str | None:
    if bloc == BLOC_BRUT:
        return code_de_ligne_de_gain(ligne)
    if bloc == BLOC_COTISATIONS:
        return code_de_ligne_de_cotisation(ligne)
    if bloc == BLOC_IMPOT:
        return CODE_IMPOT
    return None


def numeroter(codes: Iterable[str | None]) -> list[str | None]:
    """Le deuxième code identique devient « code#2 », le troisième « code#3 »."""
    vus: Counter[str] = Counter()
    sortie: list[str | None] = []
    for code in codes:
        if code is None:
            sortie.append(None)
            continue
        vus[code] += 1
        sortie.append(code if vus[code] == 1 else f"{code}#{vus[code]}")
    return sortie


class Numerotation:
    """La même numérotation que `numeroter`, quand les lignes arrivent une à une."""

    def __init__(self) -> None:
        self._vus: Counter[str] = Counter()

    def code(self, bloc: str, ligne: Mapping[str, Any]) -> str | None:
        code = code_de_ligne(bloc, ligne)
        if code is None:
            return None
        self._vus[code] += 1
        rang = self._vus[code]
        return code if rang == 1 else f"{code}#{rang}"


def champ_du_montant(ligne: Mapping[str, Any]) -> str:
    """Le champ qui porte le montant d'un gain : « gain », ou « perte » pour une retenue."""
    return "perte" if ligne.get("gain") is None and ligne.get("perte") is not None else "gain"


def mode_de_correction(
    bloc: str, ligne: Mapping[str, Any], code: str | None
) -> tuple[str | None, str | None]:
    """Par quoi la ligne se corrige (règle 3), ou pourquoi elle ne se corrige pas ici."""
    if code is None:
        return None, RAISON_INCONNUE
    if bloc == BLOC_IMPOT:
        return MODE_TAUX, None
    famille = famille_du_code(code)
    if bloc == BLOC_BRUT:
        if famille == "brut:sous_total":
            return None, RAISON_SOUS_TOTAL
        if famille == "brut:information":
            return None, RAISON_INFORMATION
        if famille == "brut:saisie":
            return None, RAISON_SAISIE
        if ligne.get("quantite") is not None and ligne.get("taux") is not None:
            return MODE_BASE_OU_TAUX, None
        return MODE_MONTANT, None
    if famille == "cotisation:regularisation":
        return None, RAISON_REGULARISATION
    if ligne.get("is_participation") or ligne.get("is_ppv"):
        return None, RAISON_HORS_SALAIRE
    if str(ligne.get("coti_id") or "") in COTI_IDS_AU_MONTANT:
        return MODE_MONTANT, None
    if ligne.get("base") is not None and (
        ligne.get("taux_salarial") is not None or ligne.get("taux_patronal") is not None
    ):
        return MODE_BASE_OU_TAUX, None
    return MODE_MONTANT, None
