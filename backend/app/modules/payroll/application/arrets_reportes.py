"""Arrêts reportés : un arrêt arrivé après la paie de son mois passe sur le bulletin suivant.

Ce que fait Quadra chez LEWIS et Cartol, et le cabinet de Colorplast (retour
d'Elsa du 26/11/2026, bulletins de février à octobre 2026 relus) : l'arrêt est
compté sur le bulletin de la période qui le contient ; connu après que ce
bulletin est fait, il passe sur le bulletin suivant, avec ses vraies dates
(Cartol : « Absence maladie 230726-240726 » sur le bulletin d'août, rien en
juillet). Martine ne le faisait pas : un arrêt saisi après la validation du
bulletin de son mois n'était sur aucun bulletin.

Un jour d'arrêt est reporté sur le bulletin du mois M quand :
- le bulletin de la période précédente existe et est validé (il ne se
  régénère plus) ;
- ce bulletin ne l'a pas compté : sa trace (`arrets_du_bulletin`, posée sur
  tout bulletin calculé depuis ce lot) ne le porte pas, ou, sans trace,
  aucune de ses retenues datées ne le couvre (« Absence maladie 220926-230926 »
  d'un bulletin repris, « … du 01/10 au 30/10 » de Martine) ;
- la gestionnaire ne l'a pas déjà porté à la main : régularisation antérieure
  du même jour au planning du mois (aux heures), ou heures normales de ce mois
  reprises depuis l'onglet « Corriger » (elles couvrent autant de journées,
  le reste est repris, et le bulletin le dit).

Le report réutilise le mécanisme des régularisations antérieures
(`is_regularisation_anterieure`) : l'événement garde sa date d'origine, la
retenue et le maintien se calculent sur ses vraies dates. La DSN du mois
déclare l'arrêt (bloc 60) à ses vraies dates : arrêt pris en compte après la
clôture de la paie de son mois (fiche net-entreprises « Gestion des arrêts de
travail en DSN »). Seule la période précédente est regardée : « le bulletin
suivant ». Si le bulletin suivant était déjà validé lui aussi, l'écran
« Arrêts & IJ » dit de le porter à la main.
"""

from __future__ import annotations

import calendar
import logging
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)

#: Les arrêts indemnisés par la CPAM (mêmes types que le suivi des IJ).
TYPES_ARRET_REPORTABLES = frozenset(
    {
        "arret_maladie",
        "arret_at",
        "arret_paternite",
        "arret_maternite",
        "arret_maladie_pro",
    }
)

#: Clé de `payslip_data` : les jours d'arrêt que le bulletin compte, dont ceux
#: qu'il reporte d'un bulletin précédent.
CLE_TRACE = "arrets_du_bulletin"

#: Statut d'un bulletin qui ne se régénère plus sans forçage.
STATUT_VALIDE = "valide"


@dataclass(frozen=True)
class JourReporte:
    jour: date
    absence_id: str
    #: Jour déjà retenu par le bulletin d'origine comme absence non rémunérée,
    #: devenu un arrêt : maintien et IJ seulement, pas de nouvelle retenue.
    sans_retenue: bool = False


# --- Ce qu'un bulletin a compté --------------------------------------------------

#: « 220926 » ou « 220926-230926 » (Quadra, Cegid).
_DATES_COMPACTES = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?:-(\d{2})(\d{2})(\d{2}))?(?!\d)")
#: « du 01/10 au 30/10 », « du 29/09/26 » (Martine).
_DATES_MARTINE = re.compile(
    r"du (\d{2})/(\d{2})(?:/(\d{2,4}))?(?: au (\d{2})/(\d{2})(?:/(\d{2,4}))?)?"
)


def _annee(texte: str | None, mois: int, annee_bulletin: int, mois_bulletin: int) -> int:
    if texte:
        valeur = int(texte)
        return valeur + 2000 if valeur < 100 else valeur
    # Sans année : celle du bulletin, ou la précédente pour un mois plus tardif
    # (décembre sur un bulletin de janvier).
    return annee_bulletin - 1 if mois > mois_bulletin else annee_bulletin


def _jours_entre(debut: date, fin: date) -> set[date]:
    if fin < debut or (fin - debut).days > 400:
        return {debut}
    return {debut + timedelta(days=k) for k in range((fin - debut).days + 1)}


def _date_sure(annee: int, mois: int, jour: int) -> date | None:
    try:
        return date(annee, mois, jour)
    except ValueError:
        return None


#: Nature d'une retenue d'absence, lue sur son libellé.
NATURE_ARRET = "arret"
NATURE_SANS_SOLDE = "sans_solde"
NATURE_CONGE = "conge"
NATURE_ACTIVITE_PARTIELLE = "activite_partielle"
NATURE_AUTRE = "autre"

_MOTS_ARRET = (
    "maladie", "a.t.", "accident", "arrêt", "arret", "maternit", "paternit",
    "rechute", "tps.part", "thérap", "therap",
)
_MOTS_SANS_SOLDE = (
    "injustifi", "non rémunér", "non remuner", "nonpay", "non pay", "s.so",
    "sans solde", "jf non", "férié non payé", "ferie non paye",
)


