#!/usr/bin/env python3
# Test rapide de génération de PDF (app.shared — modular monolith)

from pathlib import Path

from app.shared.infrastructure.pdf.credentials import generate_credentials_pdf

# Chemin vers le logo
logo_path = Path(__file__).parent.parent / "frontend" / "public" / "Colorplast.png"

print(f"Logo path: {logo_path}")
print(f"Logo exists: {logo_path.exists()}")

try:
    pdf_content = generate_credentials_pdf(
        first_name="Test",
        last_name="User",
        username="test.user",
        password="TestPass123!",
        logo_path=str(logo_path),
    )

    print(f"✅ PDF généré avec succès! Taille: {len(pdf_content)} bytes")

    # Sauvegarder le PDF pour test
    output_path = Path(__file__).parent / "test_credentials.pdf"
    output_path.write_bytes(pdf_content)
    print(f"✅ PDF sauvegardé dans: {output_path}")

except Exception as e:
    print(f"❌ Erreur lors de la génération du PDF: {e}")
    import traceback

    traceback.print_exc()
