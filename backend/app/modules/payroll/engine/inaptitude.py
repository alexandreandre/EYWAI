"""Licenciement pour inaptitude : ce que change son origine.

Sources ouvertes le 08/11/2026 :
- Code du travail, art. L1226-14 (code.travail.gouv.fr) : la rupture « ouvre
  droit, pour le salarié, à une indemnité compensatrice d'un montant égal à
  celui de l'indemnité compensatrice de préavis prévue à l'article L. 1234-5
  ainsi qu'à une indemnité spéciale de licenciement qui, sauf dispositions
  conventionnelles plus favorables, est égale au double de l'indemnité prévue
  par l'article L. 1234-9. Toutefois, ces indemnités ne sont pas dues par
  l'employeur qui établit que le refus par le salarié du reclassement qui lui
  est proposé est abusif. »
- Art. L1226-16 : ces indemnités « sont calculées sur la base du salaire moyen
  qui aurait été perçu par l'intéressé au cours des trois derniers mois s'il
  avait continué à travailler au poste qu'il occupait avant la suspension ».
- Art. L1226-4 (origine non professionnelle) : « le préavis n'est pas exécuté
  [...] Le préavis est néanmoins pris en compte pour le calcul de l'indemnité
  mentionnée à l'article L. 1234-9. Par dérogation à l'article L. 1234-5,
  l'inexécution du préavis ne donne pas lieu au versement d'une indemnité
  compensatrice. »
- service-public.gouv.fr F31225 (vérifié le 11/08/2025) : l'indemnité spéciale
  « est versée sans condition d'ancienneté » ; refus abusif : « il perçoit
  l'indemnité légale de licenciement ».

Module pur : aucune lecture, aucune écriture.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

ORIGINE_PROFESSIONNELLE = "professionnelle"
ORIGINE_NON_PROFESSIONNELLE = "non_professionnelle"

LIBELLE_INDEMNITE_SPECIALE = "Indemnité spéciale de licenciement"
LIBELLE_INDEMNITE_COMPENSATRICE = "Indemnité compensatrice d'inaptitude"

#: Dites aux RH sur chaque dossier d'inaptitude d'origine professionnelle.
ALERTES_ORIGINE_PROFESSIONNELLE = (
    "Inaptitude d'origine professionnelle : si l'employeur établit le refus abusif du "
    "reclassement, ces indemnités ne sont pas dues et seule l'indemnité légale l'est "
    "(L1226-14, F31225) : à corriger à la main.",
    "Indemnité compensatrice d'inaptitude portée au brut et soumise aux cotisations comme "
    "un préavis, en attendant la vérification de son régime social.",
)

ALERTE_PREAVIS_NON_SAISI = (
    "Durée du préavis non saisie : l'indemnité compensatrice d'inaptitude (L1226-14) n'est "
    "pas calculée. Saisir la durée du préavis dans le dossier."
)

CALCUL_NON_PROFESSIONNELLE = (
    "Licenciement pour inaptitude d'origine non professionnelle : préavis non exécuté, "
    "pas d'indemnité compensatrice (L1226-4). Sa durée compte dans l'ancienneté de "
    "l'indemnité de licenciement."
)


def origine_inaptitude(exit_notes: Any) -> Optional[str]:
    """L'origine saisie au dossier, None pour un licenciement ordinaire."""
    if not isinstance(exit_notes, dict):
        return None
    origine = exit_notes.get("inaptitude_origine")
    if origine in (ORIGINE_PROFESSIONNELLE, ORIGINE_NON_PROFESSIONNELLE):
        return str(origine)
    return None


def indemnite_speciale(bloc_legal: Dict[str, Any]) -> Dict[str, Any]:
    """Le double de l'indemnité légale (L1226-14)."""
    simple = round(float(bloc_legal.get("montant") or 0.0), 2)
    bloc = dict(bloc_legal)
    bloc.update(
        {
            "montant": round(simple * 2, 2),
            "indemnite_legale_simple": simple,
            "libelle_bulletin": LIBELLE_INDEMNITE_SPECIALE,
            "description": "Indemnité spéciale de licenciement pour inaptitude professionnelle (article L1226-14)",
            "calcul": f"Double de l'indemnité légale (L1226-14) : {bloc_legal.get('calcul') or ''}",
        }
    )
    return bloc


def indemnite_compensatrice(bloc_preavis: Dict[str, Any], alertes: List[str]) -> Dict[str, Any]:
    """Le bloc de préavis devenu l'indemnité compensatrice de L1226-14 : un
    montant égal à celui du préavis, qui n'est pas un préavis."""
    bloc = dict(bloc_preavis)
    bloc.update(
        {
            "libelle_bulletin": LIBELLE_INDEMNITE_COMPENSATRICE,
            "description": "Indemnité compensatrice d'inaptitude (article L1226-14)",
            "inaptitude_professionnelle": True,
            "alertes": list(bloc_preavis.get("alertes") or []) + alertes,
        }
    )
    return bloc
