"""Classement final des écarts du rejeu (tâche 9, étape 7), règle par règle.

Chaque ligne ni « identique » ni « arrondi » reçoit un classement parmi `erreur_eywai`,
`erreur_quadra`, `methode_legale_differente`, `donnee_manquante` et `arrondi`, l'ID de la
règle de `regles.md`, et une note d'une phrase. Les écarts qui se répètent (SMIC de juin à
12,31 €, sa reprise en juillet, janvier chez Comitech) sont classés en bloc par motif, comme
le permet le plan ; ce qui ne tombe dans aucun motif reste « a_revoir », jamais deviné.

Indépendant du moteur : ne rien importer de app/.
"""
from __future__ import annotations

from dataclasses import dataclass

from scripts.verification_rgdu.comparaison import TOLERANCE_SMIC, LigneComparee

#: Écart de SMIC qu'ajoute un mois calculé à 12,31 € au lieu de 12,02 € (R-F2).
HAUSSE_DE_JUIN = (12.31 - 12.02) / 12.02
#: Tolérance d'appariement d'un mois de juillet avec l'excès de juin qu'il reprend.
TOLERANCE_REPRISE = 15.0
CLASSEMENTS = ("erreur_eywai", "erreur_quadra", "methode_legale_differente", "donnee_manquante",
               "arrondi", "a_revoir")


@dataclass(frozen=True)
class Contexte:
    """Ce qu'un mois isolé ne dit pas, lu sur le salarié entier.

    `exces_juin` : le SMIC de juin que Quadra a compté en trop (12,31 € au lieu de 12,02 €),
    lu sur sa DSN de juin ou, quand la DSN déclare 12,02 €, sur l'écart entre son SMIC cumulé
    implicite de juin et celui de ses DSN de janvier à juin ; None s'il n'y en a pas."""
    exces_juin: float | None = None
    societe_sans_reduction_en_janvier: bool = False


def _delta(l: LigneComparee) -> float | None:
    if l.smic_quadra is None or l.smic_loi is None:
        return None
    return round(l.smic_quadra - l.smic_loi, 2)


def ecart_martine(l: LigneComparee, regle_loi: str) -> tuple[str, str, str] | None:
    """Le classement du seul écart de MARTINE à la loi, sur un mois payé par Quadra.

    Sur ces mois, MARTINE calcule en bac à sable avec ses propres données du mois (planning,
    absences, maintien conventionnel posé le 24/10), pas avec le bulletin de Quadra : ce ne sont
    pas les mêmes entrées. Un écart y dit donc d'abord une donnée du mois repris, sauf l'arrêt où
    MARTINE verse le maintien de la convention que Quadra n'a pas versé ce mois-là. None si MARTINE
    suit la loi (ou n'est pas calculé)."""
    if l.smic_eywai is None or l.smic_loi is None:
        return None
    e = round(l.smic_eywai - l.smic_loi, 2)
    if abs(e) <= TOLERANCE_SMIC:
        return None
    if e > 0 and "R-H4" in regle_loi:
        return ("methode_legale_differente", "R-H4",
                f"MARTINE verse le maintien de la convention que le bulletin de Quadra ne porte pas ce mois-là "
                f"(rattrapé par rappel) : heures d'arrêt gardées, {e:+.2f} € de SMIC")
    if e > 0:
        return ("donnee_manquante", regle_loi or "R-H1",
                f"mois repris : l'absence du bulletin de Quadra manque aux données de MARTINE pour ce mois, {e:+.2f} € de SMIC")
    return ("donnee_manquante", regle_loi or "R-H1",
            f"mois repris : planning ou absences de MARTINE différents du bulletin de Quadra "
            f"(août : congés d'été absents du planning), {e:+.2f} € de SMIC")


def classer(l: LigneComparee, regle_loi: str, ctx: Contexte) -> tuple[str, str, str]:
    """(classement_final, règle, note) d'une ligne ; trois chaînes vides si elle est
    « identique » ou « arrondi » (rien à classer). Une ligne où seul MARTINE s'écarte prend le
    classement de MARTINE ; quand les deux s'écartent, celui de Quadra, la note dit celui de MARTINE."""
    if l.preclassement in ("identique", "arrondi"):
        return "", "", ""
    martine = ecart_martine(l, regle_loi)
    if l.preclassement == "erreur_eywai" and martine is not None:
        return martine
    classe, regle, note = _classer_quadra(l, regle_loi, ctx)
    if martine is not None and l.preclassement == "a_juger_les_deux":
        if classe == "arrondi":
            return martine[0], martine[1], f"{martine[2]} ; Quadra : {note}"
        note = f"{note} ; MARTINE : {martine[2]}"
    return classe, regle, note


