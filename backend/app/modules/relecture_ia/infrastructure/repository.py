"""Lectures et écritures de la relecture. Seules les tables relectures_ia* sont écrites.

Les bulletins ne sont que lus, par lots (société et mois, ou liste d'identifiants),
en ne sélectionnant que les colonnes utiles.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any

from app.core.database import supabase
from app.core.supabase_resilience import execute_with_retry
from app.modules.relecture_ia.domain.selection import est_genere_par_martine

_TAILLE_PAGE = 1000
_TAILLE_LISTE = 200

_T_RELECTURES = "relectures_ia"
_T_BULLETINS = "relectures_ia_bulletins"
_T_VUS = "relectures_ia_vus"
_T_REGLES = "relecture_ia_regles"

_COLONNES_CONTRAT = (
    "id, duree_hebdomadaire, is_forfait_jour, is_temps_partiel, contract_type, statut, job_title, "
    # Les noms ne vont pas dans la fiche : ils servent à les retirer des libellés.
    "first_name, last_name, nom_usage"
)


def maintenant_iso() -> str:
    return datetime.now(UTC).isoformat()


def _par_lots(valeurs: Iterable[str], taille: int = _TAILLE_LISTE) -> list[list[str]]:
    liste = list(dict.fromkeys(str(v) for v in valeurs))
    return [liste[i : i + taille] for i in range(0, len(liste), taille)]


def _est_doublon(exc: Exception) -> bool:
    texte = str(exc)
    return "23505" in texte or "duplicate key" in texte


class DepotRelecture:
    def __init__(self, client: Any = None) -> None:
        self._db = client if client is not None else supabase

    def _table(self, nom: str) -> Any:
        return self._db.table(nom)

    @staticmethod
    def _executer(requete: Callable[[], Any]) -> list[dict[str, Any]]:
        return list(execute_with_retry(requete).data or [])

    def _tout_lire(self, construire: Callable[[], Any]) -> list[dict[str, Any]]:
        lignes: list[dict[str, Any]] = []
        debut = 0
        while True:
            fin = debut + _TAILLE_PAGE - 1
            page = self._executer(lambda: construire().range(debut, fin).execute())
            lignes.extend(page)
            if len(page) < _TAILLE_PAGE:
                return lignes
            debut += _TAILLE_PAGE

    # --- bulletins, en lecture seule --------------------------------------

    def bulletins_du_mois(
        self, company_ids: list[str], year: int, month: int
    ) -> list[dict[str, Any]]:
        if not company_ids:
            return []
        lignes = self._tout_lire(
            lambda: self._table("payslips")
            .select("id, company_id, employee_id, contract_period_id, updated_at, bulletin_kind, origine")
            .in_("company_id", company_ids)
            .eq("year", year)
            .eq("month", month)
            .order("id")
        )
        return [l for l in lignes if est_genere_par_martine(l)]

    def contenus_des_bulletins(self, ids: list[str]) -> list[dict[str, Any]]:
        contenus: list[dict[str, Any]] = []
        for lot in _par_lots(ids):
            contenus.extend(
                self._executer(
                    lambda: self._table("payslips")
                    .select(
                        "id, company_id, employee_id, year, month, contract_period_id, "
                        "updated_at, payslip_data"
                    )
                    .in_("id", lot)
                    .execute()
                )
            )
        return contenus

    def bulletins_du_mois_precedent(
        self, company_id: str, employee_ids: list[str], year: int, month: int
    ) -> list[dict[str, Any]]:
        lignes: list[dict[str, Any]] = []
        for lot in _par_lots(employee_ids):
            lignes.extend(
                self._executer(
                    lambda: self._table("payslips")
                    .select("employee_id, contract_period_id, bulletin_kind, payslip_data")
                    .eq("company_id", company_id)
                    .eq("year", year)
                    .eq("month", month)
                    .in_("employee_id", lot)
                    .execute()
                )
            )
        return [l for l in lignes if not l.get("bulletin_kind")]

    def contrats(self, employee_ids: list[str]) -> list[dict[str, Any]]:
        lignes: list[dict[str, Any]] = []
        for lot in _par_lots(employee_ids):
            lignes.extend(
                self._executer(
                    lambda: self._table("employees")
                    .select(_COLONNES_CONTRAT)
                    .in_("id", lot)
                    .execute()
                )
            )
        return lignes

    def noms_des_salaries(self, employee_ids: list[str]) -> list[dict[str, Any]]:
        lignes: list[dict[str, Any]] = []
        for lot in _par_lots(employee_ids):
            lignes.extend(
                self._executer(
                    lambda: self._table("employees")
                    .select("id, first_name, last_name, nom_usage")
                    .in_("id", lot)
                    .execute()
                )
            )
        return lignes

    # --- règles et points vus ---------------------------------------------

    def regles(self, company_id: str) -> str | None:
        lignes = self._executer(
            lambda: self._table(_T_REGLES)
            .select("texte")
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        return lignes[0].get("texte") if lignes else None

    def societes_avec_regles(self, company_ids: list[str]) -> set[str]:
        if not company_ids:
            return set()
        lignes = self._executer(
            lambda: self._table(_T_REGLES)
            .select("company_id")
            .in_("company_id", company_ids)
            .execute()
        )
        return {str(l["company_id"]) for l in lignes}

    def vus_de_la_societe(self, company_id: str) -> list[dict[str, Any]]:
        return self._tout_lire(
            lambda: self._table(_T_VUS)
            .select("employee_id, ligne_normalisee")
            .eq("company_id", company_id)
            .order("id")
        )

    def enregistrer_vu(self, ligne: dict[str, Any]) -> None:
        self._executer(
            lambda: self._table(_T_VUS)
            .upsert(ligne, on_conflict="company_id,employee_id,ligne_normalisee")
            .execute()
        )

    # --- relectures -------------------------------------------------------

    def relecture(self, relecture_id: str) -> dict[str, Any] | None:
        lignes = self._executer(
            lambda: self._table(_T_RELECTURES).select("*").eq("id", relecture_id).limit(1).execute()
        )
        return lignes[0] if lignes else None

    def relecture_en_cours(self) -> dict[str, Any] | None:
        lignes = self._executer(
            lambda: self._table(_T_RELECTURES)
            .select("*")
            .eq("statut", "en_cours")
            .limit(1)
            .execute()
        )
        return lignes[0] if lignes else None

    def derniere_relecture(self) -> dict[str, Any] | None:
        lignes = self._executer(
            lambda: self._table(_T_RELECTURES)
            .select("*")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return lignes[0] if lignes else None

    def derniere_relecture_terminee(self, year: int, month: int) -> dict[str, Any] | None:
        lignes = self._executer(
            lambda: self._table(_T_RELECTURES)
            .select("termine_at, company_ids")
            .eq("year", year)
            .eq("month", month)
            .eq("statut", "terminee")
            .order("termine_at", desc=True)
            .limit(1)
            .execute()
        )
        return lignes[0] if lignes else None

    def creer_relecture(
        self, relecture: dict[str, Any], bulletins: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """None si une relecture est déjà en cours (index unique)."""
        try:
            creee = self._executer(
                lambda: self._table(_T_RELECTURES)
                .insert({**relecture, "battement_at": maintenant_iso()})
                .execute()
            )[0]
        except Exception as exc:
            if _est_doublon(exc):
                return None
            raise
        try:
            for i in range(0, len(bulletins), _TAILLE_LISTE):
                lot = [{**b, "relecture_id": creee["id"]} for b in bulletins[i : i + _TAILLE_LISTE]]
                self._executer(lambda: self._table(_T_BULLETINS).insert(lot).execute())
        except Exception:
            # Sans ses lignes, la relecture bloquerait les suivantes.
            self.modifier_relecture(creee["id"], statut="echec", message=_MESSAGE_CREATION_ECHOUEE)
            raise
        return creee

    def modifier_relecture(self, relecture_id: str, **champs: Any) -> None:
        self._executer(
            lambda: self._table(_T_RELECTURES)
            .update({**champs, "battement_at": maintenant_iso()})
            .eq("id", relecture_id)
            .execute()
        )

    def reprendre_si_bloquee(self, relecture_id: str, avant: str) -> bool:
        """Prend la main sur une relecture dont le battement est plus ancien que `avant`."""
        return bool(
            self._executer(
                lambda: self._table(_T_RELECTURES)
                .update({"battement_at": maintenant_iso()})
                .eq("id", relecture_id)
                .eq("statut", "en_cours")
                .lt("battement_at", avant)
                .execute()
            )
        )

    def bulletins_a_traiter(self, relecture_id: str, limite: int) -> list[dict[str, Any]]:
        return self._executer(
            lambda: self._table(_T_BULLETINS)
            .select("id, payslip_id, company_id, employee_id, year, month, contract_period_id")
            .eq("relecture_id", relecture_id)
            .eq("statut", "a_faire")
            .order("company_id")
            .order("id")
            .limit(limite)
            .execute()
        )

    def enregistrer_resultat(self, ligne_id: str, **champs: Any) -> None:
        self._executer(
            lambda: self._table(_T_BULLETINS)
            .update({**champs, "termine_at": maintenant_iso()})
            .eq("id", ligne_id)
            .execute()
        )

    def resultats_de_la_relecture(self, relecture_id: str) -> list[dict[str, Any]]:
        return self._tout_lire(
            lambda: self._table(_T_BULLETINS)
            .select("statut, signalements, cout_usd")
            .eq("relecture_id", relecture_id)
            .order("id")
        )

    def couts_recents(self, limite: int = 300) -> list[float]:
        """Ce qu'ont réellement coûté les derniers bulletins relus, en dollars."""
        lignes = self._executer(
            lambda: self._table(_T_BULLETINS)
            .select("cout_usd")
            .eq("statut", "fait")
            .order("termine_at", desc=True)
            .limit(limite)
            .execute()
        )
        return [float(l["cout_usd"]) for l in lignes if l.get("cout_usd")]

    def versions_relues(
        self, company_ids: list[str], year: int, month: int
    ) -> list[dict[str, Any]]:
        if not company_ids:
            return []
        return self._tout_lire(
            lambda: self._table(_T_BULLETINS)
            .select("payslip_id, payslip_updated_at, termine_at")
            .in_("company_id", company_ids)
            .eq("year", year)
            .eq("month", month)
            .eq("statut", "fait")
            .order("id")
        )

    def resultats_du_mois(self, company_id: str, year: int, month: int) -> list[dict[str, Any]]:
        return self._tout_lire(
            lambda: self._table(_T_BULLETINS)
            .select("id, payslip_id, employee_id, payslip_updated_at, signalements, termine_at")
            .eq("company_id", company_id)
            .eq("year", year)
            .eq("month", month)
            .eq("statut", "fait")
            .order("id")
        )

    def bulletin_relu(self, ligne_id: str, company_id: str) -> dict[str, Any] | None:
        lignes = self._executer(
            lambda: self._table(_T_BULLETINS)
            .select("employee_id, year, month, signalements")
            .eq("id", ligne_id)
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        return lignes[0] if lignes else None


_MESSAGE_CREATION_ECHOUEE = "La relecture n'a pas pu démarrer. Relancez-la."
