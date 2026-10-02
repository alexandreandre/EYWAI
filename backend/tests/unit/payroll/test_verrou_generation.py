"""Une seule génération de bulletin à la fois pour un salarié et un mois."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.modules.payroll.documents import verrou_generation
from app.modules.payroll.documents.verrou_generation import (
    GenerationDejaEnCours,
    verrou_de_generation,
)

RACINE = Path(__file__).resolve().parents[4]
MIGRATION = RACINE / "supabase/migrations/20260926140000_verrou_generation_bulletin.sql"


def _autre_requete(fonction):
    """Une autre requête HTTP a son propre contexte (Starlette le copie)."""
    import contextvars

    return contextvars.Context().run(fonction)


def test_une_seconde_generation_du_meme_bulletin_est_refusee(verrous_de_generation):
    def seconde():
        with verrou_de_generation("e1", 2026, 8):
            pass

    with verrou_de_generation("e1", 2026, 8):
        with pytest.raises(GenerationDejaEnCours):
            _autre_requete(seconde)
    # Rendu à la sortie : on peut régénérer ensuite.
    with verrou_de_generation("e1", 2026, 8):
        pass
    assert verrous_de_generation.tenus == {}


def test_deux_mois_ou_deux_salaries_ne_se_bloquent_pas():
    with verrou_de_generation("e1", 2026, 8):
        with verrou_de_generation("e1", 2026, 9):
            with verrou_de_generation("e2", 2026, 8):
                pass


def test_le_verrou_est_rendu_meme_si_la_generation_echoue(verrous_de_generation):
    with pytest.raises(RuntimeError):
        with verrou_de_generation("e1", 2026, 8):
            raise RuntimeError("moteur en échec")
    assert verrous_de_generation.tenus == {}


def test_base_indisponible_la_paie_continue_sans_verrou(monkeypatch):
    appels = []

    def en_panne(nom, params):
        appels.append(nom)
        raise ConnectionError("base injoignable")

    monkeypatch.setattr(verrou_generation, "_rpc", en_panne)
    passe = False
    with verrou_de_generation("e1", 2026, 8):
        passe = True
    assert passe
    # Rien à rendre : le verrou n'a jamais été pris.
    assert appels == ["prendre_verrou_generation_bulletin"]


def test_le_refus_devient_un_409_lisible():
    from app.modules.payslips.api.router import _map_app_errors

    with pytest.raises(HTTPException) as exc:
        _map_app_errors(GenerationDejaEnCours())
    assert exc.value.status_code == 409
    # Une phrase : l'écran de paie affiche un `detail` texte tel quel, et
    # réserve le 409 structuré au bulletin déjà validé.
    assert isinstance(exc.value.detail, str)
    assert "déjà en cours" in exc.value.detail


def test_generate_payslip_prend_le_verrou(monkeypatch, verrous_de_generation):
    from app.modules.payslips.application import commands
    from app.modules.payslips.application.dto import GeneratePayslipInput

    vus = []

    def sous_verrou(cmd, employee):
        vus.append(dict(verrous_de_generation.tenus))
        return "fait"

    monkeypatch.setattr(commands._employee_repository, "get_by_id_only", lambda _id: {"id": "e1"})
    monkeypatch.setattr(commands, "enrich_employee_with_exit_context", lambda e: e)
    monkeypatch.setattr(commands, "_raison_de_blocage_du_salarie", lambda *a: None)
    monkeypatch.setattr(commands, "payslip_employment_period_block_reason", lambda *a: None)
    monkeypatch.setattr(commands, "raison_de_blocage_avant_bascule", lambda *a: None)
    monkeypatch.setattr(commands, "_generer_sous_verrou", sous_verrou)

    cmd = GeneratePayslipInput(employee_id="e1", year=2026, month=8)
    assert commands.generate_payslip(cmd) == "fait"
    assert [list(v) for v in vus] == [[("e1", 2026, 8)]]
    assert verrous_de_generation.tenus == {}

    with verrou_de_generation("e1", 2026, 8):
        with pytest.raises(GenerationDejaEnCours):
            _autre_requete(lambda: commands.generate_payslip(cmd))


def test_la_regeneration_ijss_passe_par_le_meme_verrou():
    source = (
        RACINE / "backend/app/modules/ijss_tracking/application/apply_to_payslip.py"
    ).read_text(encoding="utf-8")
    debut = source.index("with verrou_de_generation(employee_id, year, month):")
    assert source.index("process_payslip_generation(", debut) > debut
    assert source.index("_archive_before_regeneration(\n", debut) > debut


def test_la_migration_ferme_la_table_et_les_fonctions_au_public():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "enable row level security" in sql
    assert "revoke all on table public.payslip_generation_locks from anon, authenticated" in sql
    for fonction in ("prendre_verrou_generation_bulletin", "rendre_verrou_generation_bulletin"):
        assert f"revoke all on function public.{fonction}(" in sql
        assert sql.count(f"grant execute on function public.{fonction}(") == 1
    assert "to service_role" in sql
    assert " to anon" not in sql and " to authenticated" not in sql


# --- Réentrant dans la même requête (correction puis régénération) ---


def test_le_meme_contexte_reprend_le_verrou_qu_il_tient_deja(verrous_de_generation):
    from app.modules.payroll.documents.verrou_generation import verrou_de_generation

    with verrou_de_generation("e1", 2026, 8):
        with verrou_de_generation("e1", 2026, 8):
            assert ("e1", 2026, 8) in verrous_de_generation.tenus
        # Le bloc intérieur ne rend pas le verrou de l'extérieur.
        assert ("e1", 2026, 8) in verrous_de_generation.tenus
    assert not verrous_de_generation.tenus
    assert verrous_de_generation.appels.count("prendre_verrou_generation_bulletin") == 1


def test_un_autre_contexte_reste_refuse(verrous_de_generation):
    import contextvars

    from app.modules.payroll.documents.verrou_generation import (
        GenerationDejaEnCours,
        verrou_de_generation,
    )

    def autre_requete():
        with verrou_de_generation("e1", 2026, 8):
            pass

    with verrou_de_generation("e1", 2026, 8):
        with pytest.raises(GenerationDejaEnCours):
            contextvars.Context().run(autre_requete)


def test_un_autre_mois_se_prend_normalement(verrous_de_generation):
    from app.modules.payroll.documents.verrou_generation import verrou_de_generation

    with verrou_de_generation("e1", 2026, 8):
        with verrou_de_generation("e1", 2026, 9):
            assert len(verrous_de_generation.tenus) == 2


def test_un_verrou_abandonne_ne_bloque_que_cinq_minutes():
    """Une génération coupée net (instance arrêtée) ne rend pas son verrou :
    il bloquait 15 minutes avec « réessayez dans quelques instants » (recette
    du 02/10/2026). Un bulletin se calcule en une quinzaine de secondes."""
    assert verrou_generation.DUREE_SECONDES == 300
    message = str(GenerationDejaEnCours())
    assert "déjà en cours" in message
    assert "5 minutes" in message
