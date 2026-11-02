"""Liste des événements familiaux proposés : la loi, même sans convention."""

from __future__ import annotations

from unittest.mock import patch

from app.modules.absences.infrastructure import evenements_familiaux as ef

REFERENCE = [
    {"code": "mariage_salarie", "libelle": "Mariage du salarié", "duree_legale_jours": 4, "type_jours_legal": "JO", "ordre_affichage": 1},
    {"code": "pacs_salarie", "libelle": "PACS du salarié", "duree_legale_jours": 1, "type_jours_legal": "JO", "ordre_affichage": 2},
    {"code": "deces_grands_parents", "libelle": "Décès des grands-parents", "duree_legale_jours": 1, "type_jours_legal": "JO", "ordre_affichage": 10},
]


class _Requete:
    def __init__(self, table: str, donnees: dict):
        self.table, self.donnees, self.filtres, self.unique = table, donnees, {}, False

    def select(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self.filtres[col] = val
        return self

    def maybe_single(self):
        self.unique = True
        return self

    def execute(self):
        lignes = [r for r in self.donnees.get(self.table, []) if all(r.get(c, v) == v for c, v in self.filtres.items())]
        donnees = (lignes[0] if lignes else None) if self.unique else lignes

        class _R:
            data = donnees

        return _R()


class _Base:
    def __init__(self, donnees: dict):
        self.donnees = donnees

    def table(self, nom: str):
        return _Requete(nom, self.donnees)


def _base(cc_id=None, overrides=()):
    return _Base(
        {
            "employees": [{"id": "e1", "hire_date": "2020-01-01", "collective_agreement_id": cc_id, "company_id": "c1"}],
            "company_collective_agreements": [],
            "cc_evenements_familiaux": [dict(o, collective_agreement_id=cc_id) for o in overrides],
            "evenements_familiaux_reference": REFERENCE,
            "absence_requests": [],
        }
    )


def test_sans_convention_la_liste_porte_les_evenements_de_la_loi():
    with patch.object(ef, "supabase", _base(cc_id=None)):
        liste = {e["code"]: e["quota"] for e in ef.get_events_disponibles("e1")}
    assert liste == {"mariage_salarie": 4, "pacs_salarie": 4}


def test_sans_convention_le_quota_est_celui_de_la_loi():
    with patch.object(ef, "supabase", _base(cc_id=None)):
        assert ef.get_quota_evenement("e1", "pacs_salarie")["duree_jours"] == 4
        assert ef.get_quota_evenement("e1", "deces_grands_parents") is None


def test_avec_convention_une_duree_sous_la_loi_remonte_au_minimum():
    base = _base(cc_id="cc1", overrides=[{"event_code": "pacs_salarie", "duree_jours": 2, "type_jours": "JO", "condition_anciennete_jours": None}])
    with patch.object(ef, "supabase", base):
        liste = {e["code"]: e["quota"] for e in ef.get_events_disponibles("e1")}
        assert ef.get_solde_evenement("e1", "pacs_salarie")["solde_restant"] == 4
    assert liste == {"mariage_salarie": 4, "pacs_salarie": 4, "deces_grands_parents": 1}
