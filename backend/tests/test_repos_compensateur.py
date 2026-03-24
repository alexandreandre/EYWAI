#!/usr/bin/env python3
"""
Test complet des fonctionnalités Repos Compensateur (COR).

Exécution:
  cd backend_api && python3 test_repos_compensateur.py

Pour les tests intégration BDD (recalc_service), définir SUPABASE_URL (via .env).
"""

import os
import sys
from pathlib import Path

# Charger .env si disponible (pour tests intégration BDD)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# --- Tests unitaires (logique pure, pas de BDD) ---
def test_extraction_hs():
    """Extraction des heures supp depuis calcul_du_brut"""
    from app.modules.repos_compensateur.domain.rules import extraire_heures_hs_du_bulletin

    # Bulletin vide
    assert extraire_heures_hs_du_bulletin(None) == 0.0
    assert extraire_heures_hs_du_bulletin({}) == 0.0

    # calcul_du_brut absent
    assert extraire_heures_hs_du_bulletin({"autre": []}) == 0.0

    # Une ligne HS
    bulletin = {
        "calcul_du_brut": [
            {"libelle": "Heures supplémentaires 25%", "quantite": 5.5},
            {"libelle": "Salaire de base", "quantite": 151.67},
        ]
    }
    assert extraire_heures_hs_du_bulletin(bulletin) == 5.5

    # Plusieurs lignes HS (Heures suppl, suppl)
    bulletin2 = {
        "calcul_du_brut": [
            {"libelle": "Heures suppl 25%", "quantite": 3.0},
            {"libelle": "Heures supplémentaires 50%", "quantite": 7.0},
        ]
    }
    assert extraire_heures_hs_du_bulletin(bulletin2) == 10.0

    print("  ✓ extraction_hs OK")


def test_cumuler_heures_hs_annee():
    """Cumul des HS sur l'année"""
    from app.modules.repos_compensateur.domain.rules import cumuler_heures_hs_annee

    bulletins = {
        1: {"calcul_du_brut": [{"libelle": "Heures suppl", "quantite": 10.0}]},
        2: {"calcul_du_brut": [{"libelle": "Heures suppl", "quantite": 5.0}]},
        3: {"calcul_du_brut": []},  # 0
    }
    cumuls = cumuler_heures_hs_annee(bulletins)
    assert cumuls[1] == 10.0
    assert cumuls[2] == 15.0
    assert cumuls[3] == 15.0
    assert cumuls[12] == 15.0  # mois 4-12 sans bulletin = cumul inchangé

    print("  ✓ cumuler_heures_hs_annee OK")


def test_calcul_cor():
    """Calcul des heures COR"""
    from app.modules.repos_compensateur.domain.rules import (
        CONTINGENT_DEFAUT,
        calculer_heures_cor_mois,
        get_taux_cor_par_effectif,
        heures_vers_jours,
    )

    # Contingent 220h, pas de COR si cumul < 220
    assert calculer_heures_cor_mois(200, 150, contingent=220, taux_cor=1.0) == 0.0

    # Cumul passe de 200 à 250 : 30h au-delà du contingent → 30h COR
    assert calculer_heures_cor_mois(250, 200, contingent=220, taux_cor=1.0) == 30.0

    # Taux 50% (< 20 sal)
    assert calculer_heures_cor_mois(250, 200, contingent=220, taux_cor=0.5) == 15.0

    # heures_vers_jours
    assert heures_vers_jours(7.0) == 1.0
    assert heures_vers_jours(14.0) == 2.0

    # Taux par effectif
    assert get_taux_cor_par_effectif(10) == 0.5
    assert get_taux_cor_par_effectif(20) == 1.0
    assert get_taux_cor_par_effectif(None) == 1.0

    print("  ✓ calcul_cor OK")


