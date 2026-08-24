"""
Garde structurelle : aucune route de DONNÉES ne doit être publique.

Audit du 22/08/2026 : 10 routes montées sans aucune dépendance d'auth
exposaient en anonyme, sur la PROD, les saisies de paie de toutes les
sociétés (lecture ET écriture) et les historiques d'absences (arrêts
maladie, URLs signées des justificatifs). Le client Supabase du backend
tourne en service_role : une route sans garde contourne la RLS et tout
cloisonnement société.

Ce test inspecte l'application RÉELLE (app.main.app) et échoue dès qu'une
route /api sort de la liste blanche sans dépendance d'authentification —
y compris une route ajoutée demain.
"""

from __future__ import annotations

from typing import Set

from app.main import app

# Noms de dépendances qui valent authentification.
DEPENDANCES_AUTH = (
    "get_current_user",
    "require_",
    "verify_super_admin",
    "get_badgeuse_terminal_context",  # jeton terminal + rate limit dédiés
)

# Routes publiques par CONCEPTION, chacune justifiée.
ROUTES_PUBLIQUES_ASSUMEES = {
    # Authentification : ne peuvent pas exiger un jeton pour en délivrer un.
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/refresh"),
    ("POST", "/api/auth/request-password-reset"),
    ("POST", "/api/auth/reset-password"),
    ("POST", "/api/auth/verify-reset-token"),
    # Activation : le jeton d'invitation EST l'authentification (usage
    # unique, 7 jours, empreinte seule en base).
    ("POST", "/api/activation/verify"),
    ("POST", "/api/activation/complete"),
    # Environnement de test : 403 en dehors de APP_ENV=test.
    ("GET", "/api/test-env/status"),
    ("POST", "/api/test-env/refresh"),
}


def _routes_terminales() -> list:
    """Toutes les routes, sous-routeurs dépliés.

    Selon la version de FastAPI — non épinglée dans requirements.txt —
    `app.routes` contient les routes à plat, ou un objet par `include_router`.
    Le 24/08/2026 la CI installait une version qui n'aplatit pas : ce test y
    voyait SIX routes au lieu de plusieurs centaines et passait donc à vide,
    sans rien vérifier, depuis sa création. Même parcours que dans
    `test_routes_ne_bloquent_pas.py`.
    """
    terminales = []
    a_visiter = list(getattr(app, "routes", []) or [])
    vus = set()
    while a_visiter:
        route = a_visiter.pop()
        if id(route) in vus:
            continue
        vus.add(id(route))
        directes = getattr(route, "routes", None)
        if not directes:
            # FastAPI 0.141 expose `original_router` sur son `_IncludedRouter` ;
            # les versions antérieures aplatissaient. Un `Mount` porte `app`.
            for attribut in ("original_router", "router", "app"):
                porteur = getattr(route, attribut, None)
                directes = getattr(porteur, "routes", None)
                if directes:
                    break
        if directes:
            a_visiter.extend(directes)
            continue
        terminales.append(route)
    return terminales


def _dependances(route) -> Set[str]:
    noms: Set[str] = set()
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return noms
    pile = list(dependant.dependencies)
    while pile:
        courant = pile.pop()
        appel = getattr(courant, "call", None)
        if appel is not None:
            noms.add(getattr(appel, "__name__", str(appel)))
        pile.extend(getattr(courant, "dependencies", []) or [])
    return noms


def test_le_balayage_voit_bien_les_routes():
    """Sans ce contrôle, le test suivant passe à vide et n'assure plus rien."""
    routes_api = [
        r for r in _routes_terminales()
        if getattr(r, "path", "").startswith("/api")
    ]
    assert len(routes_api) > 200, (
        f"seulement {len(routes_api)} routes /api balayées — la garde "
        "ci-dessous serait verte sans rien vérifier."
    )


def test_aucune_route_de_donnees_sans_authentification():
    non_gardees = set()
    for route in _routes_terminales():
        chemin = getattr(route, "path", "")
        if not chemin.startswith("/api"):
            continue
        noms = _dependances(route)
        if any(any(garde in nom for garde in DEPENDANCES_AUTH) for nom in noms):
            continue
        for methode in getattr(route, "methods", set()) or set():
            if methode == "OPTIONS":
                continue
            if (methode, chemin) not in ROUTES_PUBLIQUES_ASSUMEES:
                non_gardees.add((methode, chemin))

    assert not non_gardees, (
        "Routes /api sans authentification (ajoutez une dépendance d'auth, ou "
        "inscrivez-les dans ROUTES_PUBLIQUES_ASSUMEES avec leur justification) :\n"
        + "\n".join(f"  {m} {c}" for m, c in sorted(non_gardees))
    )


def test_la_liste_blanche_ne_contient_pas_de_route_de_donnees():
    """Filet anti-contournement : la liste blanche ne doit jamais accueillir
    une route qui manipule des données métier."""
    prefixes_metier = (
        "/api/monthly-inputs",
        "/api/employees",
        "/api/payslips",
        "/api/absences",
        "/api/salaries",
        "/api/documents",
        "/api/schedules",
        "/api/primes-catalogue",
        "/api/saisies-avances",
        "/api/dsn",
    )
    fautives = [
        (m, c)
        for (m, c) in ROUTES_PUBLIQUES_ASSUMEES
        if c.startswith(prefixes_metier)
    ]
    assert not fautives, f"Routes métier dans la liste blanche : {fautives}"