def nature_du_libelle(libelle: str) -> str:
    texte = libelle.lower()
    if any(m in texte for m in _MOTS_SANS_SOLDE):
        return NATURE_SANS_SOLDE
    if "act. partiel" in texte or "act.partiel" in texte or "activité partielle" in texte:
        return NATURE_ACTIVITE_PARTIELLE
    if "congé" in texte or "conge" in texte:
        return NATURE_CONGE
    if any(m in texte for m in _MOTS_ARRET):
        return NATURE_ARRET
    return NATURE_AUTRE


def _dates_du_libelle(libelle: str, annee: int, mois: int) -> set[date]:
    jours: set[date] = set()
    for m in _DATES_COMPACTES.finditer(libelle):
        debut = _date_sure(2000 + int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if debut is None:
            continue
        fin = (
            _date_sure(2000 + int(m.group(6)), int(m.group(5)), int(m.group(4)))
            if m.group(4)
            else debut
        )
        jours |= _jours_entre(debut, fin or debut)
    for m in _DATES_MARTINE.finditer(libelle):
        mois_debut = int(m.group(2))
        debut = _date_sure(_annee(m.group(3), mois_debut, annee, mois), mois_debut, int(m.group(1)))
        if debut is None:
            continue
        fin = debut
        if m.group(4):
            mois_fin = int(m.group(5))
            fin = _date_sure(_annee(m.group(6), mois_fin, annee, mois), mois_fin, int(m.group(4))) or debut
        jours |= _jours_entre(debut, fin)
    return jours


def _retenues(lignes: Iterable[Mapping[str, Any]] | None) -> list[Mapping[str, Any]]:
    gardees = []
    for ligne in lignes or []:
        if not isinstance(ligne, Mapping):
            continue
        try:
            perte = float(ligne.get("perte") or 0.0)
        except (TypeError, ValueError):
            perte = 0.0
        if perte > 0:
            gardees.append(ligne)
    return gardees


def retenues_datees(
    lignes: Iterable[Mapping[str, Any]] | None, annee: int, mois: int
) -> dict[date, str]:
    """Les jours que couvrent les retenues datées d'un bulletin, avec leur nature
    (un arrêt l'emporte sur une autre retenue du même jour)."""
    jours: dict[date, str] = {}
    for ligne in _retenues(lignes):
        libelle = str(ligne.get("libelle") or "")
        nature = NATURE_ARRET if ligne.get("is_arret_maladie") else nature_du_libelle(libelle)
        for jour in _dates_du_libelle(libelle, annee, mois):
            if jours.get(jour) != NATURE_ARRET:
                jours[jour] = nature
    return jours


def jours_des_libelles(
    lignes: Iterable[Mapping[str, Any]] | None, annee: int, mois: int
) -> set[date]:
    """Les jours que couvrent les retenues datées d'un bulletin."""
    return set(retenues_datees(lignes, annee, mois))


def trace_du_bulletin(payslip_data: Mapping[str, Any] | None) -> dict[str, Any] | None:
    trace = (payslip_data or {}).get(CLE_TRACE)
    return trace if isinstance(trace, Mapping) else None


def _dates(valeurs: Iterable[Any] | None) -> set[date]:
    jours: set[date] = set()
    for v in valeurs or []:
        brut = v.get("date") if isinstance(v, Mapping) else v
        try:
            jours.add(date.fromisoformat(str(brut)[:10]))
        except ValueError:
            continue
    return jours


def jours_reportes_par_le_bulletin(payslip_data: Mapping[str, Any] | None) -> set[date]:
    """Les jours d'une période précédente que ce bulletin a repris."""
    return _dates((trace_du_bulletin(payslip_data) or {}).get("reportes"))


@dataclass
class LectureDuBulletin:
    """Ce qu'un bulletin d'origine dit de ses jours d'absence."""

    arrets: set[date] = field(default_factory=set)
    #: Jours retenus pour une autre absence (sans solde, congé, activité partielle).
    autres: dict[date, str] = field(default_factory=dict)
    #: Jours d'arrêt écartés parce que le bulletin suivant les avait repris.
    repris_par_le_suivant: set[date] = field(default_factory=set)
    avec_trace: bool = False
    #: Une ligne d'arrêt sans date lisible : on ne sait pas ce qu'il a compté.
    illisible: bool = False


def lire_le_bulletin(bulletin: Mapping[str, Any], annee: int, mois: int) -> LectureDuBulletin:
    """Sa trace (tout bulletin calculé depuis ce lot), sinon ses retenues datées."""
    donnees = bulletin.get("payslip_data") or {}
    trace = trace_du_bulletin(donnees)
    if trace is not None:
        autres = {}
        for iso, nature in (trace.get("jours_retenus") or {}).items():
            autres.update({j: str(nature) for j in _dates([iso])})
        return LectureDuBulletin(
            arrets=_dates(trace.get("jours_comptes")) | _dates(trace.get("reportes")),
            autres=autres,
            repris_par_le_suivant=_dates(trace.get("jours_repris_par_le_suivant")),
            avec_trace=True,
        )
    lignes = list(donnees.get("calcul_du_brut") or []) + list(donnees.get("details_absences") or [])
    lecture = LectureDuBulletin()
    for jour, nature in retenues_datees(lignes, annee, mois).items():
        if nature == NATURE_ARRET:
            lecture.arrets.add(jour)
        else:
            lecture.autres[jour] = nature
    lecture.illisible = any(
        (ligne.get("is_arret_maladie") or nature_du_libelle(str(ligne.get("libelle") or "")) == NATURE_ARRET)
        and not _dates_du_libelle(str(ligne.get("libelle") or ""), annee, mois)
        for ligne in _retenues(lignes)
    )
    return lecture


def jours_comptes_par_le_bulletin(
    bulletin: Mapping[str, Any], annee: int, mois: int
) -> set[date]:
    """Les jours d'arrêt qu'un bulletin a retenus : sa trace, ou ses libellés."""
    return lire_le_bulletin(bulletin, annee, mois).arrets


def _est_une_reprise(bulletin: Mapping[str, Any]) -> bool:
    return isinstance((bulletin.get("payslip_data") or {}).get("reprise"), Mapping)


# --- Ce que la gestionnaire a déjà porté à la main --------------------------------


def heures_reprises_a_la_main(
    regularisations_heures: Iterable[Mapping[str, Any]] | None, annee: int, mois: int
) -> float:
    """Heures normales de ce mois déjà reprises sur le bulletin (onglet « Corriger »)."""
    cle = f"{annee:04d}-{mois:02d}"
    total = 0.0
    for regul in regularisations_heures or []:
        if not isinstance(regul, Mapping) or regul.get("nature") != "normales":
            continue
        try:
            quantite = float(regul.get("quantite") or 0.0)
        except (TypeError, ValueError):
            continue
        debut = str(regul.get("mois_origine") or "")
        fin = str(regul.get("mois_fin") or debut)
        if quantite < 0 and debut <= cle <= fin:
            total += -quantite
    return round(total, 2)


def dates_des_regularisations_manuelles(planned_calendar: Mapping[str, Any] | None) -> set[date]:
    """Les jours d'arrêt déjà portés à la main au planning du mois (aux heures seulement :
    le forfait jours n'applique pas les régularisations antérieures)."""
    jours: set[date] = set()
    for entree in (planned_calendar or {}).get("regularisations_anterieures") or []:
        if not isinstance(entree, Mapping) or not str(entree.get("type") or "").startswith("arret"):
            continue
        try:
            jours.add(date.fromisoformat(str(entree.get("date_complete"))[:10]))
        except ValueError:
            continue
    return jours


# --- Le choix des jours ------------------------------------------------------------


@dataclass(frozen=True)
class AnalyseDuReport:
    """Ce que l'examen du bulletin d'origine dit des jours d'un arrêt.

    `jours` : à reprendre sur le bulletin suivant. `comptes` : déjà retenus en
    arrêt par le bulletin d'origine (ou par le bulletin repris du mois).
    `portes_a_la_main` : déjà portés par la gestionnaire. `a_reprendre_a_la_main` :
    payés autrement (congé, activité partielle) ou illisibles : rien n'est
    repris, une alerte dit quoi faire. `origine_validee` : le bulletin d'origine
    existe et ne se régénère plus."""

    jours: tuple[JourReporte, ...] = ()
    comptes: frozenset[date] = frozenset()
    portes_a_la_main: frozenset[date] = frozenset()
    a_reprendre_a_la_main: frozenset[date] = frozenset()
    alertes: tuple[str, ...] = ()
    origine_validee: bool = False


def _week_end(jour: date) -> bool:
    return jour.weekday() >= 5


def _garder_les_week_ends_utiles(non_comptes: list[date], comptes: set[date]) -> list[date]:
    """Sans trace : un samedi ou un dimanche non compté ne se reprend qu'avec un
    jour ouvré repris.

    Les retenues d'un bulletin s'arrêtent au vendredi : un bord de week-end
    d'un arrêt retenu jusqu'au vendredi (ou à partir du lundi) a déjà eu ses
    IJ. Il suit le vendredi repris qui le précède, ou ouvre l'arrêt quand le
    lundi qui le suit est repris et qu'aucun jour n'a été compté avant lui.
    Avec une trace, le bulletin a noté ses jours calendaires : un week-end
    absent de la trace n'a rien eu, il se reprend (maintien et IJ, sans retenue).
    """
    gardes: list[date] = []
    ensemble = set(non_comptes)
    for jour in non_comptes:
        if not _week_end(jour):
            gardes.append(jour)
            continue
        vendredi = jour - timedelta(days=jour.weekday() - 4)
        lundi = jour + timedelta(days=7 - jour.weekday())
        if vendredi in ensemble or lundi in ensemble and not any(c < jour for c in comptes):
            gardes.append(jour)
    return gardes


_LIBELLES_NATURE = {
    NATURE_SANS_SOLDE: "absence non rémunérée",
    NATURE_CONGE: "congé payé",
    NATURE_ACTIVITE_PARTIELLE: "activité partielle",
    NATURE_AUTRE: "autre absence payée (RTT, repos, événement familial…)",
}


def _jours_fr(jours: Iterable[date]) -> str:
    return ", ".join(f"{j:%d/%m}" for j in sorted(jours))


def analyser_le_report(
    arrets: Iterable[Mapping[str, Any]],
    bulletins_origine: list[Mapping[str, Any]],
    periode_origine: tuple[date, date],
    *,
    annee_origine: int,
    mois_origine: int,
    deja_portes: set[date] | None = None,
    heures_a_la_main: float = 0.0,
    heures_par_jour: float = 7.0,
    bulletins_repris_voisins: Iterable[Mapping[str, Any]] = (),
) -> AnalyseDuReport:
    """Les jours d'arrêt de la période précédente que son bulletin n'a pas comptés.

    « Compté » se lit sur la trace du bulletin (tout bulletin calculé par Martine
    depuis le 26/11 la porte, même vide) ; sinon sur ses retenues datées
    (bulletin repris, ou de Martine d'avant la trace). Jamais sur sa date de
    calcul : une prolongation de la même demande, saisie après la validation,
    a ajouté des jours que le bulletin n'a pas vus. Au forfait jours, la période
    déborde sur le mois civil d'avant : les retenues du bulletin repris de ce
    mois-là comptent aussi (`bulletins_repris_voisins`).

    Un jour que le bulletin d'origine a retenu comme absence non rémunérée et
    qui est devenu un arrêt se reprend sans nouvelle retenue (maintien et IJ
    seulement). Payé en congé ou en activité partielle : rien n'est repris, une
    alerte dit de le faire à la main. Une ligne d'arrêt sans date lisible :
    rien n'est repris non plus, et le bulletin le dit.

    Bulletin d'origine pas encore validé : il comptera l'arrêt à son calcul,
    sauf les jours qu'il a écartés parce que le bulletin suivant les avait
    repris (sa trace les note) : ceux-là restent repris.
    """
    if not bulletins_origine:
        return AnalyseDuReport()
    valides = all(b.get("status") == STATUT_VALIDE for b in bulletins_origine)
    debut, fin = periode_origine
    lectures = [lire_le_bulletin(b, annee_origine, mois_origine) for b in bulletins_origine]
    for b in bulletins_repris_voisins:
        if _est_une_reprise(b):
            lectures.append(
                lire_le_bulletin(b, int(b.get("year") or annee_origine), int(b.get("month") or mois_origine))
            )
    comptes: set[date] = set()
    autres: dict[date, str] = {}
    repris_par_le_suivant: set[date] = set()
    for lecture in lectures:
        comptes |= lecture.arrets
        repris_par_le_suivant |= lecture.repris_par_le_suivant
        for jour, nature in lecture.autres.items():
            autres.setdefault(jour, nature)
    avec_trace = all(l.avec_trace for l in lectures[: len(bulletins_origine)])
    alertes: list[str] = []
    # Le bulletin d'origine se recalcule : il comptera l'arrêt, sauf ce qu'il a
    # laissé au bulletin suivant.
    if not valides and not repris_par_le_suivant:
        return AnalyseDuReport()
    illisible = any(l.illisible for l in lectures)
    portes = set(deja_portes or ())
    candidats: dict[date, JourReporte] = {}
    comptes_vus: set[date] = set()
    portes_vus: set[date] = set()
    a_la_main: dict[date, str] = {}
    for arret in arrets:
        if arret.get("type") not in TYPES_ARRET_REPORTABLES:
            continue
        if arret.get("status", "validated") != "validated":
            continue
        jours_de_l_arret: list[date] = []
        comptes_de_l_arret: set[date] = set()
        for brut in arret.get("selected_days") or []:
            try:
                jour = date.fromisoformat(str(brut)[:10])
            except ValueError:
                continue
            if not (debut <= jour <= fin):
                continue
            if not valides and jour not in repris_par_le_suivant:
                continue
            if jour in comptes:
                comptes_de_l_arret.add(jour)
                continue
            if jour in portes:
                portes_vus.add(jour)
                continue
            nature = autres.get(jour)
            if nature is not None and nature != NATURE_SANS_SOLDE:
                a_la_main[jour] = nature
                continue
            jours_de_l_arret.append(jour)
        comptes_vus |= comptes_de_l_arret
        gardes = (
            sorted(jours_de_l_arret)
            if avec_trace
            else _garder_les_week_ends_utiles(sorted(jours_de_l_arret), comptes_de_l_arret)
        )
        if not avec_trace and not any(not _week_end(j) for j in gardes):
            continue
        for jour in gardes:
            candidats.setdefault(
                jour,
                JourReporte(jour, str(arret.get("id") or ""), autres.get(jour) == NATURE_SANS_SOLDE),
            )
    candidats_illisibles: list[date] = []
    if illisible and candidats:
        alertes.append(
            f"Bulletin de {_mois(mois_origine)} {annee_origine} : une ligne d'arrêt sans date lisible. "
            f"Les jours d'arrêt du {_jours_fr(candidats)} ne sont pas repris : vérifiez s'il les a "
            "comptés et portez-les à la main sinon."
        )
        candidats_illisibles.extend(candidats)
        a_la_main.update({j: NATURE_AUTRE for j in candidats})
        candidats = {}
    illisibles = set(candidats_illisibles)
    for nature in sorted({n for j, n in a_la_main.items() if j not in illisibles}):
        jours_nature = [j for j, n in a_la_main.items() if n == nature]
        alertes.append(
            f"Arrêt du {_jours_fr(jours_nature)} : ces jours étaient payés en "
            f"{_LIBELLES_NATURE[nature]} sur le bulletin de {_mois(mois_origine)} {annee_origine}. "
            "Martine ne les reprend pas : régularisez à la main (onglet « Corriger »)."
        )
    sans_retenue = [j for j, r in candidats.items() if r.sans_retenue]
    if sans_retenue:
        alertes.append(
            f"Absence requalifiée en arrêt le {_jours_fr(sans_retenue)} : déjà retenue en "
            f"{_mois(mois_origine)} {annee_origine} comme absence non rémunérée, elle n'est pas "
            "retenue une seconde fois ; le maintien et les IJ sont repris."
        )
    jours = sorted(candidats)
    if heures_a_la_main > 0 and jours:
        # Heures du mois d'origine déjà reprises à la main : elles couvrent les
        # premiers jours ouvrés de l'arrêt, une journée par tranche ; le reste
        # est repris. Jamais tout l'arrêt sur une reprise partielle.
        reste = heures_a_la_main
        couverts: set[date] = set()
        for jour in jours:
            if _week_end(jour):
                if (jour - timedelta(days=jour.weekday() - 4)) in couverts:
                    couverts.add(jour)
                continue
            if reste + 1e-6 >= heures_par_jour:
                couverts.add(jour)
                reste -= heures_par_jour
        portes_vus |= couverts
        jours = [j for j in jours if j not in couverts]
        nb = len([j for j in couverts if not _week_end(j)])
        alertes.append(
            f"{_heures(heures_a_la_main)} h de {_mois(mois_origine)} {annee_origine} déjà reprises "
            f"à la main : {nb} jour(s) d'arrêt considéré(s) comme portés"
            + (
                f", {len([j for j in jours if not _week_end(j)])} repris par Martine. Vérifiez."
                if jours
                else "."
            )
        )
    return AnalyseDuReport(
        jours=tuple(candidats[j] for j in jours),
        comptes=frozenset(comptes_vus),
        portes_a_la_main=frozenset(portes_vus),
        a_reprendre_a_la_main=frozenset(a_la_main),
        alertes=tuple(alertes),
        origine_validee=valides,
    )


_NOMS_DES_MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
    "août", "septembre", "octobre", "novembre", "décembre",
)


