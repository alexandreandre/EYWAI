#!/usr/bin/env python3
"""
Tests complets des fonctionnalités Promotions — sans connexion HTTP.

Exécute les mêmes scénarios que l’onglet Promotions en appelant directement
les services et la base (Supabase). Aucun login, aucun appel API.

À lancer depuis backend_api avec : python test_promotions_complet.py
Prérequis : .env avec SUPABASE_URL et SUPABASE_KEY (service role).
"""

import sys
import os
from pathlib import Path
from datetime import date, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))

try:
    from dotenv import load_dotenv

    load_dotenv(_here / ".env")
except ImportError:
    pass

from app.core.database import supabase
from app.modules.promotions.application.commands import (
    create_promotion_cmd as create_promotion,
    delete_promotion_cmd as delete_promotion,
    mark_effective_promotion_cmd as mark_promotion_effective,
    update_promotion_cmd as update_promotion,
)
from app.modules.promotions.application.queries import (
    get_employee_rh_access_query as get_employee_rh_access,
    get_promotion_by_id_query as get_promotion_by_id,
    get_promotion_stats_query as get_promotion_stats,
    list_promotions_query as get_promotions,
)
from app.modules.promotions.schemas import (
    PromotionCreate,
    PromotionListItem,
    PromotionUpdate,
)


@dataclass
class TestResult:
    name: str
    success: bool
    message: str
    data: Optional[Any] = None


