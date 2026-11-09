"""
Cloisonnement entre sociétés, route par route (R-620, 09/11/2026).

Le client Supabase du backend tourne en service_role : la RLS ne protège
personne, c'est le code de chaque route qui borne à la société de l'appelant.
Cette garde parcourt les routes RÉELLES de l'application (`app.main.app`) et
contrôle trois choses, à la lecture du code seulement (aucune requête) :

1. toute route /api atteint une garde de société ou d'administration ;
2. un identifiant de société fourni par le client (query, chemin, corps,
   en-tête brut) passe d'abord par une garde qui reçoit CETTE valeur : les
   incidents du 09/11 venaient d'un en-tête ou d'un paramètre lu tel quel ;
3. un identifiant d'objet du chemin voyage avec la société, ou passe par une
   garde de périmètre, avant d'atteindre un service.

Limite : l'analyse lit des noms et ne peut pas prouver le filtre SQL d'un
dépôt. Elle sert de cliquet : une route nouvelle ou un paramètre nouveau sans
garde fait échouer le test, et chaque exception est inscrite ici avec sa raison.
"""

from __future__ import annotations

import ast
import inspect
import re
import textwrap
import types
from typing import Iterable

from pydantic import BaseModel

from app.main import app  # noqa: F401  (monte tous les routeurs)
from tests.unit.security.test_routes_authentifiees import (
    _dependances,
    _routes_terminales,
)

# ---------------------------------------------------------------------------
# Vocabulaire des gardes
# ---------------------------------------------------------------------------

GARDES = {
    "accessible_companies",
    "active_company_id",
    "assert_employee_in_company",
    "employee_belongs_to_company",
    "get_badgeuse_terminal_context",
    "get_role_in_company",
    "has_access_to_company",
    "has_rh_access_in_company",
    "is_admin_in_company",
    "is_group_admin",
    "is_platform_admin",
    "is_rh_in_company",
    "is_super_admin",
    "require_active_company",
    "require_employee_access",
    "require_employee_in_company",
    "require_rh_employee_in_company",
    "super_admin_auth_user_id",
    "verify_super_admin",
    "verify_super_admin_and_return_row",
    "verify_super_admin_or_company_access",
    "_verify_super_admin",
}

# Sous-ensemble qui confronte une valeur aux accès de l'appelant. Lire
# `active_company_id` n'en fait pas partie : `company_id or active_company_id`
# ne contrôle rien, c'était le défaut du repos compensateur.
GARDES_DE_VALEUR = {
    "assert_employee_in_company",
    "can_access_company_as_rh",
    "employee_belongs_to_company",
    "get_role_in_company",
    "has_access_to_company",
    "has_rh_access_in_company",
    "is_admin_in_company",
    "is_rh_in_company",
    "require_employee_access",
    "require_employee_in_company",
    "require_rh_employee_in_company",
}

# Appel qui, par son nom, contrôle la valeur qu'on lui passe.
_APPEL_GARDE = re.compile(
    r"has_\w*access|require|verify|ensure|check_|assert|is_admin_in|"
    r"get_role_in|is_rh|acces|perimetre|autoris"
)

_NOM_SOCIETE = re.compile(r"company_id|x_active_company|entreprise_id|societe_id")

# ---------------------------------------------------------------------------
# Exceptions assumées, chacune justifiée
# ---------------------------------------------------------------------------