def _mois(mois: int) -> str:
    return _NOMS_DES_MOIS[(mois - 1) % 12]


def _heures(valeur: float) -> str:
    return f"{valeur:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def jours_a_reporter(*args: Any, **kwargs: Any) -> list[JourReporte]:
    """Les seuls jours à reprendre (voir `analyser_le_report`)."""
    return list(analyser_le_report(*args, **kwargs).jours)


# --- Les événements du bulletin ------------------------------------------------------


def _date_de_l_evenement(ev: Mapping[str, Any], annee: int, mois: int) -> date | None:
    if ev.get("date_complete"):
        try:
            return date.fromisoformat(str(ev["date_complete"])[:10])
        except ValueError:
            return None
    try:
        return date(int(ev.get("annee") or annee), int(ev.get("mois") or mois), int(ev["jour"]))
    except (KeyError, TypeError, ValueError):
        return None


#: Ce qu'un jour d'arrêt porte, repris sur un férié compris dans l'arrêt.
_META_ARRET = (
    "arret_type",
    "subrogation_active",
    "nombre_enfants",
    "is_temps_partiel",
    "quotite_temps_partiel",
    "historique_arrets_annee",
    "date_dernier_arret",
    "salaire_periode_reelle",
    "maintien_base_ouvree",
    "date_debut_arret_reel",
    "date_fin_arret_reel",
    "source_absence",
    "date_accident",
)


