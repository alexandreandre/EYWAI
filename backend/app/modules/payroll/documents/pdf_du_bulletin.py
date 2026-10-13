"""Chemin du PDF d'un bulletin dans le stockage : un nouveau à chaque impression.

Le PDF était réécrit au même chemin à chaque régénération. Le stockage
Supabase sert ses fichiers derrière un cache : un fichier réécrit en place
peut y rester servi dans son ancienne version (jusqu'à 60 s d'après la
documentation Supabase, qui conseille de déposer à un nouveau chemin plutôt
que d'écraser). Chaque impression porte donc son horodatage, et l'ancien
fichier n'est retiré qu'une fois la ligne du bulletin à jour : jusque-là, un
lien servi pointe vers un fichier qui existe.

Le client est passé en paramètre : chaque appelant garde le sien (celui que
doublent ses tests).
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from weasyprint import HTML

logger = logging.getLogger(__name__)

BUCKET = "payslips"
#: `_20260930T183005123456` : date, heure et microsecondes (UTC).
_HORODATAGE = re.compile(r"_\d{8}T\d{12}$")
#: Le même, dans un nom de fichier, éventuellement suivi du numéro de version archivée.
_HORODATAGE_DU_NOM = re.compile(r"_\d{8}T\d{12}(?=(_v\d+)?\.pdf$)", re.IGNORECASE)


def _horodater(dossier: str, nom: str, maintenant: datetime | None) -> str:
    base = nom[:-4] if nom.lower().endswith(".pdf") else nom
    base = _HORODATAGE.sub("", base)
    instant = (maintenant or datetime.now(UTC)).strftime("%Y%m%dT%H%M%S%f")
    return f"{dossier}/{base}_{instant}.pdf"


def chemin_horodate(
    company_id: str, employee_id: str, pdf_name: str, *, maintenant: datetime | None = None
) -> str:
    """`<société>/<salarié>/bulletins/<nom>_<horodatage>.pdf`."""
    return _horodater(f"{company_id}/{employee_id}/bulletins", pdf_name, maintenant)


def rehorodater(chemin: str, *, maintenant: datetime | None = None) -> str:
    """Même dossier, même nom, nouvel horodatage (un ancien est remplacé, pas empilé)."""
    dossier, _, nom = chemin.rpartition("/")
    return _horodater(dossier, nom, maintenant)


def nom_affiche(chemin: str) -> str:
    """Nom du fichier sans l'horodatage : celui des listes et du téléchargement."""
    return _HORODATAGE_DU_NOM.sub("", chemin.rpartition("/")[2])


def chemin_enregistre(
    client: Any, company_id: str, employee_id: str, year: int, month: int
) -> str | None:
    """Chemin du PDF du bulletin en place, avant qu'une génération ne le remplace.

    None s'il n'y a pas encore de bulletin, ou si la lecture échoue : l'ancien
    fichier reste alors dans le stockage, ce qui ne gêne que la place prise.
    """
    try:
        r = (
            client.table("payslips")
            .select("pdf_storage_path")
            .match(
                {"company_id": company_id, "employee_id": employee_id, "year": year, "month": month}
            )
            .maybe_single()
            .execute()
        )
    except Exception:
        logger.warning(
            "PDF en place non lu (%s, %s, %02d/%s) : il restera dans le stockage.",
            company_id,
            employee_id,
            month,
            year,
            exc_info=True,
        )
        return None
    ligne = r.data if r else None
    return (ligne or {}).get("pdf_storage_path") or None


def retirer_pdf_remplace(client: Any, ancien: str | None, nouveau: str) -> None:
    """Retire l'ancien PDF une fois le bulletin enregistré. Jamais bloquant."""
    if not ancien or ancien == nouveau:
        return
    try:
        client.storage.from_(BUCKET).remove([ancien])
    except Exception:
        logger.warning("PDF remplacé non retiré du stockage : %s", ancien, exc_info=True)


# --- Le HTML imprimé, gardé à côté du PDF (lot 43) ---------------------------------
#
# Le moteur imprime le bulletin, puis l'enrichissement (avances, saisies, prêts)
# le réimprimait toujours, même quand rien n'avait changé : une impression de
# trop à chaque génération. Le HTML de la première impression est gardé à côté
# du PDF ; la seconde n'a lieu que si le HTML à imprimer diffère (le gabarit
# n'appelle aucune ressource extérieure : même HTML, même document).


def _chemin_du_html(chemin_pdf: Path) -> Path:
    return Path(chemin_pdf).with_suffix(".html")


def imprimer_le_bulletin(html: str, chemin_pdf: Path, *, base_url: str | None = None) -> None:
    """Imprime le PDF et garde à côté le HTML imprimé (`html_imprime`).

    Un HTML d'une impression précédente est d'abord retiré : celui qui reste
    est toujours celui du PDF qui est à côté.
    """
    a_cote = _chemin_du_html(chemin_pdf)
    a_cote.unlink(missing_ok=True)
    HTML(string=html, base_url=base_url).write_pdf(chemin_pdf)
    a_cote.write_text(html, encoding="utf-8")


def html_imprime(chemin_pdf: Path) -> str | None:
    """Le HTML du PDF imprimé à ce chemin, ou None (pas de PDF, HTML non gardé)."""
    if not Path(chemin_pdf).exists():
        return None
    try:
        return _chemin_du_html(chemin_pdf).read_text(encoding="utf-8")
    except OSError:
        return None