def test_integration_logique_complete():
    """Chaîne complète : bulletins → cumuls → COR → jours"""
    from app.modules.repos_compensateur.domain.rules import (
        CONTINGENT_DEFAUT,
        HEURES_PAR_JOUR_REPOS,
        calculer_heures_cor_mois,
        cumuler_heures_hs_annee,
        heures_vers_jours,
    )

    # Jan: 200h, Feb: 230h, Mar: 260h (cumuls 200, 230, 260)
    bulletins = {
        1: {"calcul_du_brut": [{"libelle": "Heures suppl", "quantite": 200.0}]},
        2: {"calcul_du_brut": [{"libelle": "Heures suppl", "quantite": 30.0}]},
        3: {"calcul_du_brut": [{"libelle": "Heures suppl", "quantite": 30.0}]},
    }
    cumuls = cumuler_heures_hs_annee(bulletins)
    assert cumuls[1] == 200 and cumuls[2] == 230 and cumuls[3] == 260

    # Jan: 0 (cumul 200 < 220)
    h1 = calculer_heures_cor_mois(200, 0, contingent=220, taux_cor=1.0)
    assert h1 == 0.0

    # Feb: (230-220) - 0 = 10h COR
    h2 = calculer_heures_cor_mois(230, 200, contingent=220, taux_cor=1.0)
    assert h2 == 10.0

    # Mar: (260-220) - 10 = 30h COR
    h3 = calculer_heures_cor_mois(260, 230, contingent=220, taux_cor=1.0)
    assert h3 == 30.0

    j2 = heures_vers_jours(10, HEURES_PAR_JOUR_REPOS)
    assert abs(j2 - 1.43) < 0.01

    print("  ✓ Chaîne complète logique OK")


# --- Tests intégration (nécessitent BDD Supabase) ---
def test_recalc_service_and_api():
    """Test recalc_service + présence table repos_compensateur_credits"""
    import os

    if not os.getenv("SUPABASE_URL") and not os.getenv("VITE_SUPABASE_URL"):
        print("  ⊘ Skip (pas de SUPABASE_URL) - tests intégration repos compensateur")
        return

    from app.core.database import supabase

    # Vérifier que la table existe
    try:
        r = supabase.table("repos_compensateur_credits").select("id").limit(1).execute()
        print("  ✓ Table repos_compensateur_credits accessible")
    except Exception as e:
        print(f"  ✗ Table repos_compensateur_credits: {e}")
        return

    # Récupérer un employé et une company pour tester
    emp = supabase.table("employees").select("id, company_id").limit(1).execute().data
    if not emp:
        print("  ⊘ Skip (aucun employé en BDD)")
        return

    emp_id = emp[0]["id"]
    company_id = emp[0]["company_id"]

    from app.modules.repos_compensateur.application.service import (
        recalculer_credits_repos_employe,
    )

    n = recalculer_credits_repos_employe(emp_id, company_id, 2025)
    assert n == 12, f"Recalc devrait upsert 12 mois, a fait {n}"
    print(f"  ✓ recalculer_credits_repos_employe OK (12 mois upsertés)")


def test_imports_and_structure():
    """Vérifier que tous les modules s'importent correctement"""
    from app.modules.repos_compensateur.domain.rules import (
        calculer_heures_cor_mois,
        cumuler_heures_hs_annee,
        extraire_heures_hs_du_bulletin,
        get_taux_cor_par_effectif,
        heures_vers_jours,
    )

    # recalc + router nécessitent Supabase
    if not os.getenv("SUPABASE_URL"):
        print("  ✓ Imports logique OK (recalc/router skip: pas de SUPABASE_URL)")
        return

    from app.modules.repos_compensateur.api import router as repos_router
    from app.modules.repos_compensateur.application.service import (
        recalculer_credits_repos_employe,
    )

    assert hasattr(repos_router, "routes")
    routes = [r.path for r in repos_router.routes if hasattr(r, "path")]
    assert any("calculer-credits" in p for p in routes), "Route calculer-credits manquante"

    print("  ✓ Imports et structure OK")


# --- Exécution ---
def main():
    print("\n=== Test Repos Compensateur (COR) ===\n")

    errors = []
    for name, fn in [
        ("extraction_hs", test_extraction_hs),
        ("cumuler_heures_hs_annee", test_cumuler_heures_hs_annee),
        ("calcul_cor", test_calcul_cor),
        ("Chaîne logique complète", test_integration_logique_complete),
        ("Imports et structure", test_imports_and_structure),
        ("recalc_service + BDD", test_recalc_service_and_api),
    ]:
        try:
            print(f"[{name}]")
            fn()
        except AssertionError as e:
            print(f"  ✗ AssertionError: {e}")
            errors.append((name, str(e)))
        except Exception as e:
            print(f"  ✗ {type(e).__name__}: {e}")
            errors.append((name, str(e)))
        print()

    print("=" * 50)
    if errors:
        print(f"ÉCHEC: {len(errors)} test(s)")
        for name, msg in errors:
            print(f"  - {name}: {msg}")
        sys.exit(1)
    else:
        print("OK: Tous les tests passent.")
        sys.exit(0)


if __name__ == "__main__":
    main()