def evenements_du_report(
    evenements_origine: Iterable[Mapping[str, Any]],
    jours: Iterable[JourReporte],
    annee: int,
    mois: int,
) -> list[dict[str, Any]]:
    """Les jours d'arrêt de la période précédente, rattachés au bulletin du mois.

    Ils gardent leur date d'origine (`is_regularisation_anterieure`) et disent
    de quel arrêt ils viennent (`arret_reporte`, `absence_id`). L'analyse d'un
    mois ne date ses jours que par leur numéro : `annee`, `mois` complètent.
    Un férié compris dans l'arrêt le suit : il est retenu comme un jour d'arrêt,
    avec les données de l'arrêt (aux heures comme au forfait jours).
    """
    par_date = {j.jour: j for j in jours}
    if not par_date:
        return []
    origine = [(_date_de_l_evenement(ev, annee, mois), ev) for ev in evenements_origine]
    arrets = {d: ev for d, ev in origine if d and str(ev.get("type") or "").startswith("arret")}
    reportes: list[dict[str, Any]] = []
    vus: set[date] = set()
    for jour, ev in origine:
        if jour is None or jour not in par_date or jour in vus:
            continue
        type_ev = str(ev.get("type") or "")
        if type_ev.startswith("arret"):
            base = dict(ev)
        elif type_ev == "ferie":
            modele = next(
                (
                    arrets[d]
                    for d in sorted(arrets, key=lambda d: abs((d - jour).days))
                    if par_date.get(d) and par_date[d].absence_id == par_date[jour].absence_id
                ),
                None,
            )
            if modele is None:
                continue
            base = {
                **{k: v for k, v in ev.items() if k not in ("type", "heures")},
                **{k: modele[k] for k in _META_ARRET if k in modele},
                "type": modele.get("type") or "arret_maladie",
                "heures": 0.0,
                "ferie_dans_l_arret": True,
            }
        else:
            continue
        vus.add(jour)
        reportes.append(
            {
                **base,
                "annee": jour.year,
                "mois": jour.month,
                "jour": jour.day,
                "date_complete": jour.isoformat(),
                "is_regularisation_anterieure": True,
                "arret_reporte": True,
                "absence_id": par_date[jour].absence_id,
                # Déjà retenu comme absence non rémunérée : maintien et IJ seulement.
                "sans_retenue": par_date[jour].sans_retenue,
            }
        )
    return sorted(reportes, key=lambda e: e["date_complete"])