ROUTES_SANS_SOCIETE = {
    # Publiques par conception (voir test_routes_authentifiees).
    ("POST", "/api/activation/complete"): "jeton d'invitation",
    ("POST", "/api/activation/verify"): "jeton d'invitation",
    ("GET", "/api/test-env/status"): "aucune donnée métier",
    # Rattachées au compte connecté, jamais à une société.
    ("POST", "/api/absences/get-upload-url"): "chemin bâti sur l'identifiant du compte",
    ("POST", "/api/client-errors"): "journal d'erreurs du navigateur",
    ("GET", "/api/users/me"): "profil du compte",
    ("GET", "/api/me/badgeuse/qr"): "compte connecté",
    ("GET", "/api/me/badgeuse/status-today"): "compte connecté",
    ("POST", "/api/me/badgeuse/toggle"): "compte connecté",
    ("GET", "/api/me/current-cumuls"): "compte connecté",
    # Référentiels communs à toutes les sociétés.
    ("GET", "/api/collective-agreements/catalog"): "catalogue commun",
    ("GET", "/api/collective-agreements/catalog/suggest"): "catalogue commun",
    ("GET", "/api/collective-agreements/catalog/{agreement_id}"): "catalogue commun",
    (
        "GET",
        "/api/collective-agreements/catalog/{agreement_id}/classifications",
    ): "catalogue commun",
    (
        "GET",
        "/api/collective-agreements/catalog/{agreement_id}/salary-minima",
    ): "catalogue commun",
    ("GET", "/api/maintenance-settings/baremes"): "barème légal",
    ("GET", "/api/pcs-ese/referentiel"): "nomenclature INSEE",
    # Calculs sur le seul fichier ou montant envoyé, sans lecture en base.
    ("POST", "/api/contract-parser/extract-from-pdf"): "fichier envoyé, rien en base",
    (
        "POST",
        "/api/contract-parser/extract-questionnaire-from-pdf",
    ): "fichier envoyé, rien en base",
    ("POST", "/api/contract-parser/extract-rib-from-pdf"): "fichier envoyé, rien en base",
    (
        "POST",
        "/api/saisies-avances/salary-seizures/calculate-seizable",
    ): "calcul sur le montant envoyé",
}

# Identifiant d'objet qui n'a pas besoin de la société : objet commun, ou
# garde placée juste après l'appel, ou propriété du compte.
OBJETS_SANS_SOCIETE = {
    ("GET", "/api/support/tickets/{ticket_id}"): "société du ticket comparée après lecture",
    ("GET", "/api/pas-rates/{employee_id}/historique"): "société du salarié comparée après lecture",
    ("GET", "/api/work-medals/employees/{employee_id}"): "société du dossier comparée après lecture",
    ("PUT", "/api/notifications/{notification_id}/read"): "bornée au salarié du compte",
    ("GET", "/api/company-groups/{group_id}/available-companies"): "super admin, sans le groupe",
    (
        "GET",
        "/api/competencies/employees/{employee_id}/mobility-analysis",
    ): "répond toujours 404",
    (
        "POST",
        "/api/collective-agreements/catalog/{agreement_id}/import-legifrance",
    ): "catalogue commun, super admin",
    ("GET", "/api/collective-agreements/catalog/{agreement_id}"): "catalogue commun",
    (
        "GET",
        "/api/collective-agreements/catalog/{agreement_id}/classifications",
    ): "catalogue commun",
    (
        "GET",
        "/api/collective-agreements/catalog/{agreement_id}/salary-minima",
    ): "catalogue commun",
    # Catalogue commun : le drapeau is_platform_admin est contrôlé dans la commande.
    ("DELETE", "/api/collective-agreements/catalog/{agreement_id}"): "super admin en commande",
    ("PATCH", "/api/collective-agreements/catalog/{agreement_id}"): "super admin en commande",
    (
        "GET",
        "/api/collective-agreements/catalog/{agreement_id}/training-recommendations",
    ): "super admin en commande",
    (
        "PATCH",
        "/api/collective-agreements/training-recommendations/{recommendation_id}",
    ): "super admin en commande",
    (
        "POST",
        "/api/collective-agreements/catalog/rules/rollback/{log_id}",
    ): "super admin en commande",
    (
        "POST",
        "/api/collective-agreements/catalog/{agreement_id}/extract-rules",
    ): "super admin en commande",
    (
        "POST",
        "/api/collective-agreements/catalog/{agreement_id}/extract-trainings",
    ): "super admin en commande",
}

# ---------------------------------------------------------------------------
# Parcours
# ---------------------------------------------------------------------------


def _routes_api() -> list:
    return [
        r for r in _routes_terminales() if getattr(r, "path", "").startswith("/api")
    ]


def _codes(code: types.CodeType) -> Iterable[types.CodeType]:
    yield code
    for constante in code.co_consts:
        if isinstance(constante, types.CodeType):
            yield from _codes(constante)


def _noms(fonction) -> set[str]:
    noms: set[str] = set()
    for code in _codes(fonction.__code__):
        noms |= set(code.co_names)
    return noms


