"""
Toute colonne demandée à la base existe vraiment.

Deux défauts de cette famille ont déjà coûté cher :

- `is_company_manager()` interrogeait une colonne `is_manager` inexistante et
  levait à chaque appel, ce qui faisait échouer sept politiques RLS : les
  salariés ne voyaient ni leur planning, ni leurs frais, ni leurs absences.
- `get_company_parametres_paie()` sélectionnait `companies.parametres_paie`,
  qui n'a jamais existé — `parametres_paie` est assemblé en code. L'erreur
  était avalée par un `try/except` et les salariés au forfait-jours
  retombaient silencieusement sur un découpage au mois calendaire.

Aucun test unitaire ne peut voir ça : les doublures répondent à tout. Ce test
compare les colonnes écrites dans le code au schéma réel de la base.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import httpx
import pytest

RACINE_APP = Path(__file__).resolve().parents[3] / "app"

#: Noms acceptés bien qu'absents du schéma : agrégats et jokers PostgREST.
TOLERES = {"*", "count"}

#: Écritures volontairement optimistes, tentées puis rattrapées. Chaque entrée
#: doit porter sa justification — sans quoi elle devient un tapis à poussière.
ADMISES = {
    # signatures/queries.py : la relance note sa date si la colonne est
    # déployée, et retombe sur `updated_at` sinon. Comportement assumé,
    # documenté dans la fonction, enveloppé dans un try/except.
    ("annual_reviews", "last_reminder_at"),
}

IDENTIFIANT = re.compile(r"^[a-z_][a-z0-9_]*$")


# --------------------------------------------------------------------------
# Lecture du schéma réel
# --------------------------------------------------------------------------


def _schema_reel() -> dict[str, set[str]]:
    """{table: {colonnes}} d'après le schéma que PostgREST publie."""
    url = os.environ.get("SUPABASE_URL")
    cle = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not cle:
        pytest.skip("SUPABASE_URL/SUPABASE_KEY absents — schéma inaccessible")
    reponse = httpx.get(
        f"{url}/rest/v1/",
        headers={"apikey": cle, "Authorization": f"Bearer {cle}"},
        timeout=60,
    )
    reponse.raise_for_status()
    definitions = reponse.json().get("definitions") or {}
    return {
        table: set((corps.get("properties") or {}).keys())
        for table, corps in definitions.items()
    }


# --------------------------------------------------------------------------
# Lecture des colonnes demandées par le code
# --------------------------------------------------------------------------


def colonnes_demandees(expression: str) -> list[str]:
    """Colonnes de premier niveau d'une chaîne `select()`.

    Les ressources imbriquées — `companies(id, name)` — sont ignorées : elles
    portent sur une autre table, dont le nom peut être un alias de clé
    étrangère. Les alias (`brut:salaire_brut`) et les chemins JSON
    (`payslip_data->>total`) sont ramenés à la colonne réelle.
    """
    trouvees: list[str] = []
    profondeur = 0
    courant = ""
    for caractere in expression:
        if caractere == "(":
            profondeur += 1
            courant = ""  # `rel(` : `rel` désigne une table, pas une colonne
            continue
        if caractere == ")":
            profondeur -= 1
            continue
        if caractere == "," and profondeur == 0:
            trouvees.append(courant)
            courant = ""
            continue
        if profondeur == 0:
            courant += caractere
    trouvees.append(courant)

    nettoyees = []
    for brute in trouvees:
        morceau = brute.strip()
        if not morceau:
            continue
        if ":" in morceau:  # alias:colonne
            morceau = morceau.split(":", 1)[1].strip()
        morceau = re.split(r"->>|->", morceau)[0].strip()
        morceau = morceau.split("::")[0].strip()
        if morceau and morceau not in TOLERES and IDENTIFIANT.match(morceau):
            nettoyees.append(morceau)
    return nettoyees


#: Méthodes dont le premier argument nomme une colonne.
FILTRES = {
    "eq", "neq", "gt", "gte", "lt", "lte",
    "like", "ilike", "is_", "in_", "contains", "order",
}

#: Méthodes dont l'argument est une charge utile {colonne: valeur}.
ECRITURES = {"insert", "update", "upsert"}


