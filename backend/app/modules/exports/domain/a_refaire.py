"""Un export déjà fait est « à refaire » quand un bulletin de son mois a changé depuis.

Les exports relisent les bulletins à chaque génération, mais un fichier déjà
sorti (journal de paie, virement, écritures, DSN…) ne bouge plus : un bulletin
du mois recalculé, supprimé ou ajouté après lui le laissait faux sans que rien
ne le dise (audit du 04/10). La règle se calcule à la lecture, sans rien
écrire : la date de l'export contre la dernière modification des bulletins du
mois de la société — leur dernier calcul (`payslips.generated_at`, reposé à
chaque calcul) ou la dernière suppression (journal d'audit).

Seul l'export le plus récent d'un type et d'un mois peut être à refaire : un
export refait depuis remplace l'ancien. Les exports qui ne lisent pas les
bulletins (congés et absences, notes de frais, virement des acomptes) ne le
sont jamais.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

#: Exports qui ne lisent aucun bulletin : un bulletin recalculé ne les rend pas faux.
EXPORTS_HORS_BULLETINS = frozenset({"conges_absences", "notes_frais", "virement_acomptes"})


def instant(valeur: Any) -> datetime | None:
    """Date de la base, toujours avec fuseau (sans fuseau : UTC) ; None si illisible."""
    if not valeur:
        return None
    try:
        lu = datetime.fromisoformat(str(valeur))
    except ValueError:
        return None
    return lu if lu.tzinfo else lu.replace(tzinfo=UTC)


def periode(annee: Any, mois: Any) -> str | None:
    """« AAAA-MM » ; None si l'année ou le mois manque."""
    try:
        return f"{int(annee):04d}-{int(mois):02d}"
    except (TypeError, ValueError):
        return None


def _retenir(dernieres: dict[str, datetime], cle: str | None, quand: datetime | None) -> None:
    if cle and quand and (cle not in dernieres or quand > dernieres[cle]):
        dernieres[cle] = quand


def derniere_modification_par_mois(
    calculs: Iterable[Mapping[str, Any]],
    suppressions: Iterable[Mapping[str, Any]],
) -> dict[str, datetime]:
    """Par mois, le dernier calcul ou la dernière suppression d'un bulletin.

    `calculs` : lignes `payslips` (`year`, `month`, `generated_at`) ;
    `suppressions` : lignes du journal d'audit (`details.year/month`, `created_at`).
    """
    dernieres: dict[str, datetime] = {}
    for ligne in calculs:
        _retenir(dernieres, periode(ligne.get("year"), ligne.get("month")), instant(ligne.get("generated_at")))
    for ligne in suppressions:
        details = ligne.get("details") if isinstance(ligne.get("details"), Mapping) else {}
        _retenir(dernieres, periode(details.get("year"), details.get("month")), instant(ligne.get("created_at")))
    return dernieres


def derniers_exports_tires_des_bulletins(exports: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Le plus récent export généré de chaque type et de chaque mois, s'il lit les bulletins."""
    derniers: dict[tuple[str, str], tuple[datetime, Mapping[str, Any]]] = {}
    for export in exports:
        type_ = str(export.get("export_type") or "")
        if export.get("status") != "generated" or type_ in EXPORTS_HORS_BULLETINS:
            continue
        quand = instant(export.get("generated_at"))
        cle = (type_, str(export.get("period") or ""))
        if quand and (cle not in derniers or quand > derniers[cle][0]):
            derniers[cle] = (quand, export)
    return [export for _, export in derniers.values()]


def exports_a_refaire(
    exports: Iterable[Mapping[str, Any]],
    modifies_le: Mapping[str, datetime],
) -> set[str]:
    """Les ids des exports dont un bulletin du mois a changé depuis."""
    a_refaire: set[str] = set()
    for export in derniers_exports_tires_des_bulletins(exports):
        quand = instant(export.get("generated_at"))
        modifie = modifies_le.get(str(export.get("period") or ""))
        if quand and modifie and modifie > quand:
            a_refaire.add(str(export.get("id")))
    return a_refaire
