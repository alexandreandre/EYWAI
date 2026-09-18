"""Bascule de reprise de paie : avant la bascule, le passé appartient à l'ancien logiciel.

Reprendre la paie d'une société en cours d'année ne se fait pas en rejouant ses
mois passés, mais en important les compteurs de l'ancien logiciel à une date de
bascule. Deux règles en découlent, et ce module les porte toutes les deux.

1. **Aucun mois antérieur ou égal à la bascule ne se calcule.** Il est importé,
   affiché, verrouillé. Recalculer un mois d'avant remplacerait un fait par une
   estimation, et surtout laisserait les mois suivants sur une base cumulative
   périmée : le générateur n'écrit le cumul que du mois demandé, il n'existe
   aucune cascade vers les mois d'après.

2. **Le cumul du mois précédent doit exister.** Un cumul absent ne vaut pas
   zéro. Il fausse silencieusement la régularisation progressive de la réduction
   générale, les tranches Agirc-Arrco (donc la prévoyance TU2), le plafond
   d'exonération d'impôt des heures supplémentaires et la base du dixième des
   congés payés. Mieux vaut refuser de produire le bulletin.

Le module ne lève rien : il renvoie des raisons de blocage, comme
`payroll_block_reason` et `payslip_employment_period_block_reason`. C'est
l'appelant qui choisit son exception.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.database import supabase
from app.core.logging import get_logger

logger = get_logger(__name__)

#: Origine d'un bulletin. « importe » = repris de l'ancien logiciel, jamais recalculé.
ORIGINE_CALCULE = "calcule"
ORIGINE_IMPORTE = "importe"


def rang_du_mois(annee: int, mois: int) -> int:
    """Numéro d'ordre absolu d'un mois, pour comparer deux (année, mois)."""
    return annee * 12 + mois


def mois_precedent(annee: int, mois: int) -> tuple[int, int]:
    """Le mois d'avant, en franchissant l'année. Même convention que le générateur."""
    return (annee, mois - 1) if mois > 1 else (annee - 1, 12)


@dataclass(frozen=True)
class Bascule:
    """Dernier mois payé par le système précédent."""

    annee: int
    mois: int
    source: str = "bulletins"
    logiciel_precedent: str | None = None
    note: str | None = None

    @property
    def rang(self) -> int:
        return rang_du_mois(self.annee, self.mois)

    @property
    def libelle(self) -> str:
        return f"{self.mois:02d}/{self.annee:04d}"

    def couvre(self, annee: int, mois: int) -> bool:
        """Vrai si ce mois est antérieur ou égal à la bascule, donc importé."""
        return rang_du_mois(annee, mois) <= self.rang

    @property
    def premier_mois_calcule(self) -> tuple[int, int]:
        return (self.annee, self.mois + 1) if self.mois < 12 else (self.annee + 1, 1)


def lire_bascule(company_id: str | None) -> Bascule | None:
    """La bascule de la société, ou None si elle est calculée depuis le début."""
    if not company_id:
        return None
    try:
        res = (
            supabase.table("company_payroll_takeover")
            .select("cutoff_year, cutoff_month, source, previous_software, note")
            .eq("company_id", str(company_id))
            .maybe_single()
            .execute()
        )
    except Exception:  # noqa: BLE001 - table absente ou base injoignable
        logger.warning(
            "Bascule de reprise illisible pour la société %s : la paie est traitée "
            "comme calculée depuis le début.",
            company_id,
        )
        return None
    ligne = getattr(res, "data", None)
    if not ligne:
        return None
    try:
        return Bascule(
            annee=int(ligne["cutoff_year"]),
            mois=int(ligne["cutoff_month"]),
            source=str(ligne.get("source") or "bulletins"),
            logiciel_precedent=ligne.get("previous_software"),
            note=ligne.get("note"),
        )
    except (KeyError, TypeError, ValueError):
        logger.warning("Bascule de reprise mal formée pour la société %s.", company_id)
        return None


def raison_de_blocage_avant_bascule(
    company_id: str | None, annee: int, mois: int, bascule: Bascule | None = None
) -> str | None:
    """Refuse de calculer un mois que l'ancien logiciel a déjà payé."""
    bascule = bascule if bascule is not None else lire_bascule(company_id)
    if bascule is None or not bascule.couvre(annee, mois):
        return None
    prem_annee, prem_mois = bascule.premier_mois_calcule
    quoi = f"{bascule.logiciel_precedent} " if bascule.logiciel_precedent else ""
    return (
        f"Le mois {mois:02d}/{annee:04d} a été payé par le logiciel précédent {quoi}"
        f"et son bulletin est repris tel quel : il ne se recalcule pas. "
        f"La paie reprend au {prem_mois:02d}/{prem_annee:04d}."
    )


def _un_bulletin_existe_avant(employee_id: str, annee: int, mois: int) -> bool:
    """Un bulletin a-t-il déjà été produit à ce mois ou avant ? (chaîne attendue)"""
    borne = rang_du_mois(annee, mois)
    try:
        res = (
            supabase.table("payslips")
            .select("year, month")
            .eq("employee_id", str(employee_id))
            .lte("year", annee)
            .execute()
        )
    except Exception:  # noqa: BLE001
        return False
    for ligne in getattr(res, "data", None) or []:
        try:
            if rang_du_mois(int(ligne["year"]), int(ligne["month"])) <= borne:
                return True
        except (KeyError, TypeError, ValueError):
            continue
    return False


def raison_de_cumul_manquant(
    company_id: str | None,
    employee_id: str,
    annee: int,
    mois: int,
    cumul_trouve: bool,
    bascule: Bascule | None = None,
) -> str | None:
    """Erreur dure quand le cumul du mois précédent manque alors qu'il devrait exister.

    Trois cas donnent un blocage, et un seul est légitime :
    - le mois précédent est celui de la bascule → le solde d'ouverture n'a pas été importé ;
    - le mois précédent est postérieur à la bascule → la chaîne est rompue ;
    - pas de bascule, mais un bulletin existe déjà à ce mois ou avant → chaîne rompue.

    Le cas légitime est le tout premier bulletin d'un salarié : rien à chaîner.
    """
    if cumul_trouve:
        return None
    prec_annee, prec_mois = mois_precedent(annee, mois)
    precedent = f"{prec_mois:02d}/{prec_annee:04d}"
    bascule = bascule if bascule is not None else lire_bascule(company_id)

    if bascule is not None and rang_du_mois(prec_annee, prec_mois) == bascule.rang:
        return (
            f"Le solde d'ouverture de la reprise ({precedent}) est absent pour ce "
            f"collaborateur. Importez ses compteurs de fin {bascule.libelle} avant de "
            f"calculer {mois:02d}/{annee:04d}, sinon la réduction générale, les tranches "
            f"Agirc-Arrco et le plafond des heures supplémentaires repartiraient de zéro."
        )
    if bascule is not None and rang_du_mois(prec_annee, prec_mois) > bascule.rang:
        return (
            f"La chaîne des cumuls est rompue : le bulletin de {precedent} manque, alors "
            f"que la paie de cette société est reprise depuis {bascule.libelle}. "
            f"Générez {precedent} avant {mois:02d}/{annee:04d}."
        )
    if bascule is None and _un_bulletin_existe_avant(employee_id, prec_annee, prec_mois):
        return (
            f"La chaîne des cumuls est rompue : des bulletins existent jusqu'à "
            f"{precedent} mais leurs cumuls sont introuvables. Régénérez {precedent} "
            f"avant {mois:02d}/{annee:04d}."
        )
    return None
