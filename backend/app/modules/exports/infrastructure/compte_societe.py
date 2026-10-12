"""Compte bancaire de la société qui paie : donneur d'ordre des remises SEPA.

Saisi dans « Entreprise > Paramètres de paie », rangé dans
`companies.settings.compte_bancaire` ({iban, bic, titulaire}).
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from app.core.database import supabase
from app.shared.utils.iban import normalize_iban, validate_iban

MESSAGE_COMPTE_MANQUANT = (
    "Compte bancaire de la société non renseigné : saisissez l'IBAN, le BIC et le "
    "titulaire dans Entreprise > Paramètres de paie. Sans lui, la remise SEPA n'a "
    "ni donneur d'ordre ni compte à débiter."
)


def compte_depuis_societe(societe: Optional[Mapping[str, Any]]) -> Optional[Dict[str, str]]:
    """{iban, bic, titulaire} de la société, ou None si absent ou illisible.

    Le titulaire absent est le nom de la société.
    Un IBAN dont la clé est fausse compte pour absent : la banque refuserait la remise.
    """
    if not isinstance(societe, Mapping):
        return None
    reglages = societe.get("settings")
    brut = reglages.get("compte_bancaire") if isinstance(reglages, Mapping) else None
    if not isinstance(brut, Mapping):
        return None
    iban = normalize_iban(str(brut.get("iban") or ""))
    if not validate_iban(iban):
        return None
    titulaire = str(brut.get("titulaire") or "").strip() or str(
        societe.get("company_name") or ""
    ).strip()
    return {
        "iban": iban,
        "bic": str(brut.get("bic") or "").replace(" ", "").upper(),
        "titulaire": titulaire,
    }


def charger_compte_societe(company_id: str) -> Optional[Dict[str, str]]:
    """Lit le compte de la société en base (lecture seule)."""
    reponse = (
        supabase.table("companies")
        .select("company_name, settings")
        .eq("id", company_id)
        .execute()
    )
    lignes = reponse.data or []
    return compte_depuis_societe(lignes[0] if lignes else None)


def donneur_d_ordre(
    compte: Optional[Mapping[str, str]],
    debtor_name: Optional[str] = None,
    debtor_iban: Optional[str] = None,
    debtor_bic: Optional[str] = None,
) -> tuple[str, str, str]:
    """(nom, IBAN, BIC) du donneur d'ordre : ce qui est passé d'abord, puis le compte
    de la société, puis les valeurs vides (le garde-fou de l'aperçu bloque avant)."""
    compte = compte or {}
    return (
        debtor_name or compte.get("titulaire") or "Entreprise",
        debtor_iban or compte.get("iban") or "",
        debtor_bic or compte.get("bic") or "",
    )


def anomalie_compte_manquant() -> Dict[str, Any]:
    """Anomalie bloquante de l'aperçu d'un virement sans compte à débiter."""
    return {
        "type": "error",
        "message": MESSAGE_COMPTE_MANQUANT,
        "severity": "blocking",
    }