def _appels_colonnes() -> list[tuple[str, str, str, int]]:
    """(fichier, table, colonne, ligne) pour chaque colonne nommée dans le code.

    Couvre les trois façons de nommer une colonne : la lire (`select`),
    l'écrire (`insert`/`update`/`upsert`) et filtrer dessus (`eq`, `order`…).
    Le défaut `base_role` vivait surtout dans les écritures.
    """
    releves: list[tuple[str, str, str, int]] = []
    for fichier in sorted(RACINE_APP.rglob("*.py")):
        try:
            arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        chemin = str(fichier.relative_to(RACINE_APP.parent))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            fonction = noeud.func
            if not isinstance(fonction, ast.Attribute):
                continue
            table = _table_de(fonction.value)
            if not table:
                continue

            nom = fonction.attr
            colonnes: list[str] = []

            if nom == "select" and noeud.args:
                if isinstance(noeud.args[0], ast.Constant) and isinstance(
                    noeud.args[0].value, str
                ):
                    colonnes = colonnes_demandees(noeud.args[0].value)

            elif nom in FILTRES and noeud.args:
                premier = noeud.args[0]
                if isinstance(premier, ast.Constant) and isinstance(premier.value, str):
                    brut = premier.value.strip()
                    # `companies.id` filtre une ressource imbriquée, pas une
                    # colonne de la table courante : hors de portée du test.
                    if "." not in brut and IDENTIFIANT.match(brut):
                        colonnes = [brut]

            elif nom in ECRITURES and noeud.args:
                charge = noeud.args[0]
                if isinstance(charge, ast.Dict):
                    colonnes = [
                        cle.value
                        for cle in charge.keys
                        if isinstance(cle, ast.Constant)
                        and isinstance(cle.value, str)
                        and IDENTIFIANT.match(cle.value)
                    ]

            for colonne in colonnes:
                releves.append((chemin, table, colonne, noeud.lineno))
    return releves


def _table_de(noeud: ast.expr) -> str | None:
    """Nom littéral passé à `.table("…")` dans la chaîne d'appels."""
    while isinstance(noeud, ast.Call):
        fonction = noeud.func
        if isinstance(fonction, ast.Attribute) and fonction.attr in ("table", "from_"):
            if noeud.args and isinstance(noeud.args[0], ast.Constant):
                valeur = noeud.args[0].value
                return valeur if isinstance(valeur, str) else None
            return None
        noeud = fonction.value if isinstance(fonction, ast.Attribute) else None
        if noeud is None:
            return None
    if isinstance(noeud, ast.Attribute):
        return _table_de(noeud.value)
    return None


# --------------------------------------------------------------------------
# Le test
# --------------------------------------------------------------------------


class TestColonnesSelectionnees:
    def test_aucune_colonne_inexistante(self):
        schema = _schema_reel()
        inconnues = []
        for chemin, table, colonne, ligne in _appels_colonnes():
            connues = schema.get(table)
            if connues is None:
                continue  # vue, RPC ou table hors schéma exposé
            if colonne not in connues and (table, colonne) not in ADMISES:
                inconnues.append(f"{chemin}:{ligne} — {table}.{colonne}")

        assert not inconnues, (
            "Ces colonnes sont demandées à la base mais n'existent pas. "
            "PostgREST répond par une erreur ; si l'appel est enveloppé dans "
            "un `try/except`, le défaut devient invisible et la fonctionnalité "
            "se dégrade en silence.\n  " + "\n  ".join(sorted(set(inconnues)))
        )


class TestLecteurDeColonnes:
    """Le détecteur doit lire correctement, sinon le test ci-dessus est creux."""

    def test_liste_simple(self):
        assert colonnes_demandees("id, nom, email") == ["id", "nom", "email"]

    def test_ignore_les_ressources_imbriquees(self):
        assert colonnes_demandees("id, companies(id, company_name)") == ["id"]

    def test_denoue_les_alias(self):
        assert colonnes_demandees("brut:salaire_brut, id") == ["salaire_brut", "id"]

    def test_denoue_les_chemins_json(self):
        assert colonnes_demandees("payslip_data->>total, id") == [
            "payslip_data",
            "id",
        ]

    def test_ignore_le_joker(self):
        assert colonnes_demandees("*") == []

    def test_imbrication_profonde(self):
        assert colonnes_demandees("id, a(b(c, d), e), f") == ["id", "f"]

    def test_repere_la_colonne_qui_a_cause_le_defaut(self):
        assert colonnes_demandees("parametres_paie") == ["parametres_paie"]
