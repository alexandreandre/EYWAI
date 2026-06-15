"""Utilitaires pour parcourir les routes FastAPI (routers imbriqués)."""

from __future__ import annotations

from typing import Any, Iterable, List


def _collect_paths_from_routes(routes: Iterable[Any], *, prefix: str = "") -> List[str]:
    paths: List[str] = []
    for route in routes:
        segment = getattr(route, "path", None)
        nested = getattr(route, "routes", None)

        if isinstance(segment, str):
            full = prefix + segment
            paths.append(full)
            if nested:
                paths.extend(_collect_paths_from_routes(nested, prefix=full))
        elif nested:
            paths.extend(_collect_paths_from_routes(nested, prefix=prefix))
    return paths


def collect_app_route_paths(app: Any) -> List[str]:
    """Retourne tous les chemins enregistrés, y compris sous routers inclus."""
    return _collect_paths_from_routes(getattr(app, "routes", []))
