#!/usr/bin/env python3
# Test création d'employé avec génération PDF

import sys
from pathlib import Path
from datetime import date

from app.core.database import supabase
from app.shared.infrastructure.pdf.credentials import generate_credentials_pdf
from app.shared.utils.text import remove_accents

print("=== Test Création Employé avec PDF ===\n")

# Données de test minimales
test_employee = {
    "first_name": "Jean",
    "last_name": "TestPDF",
    "email": f"jean.testpdf+{date.today().strftime('%Y%m%d')}@test.com",
    "nir": "199123456789012",
    "date_naissance": "1991-01-01",
    "lieu_naissance": "75001 Paris",
    "nationalite": "Française",
    "adresse": {
        "rue": "1 rue de Test",
        "code_postal": "75001",
        "ville": "Paris"
    },
    "coordonnees_bancaires": {
        "iban": "FR7612345678901234567890123",
        "bic": "TESTFR2AXXX"
    },
    "hire_date": date.today().isoformat(),
    "contract_type": "CDI",
    "statut": "Non-Cadre",
    "job_title": "Testeur",
    "is_temps_partiel": False,
    "duree_hebdomadaire": 35,
    "salaire_de_base": {"valeur": 2000},
    "classification_conventionnelle": {
        "groupe_emploi": "C",
        "classe_emploi": 6,
        "coefficient": 240
    },
    "avantages_en_nature": {
        "repas": {"nombre_par_mois": 0},
        "logement": {"beneficie": False},
        "vehicule": {"beneficie": False}
    },
    "specificites_paie": {
        "is_alsace_moselle": False,
        "prelevement_a_la_source": {
            "is_personnalise": False,
            "taux": 0
        },
        "transport": {"abonnement_mensuel_total": 0},
        "titres_restaurant": {
            "beneficie": True,
            "nombre_par_mois": 0
        },
        "mutuelle": {
            "adhesion": False,
            "lignes_specifiques": []
        },
        "prevoyance": {
            "adhesion": True,
            "lignes_specifiques": []
        }
    }
}

print(f"Email de test: {test_employee['email']}")
print(f"Nom complet: {test_employee['first_name']} {test_employee['last_name']}\n")

# Générer username et password (normaliser les noms)
username = f"{remove_accents(test_employee['first_name']).lower()}.{remove_accents(test_employee['last_name']).lower()}"
password = "TestPass123!"

print(f"Username: {username}")
print(f"Password: {password}\n")

# Test de génération PDF
print("1. Test génération PDF...")
logo_path = Path(__file__).parent.parent / "frontend" / "public" / "Colorplast.png"
try:
    pdf_content = generate_credentials_pdf(
        first_name=test_employee["first_name"],
        last_name=test_employee["last_name"],
        username=username,
        password=password,
        logo_path=str(logo_path)
    )
    print(f"✅ PDF généré: {len(pdf_content)} bytes\n")
except Exception as e:
    print(f"❌ Erreur: {e}\n")
    sys.exit(1)

# Test upload (normaliser les noms pour correspondre à la vraie application)
folder_name = f"{remove_accents(test_employee['last_name']).upper()}_{remove_accents(test_employee['first_name']).capitalize()}"
storage_path = f"{folder_name}/creation_compte.pdf"

print("2. Test upload vers bucket 'creation_compte'...")
print(f"   Dossier: {folder_name}")
print(f"   Chemin: {storage_path}")

try:
    result = supabase.storage.from_("creation_compte").upload(
        path=storage_path,
        file=pdf_content,
        file_options={"x-upsert": "true", "content-type": "application/pdf"}
    )
    print("✅ Upload réussi!\n")
except Exception as e:
    print(f"❌ Erreur: {e}\n")
    import traceback
    traceback.print_exc()

# Test récupération URL signée
print("3. Test récupération URL signée...")
try:
    list_response = supabase.storage.from_("creation_compte").list(folder_name)
    print(f"   Fichiers dans {folder_name}: {[f['name'] for f in list_response]}")

    if any(f['name'] == 'creation_compte.pdf' for f in list_response):
        signed_url_response = supabase.storage.from_("creation_compte").create_signed_url(
            storage_path,
            3600,
            options={'download': True}
        )

        signed_data = getattr(signed_url_response, "data", signed_url_response)
        url = signed_data.get("signedURL") if isinstance(signed_data, dict) else None

        if url:
            print(f"✅ URL signée générée: {url[:80]}...\n")
        else:
            print("❌ Pas d'URL générée\n")
    else:
        print("❌ Fichier non trouvé\n")

except Exception as e:
    print(f"❌ Erreur: {e}\n")
    import traceback
    traceback.print_exc()

print("=== Test terminé ===")
