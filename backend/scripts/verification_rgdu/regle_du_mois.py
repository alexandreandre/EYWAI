"""SMIC légal du mois, tiré d'un bulletin Quadra (docs/reference/reduction-generale-2026/regles.md).

La loi (CSS D241-7, IV) part du SMIC d'un mois complet et le corrige, quand le salarié n'est
pas payé tout le mois, du **rapport des salaires** : rémunération due ÷ rémunération d'un mois
complet, hors éléments non affectés par l'absence, plafonné à 1. Les heures structurelles
suivent le rapport ; les heures supplémentaires occasionnelles et complémentaires s'ajoutent
ensuite, entières (`oracle_smic`, choix de calcul n° 3).

Ce module lit le bulletin pour fournir ces deux montants :

- **mois complet** = salaire de base + heures structurelles payées (« H. supp majorées ») ;
  quand le salaire de base est proratisé (entrée ou sortie sans ligne « Absence pour entrée ou
  sortie »), ces heures viennent d'un autre mois du même contrat (`choisir_reference`),
  valorisées au taux du mois ;
- **rémunération due** = ce mois complet payé, moins toutes les retenues d'absence (« autre »
  compris) et les heures structurelles retirées, plus le maintien de salaire (tout le maintien
  du bulletin, pas celui de la seule maladie) et les IJ complémentaires de prévoyance.

Primes, indemnités de congés payés, indemnités de rupture, régularisations et participation
restent hors du rapport : elles sont soit non affectées par l'absence (R-H3, R-H7, R-H12),
soit proportionnelles au salaire de base et sans effet sur le rapport. Les congés payés pris
ne réduisent rien (R-H2) : leur retenue, les heures structurelles retirées juste après et
l'indemnité se neutralisent et sortent du calcul.

Points non tranchés, jamais un chiffre choisi en silence :
- n° 1 (maintien à 100 % sous déduction des IJSS) : les bulletins Quadra n'impriment aucune
  ligne d'IJSS. Un arrêt (maladie, accident, rechute, temps partiel thérapeutique, paternité)
  dont le maintien ne couvre pas toute la retenue porte deux lectures, « rapport_salaires »
  (principale) et « smic_entier » (variante : l'arrêt compte comme payé), sauf si une ligne
  d'information du bulletin donne un taux inférieur à 100 % ou une carence : maintien partiel,
  rapport seul (R-H4) ;
- n° 4 (indemnité de préavis) : « hors_rapport » (principale) et « dans_rapport » (variante).

Indépendant du moteur : ne rien importer de app/.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from scripts.verification_rgdu.chemins import ANNEE
from scripts.verification_rgdu.oracle_smic import (
    DUREE_LEGALE_MENSUELLE, mois_incomplet, smic_au_rapport_des_salaires, smic_entree_sortie,
)
from scripts.verification_rgdu.quadra_mois import (
    ABSENCE_CONGES, EST_ABSENCE, EST_HEURE_COMP, NATURES, MoisQuadra,
)

EST_SALAIRE_BASE = re.compile(r"^SALAIRE\s+DE\s+BASE\b", re.I)
#: « H. supp majorées à 25 % » : heures structurelles (horaire collectif au-delà de 35 h).
EST_HS_STRUCTURELLE = re.compile(r"H\.?\s*SUPP\S*\s+MAJOR", re.I)
#: « Heures supplémentaires 25 / 50 » : heures occasionnelles du mois.
EST_HS_OCCASIONNELLE = re.compile(r"^HEURES\s+SUPPL", re.I)
EST_MAINTIEN = re.compile(r"MAINTIEN", re.I)
EST_RAPPEL = re.compile(r"RAPPEL", re.I)
#: IJ complémentaires de prévoyance reprises sur le bulletin (R-H4 : elles entrent dans le
#: rapport si l'employeur les finance, même en partie).
EST_IJ_COMPLEMENTAIRE = re.compile(r"COMPL\S*\s*PR[EÉ]VOYANCE", re.I)
EST_REGULARISATION = re.compile(r"R[EÉ]GULARISATION\s+SALAIRE", re.I)
#: Arrêts que `quadra_mois.NATURES` ne reconnaît pas : prolongation (rechute) et temps partiel
#: thérapeutique, tous deux indemnisés par la sécurité sociale comme un arrêt maladie.
EST_ARRET_SUPPLEMENTAIRE = re.compile(r"RECHUTE|TPS\.?\s*PART\.?\s*TH[EÉ]RA", re.I)
EST_ENTREE_SORTIE = re.compile(r"ENTR[EÉ]E\s+OU\s+SORTIE", re.I)
EST_JOUR_FERIE = re.compile(r"\bJF\b|F[EÉ]RI[EÉ]", re.I)
TAUX_LU = re.compile(r"(\d{2,3})\s*%")
EST_CARENCE = re.compile(r"CARENCE", re.I)
_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

#: Suspensions indemnisées par la sécurité sociale : seules concernées par le point n° 1.
NATURES_ARRET = {"maladie", "paternite"}
REGLE_DE_LA_NATURE = {
    "non_payee": "R-H3", "injustifiee": "R-H3", "sans_solde": "R-H3", "autre": "R-H3",
    "maladie": "R-H4", "paternite": "R-H5", "evenement_familial": "R-H5", "enfant_malade": "R-H5",
}
_TOLERANCE = 0.005


@dataclass
class Retenue:
    """Une retenue qui entre dans le rapport des salaires.

    `nature` : celle de `quadra_mois.NATURES` (« autre » compris), ou « heures_sup » pour des
    heures structurelles retirées. `arret` : la part du montant qui revient à un arrêt
    (`NATURES_ARRET`) — tout le montant pour une ligne d'arrêt, la part au prorata des heures
    pour des heures structurelles retirées à la suite d'un groupe d'absences."""
    nature: str
    libelle: str
    heures: float | None
    montant: float
    arret: float = 0.0


@dataclass
class ElementsLoi:
    """Ce que la loi lit sur un bulletin Quadra, lignes au-dessus de « SALAIRE BRUT »."""
    salaire_base: float | None = None
    heures_base: float | None = None
    taux_base: float | None = None
    heures_structurelles: float = 0.0
    montant_structurelles: float = 0.0
    taux_structurelles: float | None = None
    heures_occasionnelles: float = 0.0
    heures_comp: float = 0.0
    retenues: list[Retenue] = field(default_factory=list)
    maintien: float = 0.0
    rappel_maintien: bool = False
    ij_complementaires: float = 0.0
    conges_payes: bool = False
    regularisation: bool = False
    taux_maintien_lus: list[int] = field(default_factory=list)
    carence_lue: bool = False


@dataclass
class SmicLoi:
    """SMIC légal du mois. `smic_variante` et `variante` portent la seconde lecture d'un point
    non tranché (« point_1_subrogation » ou « point_4_preavis »). `regle` : les ID de
    regles.md appliqués. `note` : ce qu'un relecteur doit savoir, en une phrase par point."""
    smic: float | None
    smic_variante: float | None = None
    variante: str = ""
    regle: str = ""
    note: str = ""


