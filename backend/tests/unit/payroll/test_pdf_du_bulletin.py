"""PDF d'un bulletin : un nouveau chemin à chaque impression, l'ancien retiré après.

Le PDF était réécrit au même chemin à chaque régénération. Le stockage
Supabase sert ses fichiers derrière un cache : un fichier réécrit en place
peut y rester servi dans son ancienne version, et la documentation Supabase
conseille de déposer à un nouveau chemin plutôt que d'écraser. Chaque
impression porte donc son horodatage ; l'ancien fichier n'est retiré qu'une
fois la ligne du bulletin à jour, et un échec de ce retrait se journalise
sans faire échouer la génération.

Le bac à sable (`persister=False`) n'écrit ni ne retire rien du stockage.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.payroll.documents import payslip_generator as pg
from app.modules.payroll.documents import pdf_du_bulletin as pdf
from app.modules.payroll.documents.bac_a_sable import BacASable
from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader
from tests.unit.payroll.test_filet_heures_sur_arret import (  # noqa: F401 — fixture `moteur`
    ANNEE,
    ARRET_VALIDE,
    EMP,
    MOIS,
    SOCIETE,
    _Base,
    _reel_de_septembre,
    _Requete,
    moteur,
)

pytestmark = pytest.mark.unit

INSTANT = datetime(2026, 9, 30, 18, 30, 5, 123456, tzinfo=UTC)
INSTANT_SUIVANT = datetime(2026, 9, 30, 18, 31, 0, 7, tzinfo=UTC)
DOSSIER = f"{SOCIETE}/{EMP}/bulletins"
NOM_DU_PDF = f"Bulletin_Salarie_Filet_{MOIS:02d}-{ANNEE}.pdf"
CHEMIN_HISTORIQUE = f"{DOSSIER}/{NOM_DU_PDF}"


# --- Doublures du stockage -------------------------------------------------


class _Seau:
    def __init__(self, journal: list, *, retrait_en_echec: bool = False):
        self.journal = journal
        self.retrait_en_echec = retrait_en_echec
        self.options_de_signature: list = []

    def upload(self, path, file, file_options=None):
        self.journal.append(("deposer", path))
        return SimpleNamespace(path=path)

    def create_signed_url(self, path, expires_in, options=None):
        self.journal.append(("signer", path))
        self.options_de_signature.append(options)
        return {"signedURL": f"https://stockage.test/{path}?token=t"}

    def remove(self, paths):
        self.journal.append(("retirer", list(paths)))
        if self.retrait_en_echec:
            raise RuntimeError("stockage indisponible")
        return []


class _Stockage:
    def __init__(self, seau: _Seau):
        self.seau = seau

    def from_(self, bucket: str) -> _Seau:
        assert bucket == "payslips"
        return self.seau


class _StockageInterdit:
    def from_(self, bucket: str):
        raise AssertionError(f"accès au stockage « {bucket} » en bac à sable")


class _Client:
    """Client réduit à ce que lisent les fonctions du module."""

    def __init__(self, *, ligne=None, lecture_en_echec=False, retrait_en_echec=False):
        self.journal: list = []
        self.ligne = ligne
        self.lecture_en_echec = lecture_en_echec
        self.storage = _Stockage(_Seau(self.journal, retrait_en_echec=retrait_en_echec))

    def table(self, nom):
        client = self

        class _R:
            def select(self, *_a):
                return self

            def match(self, *_a):
                return self

            eq = match

            def maybe_single(self):
                return self

            def execute(self):
                if client.lecture_en_echec:
                    raise RuntimeError("base indisponible")
                return None if client.ligne is None else SimpleNamespace(data=client.ligne)

        assert nom == "payslips"
        return _R()


# --- Le chemin ---------------------------------------------------------------


class TestChemin:
    def test_horodate_dans_le_dossier_des_bulletins(self):
        assert pdf.chemin_horodate(SOCIETE, EMP, NOM_DU_PDF, maintenant=INSTANT) == (
            f"{DOSSIER}/Bulletin_Salarie_Filet_09-2026_20260930T183005123456.pdf"
        )

    def test_garde_le_suffixe_du_forfait(self):
        assert pdf.chemin_horodate(
            SOCIETE, EMP, "Bulletin_X_09-2026_FORFAIT.pdf", maintenant=INSTANT
        ).endswith("/Bulletin_X_09-2026_FORFAIT_20260930T183005123456.pdf")

    def test_reimprimer_change_l_horodatage_sans_l_empiler(self):
        premier = pdf.chemin_horodate(SOCIETE, EMP, NOM_DU_PDF, maintenant=INSTANT)

        assert pdf.rehorodater(premier, maintenant=INSTANT_SUIVANT) == (
            f"{DOSSIER}/Bulletin_Salarie_Filet_09-2026_20260930T183100000007.pdf"
        )

    def test_reimprimer_un_pdf_d_avant_l_horodatage(self):
        assert pdf.rehorodater(CHEMIN_HISTORIQUE, maintenant=INSTANT) == (
            f"{DOSSIER}/Bulletin_Salarie_Filet_09-2026_20260930T183005123456.pdf"
        )


class TestNomAffiche:
    """L'horodatage est pour le stockage : listes et téléchargements gardent le nom d'avant."""

    def test_sans_l_horodatage(self):
        assert pdf.nom_affiche(pdf.chemin_horodate(SOCIETE, EMP, NOM_DU_PDF, maintenant=INSTANT)) == NOM_DU_PDF

    def test_un_pdf_d_avant_l_horodatage_garde_son_nom(self):
        assert pdf.nom_affiche(CHEMIN_HISTORIQUE) == NOM_DU_PDF

    def test_le_forfait_garde_son_suffixe(self):
        chemin = pdf.chemin_horodate(SOCIETE, EMP, "Bulletin_X_09-2026_FORFAIT.pdf", maintenant=INSTANT)

        assert pdf.nom_affiche(chemin) == "Bulletin_X_09-2026_FORFAIT.pdf"

    def test_une_version_archivee_garde_son_numero(self):
        horodate = pdf.chemin_horodate(SOCIETE, EMP, NOM_DU_PDF, maintenant=INSTANT)
        version = f"{horodate[:-4]}_v4.pdf"

        assert pdf.nom_affiche(version) == "Bulletin_Salarie_Filet_09-2026_v4.pdf"


class TestListesDesBulletins:
    HORODATE = f"{DOSSIER}/Bulletin_Salarie_Filet_09-2026_20260930T183005123456.pdf"

    def test_le_lien_de_telechargement_porte_le_nom_d_avant(self, monkeypatch):
        from app.modules.payslips.infrastructure import storage_urls

        class _Seau:
            def create_signed_urls(self, paths, expires, options=None):
                suffixe = "&download=" if options and options.get("download") else ""
                return [
                    {"signedURL": f"https://stockage.test/object/sign/payslips/{p}?token=jeton.abc_-{suffixe}"}
                    for p in paths
                ]

        monkeypatch.setattr(
            storage_urls, "supabase", SimpleNamespace(storage=SimpleNamespace(from_=lambda _b: _Seau()))
        )

        telechargement, apercu = storage_urls.create_payslip_url_maps([self.HORODATE])

        assert telechargement[self.HORODATE] == (
            f"https://stockage.test/object/sign/payslips/{self.HORODATE}"
            f"?token=jeton.abc_-&download={NOM_DU_PDF}"
        )
        assert apercu[self.HORODATE] == (
            f"https://stockage.test/object/sign/payslips/{self.HORODATE}?token=jeton.abc_-"
        )

    @staticmethod
    def _base(ligne: dict) -> SimpleNamespace:
        class _R:
            def select(self, *_a):
                return self

            def eq(self, *_a, **_k):
                return self

            order = eq

            def maybe_single(self):
                self.une_ligne = True
                return self

            def execute(self):
                return SimpleNamespace(data=ligne if getattr(self, "une_ligne", False) else [ligne])

        return SimpleNamespace(table=lambda _n: _R())

    @staticmethod
    def _liens(paths, _expires):
        return {p: "https://dl" for p in paths}, {p: "https://vu" for p in paths}

    def test_les_listes_affichent_le_nom_d_avant(self, monkeypatch):
        from app.modules.payslips.infrastructure import queries

        ligne = {"id": "ps-1", "month": MOIS, "year": ANNEE, "pdf_storage_path": self.HORODATE}
        monkeypatch.setattr(queries, "supabase", self._base(ligne))
        monkeypatch.setattr(queries, "create_payslip_url_maps", self._liens)

        assert [b["name"] for b in queries.get_employee_payslips(EMP)] == [NOM_DU_PDF]
        assert [b["name"] for b in queries.get_my_payslips(EMP)] == [NOM_DU_PDF]

    def test_l_explorateur_de_documents_affiche_le_nom_d_avant(self, monkeypatch):
        from app.modules.documents.application import explorer_queries

        ligne = {
            "id": "ps-1", "employee_id": EMP, "month": MOIS, "year": ANNEE,
            "pdf_storage_path": self.HORODATE, "first_name": "Prénom", "last_name": "Test",
        }
        monkeypatch.setattr(explorer_queries, "supabase", self._base(ligne))
        monkeypatch.setattr(explorer_queries, "create_payslip_url_maps", self._liens)

        assert [b["name"] for b in explorer_queries._fetch_company_payslips(SOCIETE)] == [NOM_DU_PDF]


class TestCheminEnregistre:
    def test_lit_le_chemin_du_bulletin_en_place(self):
        client = _Client(ligne={"pdf_storage_path": CHEMIN_HISTORIQUE})

        assert pdf.chemin_enregistre(client, SOCIETE, EMP, ANNEE, MOIS) == CHEMIN_HISTORIQUE

    def test_premiere_generation(self):
        assert pdf.chemin_enregistre(_Client(ligne=None), SOCIETE, EMP, ANNEE, MOIS) is None

    def test_lecture_en_echec_journalisee_sans_bloquer(self, caplog):
        with caplog.at_level(logging.WARNING):
            chemin = pdf.chemin_enregistre(_Client(lecture_en_echec=True), SOCIETE, EMP, ANNEE, MOIS)

        assert chemin is None
        assert "PDF en place non lu" in caplog.text


class TestRetirerLePdfRemplace:
    def test_retire_l_ancien(self):
        client = _Client()

        pdf.retirer_pdf_remplace(client, CHEMIN_HISTORIQUE, f"{DOSSIER}/nouveau.pdf")

        assert client.journal == [("retirer", [CHEMIN_HISTORIQUE])]

    @pytest.mark.parametrize("ancien", [None, "", f"{DOSSIER}/nouveau.pdf"])
    def test_rien_a_retirer(self, ancien):
        client = _Client()

        pdf.retirer_pdf_remplace(client, ancien, f"{DOSSIER}/nouveau.pdf")

        assert client.journal == []

    def test_un_echec_se_journalise_sans_lever(self, caplog):
        client = _Client(retrait_en_echec=True)

        with caplog.at_level(logging.WARNING):
            pdf.retirer_pdf_remplace(client, CHEMIN_HISTORIQUE, f"{DOSSIER}/nouveau.pdf")

        assert "PDF remplacé non retiré" in caplog.text
        assert CHEMIN_HISTORIQUE in caplog.text


# --- Le générateur, pour de vrai, jusqu'au stockage --------------------------


class _RequeteEcrite(_Requete):
    def upsert(self, ligne, **_k):
        self.base.journal.append(("enregistrer", self.table, dict(ligne)))
        self._donnees = [{"id": "ps-1", **ligne}]
        return self

    def update(self, valeurs):
        self.base.journal.append(("modifier", self.table, dict(valeurs)))
        self._donnees = []
        return self

    def execute(self):
        if hasattr(self, "_donnees"):
            return SimpleNamespace(data=self._donnees)
        return super().execute()


class _BaseEcrite(_Base):
    def __init__(self, *, chemin_en_place: str | None, retrait_en_echec: bool = False):
        super().__init__(_reel_de_septembre(), compensation=False)
        self.journal: list = []
        self.chemin_en_place = chemin_en_place
        self.storage = _Stockage(_Seau(self.journal, retrait_en_echec=retrait_en_echec))
        self.lectures_payslips = 0

    def table(self, nom: str) -> _RequeteEcrite:
        return _RequeteEcrite(self, nom)

    def lire(self, table: str, colonnes: str):
        if table == "payslips":
            self.lectures_payslips += 1
            return {"pdf_storage_path": self.chemin_en_place} if self.chemin_en_place else None
        if table == "monthly_inputs":
            return []
        return super().lire(table, colonnes)


@pytest.fixture
def imprimeur(monkeypatch, moteur):  # noqa: F811 — fixture importée
    """Le calcul doublé dépose un vrai fichier PDF là où le générateur le lit."""
    from app.modules.employee_loans.application import payroll_integration
    from app.modules.payroll.documents import payslip_run_heures
    from app.modules.repos_compensateur.application import service as repos

    def calcul_qui_imprime(employee_path, year, month, *_a, **_k):
        dossier = Path(employee_path) / "bulletins"
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / NOM_DU_PDF).write_bytes(b"%PDF-1.4 bulletin de test")
        return {"alertes_baremes": [], "salaire_brut": 0.0, "net_a_payer": 0.0}

    monkeypatch.setattr(payslip_run_heures, "run_payslip_generation_heures", calcul_qui_imprime)
    monkeypatch.setattr(
        payroll_integration, "enrich_payslip_after_upsert", lambda donnees, *_a, **_k: donnees
    )
    monkeypatch.setattr(repos, "recalculer_credits_repos_employe", lambda *_a, **_k: None)
    monkeypatch.setattr(arrets_valides_reader, "par_salarie", lambda *_a, **_k: {EMP: [ARRET_VALIDE]})
    return moteur


def _generer(monkeypatch, base, **options):
    monkeypatch.setattr(pg, "supabase", base)
    return pg.process_payslip_generation(EMP, ANNEE, MOIS, **options)


def _etapes(journal: list) -> list:
    return [e for e in journal if e[0] != "modifier"]


class TestGenerateur:
    def test_regenerer_depose_a_un_nouveau_chemin_puis_retire_l_ancien(self, monkeypatch, imprimeur):
        base = _BaseEcrite(chemin_en_place=CHEMIN_HISTORIQUE)

        resultat = _generer(monkeypatch, base)

        assert resultat["status"] == "success"
        deposer, signer, enregistrer, retirer = _etapes(base.journal)
        nouveau = deposer[1]
        assert nouveau != CHEMIN_HISTORIQUE
        assert nouveau.startswith(f"{DOSSIER}/Bulletin_Salarie_Filet_09-2026_")
        assert signer == ("signer", nouveau)
        assert enregistrer[2]["pdf_storage_path"] == nouveau
        assert nouveau in enregistrer[2]["url"]
        # Retiré seulement une fois la ligne à jour : un lien servi d'ici là
        # pointe vers un fichier qui existe.
        assert retirer == ("retirer", [CHEMIN_HISTORIQUE])
        assert resultat["download_url"] == enregistrer[2]["url"]
        # Le fichier téléchargé garde son nom d'avant l'horodatage.
        assert base.storage.seau.options_de_signature == [{"download": NOM_DU_PDF}]
        assert enregistrer[2]["name"] == NOM_DU_PDF

    def test_chaque_calcul_date_le_bulletin(self, monkeypatch, imprimeur):
        """`generated_at` ne valait que la première création : un bulletin
        recalculé après un export ne le rendait pas « à refaire »."""
        base = _BaseEcrite(chemin_en_place=CHEMIN_HISTORIQUE)
        avant = datetime.now(UTC)

        _generer(monkeypatch, base)

        enregistrer = [e for e in base.journal if e[0] == "enregistrer"][0]
        calcule_le = datetime.fromisoformat(enregistrer[2]["generated_at"])
        assert calcule_le.tzinfo is not None
        assert avant <= calcule_le <= datetime.now(UTC)

    def test_premiere_generation_ne_retire_rien(self, monkeypatch, imprimeur):
        base = _BaseEcrite(chemin_en_place=None)

        _generer(monkeypatch, base)

        assert [e[0] for e in _etapes(base.journal)] == ["deposer", "signer", "enregistrer"]

    def test_un_retrait_en_echec_ne_fait_pas_echouer_la_generation(self, monkeypatch, imprimeur, caplog):
        base = _BaseEcrite(chemin_en_place=CHEMIN_HISTORIQUE, retrait_en_echec=True)

        with caplog.at_level(logging.WARNING):
            resultat = _generer(monkeypatch, base)

        assert resultat["status"] == "success"
        assert "PDF remplacé non retiré" in caplog.text

    def test_le_bac_a_sable_ne_touche_pas_au_stockage(self, monkeypatch, imprimeur):
        base = _BaseEcrite(chemin_en_place=CHEMIN_HISTORIQUE)
        base.storage = _StockageInterdit()

        resultat = _generer(monkeypatch, base, bac_a_sable=BacASable())

        assert resultat["payslip_id"] is None
        assert base.journal == []
        assert base.lectures_payslips == 0


# --- Réimpression (note du PDF) ---------------------------------------------


class _BaseReimpression:
    """`payslips` et `employees` pour `reimprimer_bulletin`, et le stockage."""

    def __init__(self, *, retrait_en_echec: bool = False):
        self.journal: list = []
        self.storage = _Stockage(_Seau(self.journal, retrait_en_echec=retrait_en_echec))
        self.bulletin = {
            "id": "ps-1", "employee_id": EMP, "company_id": SOCIETE, "year": ANNEE, "month": MOIS,
            "payslip_data": {}, "pdf_notes": "Note", "pdf_storage_path": CHEMIN_HISTORIQUE,
        }

    def table(self, nom):
        base = self

        class _R:
            def select(self, *_a):
                return self

            def eq(self, *_a):
                if hasattr(self, "_valeurs"):
                    base.journal.append(("modifier", nom, self._valeurs))
                return self

            def maybe_single(self):
                return self

            def update(self, valeurs):
                self._valeurs = dict(valeurs)
                return self

            def execute(self):
                if hasattr(self, "_valeurs"):
                    return SimpleNamespace(data=[])
                if nom == "employees":
                    return SimpleNamespace(data={"employee_folder_name": "Salarie_Filet"})
                return SimpleNamespace(data=base.bulletin)

        return _R()


@pytest.fixture
def reimpression(monkeypatch, tmp_path):
    from app.modules.payroll.documents import payslip_editor
    from app.modules.payslips.application import impression

    def imprimer(**_k):
        fichier = tmp_path / "impression.pdf"
        fichier.write_bytes(b"%PDF-1.4 reimpression")
        return fichier

    monkeypatch.setattr(payslip_editor, "regenerate_pdf_from_data", imprimer)

    def avec(base):
        monkeypatch.setattr(impression, "supabase", base)
        return impression.reimprimer_bulletin("ps-1")

    return avec


class TestReimpression:
    def test_nouveau_chemin_ligne_a_jour_puis_ancien_retire(self, reimpression):
        base = _BaseReimpression()

        lien = reimpression(base)

        deposer, signer, modifier, retirer = base.journal
        nouveau = deposer[1]
        assert nouveau != CHEMIN_HISTORIQUE
        assert nouveau.startswith(f"{DOSSIER}/Bulletin_Salarie_Filet_09-2026_")
        assert signer == ("signer", nouveau)
        assert base.storage.seau.options_de_signature == [{"download": NOM_DU_PDF}]
        assert modifier == ("modifier", "payslips", {"pdf_storage_path": nouveau, "url": lien})
        assert retirer == ("retirer", [CHEMIN_HISTORIQUE])

    def test_un_retrait_en_echec_se_journalise(self, reimpression, caplog):
        base = _BaseReimpression(retrait_en_echec=True)

        with caplog.at_level(logging.WARNING):
            lien = reimpression(base)

        assert lien
        assert "PDF remplacé non retiré" in caplog.text


# --- Diagnostic du stockage ----------------------------------------------------


class TestDiagnosticDuStockage:
    """La route de diagnostic reconstruisait le chemin : elle doit lire celui du bulletin."""

    def _diagnostic(self, monkeypatch, chemin_en_place):
        from app.modules.payslips.infrastructure import readers

        class _Base:
            def table(self, nom):
                class _R:
                    def select(self, *_a):
                        return self

                    def eq(self, *_a):
                        return self

                    match = eq

                    def single(self):
                        return self

                    maybe_single = single

                    def execute(self):
                        if nom == "employees":
                            return SimpleNamespace(
                                data={"company_id": SOCIETE, "employee_folder_name": "Salarie_Filet"}
                            )
                        if chemin_en_place is None:
                            return None
                        return SimpleNamespace(data={"pdf_storage_path": chemin_en_place})

                return _R()

        urls: list[str] = []

        def get(url, headers=None):
            urls.append(url)
            return SimpleNamespace(json=lambda: {"ok": True})

        monkeypatch.setattr(readers, "supabase", _Base())
        monkeypatch.setattr(readers.requests, "get", get)
        readers.DebugStorageInfoProvider().get_debug_storage_info(EMP, ANNEE, MOIS)
        return urls[0]

    def test_lit_le_chemin_du_bulletin(self, monkeypatch):
        horodate = f"{DOSSIER}/Bulletin_Salarie_Filet_09-2026_20260930T183005123456.pdf"

        assert self._diagnostic(monkeypatch, horodate).endswith(f"/payslips/{horodate}")

    def test_sans_bulletin_le_chemin_d_avant(self, monkeypatch):
        assert self._diagnostic(monkeypatch, None).endswith(f"/payslips/{CHEMIN_HISTORIQUE}")
