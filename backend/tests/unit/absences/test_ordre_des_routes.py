"""PATCH /{request_id} prenait « /leave-settings » pour un identifiant : l'enregistrement répondait 422."""
from app.modules.absences.api.router import router


def _chemins_patch():
    return [r.path for r in router.routes if "PATCH" in getattr(r, "methods", set())]


def test_les_reglages_passent_avant_la_route_generique():
    chemins = _chemins_patch()
    generique = next(i for i, p in enumerate(chemins) if p.endswith("/{request_id}") and "requests" not in p)
    for reglage in ("/leave-settings", "/cp-seniority-settings"):
        assert any(p.endswith(reglage) for p in chemins[:generique]), reglage
    assert generique == len(chemins) - 1
