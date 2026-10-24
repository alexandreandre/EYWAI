"""Le maintien au barème de la convention : les textes du bulletin.

Carence, alertes, détail du barème appliqué, explication de la ligne de
maintien (conception du 24/10/2026). Ces textes n'existent que sous un barème :
sans barème, le bulletin garde ses textes d'avant.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Optional

from app.modules.payroll.domain.baremes_maintien import (
    Bareme,
    bareme_par_code,
    libelle_tranche,
    pourcent,
)
from app.modules.payroll.domain.ijss_deduites import suite_ijss_deduites

#: Raisons de carence posées par le plan (`paliers_convention`).
_RAISON_CADRE = "cadre"
_RAISON_ACCIDENT = "accident"
_RAISON_ALD = "ald"
_RAISON_PREMIER_ARRET = "premier_arret"
_RAISON_RELIQUAT = "reliquat"

ALERTE_STATUT_ABSENT = "Statut absent de la fiche : barème des non-cadres appliqué."


def _date_fr(jour: date) -> str:
    return jour.strftime("%d/%m/%Y")


def _jours(n: int) -> str:
    return f"{n} jour{'s' if n > 1 else ''}"


def detail_du_bareme(bareme: Bareme, est_cadre: bool, arret: Any) -> str:
    """« Plasturgie (IDCC 0292), non-cadres, 5 ans et plus »."""
    categorie = bareme.categorie(est_cadre)
    texte = f"{bareme.libelle}, {categorie.titre.lower()}"
    tranche = getattr(arret, "tranche", None)
    if tranche is not None:
        texte += f", {libelle_tranche(categorie, tranche)}"
    return texte


def motif_sans_droit(bareme: Bareme, arret: Any) -> str:
    mois = int(getattr(arret, "mois_anciennete", 0) or 0)
    return (
        f"{bareme.nom_court} : un an d'ancienneté requis pour une maladie "
        f"({mois} mois au début de l'arrêt)."
    )


def motif_carence_du_bareme(bareme: Bareme, arret: Any) -> str:
    nom = bareme.nom_court
    if getattr(arret, "tranche", None) is None:
        return motif_sans_droit(bareme, arret)
    raison = getattr(arret, "raison_carence", "")
    if raison == _RAISON_CADRE:
        return f"{nom}, cadres : pas de carence."
    if raison == _RAISON_ACCIDENT:
        return (
            f"{nom} : pas de carence pour un accident du travail, une maladie "
            "professionnelle ou un accident de trajet."
        )
    if raison == _RAISON_ALD:
        return f"{nom} : pas de carence pour une affection de longue durée."
    if raison == _RAISON_PREMIER_ARRET:
        return f"{nom} : premier arrêt de l'année, pas de carence."
    jours = tuple(getattr(arret, "jours_de_carence", ()) or ())
    texte = f"{nom} : {_jours(len(jours))} de carence"
    if len(jours) > 1:
        texte += f", du {_date_fr(jours[0])} au {_date_fr(jours[-1])}"
    elif jours:
        texte += f", le {_date_fr(jours[0])}"
    if raison == _RAISON_RELIQUAT:
        texte += " (le premier arrêt de l'année a duré moins de 3 jours)"
    return texte + "."


def alertes_du_bareme(
    bareme: Bareme,
    maintien: Mapping[str, Any],
    plan: Any,
    debut_arret: date,
    fin_arret: date,
    *,
    statut: str,
    debut_periode: date,
    fin_periode: date,
) -> list[str]:
    """Statut absent, droit fermé, passage de palier, limite atteinte."""
    alertes: list[str] = []
    if not str(statut or "").strip():
        alertes.append(ALERTE_STATUT_ABSENT)
    arret = plan.arret_du_jour(debut_arret)
    if not maintien.get("maintien_applicable", True):
        alertes.append(str(maintien.get("motif_non_maintien") or motif_sans_droit(bareme, arret)))
        return alertes
    if arret is None or arret.tranche is None:
        return alertes
    for jour, taux in arret.bascules[1:]:
        if debut_periode <= jour <= fin_periode:
            alertes.append(f"{bareme.nom_court} : passage à {pourcent(taux)} le {_date_fr(jour)}.")
    limite = arret.limite_atteinte
    if limite is not None:
        refuses = [
            j for j in arret.jours
            if j > limite
            and debut_periode <= j <= fin_periode
            and debut_arret <= j <= fin_arret
            and j not in plan.taux_par_jour
        ]
        if refuses:
            alertes.append(
                f"{bareme.nom_court} : limite de {arret.tranche.limite} jours atteinte le "
                f"{_date_fr(limite)}, plus de maintien ensuite. Vérifier la prévoyance."
            )
    return alertes


def _euros(valeur: float) -> str:
    return f"{valeur:,.2f}".replace(",", " ").replace(".", ",") + " €"


def _jours_du_palier(n: int, ouvres: bool) -> str:
    if ouvres:
        return f"{n} jour ouvré" if n == 1 else f"{n} jours ouvrés"
    return _jours(n)


def explication_du_maintien_au_bareme(maintien: Optional[Mapping[str, Any]]) -> Optional[str]:
    """« D'où viennent ces lignes » : les paliers du mois, le garanti, les IJSS."""
    if not isinstance(maintien, Mapping) or not maintien.get("paliers"):
        return None
    ouvres = bool(maintien.get("paliers_en_jours_ouvres"))
    morceaux = [
        f"{_jours_du_palier(int(p.get('jours') or 0), ouvres)} à {pourcent(float(p.get('taux') or 0))}"
        for p in maintien["paliers"]
    ]
    garanti = round(float(maintien.get("maintien_cible") or 0.0), 2)
    if maintien.get("regle_retenue") == "legal":
        bareme = bareme_par_code(maintien.get("bareme"))
        nom = bareme.libelle if bareme else "de la convention"
        debut = f"Maintien légal, plus favorable ce mois-ci que le barème {nom}"
    else:
        debut = str(maintien.get("bareme_detail") or "Barème de la convention")
    return (
        f"{debut} : {' et '.join(morceaux)}, salaire garanti {_euros(garanti)}"
        f"{suite_ijss_deduites(maintien)}"
    )


__all__ = [
    "ALERTE_STATUT_ABSENT",
    "alertes_du_bareme",
    "explication_du_maintien_au_bareme",
    "detail_du_bareme",
    "motif_carence_du_bareme",
    "motif_sans_droit",
]
