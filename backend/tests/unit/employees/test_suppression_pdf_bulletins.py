"""Suppression d'un salarié : aucun PDF de bulletin ne reste dans le stockage.

Chaque impression dépose un nouveau PDF horodaté et retire l'ancien ; un
retrait raté laisse un fichier que la colonne `pdf_storage_path` ne connaît
plus. La suppression du salarié liste donc son dossier `bulletins/`.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from app.modules.employees.application import deletion_cleanup

SOCIETE = "co-1"
EMP = "emp-1"
DOSSIER = f"{SOCIETE}/{EMP}/bulletins"
EN_PLACE = f"{DOSSIER}/Bulletin_Salarie_09-2026_20260930T183005123456.pdf"
ORPHELINS = [
    f"{DOSSIER}/Bulletin_Salarie_09-2026_20260929T101010000000.pdf",
    f"{DOSSIER}/Bulletin_Salarie_08-2026_20260830T101010000000_v2.pdf",
    f"{DOSSIER}/Bulletin_Salarie_07-2026.pdf",
]
AUTRE_SALARIE = f"{SOCIETE}/emp-2/bulletins/Bulletin_Autre_09-2026.pdf"


class _Seau:
    def __init__(self, fichiers: list[str], *, liste_en_panne=False, retrait_en_panne=False):
        self.fichiers = set(fichiers)
        self.liste_en_panne = liste_en_panne
        self.retrait_en_panne = retrait_en_panne
        self.retraits: list[list[str]] = []

    def list(self, path=None, options=None):
        if self.liste_en_panne:
            raise RuntimeError("stockage injoignable")
        options = options or {}
        limite, decalage = options.get("limit", 100), options.get("offset", 0)
        prefixe = f"{path}/"
        noms = sorted(
            f[len(prefixe):] for f in self.fichiers if f.startswith(prefixe) and "/" not in f[len(prefixe):]
        )
        return [{"name": n, "id": f"id-{n}"} for n in noms[decalage : decalage + limite]]

    def remove(self, chemins):
        if self.retrait_en_panne:
            raise RuntimeError("retrait refusé")
        self.retraits.append(list(chemins))
        self.fichiers -= set(chemins)
        return []


class _Requete:
    def __init__(self, lignes):
        self._lignes = lignes

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    in_ = eq

    def execute(self):
        return SimpleNamespace(data=self._lignes)


class _Base:
    def __init__(self, seau_bulletins: _Seau):
        self.seaux = {"payslips": seau_bulletins}
        self.storage = SimpleNamespace(from_=self._seau)

    def _seau(self, nom):
        return self.seaux.setdefault(nom, _Seau([]))

    def table(self, nom):
        return _Requete([{"pdf_storage_path": EN_PLACE}] if nom == "payslips" else [])


@pytest.fixture
def base(monkeypatch):
    def installer(seau: _Seau) -> _Base:
        b = _Base(seau)
        monkeypatch.setattr(deletion_cleanup, "supabase", b)
        return b

    return installer


def test_les_pdf_orphelins_du_salarie_sont_retires(base):
    seau = _Seau([EN_PLACE, *ORPHELINS, AUTRE_SALARIE])
    base(seau)

    deletion_cleanup.cleanup_employee_storage(SOCIETE, EMP)

    assert seau.fichiers == {AUTRE_SALARIE}


def test_un_dossier_de_plus_de_100_pdf_est_vide_en_entier(base):
    nombreux = [f"{DOSSIER}/Bulletin_{i:03d}.pdf" for i in range(250)]
    seau = _Seau([*nombreux, AUTRE_SALARIE])
    base(seau)

    deletion_cleanup.cleanup_employee_storage(SOCIETE, EMP)

    assert seau.fichiers == {AUTRE_SALARIE}


def test_listage_en_panne_journalise_et_retire_quand_meme_le_pdf_connu(base, caplog):
    seau = _Seau([EN_PLACE, *ORPHELINS], liste_en_panne=True)
    base(seau)

    with caplog.at_level(logging.WARNING, logger=deletion_cleanup.logger.name):
        deletion_cleanup.cleanup_employee_storage(SOCIETE, EMP)

    assert EN_PLACE not in seau.fichiers
    assert any(DOSSIER in r.getMessage() for r in caplog.records)


def test_retrait_en_panne_journalise_sans_faire_echouer_la_suppression(base, caplog):
    seau = _Seau([EN_PLACE, *ORPHELINS], retrait_en_panne=True)
    base(seau)

    with caplog.at_level(logging.WARNING, logger=deletion_cleanup.logger.name):
        deletion_cleanup.cleanup_employee_storage(SOCIETE, EMP)

    assert any("payslips" in r.getMessage() for r in caplog.records)