def _fonctions_de(objet) -> Iterable:
    if inspect.isclass(objet):
        for valeur in vars(objet).values():
            if isinstance(valeur, (staticmethod, classmethod)):
                valeur = valeur.__func__
            elif isinstance(valeur, property):
                valeur = valeur.fget
            if inspect.isfunction(valeur):
                yield valeur
    elif inspect.isfunction(objet):
        yield objet


def _dans_l_application(objet) -> bool:
    return (getattr(objet, "__module__", None) or "").startswith("app.")


def _appelees(fonction) -> list:
    """Fonctions de l'application atteignables par les noms de `fonction`."""
    portee = fonction.__globals__
    noms = _noms(fonction)
    trouvees: list = []
    for nom in noms:
        objet = portee.get(nom)
        if objet is None:
            continue
        if inspect.ismodule(objet) and objet.__name__.startswith("app."):
            for attribut in noms:
                cible = getattr(objet, attribut, None)
                if (inspect.isfunction(cible) or inspect.isclass(cible)) and (
                    _dans_l_application(cible)
                ):
                    trouvees += list(_fonctions_de(cible))
        elif inspect.isfunction(objet) or inspect.isclass(objet):
            if _dans_l_application(objet):
                trouvees += list(_fonctions_de(objet))
        elif _dans_l_application(type(objet)):
            trouvees += list(_fonctions_de(type(objet)))
    qualifie = fonction.__qualname__.rsplit(".", 1)
    if len(qualifie) == 2 and inspect.isclass(portee.get(qualifie[0])):
        for valeur in vars(portee[qualifie[0]]).values():
            if inspect.isfunction(valeur) and valeur.__name__ in noms:
                trouvees.append(valeur)
    return trouvees


def _atteint_une_garde(fonction, profondeur: int = 8, gardes: set[str] = GARDES) -> bool:
    vues = set()
    pile = [(inspect.unwrap(fonction), 0)]
    while pile:
        courante, niveau = pile.pop()
        if courante in vues:
            continue
        vues.add(courante)
        if courante.__name__ in gardes or _noms(courante) & gardes:
            return True
        if niveau < profondeur:
            pile += [(inspect.unwrap(v), niveau + 1) for v in _appelees(courante)]
    return False


def _dependances_appelables(route) -> list:
    trouvees = []
    pile = list(route.dependant.dependencies)
    while pile:
        dependance = pile.pop()
        appel = getattr(dependance, "call", None)
        if (
            inspect.isfunction(appel)
            and _dans_l_application(appel)
            and appel.__name__ != "get_current_user"
        ):
            trouvees.append(appel)
        pile.extend(dependance.dependencies or [])
    return trouvees


def _route_gardee(route) -> bool:
    return any(
        _atteint_une_garde(f) for f in [route.endpoint, *_dependances_appelables(route)]
    )


def _champs_de_corps(dependant) -> list[str]:
    champs: list[str] = []
    for parametre in dependant.body_params:
        info = getattr(parametre, "field_info", None)
        modele = getattr(parametre, "type_", None) or getattr(info, "annotation", None)
        if inspect.isclass(modele) and issubclass(modele, BaseModel):
            champs += [c for c in modele.model_fields if _NOM_SOCIETE.search(c)]
        elif _NOM_SOCIETE.search(parametre.name):
            champs.append(parametre.name)
    return champs


def _societes_fournies_par_le_client(route) -> set[str]:
    """Noms de variable portant une société lue dans la requête.

    `get_current_user` valide son propre en-tête ; `get_active_company_id`,
    lui, rend l'en-tête brut, sans aucun contrôle.
    """
    noms: set[str] = set()
    pile = [route.dependant]
    while pile:
        dependant = pile.pop()
        nom_appel = getattr(getattr(dependant, "call", None), "__name__", "")
        if nom_appel == "get_current_user":
            continue
        if nom_appel == "get_active_company_id":
            noms.add("company_id")
        for parametre in (
            dependant.path_params + dependant.query_params + dependant.header_params
        ):
            if _NOM_SOCIETE.search(parametre.name):
                noms.add(parametre.name)
        noms |= set(_champs_de_corps(dependant))
        pile.extend(dependant.dependencies or [])
    return noms


def _reference(variable: str, texte: str) -> bool:
    return re.search(rf"\b{re.escape(variable)}\b", texte) is not None


