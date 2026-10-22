"""Lit les bulletins déjà générés d'un mois et les recolle. Personne n'est recalculé."""

from __future__ import annotations

import logging
from typing import Any

from app.core.database import supabase
from app.modules.employees.application.queries import get_employees_summary
from app.modules.payslips.domain.pdf_du_mois import (
    BulletinRange,
    SalarieDuMois,
    assembler,
    classer,
    nom_de_fichier,
)

logger = logging.getLogger(__name__)


def _salaries(lignes: list[dict[str, Any]]) -> list[SalarieDuMois]:
    return [
        SalarieDuMois(
            identifiant=str(ligne.get("id") or ""),
            prenom=str(ligne.get("first_name") or ""),
            nom=str(ligne.get("last_name") or ""),
            statut=str(ligne.get("employment_status") or "actif"),
            dernier_jour=(str(ligne["exit_last_working_day"])[:10] if ligne.get("exit_last_working_day") else None),
            debut=(
                str(ligne.get("date_debut_execution") or ligne.get("hire_date") or "")[:10] or None
            ),
            fin_contrat=(str(ligne["contract_end_date"])[:10] if ligne.get("contract_end_date") else None),
        )
        for ligne in lignes
        if ligne.get("id")
    ]


def _bulletins(lignes: list[dict[str, Any]]) -> list[BulletinRange]:
    """Un salarié, un fichier : le plus récemment mis à jour s'il y en a plusieurs."""
    gardes: dict[str, tuple[str, str | None]] = {}
    for ligne in lignes:
        identifiant = str(ligne.get("employee_id") or "")
        if not identifiant:
            continue
        chemin = str(ligne["pdf_storage_path"]) if ligne.get("pdf_storage_path") else None
        instant = str(ligne.get("updated_at") or "")
        deja = gardes.get(identifiant)
        if deja is None or (chemin and (not deja[1] or instant >= deja[0])):
            gardes[identifiant] = (instant, chemin)
    return [BulletinRange(identifiant=identifiant, chemin=chemin) for identifiant, (_instant, chemin) in gardes.items()]


def _lire_pdf(chemin: str) -> bytes:
    contenu = supabase.storage.from_("payslips").download(chemin)
    if isinstance(contenu, str):
        return contenu.encode()
    return bytes(contenu)


def rendre_pdf_du_mois(company_id: str, annee: int, mois: int) -> tuple[bytes, str]:
    societe = ""
    try:
        societe_lue = (
            supabase.table("companies")
            .select("company_name")
            .eq("id", company_id)
            .maybe_single()
            .execute()
        )
        if societe_lue and societe_lue.data:
            societe = str(societe_lue.data.get("company_name") or "")
    except Exception:
        logger.warning("Nom de société illisible pour le PDF du mois", exc_info=True)
    salaries = _salaries(get_employees_summary(company_id, payroll_ready_only=True))
    lus = (
        supabase.table("payslips")
        .select("employee_id, pdf_storage_path, updated_at")
        .eq("company_id", company_id)
        .eq("year", annee)
        .eq("month", mois)
        .execute()
    )
    morceaux, sans = classer(salaries, _bulletins(list(lus.data or [])), annee, mois)

    def lire(chemin: str) -> bytes:
        try:
            return _lire_pdf(chemin)
        except Exception:
            logger.warning("PDF de bulletin illisible pour le mois %s-%s", annee, mois, exc_info=True)
            raise

    return assembler(societe, annee, mois, morceaux, sans, lire), nom_de_fichier(annee, mois)
