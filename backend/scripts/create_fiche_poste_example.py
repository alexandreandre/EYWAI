"""Génère le modèle Word exemple fiche de poste (une fois)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

OUT = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "static"
    / "document_templates"
    / "fiche_poste_exemple.docx"
)

CONTENT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:r><w:t>Fiche de poste</w:t></w:r></w:p>
<w:p><w:r><w:t>Entreprise : {{nom_entreprise}} — SIRET : {{siret}}</w:t></w:r></w:p>
<w:p><w:r><w:t>Intitulé : {{poste}}</w:t></w:r></w:p>
<w:p><w:r><w:t>Localisation : {{localisation_poste}}</w:t></w:r></w:p>
<w:p><w:r><w:t>Type de contrat : {{type_contrat}}</w:t></w:r></w:p>
<w:p><w:r><w:t>Missions : {{missions}}</w:t></w:r></w:p>
<w:p><w:r><w:t>Salarié : {{prenom}} {{nom}}</w:t></w:r></w:p>
<w:p><w:r><w:t>Service : {{service}} — Manager : {{manager}}</w:t></w:r></w:p>
<w:p><w:r><w:t>Date : {{date_generation}}</w:t></w:r></w:p>
</w:body></w:document>"""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        from docx import Document

        doc = Document()
        for line in [
            "Fiche de poste",
            "Entreprise : {{nom_entreprise}} — SIRET : {{siret}}",
            "Intitulé : {{poste}}",
            "Localisation : {{localisation_poste}}",
            "Type de contrat : {{type_contrat}}",
            "Missions : {{missions}}",
            "Salarié : {{prenom}} {{nom}}",
            "Service : {{service}} — Manager : {{manager}}",
            "Date : {{date_generation}}",
        ]:
            doc.add_paragraph(line)
        doc.save(OUT)
    except ImportError:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                "</Types>",
            )
            zf.writestr(
                "_rels/.rels",
                '<?xml version="1.0"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                "</Relationships>",
            )
            zf.writestr("word/document.xml", CONTENT)
            zf.writestr(
                "word/_rels/document.xml.rels",
                '<?xml version="1.0"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>',
            )
        OUT.write_bytes(buf.getvalue())
    print(f"Écrit : {OUT}")


if __name__ == "__main__":
    main()
