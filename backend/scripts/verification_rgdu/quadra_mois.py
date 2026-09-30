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
from scripts.reprise_colorplast_solde_ouverture import (
    EST_DEDUCTION_HS, EST_HEURE_SUP, EST_REDUCTION_GENERALE, _somme_des_lignes,
)
from scripts.verification_rgdu.chemins import ANNEE, SOCIETES

#: « H.Absence Congés Payés » (salariés à l'heure) et « Jours Absence Congés
#: Payés » (salariés au forfait, vu chez Comitech et Mont-Blanc) : même
#: rubrique, deux unités. Réutilisé aussi par `_heures_sup_detail` : une
#: retenue d'heures sup qui suit une de ces lignes reste payée par
#: l'indemnité de congé (R-H2), elle ne doit pas réduire `heures_sup`.
ABSENCE_CONGES = re.compile(r"ABSENCE\s+CONG", re.I)

#: Nature d'une absence, dans l'ordre où elle est reconnue (la première qui
#: correspond l'emporte). Vérifié en relisant tous les libellés distincts des
#: bulletins réels de Colorplast, Comitech et Mont-Blanc (janvier à août 2026,
#: janvier à juillet pour mbc) — voir l'étape 5 du brief et le rapport de tâche.
NATURES = [
    # « Absence A.T. » (accident du travail, abrégé) : même famille que l'arrêt
    # maladie (R-H4), même formule légale (rapport des salaires ou SMIC entier
    # selon le maintien).
    ("maladie", re.compile(r"ABSENCE\s+MALADIE|ACCIDENT|ARR[EÊ]T|ABSENCE\s+A\.T\.", re.I)),
    # « Enfant malade » (Art. L1225-61) : nature à part, pas fondue dans
    # « non_payee ». Corrigé après revue : elle PEUT être maintenue (vu à
    # 80 % sur trois cas réels Mont-Blanc, ligne d'info « = 80% enfant
    # malade » juste après une ligne « Maintien de salaire ») — ce n'est
    # donc pas systématiquement une absence non payée au sens de R-H3.
    ("enfant_malade", re.compile(r"ENFANT\s+MALADE", re.I)),
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
    ("non_payee", re.compile(r"NON\s*PAY|ABS\s+AUT\s+NON\b", re.I)),
    ("conges_payes", ABSENCE_CONGES),
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
    #: Heures sup payées du mois (lignes en gain).
    heures_sup_payees: float = 0.0
    #: Heures sup retirées pour absence (lignes en retenue, hors congés payés) :
    #: une vraie déduction, pas un artefact — corrigé après revue (l'ancienne
    #: version les additionnait au lieu de les retrancher).
    heures_sup_retirees_absence: float = 0.0
    #: Heures sup retirées par une ligne en retenue qui suit une ligne
    #: d'absence pour congés payés : restent payées par l'indemnité de congé
    #: (R-H2), donc à part, jamais soustraites de `heures_sup`.
    heures_sup_retirees_conges: float = 0.0
    #: = heures_sup_payees − heures_sup_retirees_absence ; reproduit l'avance
    #: du « Cumul h.sup » imprimé par Quadra (`heures_sup_quadra`) sur les
    #: bulletins réels vérifiés (voir le rapport de tâche).
    heures_sup: float = 0.0
    #: Avance du « Cumul h.sup » imprimé par Quadra entre ce mois et le mois
    #: précédent du même matricule (droite `cumul_hs`) : None si le mois
    #: précédent manque, ou si l'un des deux bulletins n'imprime pas ce cumul.
    #: Sert de vérité de référence pour contrôler `heures_sup`, pas à consommer
    #: telle quelle (elle ne distingue pas payées/retirées/congés).
    heures_sup_quadra: float | None = None
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


def _heures_sup_detail(b) -> tuple[float, float, float]:
    """(payées, retirées pour absence, retirées après un congé payé).

    Corrigé après revue : une ligne d'heures sup en retenue (`montant_sal`,
    sans `gain`) est une vraie déduction — des heures sup RETIRÉES pour
    absence — pas un artefact de colonnes comme cru à tort à la première
    écriture de ce module. Vérifié en reproduisant l'avance du « Cumul h.sup »
    imprimé par Quadra sur les bulletins réels (48/48 Colorplast, 122/122
    Comitech ; voir le rapport de tâche, section « Corrections après revue »).

    Exception : une retenue qui suit immédiatement une ligne d'absence pour
    congés payés (« H.Absence Congés Payés » / « Jours Absence Congés Payés »)
    reste payée par l'indemnité de congé (R-H2) — elle ne réduit pas les
    heures sup, elle est seulement comptée à part (`retirees_conges`).

    « EWZB REDUCT HEURES SUPPL. » (réduction forfaitaire patronale, motif
    `EST_DEDUCTION_HS`) n'est ni une paye ni une retenue côté salarié : exclue.
    """
    payees = retirees_absence = retirees_conges = 0.0
    lib_precedent = ""
    for l in b.lignes:
        if EST_HEURE_SUP.search(l.libelle) and not EST_DEDUCTION_HS.search(l.libelle) and l.base is not None:
            if l.gain is not None:
                payees += l.base
            elif l.montant_sal is not None:
                if ABSENCE_CONGES.search(lib_precedent):
                    retirees_conges += l.base
                else:
                    retirees_absence += l.base
        lib_precedent = l.libelle
    return round(payees, 2), round(retirees_absence, 2), round(retirees_conges, 2)


def _heures_sup_quadra(b, prec) -> float | None:
    """Avance du « Cumul h.sup » imprimé par Quadra ; None si l'un des deux mois manque."""
    if prec is None:
        return None
    c, cp = b.droite.get("cumul_hs"), prec.droite.get("cumul_hs")
    if c is None or cp is None:
        return None
    return round(float(c) - float(cp), 2)


def _heures_comp(b) -> float:
    total = 0.0
    for l in b.lignes:
        if EST_HEURE_COMP.search(l.libelle) and (l.gain is not None or l.montant_sal is not None) and l.base is not None:
            total += l.base
    return round(total, 2)


def _ijss(b) -> float:
    """Le gain seulement : `montant_sal` serait une retenue (ex. une IJSS reversée
    à la CPAM après régularisation), pas une seconde IJSS à additionner — `gain or
    montant_sal` compterait deux fois une déduction suivie d'un reversement.
    Corrigé après revue ; aucune ligne réelle n'existe pour le vérifier."""
    return round(sum(l.gain or 0.0 for l in b.lignes if EST_IJSS.search(l.libelle)), 2)


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


def _verifier_bulletin_simple(b, matricule: str) -> None:
    """Refuse un bulletin qui mélangerait plusieurs salariés sous un même matricule.

    Vu réellement chez Mont-Blanc : `MATRICULE` (colorplast_lignes_quadra.py) tronque
    des matricules suffixés (« MIR2 », « MIR3 »…) à leur partie alphabétique, fusionnant
    2 à 3 salariés sous une seule clé — plusieurs lignes « SALAIRE BRUT », plus de deux
    pages (un bulletin réel tient sur une ou deux pages, jamais plus). On ne peut pas
    compter les NIR directement : `colorplast_lignes_quadra` n'en garde qu'un par
    bulletin (`infos["nir"]` n'est jamais réécrit une fois posé), donc un deuxième NIR
    fusionné dedans est invisible depuis `Bulletin.infos` — les pages et les lignes
    « SALAIRE BRUT » sont le signal fiable disponible ici.
    """
    n_brut = sum(1 for l in b.lignes if l.libelle.strip().upper() == "SALAIRE BRUT" and l.gain is not None)
    if n_brut > 1 or len(b.pages) > 2:
        raise ValueError(
            f"bulletin {matricule} : {n_brut} ligne(s) SALAIRE BRUT sur {len(b.pages)} page(s) — "
            "plusieurs salariés semblent fusionnés sous ce matricule (troncature de MATRICULE "
            "dans scripts/backtest/colorplast_lignes_quadra.py)"
        )


def elements_du_mois(bulletins: dict, precedents: dict | None, societe: str, mois: int) -> list[MoisQuadra]:
    sortie: list[MoisQuadra] = []
    for mat, b in sorted(bulletins.items()):
        _verifier_bulletin_simple(b, mat)
        prec = (precedents or {}).get(mat)
        cumul_h = float(b.droite.get("cumul_heures") or 0.0)
        heures_periode = b.droite.get("heures_periode")
        if heures_periode is not None:
            # Fiable dans tous les cas : imprimé par Quadra pour le mois, sans dépendre
            # du mois précédent.
            heures_mois = round(float(heures_periode), 2)
        else:
            # Repli seulement : faux quand le bulletin précédent manque (nouvel
            # embauché, ou janvier) — la différence de cumul part alors de zéro et
            # compte tout l'historique comme le mois en cours. Vu réellement à
            # Mont-Blanc (avril, mai) : corrigé après revue.
            h_prec = float(prec.droite.get("cumul_heures") or 0.0) if prec else 0.0
            heures_mois = round(cumul_h - h_prec, 2)
        payees, retirees_absence, retirees_conges = _heures_sup_detail(b)
        m = MoisQuadra(
            societe=societe, mois=mois, matricule=mat, nir=str(b.infos.get("nir") or "")[:13],
            brut_mois=_brut(b), cumul_bruts=float(b.droite.get("cumul_bruts") or 0.0),
            cumul_heures=cumul_h, heures_mois=heures_mois,
            reduction_mois=round(-_somme_des_lignes(b, EST_REDUCTION_GENERALE), 2),
            entree=_dans_le_mois(b.infos.get("entree"), ANNEE, mois),
            sortie=_dans_le_mois(b.infos.get("sortie"), ANNEE, mois),
            heures_base=_heures_base(b),
            heures_sup_payees=payees, heures_sup_retirees_absence=retirees_absence,
            heures_sup_retirees_conges=retirees_conges,
            heures_sup=round(payees - retirees_absence, 2), heures_sup_quadra=_heures_sup_quadra(b, prec),
            heures_comp=_heures_comp(b), ijss=_ijss(b), indemnite_preavis=_indemnite_preavis(b),
        )
        for l in b.lignes:
            lib = l.libelle.strip()
            if f := FORFAIT.search(lib):
                m.forfait_jours = int(f.group(1))
            if EST_MAINTIEN.search(lib) and l.gain:
                m.maintien = round(m.maintien + l.gain, 2)
            elif l.base is None and l.montant_sal is None:
                # Ligne d'information sans heures ni montant (ex. « jour enfant malade
                # 02/02 », « le 08-01 = 80% enfant malade ») : rien à retenir pour la
                # réduction, jamais une absence en soi. Corrigé après revue.
                continue
            elif EST_ABSENCE.search(lib) or _nature(lib) != "autre":
                m.absences.append(Absence(_nature(lib), lib, l.base, l.montant_sal))
        sortie.append(m)
    return sortie


def lire_societe(societe: str) -> dict[tuple[str, int], MoisQuadra]:
    """Indexé par `(clé, mois)`, où `clé` = `"{nir}/{matricule}"` si le NIR est connu,
    sinon le matricule seul.

    Corrigé après revue : indexer par le seul NIR écrasait en silence un salarié qui
    change de matricule sans changer de NIR dans le même mois (contrats successifs :
    ex. un CDD sorti le 30 et un contrat d'apprentissage entré le 31 du même mois,
    vu réellement chez Comitech en août — même NIR, deux matricules, deux bulletins).
    Le matricule fait partie de la clé pour que les deux survivent.
    """
    lus = {m: lire_bulletins(ANNEE, m, SOCIETES[societe]["dossier"]) for m in SOCIETES[societe]["mois"]}
    index: dict[tuple[str, int], MoisQuadra] = {}
    for m in SOCIETES[societe]["mois"]:
        for mq in elements_du_mois(lus[m], lus.get(m - 1), societe, m):
            cle = f"{mq.nir}/{mq.matricule}" if mq.nir else mq.matricule
            index[(cle, m)] = mq
    return index