def _resoudre(nom_appel: str, portee: dict):
    """L'objet derrière `f` ou `module.f`, s'il est résoluble statiquement."""
    morceaux = nom_appel.split(".")
    objet = portee.get(morceaux[0])
    for morceau in morceaux[1:]:
        objet = getattr(objet, morceau, None) if objet is not None else None
    return objet


def _avec_alias(arbre: ast.AST, variables: set[str]) -> set[str]:
    """Ajoute les alias simples : `target = company_id or active`."""
    connus = set(variables)
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Assign) and any(
            _reference(v, ast.unparse(noeud.value)) for v in connus
        ):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name):
                    connus.add(cible.id)
    return connus


def _lue_dans_le_corps(fonction, variables: set[str]) -> set[str]:
    """Les variables réellement lues : un `company_id` déclaré mais ignoré
    (la route travaille sur la société active) n'ouvre rien."""
    lues: set[str] = set()
    for noeud in ast.walk(_corps_seul(fonction)):
        if isinstance(noeud, ast.Name) and noeud.id in variables:
            lues.add(noeud.id)
        elif isinstance(noeud, ast.Attribute) and noeud.attr in variables:
            lues.add(noeud.attr)  # request.company_id
    return lues


def _comparee_puis_refusee(arbre: ast.AST, variables: set[str]) -> bool:
    """`if company_id != cid: raise ...` : la valeur du client est confrontée
    à une société déjà contrôlée, et refusée si elle diffère."""
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.If):
            continue
        if not any(isinstance(n, ast.Raise) for b in noeud.body for n in ast.walk(b)):
            continue
        for comparaison in ast.walk(noeud.test):
            if not isinstance(comparaison, ast.Compare):
                continue
            termes = [comparaison.left, *comparaison.comparators]
            if any(isinstance(t, ast.Constant) for t in termes):
                continue
            if any(_reference(v, ast.unparse(comparaison)) for v in variables):
                return True
    return False


def _corps_seul(fonction) -> ast.Module:
    """Le corps de la fonction, sans décorateurs ni valeurs par défaut : ni
    `@router.post("/{company_id}")` ni `Query(None)` ne sont des usages."""
    source = textwrap.dedent(inspect.getsource(fonction))
    definition = ast.parse(source).body[0]
    return ast.Module(body=definition.body, type_ignores=[])  # type: ignore[attr-defined]


def _appels_dans_l_ordre(arbre: ast.AST) -> list[ast.Call]:
    appels = [n for n in ast.walk(arbre) if isinstance(n, ast.Call)]
    return sorted(appels, key=lambda n: (n.lineno, n.col_offset))


def _texte_des_arguments(appel: ast.Call) -> str:
    valeurs = [*appel.args, *[k.value for k in appel.keywords]]
    return " ".join(ast.unparse(v) for v in valeurs)


_UTILISATEUR = re.compile(r"\bcurrent_user\b|\buser\b")


def _appel_controle(appel: ast.Call, fonction) -> bool:
    """Cet appel confronte-t-il ce qu'il reçoit aux accès de l'appelant ?

    Fonction résolue : elle doit atteindre une garde de valeur, et s'appeler
    comme une garde ou recevoir l'utilisateur. Méthode non résoluble
    (`current_user.has_...`) : son nom seul décide.
    """
    nom = ast.unparse(appel.func)
    cible = _resoudre(nom, fonction.__globals__)
    if inspect.isfunction(cible) and _dans_l_application(cible):
        recoit_l_utilisateur = _UTILISATEUR.search(_texte_des_arguments(appel))
        return bool(
            (_APPEL_GARDE.search(nom) or recoit_l_utilisateur)
            and _atteint_une_garde(cible, profondeur=4, gardes=GARDES_DE_VALEUR)
        )
    return bool(_APPEL_GARDE.search(nom))


def _variable_gardee(fonction, variables: set[str]) -> bool:
    """Le PREMIER appel qui reçoit la société venue du client la contrôle-t-il ?

    « Le premier » et non « l'un d'eux » : les tickets support contrôlaient
    l'en-tête dans une branche et l'utilisaient tel quel dans une autre.
    """
    arbre = _corps_seul(fonction)
    variables = _avec_alias(arbre, variables)
    if _comparee_puis_refusee(arbre, variables):
        return True
    for appel in _appels_dans_l_ordre(arbre):
        texte = _texte_des_arguments(appel)
        if any(_reference(v, texte) for v in variables):
            return _appel_controle(appel, fonction)
    return False


