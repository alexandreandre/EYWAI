"""L'aperçu d'un signalement n'écrit rien : ni historique, ni fichier, ni base.

Toute écriture lève : les fonctions de rangement du service, et, sous elles,
chaque écriture du client Supabase (insert, update, upsert, delete, dépôt de
fichier). Données fictives uniquement.
"""

from contextlib import ExitStack
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest import SyncRequestBuilder
from storage3._sync.file_api import SyncBucketActionsMixin

from app.modules.exports.application import signalements as service

MODULE = "app.modules.exports.application.signalements"
NIR = "1900101234567"
FICHIER = "\r\n".join([
    "S10.G00.00.001,'Martine'",
    "S10.G00.00.005,'02'",
    "S20.G00.05.001,'04'",
    "S21.G00.30.001,'1900101234567'",
    "S21.G00.30.002,'DUPONT'",
    "S21.G00.60.001,'01'",
    "S21.G00.60.002,'04102026'",
    "S21.G00.60.003,'09102026'",
    "S21.G00.60.004,'02'",
    "S90.G00.90.001,'10'",
    "S90.G00.90.002,'1'",
]) + "\r\n"


class EcritureInterdite(AssertionError):
    pass


def _interdit(*_args, **_kwargs):
    raise EcritureInterdite("l'aperçu a tenté d'écrire")


def _arret(du, au, saisi):
    jours = [date.fromordinal(o).isoformat() for o in range(du.toordinal(), au.toordinal() + 1)]
    return {"employee_id": "e1", "type": "arret_maladie", "selected_days": jours,
            "subrogation_active": False, "arret_type": None, "created_at": f"{saisi}T09:00:00+00:00"}


@pytest.fixture
def piege():
    """Chaque écriture possible lève ; les lectures du service sont simulées."""
    with ExitStack() as pile:
        for nom in ("insert", "update", "upsert", "delete"):
            pile.enter_context(patch.object(SyncRequestBuilder, nom, _interdit))
        for nom in ("upload", "update", "remove", "move"):
            pile.enter_context(patch.object(SyncBucketActionsMixin, nom, _interdit))
        for cible in ("upload_export_file", "create_signed_url", "commands.record_export_history",
                      "_ranger"):
            pile.enter_context(patch(f"{MODULE}.{cible}", side_effect=_interdit))
        pile.enter_context(patch(f"{MODULE}._arrets", return_value=[
            _arret(date(2026, 10, 5), date(2026, 10, 9), "2026-10-06")]))
        pile.enter_context(patch(f"{MODULE}._envoyes", return_value=[]))
        pile.enter_context(patch(f"{MODULE}._depuis", return_value=date(2026, 10, 1)))
        pile.enter_context(patch(f"{MODULE}._effectif", return_value=20))
        pile.enter_context(patch(f"{MODULE}._noms", return_value={"e1": "J. D."}))
        pile.enter_context(patch(f"{MODULE}._sorties", return_value=[]))
        pile.enter_context(patch(f"{MODULE}._contrats", return_value=[]))
        pile.enter_context(patch(f"{MODULE}._bulletins", return_value=set()))
        yield pile


def test_le_piege_leve_bien_sur_une_ecriture(piege):
    from app.core.database import supabase

    with pytest.raises(EcritureInterdite):
        supabase.table("exports_history").insert({"x": 1})
    with pytest.raises(EcritureInterdite):
        supabase.storage.from_("exports").upload("a.dsn", b"x")
    # La génération, elle, range le fichier : le piège l'arrête.
    with patch(f"{MODULE}._fichier", return_value=FICHIER), pytest.raises(EcritureInterdite):
        service.generer("c1", "u1", employee_id="e1", nature="04", debut="2026-10-05", essai=True)


