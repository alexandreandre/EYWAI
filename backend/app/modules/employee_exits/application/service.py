"""
Service applicatif partagé du module employee_exits.

Délègue à l'infrastructure (repositories, queries). Comportement identique au router.
"""
import sys
from typing import Any, Dict, List

from app.modules.employee_exits.infrastructure import queries as infra_queries

# Liste des items par défaut (règle métier : contenu fixe)
DEFAULT_CHECKLIST_ITEMS: List[Dict[str, Any]] = [
    {"item_code": "badge_return", "item_label": "Restitution du badge d'accès", "item_description": "Le salarié doit restituer son badge d'accès aux locaux", "item_category": "materiel", "is_required": True, "display_order": 0},
    {"item_code": "equipment_return", "item_label": "Restitution du matériel informatique", "item_description": "Ordinateur portable, téléphone, accessoires, etc.", "item_category": "materiel", "is_required": True, "display_order": 1},
    {"item_code": "email_deactivation", "item_label": "Désactivation de l'adresse email professionnelle", "item_description": "Configurer le transfert ou la réponse automatique puis désactiver", "item_category": "acces", "is_required": True, "display_order": 2},
    {"item_code": "access_revocation", "item_label": "Révocation des accès aux systèmes", "item_description": "Supprimer les accès aux applications, VPN, serveurs, etc.", "item_category": "acces", "is_required": True, "display_order": 3},
    {"item_code": "final_payslip", "item_label": "Génération du bulletin de paie de solde", "item_description": "Bulletin incluant les indemnités de sortie", "item_category": "administratif", "is_required": True, "display_order": 4},
    {"item_code": "work_certificate", "item_label": "Certificat de travail", "item_description": "Document obligatoire (Article L1234-19)", "item_category": "legal", "is_required": True, "display_order": 5},
    {"item_code": "unemployment_certificate", "item_label": "Attestation Pôle Emploi", "item_description": "Nécessaire pour les allocations chômage", "item_category": "legal", "is_required": True, "display_order": 6},
    {"item_code": "final_settlement", "item_label": "Solde de tout compte", "item_description": "Récapitulatif des sommes versées (Article D1234-7)", "item_category": "legal", "is_required": True, "display_order": 7},
]


def create_default_checklist_sync(exit_id: str, company_id: str, supabase_client: Any = None) -> None:
    """Crée la checklist par défaut pour une sortie. Délègue au repository."""
    from app.modules.employee_exits.infrastructure.repository import ExitChecklistRepository
    repo = ExitChecklistRepository(supabase_client)
    items = [{"exit_id": exit_id, "company_id": company_id, **item} for item in DEFAULT_CHECKLIST_ITEMS]
    try:
        repo.create_many(items)
        print(f"✓ Checklist créée pour sortie {exit_id}", file=sys.stderr)
    except Exception as e:
        print(f"⚠ Erreur création checklist: {e}", file=sys.stderr)


def enrich_exit_with_documents_and_checklist(
    exit_record: Dict[str, Any],
    signed_url_expiry_seconds: int = 3600,
    supabase_client: Any = None,
) -> None:
    """
    Enrichit sur place une sortie (documents, checklist, taux). Délègue à infrastructure.queries.
    """
    infra_queries.enrich_exit_with_documents_and_checklist(
        exit_record, signed_url_expiry_seconds, supabase_client
    )
