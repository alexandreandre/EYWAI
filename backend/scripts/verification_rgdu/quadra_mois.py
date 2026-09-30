"""Éléments du mois utiles à la réduction, tirés des bulletins Quadra (PDF).

Complète, par salarié et par mois, ce que la tâche 9 lit pour calculer le SMIC
de référence légal (docs/reference/reduction-generale-2026/regles.md, R-H1 à
R-H12) : le brut du mois, les cumuls, les heures, les absences typées, le
maintien de salaire, le forfait jours, l'entrée/la sortie — et, pour la
formule légale elle-même, la base horaire du salaire, les heures
supplémentaires et complémentaires payées, les IJSS subrogées et l'indemnité
de préavis.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from scripts.backtest.colorplast_lignes_quadra import lire_bulletins
from scripts.reprise_colorplast_solde_ouverture import EST_HEURE_SUP, EST_REDUCTION_GENERALE, _somme_des_lignes
from scripts.verification_rgdu.chemins import ANNEE, SOCIETES

#: Nature d'une absence, dans l'ordre où elle est reconnue (la première qui
#: correspond l'emporte). Vérifié en relisant tous les libellés distincts des
#: bulletins réels de Colorplast, Comitech et Mont-Blanc (janvier à août 2026,
#: janvier à juillet pour mbc) — voir l'étape 5 du brief et le rapport de tâche.
NATURES = [
    # « Absence A.T. » (accident du travail, abrégé) : même famille que l'arrêt
    # maladie (R-H4), même formule légale (rapport des salaires ou SMIC entier
    # selon le maintien).
    ("maladie", re.compile(r"ABSENCE\s+MALADIE|ACCIDENT|ARR[EÊ]T|ABSENCE\s+A\.T\.", re.I)),
    ("paternite", re.compile(r"PATERNIT|MATERNIT", re.I)),
    ("evenement_familial", re.compile(r"EVT\s+FAMIL", re.I)),
    # Quadra tronque parfois « injustifiée » en « injusti » quand la ligne
    # porte une plage de dates au lieu d'une seule date : motif raccourci pour
    # attraper les deux formes (« injusti » est un préfixe de « injustifiée »).
    ("injustifiee", re.compile(r"INJUSTI", re.I)),
    # Même troncature pour « s.solde » → « s.so » sur les plages de dates.
    ("sans_solde", re.compile(r"S\.?\s*SO(?:LDE)?\b", re.I)),
    # « Abs aut nonpayé DATE » (jour unique) vs « Abs aut non DATE-DATE » (plage,
    # tronqué avant « payé ») : même absence, deux habillages Quadra.
    # « Enfant malade » (Art. L1225-61) : jamais maintenu sur les bulletins vus,
    # donc une absence non payée au sens de R-H3 — pas un arrêt maladie du
    # salarié lui-même (R-H4, qui a son propre régime IJSS/subrogation).
    ("non_payee", re.compile(r"NON\s*PAY|ABS\s+AUT\s+NON\b|ENFANT\s+MALADE", re.I)),
    # « H.Absence Congés Payés » (salariés à l'heure) et « Jours Absence
    # Congés Payés » (salariés au forfait, vu chez Comitech et Mont-Blanc) :
    # même rubrique, deux unités.
    ("conges_payes", re.compile(r"ABSENCE\s+CONG", re.I)),
]
EST_ABSENCE = re.compile(r"^ABS|ABSENCE|MALADIE|PATERNIT", re.I)
EST_MAINTIEN = re.compile(r"MAINTIEN", re.I)
FORFAIT = re.compile(r"FORFAIT\s+(\d{2,3})\s+JOURS", re.I)
#: Heures complémentaires (temps partiel, L3123-8/-9/-20/-28) : jamais vues sur
#: les bulletins relus (aucun salarié à temps partiel n'en a eu sur la
#: période) — motif écrit d'après le terme légal, à confirmer sur un vrai
#: bulletin dès qu'un cas se présente (voir le rapport de tâche).
EST_HEURE_COMP = re.compile(r"HEURES?\s+COMPL[EÉ]MENTAIRES?", re.I)
#: Indemnités journalières de sécurité sociale, subrogées : aucun libellé
#: trouvé sur les bulletins relus (voir le rapport de tâche) — motif d'après
#: le terme légal, non vérifié.
EST_IJSS = re.compile(r"\bIJSS\b|INDEMNIT[EÉ]S?\s+JOURNALI[EÈ]RES?", re.I)
#: Indemnité (compensatrice) de préavis : aucun libellé trouvé sur les
#: bulletins relus (voir le rapport de tâche) — motif d'après le terme légal,
#: non vérifié.
EST_PREAVIS = re.compile(r"PR[EÉ]AVIS", re.I)
_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


@dataclass
class Absence:
    nature: str
    libelle: str
    heures: float | None
    montant: float | None


@dataclass
class MoisQuadra:
    societe: str
    mois: int
    matricule: str
    nir: str
    brut_mois: float
    cumul_bruts: float
    cumul_heures: float
    heures_mois: float
    reduction_mois: float
    absences: list[Absence] = field(default_factory=list)
    maintien: float = 0.0
    forfait_jours: int | None = None
    entree: str | None = None
    sortie: str | None = None
    #: Base horaire de la ligne « SALAIRE DE BASE » (151,67 h à temps plein) ;
    #: None pour un forfait jours, qui n'en a pas.
    heures_base: float | None = None
    #: Heures supplémentaires payées du mois (base des lignes, signe conservé :
    #: une ligne qui retirerait des heures sup pour absence les soustrairait).
    heures_sup: float = 0.0
    #: Heures complémentaires payées du mois (temps partiel).
    heures_comp: float = 0.0
    #: IJSS subrogées reprises sur le bulletin.
    ijss: float = 0.0
    #: Indemnité (compensatrice) de préavis du mois, si la ligne existe.
    indemnite_preavis: float | None = None


def _nature(libelle: str) -> str:
    return next((n for n, motif in NATURES if motif.search(libelle)), "autre")


def _brut(b) -> float:
    return next((round(l.gain, 2) for l in b.lignes if l.libelle.strip().upper() == "SALAIRE BRUT" and l.gain is not None), 0.0)


def _heures_base(b) -> float | None:
    return next((round(l.base, 2) for l in b.lignes if l.libelle.strip().upper() == "SALAIRE DE BASE" and l.base is not None), None)


def _heures_sup(b) -> float:
    """Base horaire des lignes d'heures sup payées, moins celles qui en retirent pour absence.

    Les lignes vues sur les bulletins réels sont toutes des paiements (base et
    montant positifs, base × taux = montant) : aucune n'est une vraie retenue
    (montant négatif). Certaines de ces lignes payées atterrissent malgré tout
    dans `montant_sal` plutôt que `gain` — un artefact de `colorplast_lignes_quadra`
    pour les petits montants (la colonne détectée par position de caractères
    est trop étroite) — donc on prend `base` dès que l'une ou l'autre colonne
    salariale est renseignée, jamais seulement `montant_pat` (ligne purement
    patronale, ex. « EWZB REDUCT HEURES SUPPL. »). Si une vraie retenue
    apparaît un jour (base négative), l'addition la soustrait naturellement.
    """
    total = 0.0
    for l in b.lignes:
        if EST_HEURE_SUP.search(l.libelle) and (l.gain is not None or l.montant_sal is not None) and l.base is not None:
            total += l.base
    return round(total, 2)


def _heures_comp(b) -> float:
    total = 0.0
    for l in b.lignes:
        if EST_HEURE_COMP.search(l.libelle) and (l.gain is not None or l.montant_sal is not None) and l.base is not None:
            total += l.base
    return round(total, 2)


def _ijss(b) -> float:
    return round(sum(l.gain or l.montant_sal or 0.0 for l in b.lignes if EST_IJSS.search(l.libelle)), 2)


def _indemnite_preavis(b) -> float | None:
    return next((round(l.gain, 2) for l in b.lignes if EST_PREAVIS.search(l.libelle) and l.gain is not None), None)


def _dans_le_mois(date_str: str | None, annee: int, mois: int) -> str | None:
    """Renvoie la date si elle tombe dans (annee, mois), sinon None.

    L'en-tête du bulletin (`infos["entree"]`/`infos["sortie"]`) répète la date
    d'entrée ou de sortie sur TOUS les mois de présence, pas seulement celui
    de l'événement : sans ce filtre, `entree`/`sortie` serait renseigné sur
    chaque bulletin. Vérifié sur un salarié entré en cours de mois (avril) et
    un autre sorti en cours de mois (juillet) : le champ n'est renseigné que
    ce mois-là dans les deux cas.
    """
    if not date_str:
        return None
    m = _DATE.match(date_str.strip())
    if not m:
        return None
    _jour, m_, a = m.groups()
    return date_str if (int(a), int(m_)) == (annee, mois) else None


def elements_du_mois(bulletins: dict, precedents: dict | None, societe: str, mois: int) -> list[MoisQuadra]:
    sortie: list[MoisQuadra] = []
    for mat, b in sorted(bulletins.items()):
        prec = (precedents or {}).get(mat)
        cumul_h = float(b.droite.get("cumul_heures") or 0.0)
        h_prec = float(prec.droite.get("cumul_heures") or 0.0) if prec else 0.0
        m = MoisQuadra(
            societe=societe, mois=mois, matricule=mat, nir=str(b.infos.get("nir") or "")[:13],
            brut_mois=_brut(b), cumul_bruts=float(b.droite.get("cumul_bruts") or 0.0),
            cumul_heures=cumul_h, heures_mois=round(cumul_h - h_prec, 2),
            reduction_mois=round(-_somme_des_lignes(b, EST_REDUCTION_GENERALE), 2),
            entree=_dans_le_mois(b.infos.get("entree"), ANNEE, mois),
            sortie=_dans_le_mois(b.infos.get("sortie"), ANNEE, mois),
            heures_base=_heures_base(b), heures_sup=_heures_sup(b), heures_comp=_heures_comp(b),
            ijss=_ijss(b), indemnite_preavis=_indemnite_preavis(b),
        )
        for l in b.lignes:
            lib = l.libelle.strip()
            if f := FORFAIT.search(lib):
                m.forfait_jours = int(f.group(1))
            if EST_MAINTIEN.search(lib) and l.gain:
                m.maintien = round(m.maintien + l.gain, 2)
            elif EST_ABSENCE.search(lib) or _nature(lib) != "autre":
                m.absences.append(Absence(_nature(lib), lib, l.base, l.montant_sal))
        sortie.append(m)
    return sortie


def lire_societe(societe: str) -> dict[tuple[str, int], MoisQuadra]:
    lus = {m: lire_bulletins(ANNEE, m, SOCIETES[societe]["dossier"]) for m in SOCIETES[societe]["mois"]}
    index: dict[tuple[str, int], MoisQuadra] = {}
    for m in SOCIETES[societe]["mois"]:
        for mq in elements_du_mois(lus[m], lus.get(m - 1), societe, m):
            index[(mq.nir or mq.matricule, m)] = mq
    return index