def evenements_du_planning(
    entrees: Mapping[str, Mapping[str, Any]], jours: Iterable[JourReporte]
) -> list[dict[str, Any]]:
    """Au forfait jours : les jours reportés tirés du planning de leur mois (un jour = 1)."""
    origine = []
    for iso, entree in entrees.items():
        try:
            d = date.fromisoformat(str(iso)[:10])
        except ValueError:
            continue
        origine.append({**dict(entree), "date_complete": d.isoformat(), "heures": 0.0})
    return evenements_du_report(origine, jours, 0, 0)


def sans_les_jours_deja_reportes(
    evenements: list[dict[str, Any]], jours: set[date], annee: int, mois: int
) -> list[dict[str, Any]]:
    """Le bulletin d'origine régénéré ne recompte pas ce que le suivant a repris."""
    if not jours:
        return evenements
    return [
        ev
        for ev in evenements
        if not (
            (str(ev.get("type") or "").startswith("arret") or ev.get("type") == "ferie")
            and not ev.get("is_regularisation_anterieure")
            and _date_de_l_evenement(ev, annee, mois) in jours
        )
    ]


def periode_precedente(
    annee: int,
    mois: int,
    *,
    forfait_jours: bool,
    company_data: Mapping[str, Any] | None = None,
) -> tuple[int, int, tuple[date, date]]:
    """(année, mois, bornes) de la période du bulletin précédent : le mois civil
    aux heures, la période de la société au forfait jours."""
    annee_o, mois_o = (annee, mois - 1) if mois > 1 else (annee - 1, 12)
    return annee_o, mois_o, bornes_de_la_periode(
        annee_o, mois_o, forfait_jours=forfait_jours, company_data=company_data
    )


