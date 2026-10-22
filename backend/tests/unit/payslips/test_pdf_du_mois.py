"""Le PDF du mois recolle les fichiers existants, sans recalculer personne."""

from __future__ import annotations

import io

import pytest
from PyPDF2 import PdfReader
from reportlab.pdfgen import canvas

from app.modules.payslips.domain.pdf_du_mois import (
    BulletinRange,
    SalarieDuMois,
    assembler,
    classer,
    hors_du_mois,
    nom_de_fichier,
    present_sur_le_mois,
)

pytestmark = pytest.mark.unit


def _salarie(
    identifiant: str,
    prenom: str,
    nom: str,
    *,
    statut: str = "actif",
    dernier_jour: str | None = None,
    debut: str | None = "2020-01-01",
    fin: str | None = None,
) -> SalarieDuMois:
    return SalarieDuMois(identifiant, prenom, nom, statut, dernier_jour, debut, fin)


def _page(texte: str) -> bytes:
    tampon = io.BytesIO()
    page = canvas.Canvas(tampon)
    page.drawString(72, 720, texte)
    page.save()
    return tampon.getvalue()


def _titres(pdf: bytes) -> list[str]:
    lecteur = PdfReader(io.BytesIO(pdf))
    titres = []
    for entree in lecteur.outline or []:
        titre = getattr(entree, "title", None)
        if titre:
            titres.append(str(titre))
    return titres


def test_un_parti_reste_sur_le_mois_de_son_dernier_jour():
    assert present_sur_le_mois("parti", "2026-10-24", 2026, 10)
    assert not present_sur_le_mois("parti", "2026-09-30", 2026, 10)
    assert not present_sur_le_mois("parti", None, 2026, 10)
    assert present_sur_le_mois("actif", None, 2026, 10)


def test_quelqu_un_entre_apres_le_mois_n_est_pas_un_trou():
    assert hors_du_mois("2026-11-02", None, 2026, 10)
    assert not hors_du_mois("2026-10-02", None, 2026, 10)
    assert hors_du_mois("2020-01-01", "2026-09-30", 2026, 10)
    assert not hors_du_mois(None, None, 2026, 10)


def test_le_classement_est_alphabetique_et_ignore_qui_est_hors_du_mois():
    salaries = [
        _salarie("2", "Zoé", "Évrard"),
        _salarie("1", "alice", "bernard"),
        _salarie("3", "Camille", "Martin", debut="2026-12-01"),
        _salarie("4", "Léa", "Noël", statut="parti", dernier_jour="2026-07-24"),
    ]
    bulletins = [
        BulletinRange("2", "z.pdf"),
        BulletinRange("1", "a.pdf"),
    ]
    morceaux, sans = classer(salaries, bulletins, 2026, 10)
    assert morceaux == [("alice bernard", "a.pdf"), ("Zoé Évrard", "z.pdf")]
    assert sans == []


def test_la_page_de_garde_nomme_le_trou_et_le_signet_ouvre_le_bulletin():
    salaries = [
        _salarie("b", "Bruno", "Bernard"),
        _salarie("a", "Alice", "Martin"),
        _salarie("c", "Chloé", "Renard"),
    ]
    bulletins = [
        BulletinRange("b", "bruno.pdf"),
        BulletinRange("a", "alice.pdf"),
    ]
    morceaux, sans = classer(salaries, bulletins, 2026, 10)
    assert sans == ["Chloé Renard"]
    fichiers = {"alice.pdf": _page("PAGE-ALICE"), "bruno.pdf": _page("PAGE-BRUNO")}
    pdf = assembler("Société Démo", 2026, 10, morceaux, sans, fichiers.__getitem__)
    lecteur = PdfReader(io.BytesIO(pdf))
    assert len(lecteur.pages) == 3
    garde = lecteur.pages[0].extract_text()
    assert "Chloé Renard" in garde
    assert "Sans bulletin" in garde
    assert "Société Démo" in garde
    assert "PAGE-BRUNO" in lecteur.pages[1].extract_text()
    assert "PAGE-ALICE" in lecteur.pages[2].extract_text()
    assert _titres(pdf) == ["Bruno Bernard", "Alice Martin"]


def test_un_fichier_illisible_est_nomme_et_n_est_pas_colle():
    morceaux = [("Alice Martin", "cassé.pdf"), ("Bruno Bernard", "bon.pdf")]
    def lire(chemin: str) -> bytes:
        if chemin == "bon.pdf":
            return _page("PAGE-BRUNO")
        raise OSError("illisible")

    pdf = assembler("Société Démo", 2026, 8, morceaux, [], lire)
    lecteur = PdfReader(io.BytesIO(pdf))
    assert len(lecteur.pages) == 2
    garde = lecteur.pages[0].extract_text()
    assert "Alice Martin" in garde
    assert "illisible" in garde.lower()
    assert "PAGE-BRUNO" in lecteur.pages[1].extract_text()
    assert _titres(pdf) == ["Bruno Bernard"]


def test_le_nom_de_fichier_porte_le_mois():
    assert nom_de_fichier(2026, 10) == "Bulletins octobre 2026.pdf"
