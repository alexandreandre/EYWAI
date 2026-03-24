#!/usr/bin/env python3
"""
Script de test pour la fonctionnalité de réinitialisation de mot de passe.
Lance des tests basiques pour vérifier que tout fonctionne.
"""

import sys
import os
from datetime import datetime, timedelta, timezone

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Teste que tous les imports nécessaires fonctionnent"""
    print("🧪 Test 1 : Vérification des imports...")
    try:
        from app.shared.infrastructure.email import send_password_reset_email
        from app.modules.auth.schemas import PasswordResetRequest, PasswordResetConfirm
        import secrets
        from datetime import datetime, timedelta, timezone
        print("✅ Tous les imports sont valides\n")
        return True
    except Exception as e:
        print(f"❌ Erreur d'import: {e}\n")
        return False

def test_token_generation():
    """Teste la génération de tokens sécurisés"""
    print("🧪 Test 2 : Génération de tokens...")
    try:
        import secrets
        token = secrets.token_urlsafe(32)
        assert len(token) > 0
        assert isinstance(token, str)
        print(f"✅ Token généré avec succès: {token[:20]}...\n")
        return True
    except Exception as e:
        print(f"❌ Erreur de génération: {e}\n")
        return False

def test_datetime_generation():
    """Teste la génération de dates d'expiration"""
    print("🧪 Test 3 : Génération de dates d'expiration...")
    try:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        now = datetime.now(timezone.utc)
        assert expires_at > now
        print(f"✅ Date d'expiration générée: {expires_at}")
        print(f"   Temps restant: {(expires_at - now).total_seconds() / 60:.1f} minutes\n")
        return True
    except Exception as e:
        print(f"❌ Erreur de génération de date: {e}\n")
        return False

def test_smtp_sender_config():
    """Teste la configuration SMTP (reset password, app.shared)."""
    print("🧪 Test 4 : Configuration du service d'e-mail...")
    try:
        from app.shared.infrastructure.email.password_reset_smtp import (
            get_password_reset_smtp_sender,
        )

        sender = get_password_reset_smtp_sender()
        print(f"   SMTP Host: {sender.smtp_host}")
        print(f"   SMTP Port: {sender.smtp_port}")
        print(f"   SMTP User: {sender.smtp_user or '(Non configuré)'}")
        print(f"   From Email: {sender.from_email}")
        print(f"   Frontend URL: {sender.frontend_url}")

        if sender.smtp_user and sender.smtp_password:
            print("✅ Service SMTP configuré\n")
        else:
            print("⚠️  Service SMTP non configuré (mode développement)\n")
        return True
    except Exception as e:
        print(f"❌ Erreur de configuration: {e}\n")
        return False

def test_pydantic_models():
    """Teste les modèles Pydantic"""
    print("🧪 Test 5 : Validation des modèles Pydantic...")
    try:
        from app.modules.auth.schemas import PasswordResetRequest, PasswordResetConfirm

        # Test PasswordResetRequest
        request = PasswordResetRequest(email="test@example.com")
        assert request.email == "test@example.com"
        print("✅ PasswordResetRequest valide")

        # Test PasswordResetConfirm
        confirm = PasswordResetConfirm(token="test_token", new_password="SecurePass123")
        assert confirm.token == "test_token"
        assert confirm.new_password == "SecurePass123"
        print("✅ PasswordResetConfirm valide\n")

        return True
    except Exception as e:
        print(f"❌ Erreur de validation: {e}\n")
        return False

def test_environment_variables():
    """Teste les variables d'environnement"""
    print("🧪 Test 6 : Vérification des variables d'environnement...")
    from dotenv import load_dotenv
    load_dotenv()

    required = ["SUPABASE_URL", "SUPABASE_KEY"]
    optional = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FRONTEND_URL"]

    print("   Variables requises:")
    all_present = True
    for var in required:
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var}: {value[:30]}..." if len(value) > 30 else f"   ✅ {var}: {value}")
        else:
            print(f"   ❌ {var}: Non définie")
            all_present = False

    print("\n   Variables optionnelles (SMTP):")
    for var in optional:
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var}: {value}")
        else:
            print(f"   ⚠️  {var}: Non définie")

    print()
    return all_present

def main():
    """Exécute tous les tests"""
    print("=" * 80)
    print("🚀 TESTS DE LA FONCTIONNALITÉ DE RÉINITIALISATION DE MOT DE PASSE")
    print("=" * 80)
    print()

    tests = [
        test_imports,
        test_token_generation,
        test_datetime_generation,
        test_smtp_sender_config,
        test_pydantic_models,
        test_environment_variables,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Exception inattendue: {e}\n")
            results.append(False)

    print("=" * 80)
    print("📊 RÉSULTATS")
    print("=" * 80)
    passed = sum(results)
    total = len(results)
    print(f"Tests réussis: {passed}/{total}")

    if passed == total:
        print("\n🎉 Tous les tests sont passés ! La fonctionnalité est prête.")
        print("\n📝 Prochaines étapes:")
        print("   1. Exécutez le script SQL dans Supabase (create_password_reset_table.sql)")
        print("   2. Configurez les variables SMTP dans .env (optionnel)")
        print("   3. Lancez le backend: python main.py")
        print("   4. Testez via le frontend: http://localhost:8080/forgot-password")
    else:
        print("\n⚠️  Certains tests ont échoué. Vérifiez les erreurs ci-dessus.")
    print("=" * 80)

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