def _nature(libelle: str) -> str:
    if EST_ARRET_SUPPLEMENTAIRE.search(libelle):
        return "maladie"
    return next((n for n, motif in NATURES if motif.search(libelle)), "autre")


def _est_info(l) -> bool:
    return l.base is None and l.montant_sal is None and l.gain is None and l.taux is None


def elements_loi(bulletin) -> ElementsLoi:
    """Lit les lignes du bulletin jusqu'à « SALAIRE BRUT » (voir la docstring du module).

    Une retenue d'heures structurelles qui suit immédiatement une retenue de congés payés reste
    payée par l'indemnité de congé (R-H2, même règle que `quadra_mois`) : hors du rapport. Les
    autres sont rattachées au groupe d'absences qui les précède, au prorata des heures, pour
    savoir quelle part revient à un arrêt."""
    el = ElementsLoi()
    groupe: list[Retenue] = []
    precedent = ""
    for l in bulletin.lignes:
        lib = l.libelle.strip()
        if lib.upper() == "SALAIRE BRUT":
            break
        if l.gain is not None:
            if EST_SALAIRE_BASE.search(lib):
                el.salaire_base = round((el.salaire_base or 0.0) + l.gain, 2)
                if l.base is not None:
                    el.heures_base = round((el.heures_base or 0.0) + l.base, 2)
                el.taux_base = l.taux if l.taux is not None else el.taux_base
            elif EST_HS_STRUCTURELLE.search(lib) and l.base is not None:
                el.heures_structurelles = round(el.heures_structurelles + l.base, 2)
                el.montant_structurelles = round(el.montant_structurelles + l.gain, 2)
                el.taux_structurelles = l.taux if l.taux is not None else el.taux_structurelles
            elif EST_HS_OCCASIONNELLE.search(lib) and l.base is not None:
                el.heures_occasionnelles = round(el.heures_occasionnelles + l.base, 2)
            elif EST_HEURE_COMP.search(lib) and l.base is not None:
                el.heures_comp = round(el.heures_comp + l.base, 2)
            elif EST_MAINTIEN.search(lib):
                el.maintien = round(el.maintien + l.gain, 2)
                el.rappel_maintien = el.rappel_maintien or bool(EST_RAPPEL.search(lib))
            elif EST_IJ_COMPLEMENTAIRE.search(lib):
                el.ij_complementaires = round(el.ij_complementaires + l.gain, 2)
            elif EST_REGULARISATION.search(lib):
                el.regularisation = True
        elif l.montant_sal is not None:
            if ABSENCE_CONGES.search(lib):
                el.conges_payes = True
            elif EST_HS_STRUCTURELLE.search(lib) and l.base is not None:
                if not ABSENCE_CONGES.search(precedent):
                    heures = sum(r.heures or 0.0 for r in groupe)
                    part = (sum(r.heures or 0.0 for r in groupe if r.nature in NATURES_ARRET) / heures
                            if heures else 0.0)
                    el.retenues.append(Retenue("heures_sup", lib, l.base, l.montant_sal, l.montant_sal * part))
                    groupe = []
            elif EST_ABSENCE.search(lib) or EST_ARRET_SUPPLEMENTAIRE.search(lib) or _nature(lib) != "autre":
                nature = _nature(lib)
                if nature == "conges_payes":
                    el.conges_payes = True
                else:
                    r = Retenue(nature, lib, l.base, l.montant_sal,
                                l.montant_sal if nature in NATURES_ARRET else 0.0)
                    el.retenues.append(r)
                    groupe.append(r)
        elif _est_info(l):
            el.taux_maintien_lus += [int(t) for t in TAUX_LU.findall(lib)]
            el.carence_lue = el.carence_lue or bool(EST_CARENCE.search(lib))
        precedent = lib
    return el