def _classer_quadra(l: LigneComparee, regle_loi: str, ctx: Contexte) -> tuple[str, str, str]:
    note = l.note or ""
    d = _delta(l)
    if l.smic_loi is None:
        if "sans salaire" in note:
            return ("donnee_manquante", "R-A2",
                    "bulletin sans salaire de base (mois sans paie ou bulletin complémentaire) : la loi ne se lit pas sur ses lignes")
        if "mois complet inconnu" in note:
            return ("donnee_manquante", "R-H7",
                    "premier mois d'un contrat sans autre mois du contrat : salaire d'un mois complet inconnu")
        return "donnee_manquante", regle_loi or "R-H1", note or "SMIC légal non calculable sur ce bulletin"
    if l.smic_quadra is None:
        return ("donnee_manquante", "R-D1",
                "SMIC de Quadra introuvable : pas de DSN après juin et réduction cumulée non inversible")
    if l.preclassement == "point_non_tranche":
        return "methode_legale_differente", "R-H4 (point n° 1)", note
    if l.mois == 6 and "contrat terminé en juin" in note:
        return ("methode_legale_differente", "R-F2",
                "contrat terminé en juin : SMIC à 12,31 € admis par la tolérance du BOSS")
    if l.mois == 6 and l.source_quadra == "dsn" and d is not None and d > 0 \
            and abs(d - l.smic_loi * HAUSSE_DE_JUIN) <= TOLERANCE_SMIC:
        return ("erreur_quadra", "R-F2",
                f"juin calculé à 12,31 € au lieu du SMIC gelé à 12,02 € (décret 2026-509) : {d:+.2f} € de SMIC, repris en juillet")
    if l.mois == 7 and ctx.exces_juin and d is not None and abs(d + ctx.exces_juin) <= TOLERANCE_REPRISE:
        return ("erreur_quadra", "R-F2",
                f"juillet reprend l'excès de juin ({ctx.exces_juin:+.2f} € de SMIC) : le cumul de juin-juillet revient "
                f"à la loi à {d + ctx.exces_juin:+.2f} € près")
    if l.mois == 1 and ctx.societe_sans_reduction_en_janvier:
        return ("erreur_quadra", "R-R2",
                "janvier sans réduction chez Quadra (taux réduits de 2025) : SMIC déclaré sans effet, la base de MARTINE part de février")
    if l.smic_loi == 0 and 0 < l.smic_quadra < 400 and "R-H4" in regle_loi:
        return ("erreur_quadra", "R-H4",
                f"mois d'arrêt sans aucun salaire : Quadra déclare encore ≈ {l.smic_quadra / 12.02:.1f} h de SMIC "
                f"({l.smic_quadra:.2f} €, vraisemblablement les heures structurelles retirées), le rapport des salaires est nul")
    if abs(l.smic_quadra - 1823.03) < 0.01 and d is not None and d < -TOLERANCE_SMIC:
        return ("erreur_quadra", "R-H1",
                f"SMIC mensuel seul ({l.smic_quadra:.2f} €) : Quadra ne compte pas les heures supplémentaires "
                f"structurelles payées, {d:+.2f} € de SMIC par mois")
    if l.smic_quadra < 0:
        return ("methode_legale_differente", "R-A3",
                "SMIC négatif déclaré : Quadra régularise le mois précédent (progressive), le cumul seul compte")
    if "rappel de maintien" in note:
        return ("methode_legale_differente", "R-B1 (point n° 12)",
                "rappel de maintien payé ce mois : Quadra rétablit le SMIC des mois d'arrêt le mois du rappel "
                "(BOSS § 800), notre lecture plafonne le mois à un mois complet")
    if "point n° 1" in note or l.variante:
        return ("methode_legale_differente", "R-H4 (point n° 1)",
                "arrêt maintenu sans ligne d'IJSS : Quadra ne suit aucune des deux lectures (maintien partiel ou versé plus tard)")
    if d is not None and abs(d) <= TOLERANCE_SMIC:
        return ("arrondi", regle_loi or "R-H1",
                f"moins d'une demi-heure de SMIC ({d:+.2f} €) sur un cumul élevé : valorisation de la retenue (point n° 2)")
    if l.source_quadra == "implicite":
        return ("donnee_manquante", "R-D1",
                f"pas de DSN après juin : SMIC de Quadra retrouvé par inversion de sa réduction cumulée, {d:+.2f} € contre la loi")
    if "proratisé" in note or "R-H7" in regle_loi:
        return ("methode_legale_differente", "R-H7",
                f"mois incomplet (entrée, sortie ou absence pour entrée/sortie) : prorata de Quadra différent du rapport des salaires, {d:+.2f} €")
    if any(r in regle_loi for r in ("R-H2", "R-H3", "R-H4", "R-H5")):
        return ("methode_legale_differente", "R-H3 (point n° 2)",
                f"absences du mois (congés, événement familial, arrêt, sans solde) valorisées par Quadra "
                f"autrement que par le rapport des salaires : {d:+.2f} € de SMIC")
    return "a_revoir", regle_loi, f"écart {d:+.2f} € de SMIC sans motif reconnu ; {note}".strip(" ;")
