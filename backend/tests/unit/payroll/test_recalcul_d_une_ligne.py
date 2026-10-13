"""« Recalculer » une ligne de bulletin : moins d'allers-retours, mêmes résultats. [lot 43]

Rejeu final C3 (13/10/2026) : un « Recalculer » de ligne mettait une trentaine de
secondes. Mesure locale, à chaud (`scratchpad/lot43/mesure_generation_complete.py`,
écritures avalées) : la génération fait environ 95 lectures et 29 écritures, une
à une ; le processeur ne compte que pour 1 à 4 s. Le temps part en allers-retours
vers la base :

- 22 lectures sont des doublons exacts (la fiche, la société, les périodes des
  variables, les réglages de modulation, de maintien, d'ancienneté…), dont 15
  sans aucune écriture entre les deux ;
- les crédits de repos compensateur de l'année s'écrivent en 12 requêtes, une
  par mois ;
- le PDF est imprimé deux fois : par le moteur, puis après l'enrichissement
  (avances, saisies, prêts), même quand celui-ci ne change rien.

Corrections, sans changer un seul résultat :

- pendant la génération, une même lecture ne part qu'une fois tant que rien
  n'a été écrit ; toute écriture part et vide la mémoire ;
- les 12 crédits de l'année partent en une écriture ;
- le PDF n'est réimprimé que si le bulletin à imprimer a changé (même HTML,
  même document : le premier est déjà déposé au même chemin).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.core.lecture_seule import (
    ClientHttpSupabase,
    EcritureEnLectureSeule,
    ecritures_permises,
    lecture_seule,
    lectures_partagees,
)

pytestmark = pytest.mark.unit

URL = "https://base.test/rest/v1/employees?select=%2A&id=eq.emp"
URL_ECRITURE = "https://base.test/rest/v1/payslips?id=eq.p1"


class _Base:
    def __init__(self):
        self.recues: list[tuple[str, str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.recues.append((request.method, str(request.url)))
        return httpx.Response(200, content=json.dumps([{"lecture": len(self.recues)}]).encode())


def _client(base: _Base) -> ClientHttpSupabase:
    return ClientHttpSupabase(transport=httpx.MockTransport(base))


# --- Lectures partagées le temps d'une génération -------------------------------


class TestLecturesPartagees:
    def test_une_meme_lecture_ne_part_qu_une_fois(self):
        base = _Base()
        client = _client(base)

        with lectures_partagees():
            premiere = client.get(URL)
            seconde = client.get(URL)

        assert len(base.recues) == 1
        assert premiere.json() == seconde.json() == [{"lecture": 1}]

    def test_une_ecriture_part_et_les_lectures_suivantes_repartent(self):
        base = _Base()
        client = _client(base)

        with lectures_partagees():
            client.get(URL)
            client.patch(URL_ECRITURE, json={"status": "brouillon"})
            apres = client.get(URL)

        assert [m for m, _ in base.recues] == ["GET", "PATCH", "GET"]
        assert apres.json() == [{"lecture": 3}]

    def test_les_ecritures_sont_permises(self):
        with lectures_partagees():
            assert ecritures_permises() is True

    def test_hors_du_bloc_chaque_lecture_part(self):
        base = _Base()
        client = _client(base)

        with lectures_partagees():
            client.get(URL)
        client.get(URL)

        assert len(base.recues) == 2

    def test_la_lecture_seule_garde_la_main_dans_le_bloc(self):
        base = _Base()
        client = _client(base)

        with lectures_partagees(), lecture_seule():
            with pytest.raises(EcritureEnLectureSeule):
                client.patch(URL_ECRITURE, json={})

        assert base.recues == []


def test_la_generation_d_un_bulletin_partage_ses_lectures(monkeypatch):
    from app.core import lecture_seule as module
    from app.modules.payslips.application import commands
    from app.modules.payslips.application.dto import GeneratePayslipInput

    vues: list[bool] = []

    def _noter(*_a, **_k):
        vues.append(module.lectures_partagees_en_cours() is not None)
        return {"id": "e1", "company_id": "c1"}

    monkeypatch.setattr(commands, "salarie_generable", _noter)
    monkeypatch.setattr(commands, "_generer_sous_verrou", lambda *_a, **_k: _noter())

    class _Verrou:
        def __enter__(self):
            return None

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(commands, "verrou_de_generation", lambda *_a, **_k: _Verrou())

    commands.generate_payslip(GeneratePayslipInput(employee_id="e1", year=2026, month=9))

    assert vues == [True, True]
    assert module.lectures_partagees_en_cours() is None


# --- Crédits de repos compensateur : une écriture pour l'année --------------------


def test_les_credits_de_l_annee_partent_en_une_ecriture():
    from app.modules.repos_compensateur.application import service
    from app.modules.repos_compensateur.domain.contingent_rules import ContingentSettings

    ecritures: list[list] = []
    reglages = ContingentSettings(
        legal_cor_contingent_hours=220.0, management_contingent_hours=360.0, hours_per_rest_day=7.0
    )
    bulletins = {6: {"calcul_du_brut": [{"libelle": "Heures suppl", "quantite": 230.0}]}}
    with (
        patch.object(service, "get_contingent_settings", return_value=reglages),
        patch.object(service, "get_company_effectif", return_value=25),
        patch.object(service, "get_bulletins_par_mois_par_employe", return_value={"emp-1": bulletins}),
        patch.object(service, "upsert_credits", side_effect=lambda c: ecritures.append(list(c)) or True),
        patch.object(service, "upsert_credit", side_effect=AssertionError("une écriture par mois")),
    ):
        nombre = service.recalculer_credits_repos_employe("emp-1", "comp-1", 2026)

    assert nombre == 12
    assert len(ecritures) == 1
    assert [c.month for c in ecritures[0]] == list(range(1, 13))
    juin = ecritures[0][5]
    assert (juin.heures, juin.source, juin.year) == (10.0, "cor", 2026)


def test_l_ecriture_groupee_des_credits_porte_les_memes_lignes(monkeypatch):
    from app.modules.repos_compensateur.domain.entities import ReposCredit
    from app.modules.repos_compensateur.infrastructure import repository

    envois: list = []

    class _Table:
        def upsert(self, lignes, on_conflict=None):
            envois.append((lignes, on_conflict))
            return self

        def execute(self):
            return None

    class _Client:
        def table(self, nom):
            assert nom == "repos_compensateur_credits"
            return _Table()

    monkeypatch.setattr(repository, "supabase", _Client())
    credits = [
        ReposCredit(employee_id="e", company_id="c", year=2026, month=m, source="cor", heures=0.0, jours=0.0)
        for m in (1, 2)
    ]

    assert repository.upsert_credits(credits) is True
    assert envois == [
        ([repository.credit_to_row(c) for c in credits], "employee_id,year,month,source")
    ]


# --- Le PDF n'est réimprimé que s'il a changé ---------------------------------


class TestPdfReimprimeSeulementS_ilChange:
    def test_l_impression_du_moteur_garde_le_html_imprime(self, tmp_path, monkeypatch):
        from app.modules.payroll.documents import pdf_du_bulletin as pdf

        rendus: list = []

        class _Html:
            def __init__(self, string, base_url=None):
                self.string = string

            def write_pdf(self, chemin):
                rendus.append(self.string)
                Path(chemin).write_bytes(b"%PDF")

        monkeypatch.setattr(pdf, "HTML", _Html)
        chemin = tmp_path / "bulletins" / "Bulletin_X_09-2026.pdf"
        chemin.parent.mkdir()

        pdf.imprimer_le_bulletin("<html>bulletin</html>", chemin, base_url="/moteur")

        assert rendus == ["<html>bulletin</html>"]
        assert chemin.read_bytes() == b"%PDF"
        assert pdf.html_imprime(chemin) == "<html>bulletin</html>"
        assert pdf.html_imprime(tmp_path / "absent.pdf") is None

    def test_meme_html_rien_n_est_reimprime_ni_redepose(self, monkeypatch):
        from app.modules.employee_loans.application import payroll_integration as pi
        from app.modules.payroll.documents import payslip_editor as editeur

        rendus: list = []
        monkeypatch.setattr(editeur, "html_du_bulletin_a_imprimer", lambda *_a, **_k: "<html>A</html>")
        monkeypatch.setattr(editeur, "HTML", lambda **k: rendus.append(k) or pytest.fail("réimprimé"))
        monkeypatch.setattr(pi, "supabase", _StockageInterdit())

        pi._regenerate_and_upload_pdf({}, _config(html_imprime="<html>A</html>"))

        assert rendus == []

    def test_html_change_le_pdf_est_reimprime_et_redepose(self, tmp_path, monkeypatch):
        from app.modules.employee_loans.application import payroll_integration as pi
        from app.modules.payroll.documents import payslip_editor as editeur

        rendus: list = []

        class _Html:
            def __init__(self, string):
                self.string = string

            def write_pdf(self, chemin):
                rendus.append(self.string)
                Path(chemin).write_bytes(b"%PDF-B")

        depots: list = []
        monkeypatch.setattr(editeur, "html_du_bulletin_a_imprimer", lambda *_a, **_k: "<html>B</html>")
        monkeypatch.setattr(editeur, "HTML", _Html)
        monkeypatch.setattr(editeur, "payroll_engine_employee_bulletins", lambda *_a: tmp_path)
        monkeypatch.setattr(pi, "supabase", _StockageQuiNote(depots))

        pi._regenerate_and_upload_pdf({}, _config(html_imprime="<html>A</html>"))

        assert rendus == ["<html>B</html>"]
        assert depots == [("societe/emp/bulletins/Bulletin_X_20260930.pdf", b"%PDF-B")]

    def test_sans_html_imprime_le_pdf_est_reimprime_comme_avant(self, tmp_path, monkeypatch):
        from app.modules.employee_loans.application import payroll_integration as pi
        from app.modules.payroll.documents import payslip_editor as editeur

        class _Html:
            def __init__(self, string):
                self.string = string

            def write_pdf(self, chemin):
                Path(chemin).write_bytes(b"%PDF-A")

        depots: list = []
        monkeypatch.setattr(editeur, "html_du_bulletin_a_imprimer", lambda *_a, **_k: "<html>A</html>")
        monkeypatch.setattr(editeur, "HTML", _Html)
        monkeypatch.setattr(editeur, "payroll_engine_employee_bulletins", lambda *_a: tmp_path)
        monkeypatch.setattr(pi, "supabase", _StockageQuiNote(depots))

        pi._regenerate_and_upload_pdf({}, _config(html_imprime=None))

        assert depots == [("societe/emp/bulletins/Bulletin_X_20260930.pdf", b"%PDF-A")]

    @pytest.mark.parametrize(
        "module",
        [
            "app.modules.payroll.documents.payslip_run_heures",
            "app.modules.payroll.documents.payslip_run_forfait",
        ],
    )
    def test_le_moteur_imprime_en_gardant_son_html(self, module):
        import importlib

        source = inspect.getsource(importlib.import_module(module))
        assert "imprimer_le_bulletin(html_genere, pdf_filename" in source
        assert ".write_pdf(pdf_filename)" not in source

    @pytest.mark.parametrize(
        "module",
        [
            "app.modules.payroll.documents.payslip_generator",
            "app.modules.payroll.documents.payslip_generator_forfait",
        ],
    )
    def test_le_generateur_passe_le_html_imprime_a_l_enrichissement(self, module):
        import importlib

        source = inspect.getsource(importlib.import_module(module))
        assert "html_imprime=html_imprime(local_pdf_path)" in source


def _config(*, html_imprime):
    from app.modules.employee_loans.application.payroll_integration import PdfRegenConfig

    return PdfRegenConfig(
        employee_id="emp",
        employee_folder_name="X",
        company_id="societe",
        month=9,
        year=2026,
        storage_path="societe/emp/bulletins/Bulletin_X_20260930.pdf",
        html_imprime=html_imprime,
    )


class _StockageInterdit:
    @property
    def storage(self):
        raise AssertionError("dépôt d'un PDF identique")


class _StockageQuiNote:
    def __init__(self, depots: list):
        self.depots = depots

    @property
    def storage(self):
        depots = self.depots

        class _Seau:
            def upload(self, path, file, file_options=None):
                depots.append((path, file))

        class _Stockage:
            def from_(self, _bucket):
                return _Seau()

        return _Stockage()
