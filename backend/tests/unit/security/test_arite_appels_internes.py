"""
Garde structurelle : aucun appel interne ne doit être sous-alimenté.

Le 23/08, l'ajout d'un paramètre obligatoire `company_id` sur deux
commandes de `monthly_inputs` a laissé deux appelants avec l'ancienne
signature — validation des médailles du travail et génération des lignes de
paie d'une campagne de participation. Les deux routes renvoyaient 500 en
production, et **6638 tests passaient quand même** : les tests concernés
remplaçaient la fonction par un `MagicMock` sans gabarit, qui accepte
n'importe quel nombre d'arguments.

Ce test lit le code réel (AST) et compare, pour un ensemble de fonctions
sensibles, le nombre d'arguments passés au nombre exigé. Il n'a besoin
d'aucun mock : c'est précisément ce qui lui permet d'attraper ce que les
mocks masquent.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List, Tuple

RACINE = Path(__file__).resolve().parents[3]
DOSSIERS_SURVEILLES = [RACINE / "app", RACINE / "scripts"]

# Fonctions dont un appel sous-alimenté casse une route en production.
# (module d'origine → on ne surveille que le NOM, suffisant pour l'arité.)
FONCTIONS_SURVEILLEES = {
    "create_employee_monthly_input",
    "create_monthly_inputs_batch",
    "update_monthly_input",
    "delete_monthly_input",
    "delete_employee_monthly_input",
    "list_monthly_inputs_by_period",
    "list_monthly_inputs_by_employee_period",
    "require_employee_access",
    "assert_employee_in_company",
}


def _definitions() -> Dict[str, Tuple[int, int]]:
    """nom → (nb d'arguments obligatoires, nb total accepté)."""
    trouvees: Dict[str, Tuple[int, int]] = {}
    for dossier in DOSSIERS_SURVEILLES:
        if not dossier.exists():
            continue
        for fichier in dossier.rglob("*.py"):
            try:
                arbre = ast.parse(fichier.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if noeud.name not in FONCTIONS_SURVEILLEES:
                    continue
                args = noeud.args
                positionnels = args.posonlyargs + args.args
                # `self` ne compte pas pour un appel de méthode.
                if positionnels and positionnels[0].arg in ("self", "cls"):
                    positionnels = positionnels[1:]
                obligatoires = len(positionnels) - len(args.defaults)
                trouvees[noeud.name] = (obligatoires, len(positionnels))
    return trouvees


def _appels() -> List[Tuple[str, str, int, int]]:
    """(nom, emplacement, nb positionnels, nb mots-clés) pour chaque appel."""
    releves: List[Tuple[str, str, int, int]] = []
    for dossier in DOSSIERS_SURVEILLES:
        if not dossier.exists():
            continue
        for fichier in dossier.rglob("*.py"):
            try:
                arbre = ast.parse(fichier.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.Call):
                    continue
                cible = noeud.func
                nom = getattr(cible, "attr", None) or getattr(cible, "id", None)
                if nom not in FONCTIONS_SURVEILLEES:
                    continue
                if any(isinstance(a, ast.Starred) for a in noeud.args):
                    continue  # déballage : arité indécidable statiquement
                if any(k.arg is None for k in noeud.keywords):
                    continue  # **kwargs : idem
                emplacement = (
                    f"{fichier.relative_to(RACINE)}:{noeud.lineno}"
                )
                releves.append(
                    (nom, emplacement, len(noeud.args), len(noeud.keywords))
                )
    return releves


def test_aucun_appel_sous_alimente():
    definitions = _definitions()
    assert definitions, "aucune fonction surveillée trouvée — chemin de code ?"

    fautifs = []
    for nom, emplacement, positionnels, mots_cles in _appels():
        if nom not in definitions:
            continue
        obligatoires, _total = definitions[nom]
        if positionnels + mots_cles < obligatoires:
            fautifs.append(
                f"  {emplacement} : {nom}() reçoit {positionnels + mots_cles} "
                f"argument(s), {obligatoires} exigé(s)"
            )

    assert not fautifs, (
        "Appels sous-alimentés — ils lèvent un TypeError en production, "
        "même quand les tests qui les couvrent passent au vert :\n"
        + "\n".join(sorted(fautifs))
    )