_SOCIETE_DANS_L_APPEL = re.compile(r"company|societe|\bcid\b|\bctx\b|\bcontext\b")


def _objet_avec_societe(fonction, identifiants: list[str]) -> bool:
    """L'identifiant voyage avec la société, ou avec un utilisateur que
    l'appelé confronte vraiment à une société : recevoir `current_user` pour
    tracer l'auteur ne borne rien (modification d'un pointage)."""
    for appel in _appels_dans_l_ordre(_corps_seul(fonction)):
        texte = _texte_des_arguments(appel)
        if not any(_reference(i, texte) for i in identifiants):
            continue
        if _SOCIETE_DANS_L_APPEL.search(texte):
            return True
        if _UTILISATEUR.search(texte):
            cible = _resoudre(ast.unparse(appel.func), fonction.__globals__)
            if not (inspect.isfunction(cible) and _dans_l_application(cible)):
                return True
            if _atteint_une_garde(cible, profondeur=4):
                return True
    return False


def _est_reservee_super_admin(route) -> bool:
    if any("super_admin" in n and "company_access" not in n for n in _dependances(route)):
        return True
    source = inspect.getsource(inspect.unwrap(route.endpoint))
    return bool(re.search(r"if not current_user\.is_platform_admin", source))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_le_parcours_voit_bien_les_routes():
    assert len(_routes_api()) > 200


def test_toute_route_atteint_une_garde_de_societe():
    sans_garde = set()
    for route in _routes_api():
        if _route_gardee(route):
            continue
        for methode in route.methods or set():
            if methode != "OPTIONS" and (methode, route.path) not in ROUTES_SANS_SOCIETE:
                sans_garde.add((methode, route.path))

    assert not sans_garde, (
        "Route métier sans garde de société : borner à la société active, ou "
        "l'inscrire dans ROUTES_SANS_SOCIETE avec sa raison.\n"
        + "\n".join(f"  {m} {c}" for m, c in sorted(sans_garde))
    )


def test_la_societe_fournie_par_le_client_est_controlee():
    ouvertes = []
    for route in _routes_api():
        variables = _societes_fournies_par_le_client(route)
        if not variables or _est_reservee_super_admin(route):
            continue
        fonction = inspect.unwrap(route.endpoint)
        if not _lue_dans_le_corps(fonction, variables) and not any(
            _lue_dans_le_corps(d, variables) for d in _dependances_appelables(route)
        ):
            continue
        gardee = _variable_gardee(fonction, variables) or any(
            _variable_gardee(d, variables) for d in _dependances_appelables(route)
        )
        if not gardee:
            ouvertes.append(f"  {sorted(route.methods)} {route.path} {sorted(variables)}")

    assert not ouvertes, (
        "La société vient du client et n'est comparée à aucun accès :\n"
        + "\n".join(sorted(ouvertes))
    )


def test_un_identifiant_d_objet_voyage_avec_la_societe():
    ouvertes = []
    for route in _routes_api():
        identifiants = [
            p.name
            for p in route.dependant.path_params
            if (p.name.endswith("_id") or p.name == "id") and p.name != "company_id"
        ]
        if not identifiants or _est_reservee_super_admin(route):
            continue
        fonction = inspect.unwrap(route.endpoint)
        if _objet_avec_societe(fonction, identifiants):
            continue
        methodes = route.methods or set()
        if any((m, route.path) in OBJETS_SANS_SOCIETE for m in methodes):
            continue
        ouvertes.append(f"  {sorted(methodes)} {route.path}")

    assert not ouvertes, (
        "Identifiant d'objet utilisé sans société ni utilisateur : le borner, "
        "ou l'inscrire dans OBJETS_SANS_SOCIETE avec sa raison.\n"
        + "\n".join(sorted(ouvertes))
    )


def test_les_exceptions_correspondent_a_des_routes_existantes():
    connues = {(m, r.path) for r in _routes_api() for m in (r.methods or set())}
    perimees = (set(ROUTES_SANS_SOCIETE) | set(OBJETS_SANS_SOCIETE)) - connues
    assert not perimees, f"Exceptions sans route : {sorted(perimees)}"
