#!/usr/bin/env python3
# Test de connexion avec username et email

import requests
import json

print("=== Test Connexion avec Username et Email ===\n")

BASE_URL = "http://localhost:8000"

# 1. Test avec email
print("1. Test connexion avec EMAIL:")
print("   Credentials: anthony.espinosa6@gmail.com / (mot de passe réel)")

email_data = {
    "username": "anthony.espinosa6@gmail.com",
    "password": input("   Entrez le mot de passe pour anthony.espinosa6@gmail.com: ")
}

try:
    response = requests.post(f"{BASE_URL}/login", data=email_data)
    if response.status_code == 200:
        print(f"   ✅ Connexion réussie avec EMAIL")
        token = response.json().get("access_token")
        print(f"   Token: {token[:30]}...")
    else:
        print(f"   ❌ Échec: {response.status_code} - {response.text}")
except Exception as e:
    print(f"   ❌ Erreur: {e}")

print()

# 2. Test avec username
print("2. Test connexion avec USERNAME:")
print("   Credentials: anthony.espinosa / (même mot de passe)")

username_data = {
    "username": "anthony.espinosa",
    "password": email_data["password"]  # Même mot de passe
}

try:
    response = requests.post(f"{BASE_URL}/login", data=username_data)
    if response.status_code == 200:
        print(f"   ✅ Connexion réussie avec USERNAME")
        token = response.json().get("access_token")
        print(f"   Token: {token[:30]}...")

        # Tester /me avec ce token
        print(f"\n   Test /me avec le token...")
        me_response = requests.get(
            f"{BASE_URL}/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        if me_response.status_code == 200:
            user_data = me_response.json()
            print(f"   ✅ Profil récupéré: {user_data.get('first_name')} {user_data.get('last_name')}")
        else:
            print(f"   ❌ Échec /me: {me_response.status_code}")
    else:
        print(f"   ❌ Échec: {response.status_code} - {response.text}")
except Exception as e:
    print(f"   ❌ Erreur: {e}")

print("\n=== Test terminé ===")
