"""
Aucune route ne gèle le backend.

Un handler FastAPI déclaré `async def` s'exécute SUR la boucle d'événements.
Tout le backend parle à Supabase en HTTP **synchrone** : un handler `async`
qui fait ce travail bloque le processus entier pour toute sa durée — plus
aucune requête, d'aucun utilisateur, n'est servie pendant ce temps.

Mesuré le 24/08/2026 avant correction : l'export « provision des congés
payés » prenait 141 s sur Cartol et 128 s sur Mont Blanc Composite, et la
génération double la collecte. Le backend était donc indisponible plusieurs
minutes d'affilée à chaque export. 359 des 386 routes étaient dans ce cas.

Déclaré `def`, le même handler est exécuté dans un pool de threads et la
boucle reste libre. Ce test interdit le retour en arrière : une route ne peut
être `async` que si elle attend réellement quelque chose.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

# Import au chargement du module, comme test_routes_authentifiees.py : importer
# l'application depuis une fixture la récupérerait APRÈS que d'autres tests ont
# pu remplacer `app.main` dans sys.modules, et on inspecterait alors une
# application vide sans le voir. C'est exactement ce qui est arrivé le 24/08 —
# vert en local, rouge en CI, où l'ordre des tests diffère.
from app.main import app

RACINE_APP = Path(__file__).resolve().parents[3] / "app"

# Un décorateur de route est un appel `<quelque_chose>.<verbe_http>(...)`. Le nom
# varie d'un module à l'autre — `router`, `router_rh`, `chat_router`, `app` — et
# se limiter à « router. » raterait les sous-routeurs, qui sont nombreux.
DECORATEUR_DE_ROUTE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_.]*\.(get|post|put|patch|delete|head|options)\("
)


def _handlers_async_sans_await() -> list[str]:
    """Routes déclarées `async def` dont le corps n'attend rien."""
    fautives: list[str] = []
    for fichier in sorted(RACINE_APP.rglob("*.py")):
        try:
            arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - fichier non parsable
            continue
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.AsyncFunctionDef):
                continue
            decorateurs = [ast.unparse(d) for d in noeud.decorator_list]
            if not any(DECORATEUR_DE_ROUTE.match(d) for d in decorateurs):
                continue
            # Un websocket DOIT rester asynchrone.
            if any("websocket" in d.lower() for d in decorateurs):
                continue
            attend = any(
                isinstance(x, (ast.Await, ast.AsyncFor, ast.AsyncWith))
                for x in ast.walk(noeud)
            )
            if not attend:
                chemin = fichier.relative_to(RACINE_APP.parent)
                fautives.append(f"{chemin}:{noeud.lineno} {noeud.name}")
    return fautives


class TestAucuneRouteNeGeleLeBackend:
    def test_aucune_route_async_sans_await(self):
        fautives = _handlers_async_sans_await()
        assert not fautives, (
            "Ces routes sont `async def` mais n'attendent rien : elles feront "
            "leur travail synchrone SUR la boucle d'événements et gèleront le "
            "backend pour tous les utilisateurs pendant ce temps. Retirer le "
            "mot-clé `async` — FastAPI les exécutera alors dans un pool de "
            "threads, à comportement identique.\n  "
            + "\n  ".join(fautives[:25])
            + (f"\n  … et {len(fautives) - 25} autres" if len(fautives) > 25 else "")
        )

    def test_le_detecteur_repere_bien_une_route_fautive(self):
        """Le test ci-dessus doit mordre : on lui soumet le motif interdit."""
        source = (
            "@router.get('/x')\n"
            "async def lire():\n"
            "    return service.lire()\n"
        )
        noeud = ast.parse(source).body[0]
        assert isinstance(noeud, ast.AsyncFunctionDef)
        attend = any(
            isinstance(x, (ast.Await, ast.AsyncFor, ast.AsyncWith))
            for x in ast.walk(noeud)
        )
        assert not attend, "le motif fautif doit être reconnu comme n'attendant rien"


def _routes_api() -> list:
    return [
        route
        for route in app.routes
        if getattr(route, "path", "").startswith("/api")
        and getattr(route, "endpoint", None) is not None
    ]


class TestApplicationReelle:
    """Contrôle sur l'application montée, pas seulement sur le texte du code."""

    def test_les_routes_sont_montees(self):
        """Sans ce contrôle, les gardes qui balaient `app.routes` passent à vide.

        C'est le cas de `test_routes_authentifiees` : il affirme qu'aucune route
        n'est publique en itérant `app.routes`, donc une application vide le
        rend vert sans rien vérifier.
        """
        routes_api = _routes_api()
        if len(routes_api) <= 200:
            import app.main as module_app

            toutes = list(app.routes)
            apercu = [
                f"{type(r).__name__} {getattr(r, 'path', '?')}" for r in toutes[:12]
            ]
            raise AssertionError(
                f"seulement {len(routes_api)} routes /api montées.\n"
                f"  app.main : {getattr(module_app, '__file__', '?')}\n"
                f"  routes totales sur l'application : {len(toutes)}\n"
                f"  échantillon : {apercu}"
            )

    def test_aucune_route_api_montee_n_est_une_coroutine_sans_await(self):
        """Une route asynchrone montée doit vraiment attendre quelque chose."""
        suspectes = []
        for route in _routes_api():
            fonction = route.endpoint
            if not inspect.iscoroutinefunction(fonction):
                continue
            try:
                source = inspect.getsource(fonction)
            except OSError:  # pragma: no cover - source indisponible
                continue
            corps = ast.parse(source.lstrip()).body[0]
            if not any(
                isinstance(x, (ast.Await, ast.AsyncFor, ast.AsyncWith))
                for x in ast.walk(corps)
            ):
                suspectes.append(f"{route.path} -> {fonction.__name__}")
        assert not suspectes, (
            "Routes montées en coroutine alors qu'elles n'attendent rien :\n  "
            + "\n  ".join(suspectes)
        )
