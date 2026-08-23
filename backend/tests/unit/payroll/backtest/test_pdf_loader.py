"""
Le chargeur de bulletins de référence ne se trompe jamais de mois.

Constat de la cartographie du 23/08/2026, avant le backtest de juillet :
- il cherchait les fichiers sous `Config/<Entreprise>/Compteur CP`, un
  emplacement qui ne contient plus qu'une société sur sept — les six autres
  levaient FileNotFoundError ;
- surtout, quand aucun PDF ne correspondait au mois demandé, il retournait
  `pdfs[0]`, c'est-à-dire **le premier fichier venu**. Un backtest comparant
  silencieusement le mauvais mois est pire qu'un backtest qui plante : les
  écarts constatés sont alors ininterprétables, et on cherche un défaut de
  moteur là où il n'y a qu'une erreur de fichier.
- son filtre acceptait par ailleurs n'importe quel « 07 » présent dans le
  nom, y compris celui d'une autre année.
"""

from __future__ import annotations

import pytest

from scripts.backtest import pdf_loader


@pytest.fixture()
def arborescence(tmp_path, monkeypatch):
    """Reproduit la convention réelle : data/<societe>/bulletins/<AAAA-MM>/."""
    racine = tmp_path / "data"
    for mois in ("2026-05", "2026-06"):
        dossier = racine / "cartol" / "bulletins" / mois
        dossier.mkdir(parents=True)
        (dossier / f"{mois[5:]}-{mois[:4]}-cartol-bulletin-de-salaire.pdf").touch()
    monkeypatch.setattr(pdf_loader, "RACINE_DATA", racine)
    monkeypatch.setattr(pdf_loader, "CONFIG_ROOT", tmp_path / "Config")
    return racine


class TestChoixDuMois:
    def test_trouve_le_mois_demande(self, arborescence):
        chemin = pdf_loader.find_reference_pdf("cartol", 2026, 6)
        assert "2026-06" in str(chemin)

    def test_ne_retombe_jamais_sur_un_autre_mois(self, arborescence):
        """Juillet n'existe pas : il faut une erreur, pas le PDF de mai."""
        with pytest.raises(FileNotFoundError) as exc:
            pdf_loader.find_reference_pdf("cartol", 2026, 7)
        message = str(exc.value)
        assert "2026-07" in message, "l'erreur doit nommer le mois manquant"
        assert "cartol" in message.lower()

    def test_societe_inconnue_donne_une_erreur_explicite(self, arborescence):
        with pytest.raises(FileNotFoundError) as exc:
            pdf_loader.find_reference_pdf("societe-fantome", 2026, 6)
        assert "societe-fantome" in str(exc.value)

    def test_mois_present_mais_vide(self, arborescence):
        (arborescence / "cartol" / "bulletins" / "2026-04").mkdir(parents=True)
        with pytest.raises(FileNotFoundError) as exc:
            pdf_loader.find_reference_pdf("cartol", 2026, 4)
        assert "2026-04" in str(exc.value)


class TestNomsDeSocietes:
    @pytest.mark.parametrize(
        "saisi", ["cartol", "CARTOL", " Cartol ", "Cartol Industrie"]
    )
    def test_variantes_du_nom(self, arborescence, saisi):
        chemin = pdf_loader.find_reference_pdf(saisi, 2026, 6)
        assert "cartol" in str(chemin)