def _normal(mq: MoisQuadra, el: ElementsLoi) -> bool:
    return mq.entree is None and mq.sortie is None and bool(el.salaire_base) and el.salaire_base > 0


def choisir_reference(mois: dict[int, tuple[MoisQuadra, ElementsLoi]], mois_cible: int) -> ElementsLoi | None:
    """Le mois « normal » du même contrat le plus proche de `mois_cible` (ni entrée ni sortie
    dans le mois, un salaire de base payé) : il donne le mois complet d'un salaire de base
    proratisé. À distance égale, le mois antérieur. None s'il n'y en a aucun."""
    candidats = sorted((abs(m - mois_cible), m) for m, (mq, el) in mois.items()
                       if m != mois_cible and _normal(mq, el))
    return mois[candidats[0][1]][1] if candidats else None


def _date(texte: str | None) -> date | None:
    m = _DATE.match((texte or "").strip())
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def _mois_complet(mq: MoisQuadra, el: ElementsLoi, reference: ElementsLoi | None,
                  incomplet: bool) -> tuple[float | None, float | None, float, str]:
    """(mois complet, durée du contrat, heures structurelles d'un mois complet, note).
    Mois complet None : impossible sans deviner (la note dit pourquoi)."""
    propre = el.salaire_base + el.montant_structurelles
    ligne_es = any(EST_ENTREE_SORTIE.search(r.libelle) for r in el.retenues)
    if mq.forfait_jours:
        if incomplet and not ligne_es:
            if reference is None or not reference.salaire_base:
                return None, None, 0.0, "mois complet inconnu : forfait payé au prorata sans autre mois du contrat"
            if reference.salaire_base > el.salaire_base + _TOLERANCE:
                return reference.salaire_base, None, 0.0, "mois complet repris d'un autre mois du contrat"
        return el.salaire_base, None, 0.0, ""
    if el.heures_base is None:
        return None, None, 0.0, "salaire de base sans heures : durée du contrat inconnue"
    if not incomplet or ligne_es:
        return propre, el.heures_base, el.heures_structurelles, ""
    if reference is None or reference.heures_base is None:
        if el.heures_base >= DUREE_LEGALE_MENSUELLE - 0.01:
            return propre, el.heures_base, el.heures_structurelles, ""
        return None, None, 0.0, (f"mois complet inconnu : salaire de base proratisé ({el.heures_base} h) "
                                 "sans autre mois du contrat")
    if el.heures_base >= reference.heures_base - 0.01:
        return propre, el.heures_base, el.heures_structurelles, ""
    taux = el.taux_base if el.taux_base is not None else reference.taux_base
    taux_hs = el.taux_structurelles if el.taux_structurelles is not None else reference.taux_structurelles
    if taux is None:
        complet = reference.salaire_base + reference.montant_structurelles
    else:
        complet = reference.heures_base * taux + reference.heures_structurelles * (taux_hs or 0.0)
    return (complet, reference.heures_base, reference.heures_structurelles,
            f"salaire de base proratisé ({el.heures_base} h) : mois complet de {reference.heures_base} h "
            "repris d'un autre mois du contrat")


