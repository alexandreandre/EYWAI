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
        self.requetes = 0

    def table(self, nom: str):
        self.requetes += 1
        return _Requete(nom, self.donnees)


def _base(cc_id=None, overrides=(), pris=()):
    return _Base(
        {
            "employees": [{"id": "e1", "hire_date": "2020-01-01", "collective_agreement_id": cc_id, "company_id": "c1"}],
            "company_collective_agreements": [],
            "cc_evenements_familiaux": [dict(o, collective_agreement_id=cc_id) for o in overrides],
            "evenements_familiaux_reference": REFERENCE,
            "absence_requests": list(pris),
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


# --- Saisie RH : la liste du salarié choisi, pas celle du compte connecté ---

from app.modules.absences.application import queries as absences_queries


def test_la_rh_obtient_la_liste_du_salarie_choisi():
    with patch.object(absences_queries, "get_employee_company_id", return_value="c1"), patch.object(
        absences_queries.evenement_familial_provider, "get_events_disponibles", return_value=[{"code": "pacs_salarie"}]
    ) as lecture:
        assert absences_queries.get_evenements_familiaux_du_salarie("e1", "c1") == [{"code": "pacs_salarie"}]
    lecture.assert_called_once_with("e1")


def test_un_salarie_d_une_autre_societe_n_est_pas_lu():
    with patch.object(absences_queries, "get_employee_company_id", return_value="autre"), patch.object(
        absences_queries.evenement_familial_provider, "get_events_disponibles"
    ) as lecture:
        assert absences_queries.get_evenements_familiaux_du_salarie("e1", "c1") is None
    lecture.assert_not_called()


# --- La liste se lit en quelques requêtes, pas une série par événement ---
# Vu au tournage du 03/11 : ~16 s de « Chargement… » dans « Nouveau congé ».


def test_la_liste_se_lit_en_peu_de_requetes():
    base = _base(cc_id="cc1")
    with patch.object(ef, "supabase", base):
        ef.get_events_disponibles("e1")
    assert base.requetes <= 6


def test_les_jours_deja_pris_baissent_le_solde():
    pris = [{"employee_id": "e1", "type": "evenement_familial", "event_subtype": "mariage_salarie", "status": "validated", "selected_days": ["2026-06-01", "2026-06-02"]}]
    with patch.object(ef, "supabase", _base(cc_id=None, pris=pris)):
        liste = {e["code"]: (e["solde_restant"], e["taken"]) for e in ef.get_events_disponibles("e1")}
    assert liste["mariage_salarie"] == (2, 2)
    assert liste["pacs_salarie"] == (4, 0)
