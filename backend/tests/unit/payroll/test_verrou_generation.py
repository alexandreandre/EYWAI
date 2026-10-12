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
        appels.append((nom, params["p_jeton"]))
        raise ConnectionError("base injoignable")

    monkeypatch.setattr(verrou_generation, "_rpc", en_panne)
    passe = False
    with verrou_de_generation("e1", 2026, 8):
        passe = True
    assert passe
    # La réponse s'est perdue, pas forcément la prise : le verrou a pu être posé
    # en base. Il est rendu à la fin, avec le même jeton (sans effet s'il n'y
    # est pas). Avant, il restait posé 5 minutes.
    assert [nom for nom, _ in appels] == [
        "prendre_verrou_generation_bulletin",
        "rendre_verrou_generation_bulletin",
    ]
    assert appels[0][1] == appels[1][1]


def test_en_lecture_seule_rien_n_est_parti_rien_a_rendre(monkeypatch):
    from app.core.lecture_seule import EcritureEnLectureSeule

    appels = []

    def refuse(nom, params):
        appels.append(nom)
        raise EcritureEnLectureSeule("écriture refusée")

    monkeypatch.setattr(verrou_generation, "_rpc", refuse)
    with verrou_de_generation("e1", 2026, 8):
        pass
    assert appels == ["prendre_verrou_generation_bulletin"]


def test_le_verrou_vit_tant_que_la_generation_tourne(monkeypatch, verrous_de_generation):
    """Un processus arrêté net ne rend pas son verrou (instance tombée en pleine
    génération, 12/10/2026 : 42 s sans une requête, puis 409 pendant 5 minutes).
    Le verrou est donc court et prolongé tant que la génération tourne : mort
    avec elle, il libère le bulletin en une minute."""
    import time

    prolongations = []
    monkeypatch.setattr(verrou_generation, "INTERVALLE_PROLONGATION_SECONDES", 0.01)
    monkeypatch.setattr(
        verrou_generation, "_prolonger", lambda params: prolongations.append(params["p_jeton"])
    )
    with verrou_de_generation("e1", 2026, 8):
        time.sleep(0.1)
    assert prolongations, "le verrou n'a pas été prolongé pendant la génération"
    assert len(set(prolongations)) == 1
    apres = len(prolongations)
    time.sleep(0.05)
    assert len(prolongations) == apres, "le verrou est encore prolongé après la génération"
    assert verrous_de_generation.tenus == {}


def test_un_verrou_pris_ailleurs_n_est_pas_prolonge(monkeypatch, verrous_de_generation):
    prolongations = []
    monkeypatch.setattr(verrou_generation, "INTERVALLE_PROLONGATION_SECONDES", 0.01)
    monkeypatch.setattr(verrou_generation, "_prolonger", lambda params: prolongations.append(1))

    def en_panne(nom, params):
        raise ConnectionError("base injoignable")

    monkeypatch.setattr(verrou_generation, "_rpc", en_panne)
    import time

    with verrou_de_generation("e1", 2026, 8):
        time.sleep(0.05)
    assert prolongations == []


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
    """La saisie IJSS et le recalcul se font sous le verrou ; le recalcul est la
    génération normale, qui le reprend (réentrant)."""
    source = (
        RACINE / "backend/app/modules/ijss_tracking/application/apply_to_payslip.py"
    ).read_text(encoding="utf-8")
    debut = source.index("with verrou_de_generation(employee_id, year, month):")
    assert source.index("_ecrire_saisie_ijss(", debut) > debut
    assert source.index("generate_payslip(", debut) > debut
    assert "process_payslip_generation" not in source


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


def test_un_verrou_abandonne_ne_bloque_qu_une_minute():
    """Une génération coupée net (instance arrêtée) ne rend pas son verrou :
    il bloquait 15 minutes (recette du 02/10/2026), puis 5 minutes (relevé J.1
    du 12/10/2026). Prolongé tant que la génération vit, il peut être court ;
    une génération qui ne finit jamais ne le garde pas au-delà de la durée
    maximale d'une génération."""
    assert verrou_generation.DUREE_SECONDES == 60
    assert verrou_generation.INTERVALLE_PROLONGATION_SECONDES <= verrou_generation.DUREE_SECONDES / 3
    assert verrou_generation.PROLONGATION_MAX_SECONDES == 300
    message = str(GenerationDejaEnCours())
    assert "déjà en cours" in message
    assert "Réessayez dans une minute." in message