def test_l_apercu_rend_les_blocs_et_le_brut_sans_rien_ecrire(piege):
    with patch(f"{MODULE}._fichier", return_value=FICHIER) as fichier:
        resultat = service.apercu("c1", employee_id="e1", nature="04", debut="2026-10-05")
    # Le fichier réel (pas l'essai) : celui qui serait déposé.
    assert fichier.call_args.args[2] is False
    assert resultat["nature"] == "04" and resultat["essai"] is False
    assert resultat["a_deposer_avant"] == "2026-10-11"
    codes = [b["code"] for b in resultat["blocs"]]
    assert codes == ["S10.G00.00", "S20.G00.05", "S21.G00.30", "S21.G00.60", "S90.G00.90"]
    assert resultat["brut"] == FICHIER.replace(NIR, "19•••••••••67")
    assert NIR not in str(resultat)


def test_l_apercu_d_un_signalement_qui_n_est_plus_a_faire_est_refuse(piege):
    with pytest.raises(ValueError, match="plus à faire"):
        service.apercu("c1", employee_id="e1", nature="04", debut="2026-10-04")


def test_l_apercu_de_la_fin_de_contrat_n_ecrit_rien(piege):
    mensuelle = "\r\n".join([
        "S20.G00.05.001,'01'", "S21.G00.30.001,'1900101234567'", "S21.G00.50.001,'30112026'",
        "S21.G00.62.001,'06112026'", "S21.G00.62.002,'031'",
    ]) + "\r\n"
    with patch(f"{MODULE}._sorties", return_value=[{"employee_id": "e2", "exit_type": "fin_cdd",
                                                     "last_working_day": "2026-11-06",
                                                     "status": "validee"}]), \
         patch(f"{MODULE}._bulletins", return_value={("e2", 2026, 11)}), \
         patch(f"{MODULE}.generate_dsn_file", return_value=mensuelle.encode("iso-8859-15")) as dsn:
        resultat = service.apercu("c1", employee_id="e2", nature="07", debut="2026-11-06",
                                  aujourd_hui=date(2026, 11, 9))
    assert dsn.call_args.kwargs["essai"] is False
    assert resultat["nature"] == "07"
    motif = next(r for b in resultat["blocs"] for r in b["rubriques"] if r["code"] == "S21.G00.62.002")
    assert motif["traduction"] == "fin de contrat à durée déterminée ou fin d'accueil occasionnel"
    assert NIR not in resultat["brut"]


def _client():
    from app.core.security import get_current_user
    from app.modules.exports.api.dependencies import get_active_company_id
    from app.modules.exports.api.router import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id="u1")
    app.dependency_overrides[get_active_company_id] = lambda: "c1"
    return TestClient(app)


def test_la_route_d_apercu_rend_les_blocs_et_le_brut_sans_rien_ecrire(piege):
    with patch(f"{MODULE}._fichier", return_value=FICHIER), \
         patch("app.modules.exports.api.router._require_exports_company_access"):
        reponse = _client().get("/api/exports/dsn-signalements/apercu",
                                params={"employee_id": "e1", "nature": "04", "debut": "2026-10-05"})
    assert reponse.status_code == 200
    corps = reponse.json()
    arret = next(b for b in corps["blocs"] if b["code"] == "S21.G00.60")
    assert arret["partie"] == "evenement" and arret["libelle"] == "Arrêt de travail"
    assert arret["rubriques"][0] == {"code": "S21.G00.60.001", "libelle": "Motif de l'arrêt",
                                     "valeur": "01", "traduction": "maladie"}
    assert "S21.G00.30.001,'19•••••••••67'" in corps["brut"]
    assert NIR not in reponse.text


def test_la_route_dit_pourquoi_l_apercu_est_impossible(piege):
    with patch("app.modules.exports.api.router._require_exports_company_access"):
        reponse = _client().get("/api/exports/dsn-signalements/apercu",
                                params={"employee_id": "e1", "nature": "04", "debut": "2026-10-04"})
    assert reponse.status_code == 400
    assert "plus à faire" in reponse.json()["detail"]
