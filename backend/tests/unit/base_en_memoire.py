"""Une base Supabase en mémoire, pour suivre un état à travers plusieurs écritures.

Les doublures d'un seul appel ne disent pas ce que devient un solde quand on
génère, recalcule, supprime puis regénère un bulletin. Cette base garde ses
lignes d'un appel à l'autre et répond aux requêtes du client Supabase que le
code de paie utilise : select, eq, in_, gt/gte/lt/lte, is_, match, order,
limit, maybe_single, insert, update, delete.

Usage : `base.brancher(monkeypatch)`.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any


class _Reponse:
    def __init__(self, data: Any, count: int | None = None) -> None:
        self.data = data
        self.count = count


def _nombre(valeur: Any) -> float | None:
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _egal(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is b
    na, nb = _nombre(a), _nombre(b)
    if na is not None and nb is not None and not isinstance(a, bool):
        return na == nb
    return str(a) == str(b)


class BaseEnMemoire:
    def __init__(self, tables: dict[str, list[dict]] | None = None) -> None:
        self.tables: dict[str, list[dict]] = {
            nom: [dict(l) for l in lignes] for nom, lignes in (tables or {}).items()
        }

    def table(self, nom: str) -> "_Requete":
        return _Requete(self, nom)

    def brancher(self, monkeypatch) -> None:
        """Toute requête du client Supabase passe par cette base.

        Sur chaque instance que tient un module, pas seulement sur celle de
        `app.core.database` : un test qui recharge ce module en crée une autre,
        et les modules importés avant gardent l'ancienne.
        """
        import sys

        from app.core import database

        classe = type(database.supabase)
        instances = {id(database.supabase): database.supabase}
        for module in list(sys.modules.values()):
            client = getattr(module, "supabase", None) if module is not None else None
            if isinstance(client, classe):
                instances[id(client)] = client
        for client in instances.values():
            monkeypatch.setattr(client, "table", self.table)

    def lignes(self, nom: str, **filtres: Any) -> list[dict]:
        return [
            l
            for l in self.tables.get(nom, [])
            if all(_egal(l.get(k), v) for k, v in filtres.items())
        ]

    def ligne(self, nom: str, **filtres: Any) -> dict:
        trouvees = self.lignes(nom, **filtres)
        assert len(trouvees) == 1, f"{nom} {filtres} : {len(trouvees)} ligne(s)"
        return trouvees[0]


class _Requete:
    def __init__(self, base: BaseEnMemoire, nom: str) -> None:
        self.base, self.nom = base, nom
        self.op = "select"
        self.valeur: Any = None
        self.conditions: list = []
        self.tri: list[tuple[str, bool]] = []
        self.plafond: int | None = None
        self.une_seule = False
        self.compter = False
        self.conflit: list[str] = []

    # --- opérations ---
    def select(self, *_colonnes: Any, count: str | None = None, **_k: Any) -> "_Requete":
        self.compter = count is not None
        return self

    def insert(self, valeur: Any) -> "_Requete":
        self.op, self.valeur = "insert", valeur
        return self

    def upsert(self, valeur: Any, on_conflict: str = "", **_k: Any) -> "_Requete":
        self.op, self.valeur = "upsert", valeur
        self.conflit = [c.strip() for c in on_conflict.split(",") if c.strip()]
        return self

    def update(self, valeur: dict) -> "_Requete":
        self.op, self.valeur = "update", valeur
        return self

    def delete(self) -> "_Requete":
        self.op = "delete"
        return self

    # --- filtres ---
    def eq(self, cle: str, valeur: Any) -> "_Requete":
        self.conditions.append(lambda l: _egal(l.get(cle), valeur))
        return self

    def neq(self, cle: str, valeur: Any) -> "_Requete":
        self.conditions.append(lambda l: not _egal(l.get(cle), valeur))
        return self

    def match(self, valeurs: dict) -> "_Requete":
        for cle, valeur in valeurs.items():
            self.eq(cle, valeur)
        return self

    def in_(self, cle: str, valeurs: Any) -> "_Requete":
        valeurs = list(valeurs)
        self.conditions.append(lambda l: any(_egal(l.get(cle), v) for v in valeurs))
        return self

    def is_(self, cle: str, valeur: Any) -> "_Requete":
        attendu = None if valeur in (None, "null") else valeur
        self.conditions.append(lambda l: l.get(cle) is attendu)
        return self

    def _compare(self, cle: str, valeur: Any, test) -> "_Requete":
        def condition(l: dict) -> bool:
            a, b = _nombre(l.get(cle)), _nombre(valeur)
            if a is None or b is None:
                return l.get(cle) is not None and test(str(l.get(cle)), str(valeur))
            return test(a, b)

        self.conditions.append(condition)
        return self

    def gt(self, cle: str, valeur: Any) -> "_Requete":
        return self._compare(cle, valeur, lambda a, b: a > b)

    def gte(self, cle: str, valeur: Any) -> "_Requete":
        return self._compare(cle, valeur, lambda a, b: a >= b)

    def lt(self, cle: str, valeur: Any) -> "_Requete":
        return self._compare(cle, valeur, lambda a, b: a < b)

    def lte(self, cle: str, valeur: Any) -> "_Requete":
        return self._compare(cle, valeur, lambda a, b: a <= b)

    def or_(self, _expression: str, **_k: Any) -> "_Requete":
        """Non interprété : ne s'emploie ici que sur des tables sans cas limite."""
        return self

    def order(self, cle: str, desc: bool = False, **_k: Any) -> "_Requete":
        self.tri.append((cle, desc))
        return self

    def limit(self, n: int) -> "_Requete":
        self.plafond = n
        return self

    def range(self, debut: int, fin: int) -> "_Requete":
        self.plafond = fin + 1
        return self

    def maybe_single(self) -> "_Requete":
        self.une_seule = True
        return self

    def single(self) -> "_Requete":
        self.une_seule = True
        return self

    # --- exécution ---
    def _selection(self) -> list[dict]:
        lignes = [l for l in self.base.tables.setdefault(self.nom, []) if all(c(l) for c in self.conditions)]
        for cle, desc in reversed(self.tri):
            lignes.sort(key=lambda l: (l.get(cle) is None, l.get(cle)), reverse=desc)
        if self.plafond is not None:
            lignes = lignes[: self.plafond]
        return lignes

    def execute(self) -> _Reponse:
        table = self.base.tables.setdefault(self.nom, [])
        if self.op == "insert":
            nouvelles = self.valeur if isinstance(self.valeur, list) else [self.valeur]
            ajoutees = []
            for n in nouvelles:
                ligne = {"id": str(uuid.uuid4()), **copy.deepcopy(n)}
                table.append(ligne)
                ajoutees.append(copy.deepcopy(ligne))
            return _Reponse(ajoutees)
        if self.op == "upsert":
            nouvelles = self.valeur if isinstance(self.valeur, list) else [self.valeur]
            rendues = []
            for n in nouvelles:
                existante = next(
                    (l for l in table if all(_egal(l.get(c), n.get(c)) for c in self.conflit)),
                    None,
                ) if self.conflit else None
                if existante is not None:
                    existante.update(copy.deepcopy(n))
                    rendues.append(copy.deepcopy(existante))
                else:
                    ligne = {"id": str(uuid.uuid4()), **copy.deepcopy(n)}
                    table.append(ligne)
                    rendues.append(copy.deepcopy(ligne))
            return _Reponse(rendues)
        selection = self._selection()
        if self.op == "update":
            for l in selection:
                l.update(copy.deepcopy(self.valeur))
            return _Reponse([copy.deepcopy(l) for l in selection])
        if self.op == "delete":
            ids = {id(l) for l in selection}
            self.base.tables[self.nom] = [l for l in table if id(l) not in ids]
            return _Reponse([copy.deepcopy(l) for l in selection])
        rendues = [copy.deepcopy(l) for l in selection]
        if self.une_seule:
            return _Reponse(rendues[0] if rendues else None)
        return _Reponse(rendues, count=len(rendues) if self.compter else None)