def bornes_de_la_periode(
    annee: int, mois: int, *, forfait_jours: bool, company_data: Mapping[str, Any] | None = None
) -> tuple[date, date]:
    """La période d'un bulletin, résolue comme le moteur : au forfait, la règle de
    la société lue par `_periode_de_paie_company` (vide = mois civil) ; aux
    heures, le mois civil."""
    if forfait_jours:
        from app.modules.payroll.documents.payslip_generator_forfait import (
            _periode_de_paie_company,
        )
        from app.modules.payroll.engine.period_forfait import bornes_periode_de_paie

        regle = _periode_de_paie_company(dict(company_data or {}))
        return bornes_periode_de_paie(annee, mois, regle["jour_de_fin"], regle["occurrence"])
    from app.shared.domain.periode_variables import bornes_mois_civil

    return bornes_mois_civil(annee, mois)


# --- Lectures ------------------------------------------------------------------------

_COLONNES_BULLETIN = "id, year, month, status, generated_at, updated_at, payslip_data"


def lire_les_arrets(client: Any, employee_id: str) -> list[dict[str, Any]]:
    lignes = (
        client.table("absence_requests")
        .select("id, type, status, selected_days, created_at")
        .eq("employee_id", employee_id)
        .eq("status", "validated")
        .execute()
    ).data or []
    # Tri en Python : un filtre SQL sur l'enum échoue dès qu'un type manque.
    return [l for l in lignes if l.get("type") in TYPES_ARRET_REPORTABLES]


def lire_les_bulletins(client: Any, employee_id: str, annee: int, mois: int) -> list[dict[str, Any]]:
    return (
        client.table("payslips")
        .select(_COLONNES_BULLETIN)
        .eq("employee_id", employee_id)
        .eq("year", annee)
        .eq("month", mois)
        .execute()
    ).data or []


def _mois_civils(debut: date, fin: date) -> list[tuple[int, int]]:
    mois: list[tuple[int, int]] = []
    jour = debut.replace(day=1)
    while jour <= fin:
        mois.append((jour.year, jour.month))
        jour = (jour + timedelta(days=32)).replace(day=1)
    return mois