class PromotionTester:
    def __init__(self):
        self.company_id: Optional[str] = None
        self.employee_id: Optional[str] = None
        self.profile_id: Optional[str] = None  # pour requested_by / approved_by
        self.created_promotion_ids: List[str] = []
        self.results: List[TestResult] = []

    def log(self, message: str, level: str = "INFO"):
        prefix = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARNING": "⚠️",
            "TEST": "🧪",
        }.get(level, "ℹ️")
        print(f"{prefix} {message}")

    def add(self, name: str, success: bool, message: str, data: Any = None):
        self.results.append(
            TestResult(name=name, success=success, message=message, data=data)
        )
        self.log(f"{name}: {message}", "SUCCESS" if success else "ERROR")

    def setup_context(self) -> bool:
        """Récupère company_id, employee_id et un profile_id depuis la base."""
        self.log("Récupération company, employé et profil...", "TEST")
        try:
            # Une company
            r = supabase.table("companies").select("id").limit(1).execute()
            if not r.data or len(r.data) == 0:
                self.add("Setup", False, "Aucune company en base")
                return False
            self.company_id = r.data[0]["id"]

            # Un employé de cette company
            r = (
                supabase.table("employees")
                .select("id")
                .eq("company_id", self.company_id)
                .limit(1)
                .execute()
            )
            if not r.data or len(r.data) == 0:
                self.add("Setup", False, "Aucun employé pour cette company")
                return False
            self.employee_id = r.data[0]["id"]

            # Un profil (profiles.id = user auth) pour requested_by / approved_by
            r = supabase.table("profiles").select("id").limit(1).execute()
            if not r.data or len(r.data) == 0:
                self.add("Setup", False, "Aucun profil en base")
                return False
            self.profile_id = r.data[0]["id"]

            self.add(
                "Setup",
                True,
                f"company={self.company_id[:8]}..., employee={self.employee_id[:8]}..., profile={self.profile_id[:8]}...",
            )
            return True
        except Exception as e:
            self.add("Setup", False, str(e))
            return False

    def _effective_date_future(self) -> date:
        return date.today() + timedelta(days=30)

    def _effective_date_today(self) -> date:
        return date.today()

    def _cleanup_draft_promotions(self):
        """Nettoie les promotions en draft pour l'employé de test."""
        if not self.employee_id or not self.company_id:
            return
        try:
            # Récupérer toutes les promotions draft pour cet employé
            # (la contrainte unique s'applique aux drafts)
            response = (
                supabase.table("promotions")
                .select("id, status")
                .eq("company_id", self.company_id)
                .eq("employee_id", self.employee_id)
                .eq("status", "draft")
                .execute()
            )
            promotions_to_clean = response.data or []

            # Supprimer chaque draft
            for promo in promotions_to_clean:
                try:
                    delete_promotion(promo["id"], self.company_id)
                    if promo["id"] in self.created_promotion_ids:
                        self.created_promotion_ids.remove(promo["id"])
                except Exception:
                    pass  # Ignorer les erreurs de nettoyage
        except Exception:
            pass  # Ignorer les erreurs de nettoyage

    def test_create_promotion(self, promotion_type: str, **kwargs) -> Optional[str]:
        if not self.employee_id or not self.company_id or not self.profile_id:
            self.add(f"Create ({promotion_type})", False, "Contexte manquant")
            return None
        # Par défaut, créer avec date future (sera en draft)
        # Si effective_date est fourni dans kwargs, l'utiliser
        effective = kwargs.get("effective_date", self._effective_date_future())
        # Déterminer le statut attendu selon la date
        expected_status = "effective" if effective <= date.today() else "draft"
        data: Dict[str, Any] = {
            "employee_id": self.employee_id,
            "promotion_type": promotion_type,
            "effective_date": effective,
            "status": expected_status,  # Le backend déterminera automatiquement, mais on peut spécifier
            "reason": "Test auto",
            "justification": f"Test {promotion_type}",
        }
        if promotion_type == "poste":
            data["new_job_title"] = "Nouveau poste test"
        elif promotion_type == "salaire":
            data["new_salary"] = {"valeur": 3500, "devise": "EUR"}
        elif promotion_type == "statut":
            data["new_statut"] = "Cadre"
        elif promotion_type == "classification":
            data["new_classification"] = {"coefficient": 250, "classe_emploi": 7}
        elif promotion_type == "mixte":
            data["new_job_title"] = "Poste mixte test"
            data["new_salary"] = {"valeur": 4000, "devise": "EUR"}
            data["new_statut"] = "Cadre"
        data.update(kwargs)
        try:
            payload = PromotionCreate(**data)
            promo = create_promotion(payload, self.company_id, self.profile_id)
            pid = promo.id
            self.created_promotion_ids.append(pid)
            # Vérifier que le statut est correct (effective si date <= aujourd'hui, sinon draft)
            actual_status = promo.status
            status_ok = actual_status == expected_status
            status_msg = f"id={pid[:8]}..., status={actual_status}"
            self.add(f"Create ({promotion_type})", status_ok, status_msg, pid)
            return pid
        except Exception as e:
            self.add(f"Create ({promotion_type})", False, str(e))
            return None

    def test_get_promotions(self, **filters) -> List[PromotionListItem]:
        if not self.company_id:
            self.add("Get list", False, "company_id manquant")
            return []
        try:
            items = get_promotions(self.company_id, **filters)
            self.add("Get list", True, f"{len(items)} promotion(s)", len(items))
            return items
        except Exception as e:
            self.add("Get list", False, str(e))
            return []

    def test_get_promotion(self, promotion_id: str):
        if not self.company_id:
            self.add("Get one", False, "company_id manquant")
            return None
        try:
            promo = get_promotion_by_id(promotion_id, self.company_id)
            self.add("Get one", True, promotion_id[:8], promo.id)
            return promo
        except Exception as e:
            self.add("Get one", False, str(e))
            return None

    def test_update_promotion(self, promotion_id: str, updates: Dict[str, Any]) -> bool:
        if not self.company_id:
            self.add("Update", False, "company_id manquant")
            return False
        try:
            payload = PromotionUpdate(**updates)
            update_promotion(promotion_id, payload, self.company_id)
            self.add("Update", True, promotion_id[:8])
            return True
        except Exception as e:
            self.add("Update", False, str(e))
            return False

    def test_mark_effective(self, promotion_id: str) -> bool:
        if not self.company_id:
            self.add("Mark effective", False, "company_id manquant")
            return False
        try:
            promo = mark_promotion_effective(promotion_id, self.company_id)
            ok = promo.status == "effective"
            self.add("Mark effective", ok, f"status={promo.status}", promo.status)
            return ok
        except Exception as e:
            self.add("Mark effective", False, str(e))
            return False

    def test_delete_promotion(self, promotion_id: str) -> bool:
        if not self.company_id:
            self.add("Delete", False, "company_id manquant")
            return False
        try:
            delete_promotion(promotion_id, self.company_id)
            if promotion_id in self.created_promotion_ids:
                self.created_promotion_ids.remove(promotion_id)
            self.add("Delete", True, promotion_id[:8])
            return True
        except Exception as e:
            self.add("Delete", False, str(e))
            return False

    def test_get_stats(self, year: Optional[int] = None) -> bool:
        if not self.company_id:
            self.add("Stats", False, "company_id manquant")
            return False
        try:
            stats = get_promotion_stats(self.company_id, year=year)
            self.add("Stats", True, f"total={stats.total_promotions}", stats)
            return True
        except Exception as e:
            self.add("Stats", False, str(e))
            return False

    def test_get_employee_rh_access(self) -> bool:
        if not self.employee_id or not self.company_id:
            self.add("RH access", False, "Contexte manquant")
            return False
        try:
            access = get_employee_rh_access(self.employee_id, self.company_id)
            self.add("RH access", True, f"has_access={access.has_access}", access)
            return True
        except Exception as e:
            self.add("RH access", False, str(e))
            return False

    def run_all(self):
        self.log("=" * 60, "INFO")
        self.log("TESTS PROMOTIONS (sans connexion, services + DB)", "TEST")
        self.log("=" * 60, "INFO")

        if not self.setup_context():
            return

        # Nettoyer les promotions draft existantes pour éviter les conflits de contrainte unique
        self._cleanup_draft_promotions()

        # Création par type (date future = draft)
        # Note: La contrainte unique empêche plusieurs promotions draft pour le même employé
        # On crée une promotion, on la teste, puis on la nettoie avant d'en créer une autre
        self.log("\n--- Création (draft avec date future) ---", "TEST")
        id_poste = self.test_create_promotion("poste")

        # Liste et filtres (avec la promotion poste créée)
        self.log("\n--- Liste et filtres ---", "TEST")
        self.test_get_promotions()
        self.test_get_promotions(status="draft")
        self.test_get_promotions(promotion_type="poste")
        self.test_get_promotions(year=date.today().year)
        if id_poste:
            self.test_get_promotion(id_poste)

        # Mise à jour de la promotion poste (draft)
        if id_poste:
            self.log("\n--- Mise à jour ---", "TEST")
            self.test_update_promotion(
                id_poste,
                {
                    "new_job_title": "Poste mis à jour",
                    "justification": "Mise à jour test",
                },
            )

        # Test création directe en effective (date d'effet = aujourd'hui)
        # Nettoyer d'abord les promotions draft pour libérer la contrainte
        self._cleanup_draft_promotions()
        self.log("\n--- Création directe effective ---", "TEST")
        self.test_create_promotion(
            "poste",
            effective_date=self._effective_date_today(),
            new_job_title="Poste effective test",
        )
        # La promotion devrait être créée directement en "effective" et les changements appliqués

        # Test création en draft puis marquage comme effective (date future)
        # Nettoyer d'abord les promotions draft pour libérer la contrainte
        self._cleanup_draft_promotions()
        self.log("\n--- Workflow draft → effective ---", "TEST")
        id_draft_future = self.test_create_promotion(
            "salaire",
            effective_date=self._effective_date_future(),
            new_salary={"valeur": 3800, "devise": "EUR"},
        )
        if id_draft_future:
            # Vérifier que c'est bien en draft
            promo_check = self.test_get_promotion(id_draft_future)
            if promo_check and promo_check.status == "draft":
                self.log("  ✓ Promotion créée en draft (date future)", "SUCCESS")
            # Marquer comme effective (même si date future, pour tester)
            self.test_mark_effective(id_draft_future)

        # Créer les autres types de promotions pour tester la création
        # Contrainte unique : une seule promotion draft par employé → on supprime après chaque création
        self.log("\n--- Création autres types (draft) ---", "TEST")
        self._cleanup_draft_promotions()
        id_statut = self.test_create_promotion("statut")
        if id_statut:
            self.test_delete_promotion(id_statut)
        self._cleanup_draft_promotions()
        id_classif = self.test_create_promotion("classification")
        if id_classif:
            self.test_delete_promotion(id_classif)
        self._cleanup_draft_promotions()
        id_mixte = self.test_create_promotion("mixte")
        if id_mixte:
            self.test_delete_promotion(id_mixte)

        # Stats et accès RH
        self.log("\n--- Stats et accès RH ---", "TEST")
        self.test_get_stats()
        self.test_get_stats(year=date.today().year)
        self.test_get_employee_rh_access()

        # Nettoyage (supprimer les drafts restants)
        self.log("\n--- Nettoyage ---", "TEST")
        for pid in list(self.created_promotion_ids):
            p = self.test_get_promotion(pid)
            if p and getattr(p, "status", None) == "draft":
                self.test_delete_promotion(pid)

        # Résumé
        total = len(self.results)
        success = sum(1 for r in self.results if r.success)
        failed = total - success
        self.log("\n" + "=" * 60, "INFO")
        self.log("RÉSUMÉ", "TEST")
        self.log("=" * 60, "INFO")
        self.log(f"Total: {total} | Réussis: {success} | Échoués: {failed}", "INFO")
        if failed > 0:
            for r in self.results:
                if not r.success:
                    self.log(f"  - {r.name}: {r.message}", "ERROR")
        self.log("=" * 60, "INFO")


def main():
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        print("❌ Définir SUPABASE_URL et SUPABASE_KEY dans backend_api/.env")
        sys.exit(1)
    tester = PromotionTester()
    tester.run_all()
    failed = sum(1 for r in tester.results if not r.success)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