def _regles(mq: MoisQuadra, el: ElementsLoi, duree: float | None, incomplet: bool) -> str:
    ids: list[str] = []
    if el.conges_payes:
        ids.append("R-H2")
    for r in el.retenues:
        if r.nature == "heures_sup":
            continue
        rid = "R-H6" if EST_JOUR_FERIE.search(r.libelle) else REGLE_DE_LA_NATURE.get(r.nature, "R-H3")
        if rid not in ids:
            ids.append(rid)
    if incomplet:
        ids.append("R-H7")
    if mq.forfait_jours:
        ids.append("R-H9")
    elif duree is not None and duree < DUREE_LEGALE_MENSUELLE - 0.01:
        ids.append("R-H8")
    return ", ".join(sorted(ids) or ["R-H1"])


def smic_loi_du_mois(mq: MoisQuadra, el: ElementsLoi, reference: ElementsLoi | None = None) -> SmicLoi:
    """SMIC légal du mois de `mq`, lu sur ses éléments de bulletin `el` ; `reference` : les
    éléments d'un mois normal du même contrat (`choisir_reference`), pour un salaire de base
    proratisé. Voir la docstring du module pour la méthode et les deux points non tranchés."""
    if not el.salaire_base or el.salaire_base <= 0:
        return SmicLoi(None, regle="R-A2", note="bulletin sans salaire du mois")
    entree, sortie = _date(mq.entree), _date(mq.sortie)
    try:
        incomplet = mois_incomplet(ANNEE, mq.mois, entree, sortie)
    except ValueError:
        return SmicLoi(None, regle="R-H7, R-A2",
                       note="aucun jour de contrat dans le mois : aucun SMIC (R-A2 d)")

    complet, duree, structurelles, note_complet = _mois_complet(mq, el, reference, incomplet)
    notes = [note_complet] if note_complet else []
    if complet is None or complet <= 0:
        return SmicLoi(None, regle="R-H7" if incomplet else "R-H1", note=note_complet or "mois complet nul")
    if duree is not None and duree > DUREE_LEGALE_MENSUELLE + 0.01:
        return SmicLoi(None, note=f"salaire de base de {duree} h, au-delà de la durée légale : non interprété")

    retenues = sum(r.montant for r in el.retenues)
    maintien = el.maintien + el.ij_complementaires
    due = el.salaire_base + el.montant_structurelles - retenues + maintien

    preavis = mq.indemnite_preavis or 0.0

    def calcul(remuneration_due: float, variante_preavis: str = "hors_rapport") -> float:
        if mq.forfait_jours:
            kw = {"jours_forfait": mq.forfait_jours}
            base = None
        else:
            kw = {"heures_structurelles": structurelles,
                  "heures_sup_occasionnelles": el.heures_occasionnelles, "heures_comp": el.heures_comp}
            base = duree
        if incomplet:
            return smic_entree_sortie(base, remuneration_due, complet, indemnite_preavis=preavis,
                                      variante_preavis=variante_preavis if preavis else None, **kw)
        return smic_au_rapport_des_salaires(base, remuneration_due, complet, **kw)

    res = SmicLoi(calcul(due), regle=_regles(mq, el, duree, incomplet))
    if mq.forfait_jours and (el.heures_occasionnelles or el.heures_comp):
        notes.append("heures supplémentaires lues sur un forfait jours : ignorées (R-H9)")

    # Point non tranché n° 1 : arrêt dont le maintien ne couvre pas toute la retenue.
    arret = sum(r.arret for r in el.retenues)
    ecart = arret - maintien
    if any(r.nature in NATURES_ARRET for r in el.retenues) and maintien > 0 and ecart > _TOLERANCE:
        partiels = [t for t in el.taux_maintien_lus if t < 100]
        if partiels or el.carence_lue:
            lu = ", ".join(f"{t} %" for t in partiels) + (" carence" if el.carence_lue else "")
            notes.append(f"maintien partiel lu sur le bulletin ({lu.strip(', ')}) : rapport des salaires seul (R-H4)")
        else:
            res.smic_variante = calcul(due + ecart)
            res.variante = "point_1_subrogation"
            constat = ("maintien à 100 % lu sur le bulletin" if 100 in el.taux_maintien_lus
                       else "maintien intégral ou partiel indiscernable")
            croise = []
            if incomplet:
                croise.append("entrée" if entree and entree.month == mq.mois else "sortie")
            if any(r.nature not in NATURES_ARRET and r.nature != "heures_sup" and r.montant > 0
                   for r in el.retenues):
                croise.append("absence")
            notes.append(f"point n° 1{''.join(' × ' + c for c in croise)} : maintien de salaire sans ligne "
                         f"d'IJSS, {constat} ; lecture principale rapport_salaires, variante smic_entier")

    # Point non tranché n° 4 : indemnité compensatrice de préavis au mois de sortie.
    if preavis and incomplet:
        if res.variante:
            notes.append("point n° 4 (préavis) non combiné au point n° 1 : lecture hors_rapport seule")
        else:
            res.smic_variante = calcul(due, "dans_rapport")
            res.variante = "point_4_preavis"
            notes.append("point n° 4 : indemnité de préavis hors du rapport (principale) ou dedans (variante)")

    if any(EST_ENTREE_SORTIE.search(r.libelle) for r in el.retenues) and not incomplet:
        notes.append("retenue « Absence pour entrée ou sortie » sans entrée ni sortie dans le mois")
    if el.rappel_maintien:
        notes.append("rappel de maintien de salaire compté dans le mois (rattachement des rappels non tranché, R-B1)")
    if el.ij_complementaires:
        notes.append("IJ complémentaires de prévoyance comptées dans le rapport (R-H4)")
    if el.regularisation:
        notes.append("régularisation de salaire hors du rapport (R-B1)")
    if mq.mois == 6 and sortie is not None and sortie.month == 6:
        notes.append("contrat terminé en juin : tolérance du BOSS § 360, un SMIC à 12,31 € est admis (R-F2)")
    res.note = " ; ".join(notes)
    return res