def lire_le_planning(
    client: Any, employee_id: str, debut: date, fin: date
) -> dict[str, dict[str, Any]]:
    """Les jours du planning entre deux dates, par date (mois d'avant compris)."""
    entrees: dict[str, dict[str, Any]] = {}
    for annee, mois in _mois_civils(debut, fin):
        ligne = (
            client.table("employee_schedules")
            .select("planned_calendar")
            .eq("employee_id", employee_id)
            .eq("year", annee)
            .eq("month", mois)
            .maybe_single()
            .execute()
        )
        donnees = (getattr(ligne, "data", None) or {}).get("planned_calendar") or {}
        for e in donnees.get("calendrier_prevu") or []:
            d = _date_sure(annee, mois, int(e.get("jour") or 0)) if e.get("jour") else None
            if d and debut <= d <= fin:
                entrees[d.isoformat()] = dict(e)
    return entrees


#: Clés des saisies du mois : les générateurs passent le report au moteur.
CLE_SAISIE_REPORT = "arrets_reportes"
CLE_SAISIE_REPRIS = "jours_repris_par_le_bulletin_suivant"
CLE_SAISIE_PLANNING = "planning_des_arrets_reportes"
CLE_SAISIE_ALERTES = "alertes_des_arrets_reportes"


@dataclass(frozen=True)
class Report:
    """Ce que le bulletin du mois reprend du précédent, et ce que le suivant lui a pris."""

    jours: tuple[JourReporte, ...] = ()
    repris: frozenset[date] = frozenset()
    #: Au forfait jours, le planning des jours reportés (le moteur n'a que M-1 à M+1).
    planning: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    alertes: tuple[str, ...] = ()

    def vers_les_saisies(self) -> dict[str, Any]:
        return {
            CLE_SAISIE_REPORT: [
                {"date": j.jour.isoformat(), "absence_id": j.absence_id, "sans_retenue": j.sans_retenue}
                for j in self.jours
            ],
            CLE_SAISIE_REPRIS: sorted(d.isoformat() for d in self.repris),
            CLE_SAISIE_PLANNING: {k: dict(v) for k, v in self.planning.items()},
            CLE_SAISIE_ALERTES: list(self.alertes),
        }

    @classmethod
    def depuis_les_saisies(cls, saisie: Mapping[str, Any] | None) -> Report:
        saisie = saisie or {}
        jours = []
        for entree in saisie.get(CLE_SAISIE_REPORT) or []:
            try:
                jours.append(
                    JourReporte(
                        date.fromisoformat(str(entree["date"])[:10]),
                        str(entree.get("absence_id") or ""),
                        bool(entree.get("sans_retenue")),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        repris = set()
        for iso in saisie.get(CLE_SAISIE_REPRIS) or []:
            try:
                repris.add(date.fromisoformat(str(iso)[:10]))
            except ValueError:
                continue
        return cls(
            tuple(jours),
            frozenset(repris),
            dict(saisie.get(CLE_SAISIE_PLANNING) or {}),
            tuple(saisie.get(CLE_SAISIE_ALERTES) or ()),
        )


def _touche(arrets: list[dict[str, Any]], debut: date, fin: date) -> bool:
    for a in arrets:
        for d in a.get("selected_days") or []:
            try:
                if debut <= date.fromisoformat(str(d)[:10]) <= fin:
                    return True
            except ValueError:
                continue
    return False


class LectureDuBulletinSuivantImpossible(RuntimeError):
    """Le bulletin du mois suivant n'a pas pu être relu : le calcul s'arrête."""


MESSAGE_REPORT_ILLISIBLE = (
    "Arrêts arrivés après la validation du bulletin précédent non relus : "
    "s'il y en a, ils ne sont pas repris sur ce bulletin. Recalculez-le."
)


def preparer_le_report(
    client: Any,
    employee_id: str,
    annee: int,
    mois: int,
    *,
    forfait_jours: bool,
    company_data: Mapping[str, Any] | None,
    planned_calendar_du_mois: Mapping[str, Any] | None = None,
    saisies: Iterable[Mapping[str, Any]] | None = None,
    heures_par_jour: float = 7.0,
) -> Report:
    """Les arrêts à reprendre du bulletin précédent, et les jours de ce mois que
    le bulletin suivant a déjà repris. Les bulletins ne se lisent que si le
    salarié a un arrêt sur l'une des deux périodes. Une lecture qui échoue ne
    fait pas échouer le bulletin : il le dit (`MESSAGE_REPORT_ILLISIBLE`)."""
    try:
        return _preparer_le_report(
            client,
            employee_id,
            annee,
            mois,
            forfait_jours=forfait_jours,
            company_data=company_data,
            planned_calendar_du_mois=planned_calendar_du_mois,
            saisies=saisies,
            heures_par_jour=heures_par_jour,
        )
    except LectureDuBulletinSuivantImpossible:
        raise
    except Exception:
        logger.exception("Report des arrêts non préparé (salarié %s, %s/%s)", employee_id, mois, annee)
        return Report(alertes=(MESSAGE_REPORT_ILLISIBLE,))


def _preparer_le_report(
    client: Any,
    employee_id: str,
    annee: int,
    mois: int,
    *,
    forfait_jours: bool,
    company_data: Mapping[str, Any] | None,
    planned_calendar_du_mois: Mapping[str, Any] | None,
    saisies: Iterable[Mapping[str, Any]] | None,
    heures_par_jour: float,
) -> Report:
    from app.modules.payroll.engine.corrections_manuelles import (
        est_regularisation_heures,
    )

    arrets = lire_les_arrets(client, employee_id)
    if not arrets:
        return Report()
    annee_o, mois_o, bornes = periode_precedente(
        annee, mois, forfait_jours=forfait_jours, company_data=company_data
    )
    analyse = AnalyseDuReport()
    planning: dict[str, dict[str, Any]] = {}
    if _touche(arrets, *bornes):
        voisins: list[dict[str, Any]] = []
        for a, m in _mois_civils(*bornes):
            if (a, m) != (annee_o, mois_o):
                voisins.extend(lire_les_bulletins(client, employee_id, a, m))
        analyse = analyser_le_report(
            arrets,
            lire_les_bulletins(client, employee_id, annee_o, mois_o),
            bornes,
            annee_origine=annee_o,
            mois_origine=mois_o,
            # Le forfait jours n'applique pas les régularisations antérieures du
            # planning : elles ne peuvent pas avoir porté l'arrêt.
            deja_portes=(
                set() if forfait_jours else dates_des_regularisations_manuelles(planned_calendar_du_mois)
            ),
            heures_a_la_main=heures_reprises_a_la_main(
                [s["correction_ligne"] for s in saisies or [] if est_regularisation_heures(s)],
                annee_o,
                mois_o,
            ),
            heures_par_jour=heures_par_jour,
            bulletins_repris_voisins=voisins,
        )
        if forfait_jours and analyse.jours:
            planning = lire_le_planning(
                client, employee_id, min(j.jour for j in analyse.jours), max(j.jour for j in analyse.jours)
            )
    repris: set[date] = set()
    debut_du_mois = bornes[1] + timedelta(days=1)
    fin_du_mois = date(annee, mois, calendar.monthrange(annee, mois)[1])
    if _touche(arrets, debut_du_mois, fin_du_mois):
        annee_s, mois_s = (annee, mois + 1) if mois < 12 else (annee + 1, 1)
        try:
            suivants = lire_les_bulletins(client, employee_id, annee_s, mois_s)
        except Exception as exc:
            # Sans lui, ce bulletin recompterait un arrêt que le suivant a peut-être
            # déjà repris : il n'est pas calculé, et la raison est dite.
            raise LectureDuBulletinSuivantImpossible(
                f"Le bulletin de {_mois(mois_s)} {annee_s} n'a pas pu être relu : ce bulletin "
                "pourrait recompter un arrêt qu'il a déjà repris. Il n'est pas calculé ; réessayez."
            ) from exc
        for b in suivants:
            repris |= jours_reportes_par_le_bulletin(b.get("payslip_data"))
    return Report(analyse.jours, frozenset(repris), planning, analyse.alertes)


def appliquer_le_report_aux_evenements(
    evenements_du_mois: list[dict[str, Any]],
    evenements_precedents: Iterable[Mapping[str, Any]],
    report: Report,
    annee: int,
    mois: int,
) -> list[dict[str, Any]]:
    """Les événements du mois sans les jours que le bulletin suivant a repris,
    plus les jours d'arrêt reportés du bulletin précédent (à leur date).

    Au forfait jours, les jours reportés se tirent du planning porté par le
    report (`planning`), qui couvre aussi le mois d'avant la période."""
    annee_o, mois_o = (annee, mois - 1) if mois > 1 else (annee - 1, 12)
    evenements = sans_les_jours_deja_reportes(list(evenements_du_mois), set(report.repris), annee, mois)
    if not report.jours:
        return evenements
    if report.planning:
        return evenements + evenements_du_planning(report.planning, report.jours)
    return evenements + evenements_du_report(evenements_precedents, report.jours, annee_o, mois_o)


__all__ = [
    "CLE_SAISIE_ALERTES",
    "CLE_SAISIE_PLANNING",
    "CLE_SAISIE_REPORT",
    "CLE_SAISIE_REPRIS",
    "CLE_TRACE",
    "MESSAGE_REPORT_ILLISIBLE",
    "TYPES_ARRET_REPORTABLES",
    "AnalyseDuReport",
    "JourReporte",
    "LectureDuBulletinSuivantImpossible",
    "Report",
    "analyser_le_report",
    "appliquer_le_report_aux_evenements",
    "bornes_de_la_periode",
    "dates_des_regularisations_manuelles",
    "evenements_du_planning",
    "evenements_du_report",
    "heures_reprises_a_la_main",
    "jours_a_reporter",
    "jours_comptes_par_le_bulletin",
    "jours_des_libelles",
    "jours_reportes_par_le_bulletin",
    "periode_precedente",
    "preparer_le_report",
    "sans_les_jours_deja_reportes",
]
