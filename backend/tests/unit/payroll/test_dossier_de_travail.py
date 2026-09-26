"""Un dossier de travail par génération : plus de fichiers partagés entre deux
générations simultanées (deux onglets, ou deux homonymes de sociétés
différentes)."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from app.modules.payroll.documents.dossier_de_travail import (
    PREFIXE,
    nouveau_dossier_de_travail,
    supprimer_dossier_de_travail,
)

DOCUMENTS = Path(__file__).resolve().parents[3] / "app/modules/payroll/documents"


def test_deux_generations_du_meme_nom_ont_deux_dossiers():
    a = nouveau_dossier_de_travail("DUPONT_Jean")
    b = nouveau_dossier_de_travail("DUPONT_Jean")
    try:
        assert a != b
        # Le moteur se sert du nom du dossier comme identifiant : il ne change pas.
        assert a.name == b.name == "DUPONT_Jean"
        assert a.is_dir() and b.is_dir()
        assert a.parent.parent == Path(tempfile.gettempdir())
        assert a.parent.name.startswith(PREFIXE)
    finally:
        supprimer_dossier_de_travail(a)
        supprimer_dossier_de_travail(b)


def test_le_nettoyage_de_l_une_ne_touche_pas_l_autre():
    a = nouveau_dossier_de_travail("DUPONT_Jean")
    b = nouveau_dossier_de_travail("DUPONT_Jean")
    try:
        (b / "cumuls").mkdir()
        cumuls_b = b / "cumuls" / "07.json"
        cumuls_b.write_text("{}", encoding="utf-8")
        (a / "cumuls").mkdir()
        (a / "cumuls" / "07.json").write_text("{}", encoding="utf-8")

        supprimer_dossier_de_travail(a)

        assert not a.parent.exists()
        assert cumuls_b.exists()
    finally:
        supprimer_dossier_de_travail(b)
    assert not b.parent.exists()


def test_un_nom_avec_espaces_fonctionne():
    chemin = nouveau_dossier_de_travail("AL NOM COMPOSE_Prenom")
    try:
        assert chemin.is_dir()
        assert chemin.name == "AL NOM COMPOSE_Prenom"
    finally:
        supprimer_dossier_de_travail(chemin)


def test_ne_supprime_jamais_un_dossier_qu_il_n_a_pas_cree(tmp_path):
    etranger = tmp_path / "employes" / "DUPONT_Jean"
    etranger.mkdir(parents=True)
    (etranger / "contrat.json").write_text("{}", encoding="utf-8")

    supprimer_dossier_de_travail(etranger)
    supprimer_dossier_de_travail(None)

    assert (etranger / "contrat.json").exists()


def test_les_generateurs_n_utilisent_plus_le_dossier_partage():
    for nom in ("payslip_generator.py", "payslip_generator_forfait.py"):
        source = (DOCUMENTS / nom).read_text(encoding="utf-8")
        assert "payroll_engine_employee_folder" not in source, nom
        assert "employee_path = nouveau_dossier_de_travail(employee_folder_name)" in source, nom
        # Le dossier est supprimé dans le `finally`, même quand la génération échoue.
        bloc_finally = source[source.rindex("    finally:"):]
        assert re.search(r"supprimer_dossier_de_travail\(dossier_de_travail\)", bloc_finally), nom
