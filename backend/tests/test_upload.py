#!/usr/bin/env python3
# Test upload vers Supabase

import sys
from pathlib import Path

from app.core.database import supabase
from app.shared.infrastructure.pdf.credentials import generate_credentials_pdf

# Chemin vers le logo
logo_path = Path(__file__).parent.parent / "frontend" / "public" / "Colorplast.png"

print("=== Test Upload vers Supabase ===\n")

# 1. Générer le PDF
print("1. Génération du PDF...")
try:
    pdf_content = generate_credentials_pdf(
        first_name="Test",
        last_name="Upload",
        username="test.upload",
        password="TestPass123!",
        logo_path=str(logo_path)
    )
    print(f"✅ PDF généré: {len(pdf_content)} bytes\n")
except Exception as e:
    print(f"❌ Erreur génération PDF: {e}")
    sys.exit(1)

# 2. Tester l'upload
folder_name = "TEST_Upload"
storage_path = f"{folder_name}/creation_compte.pdf"

print("2. Upload vers bucket 'creation_compte'...")
print(f"   Chemin: {storage_path}")

try:
    result = supabase.storage.from_("creation_compte").upload(
        path=storage_path,
        file=pdf_content,
        file_options={"x-upsert": "true", "content-type": "application/pdf"}
    )
    print("✅ Upload réussi!")
    print(f"   Résultat: {result}")
except Exception as e:
    print(f"❌ Erreur upload: {e}")
    import traceback
    traceback.print_exc()

    # Essayer de lister les buckets disponibles
    print("\n3. Liste des buckets disponibles:")
    try:
        buckets = supabase.storage.list_buckets()
        for bucket in buckets:
            print(f"   - {bucket.name}")
    except Exception as e2:
        print(f"   Erreur liste buckets: {e2}")
