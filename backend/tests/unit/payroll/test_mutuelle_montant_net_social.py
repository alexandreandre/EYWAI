"""Montant net social et complément de mutuelle « Famille » à la charge du salarié.

Le BOSS (« Montant net social », version au 01/11/2026, II.A.2) retire du
montant net social « les cotisations salariales à la complémentaire santé
prévue à l'article L. 911-7 du CSS (…, dont les options individuelles
rattachées à des garanties collectives) ». Le complément « Famille » est une
option de ce type : il se retire, comme la formule Isolé.

Historique : Quadra ne le retire pas chez Colorplast (relation
`montant net social − net à payer avant impôt − acompte = 98,13` sur les
21 bulletins des trois salariés concernés, janvier à juillet 2026) et Martine
l'a imité du 28/09 au 02/11/2026 par le drapeau `part_salariale_obligatoire`.
L'audit du 01/11 (thème 7) l'a trouvé contraire au BOSS ; Alexandre a validé
le 02/11 de suivre la règle. Le drapeau reste sur les types de mutuelle, sans
effet sur le montant net social.

Chiffres repris des bulletins de janvier 2026 (env. de test).
"""

from types import SimpleNamespace

import pytest

from app.modules.payroll.engine import calcul_net

pytestmark = pytest.mark.unit

# --- Lanolet, janvier 2026 : Isolé + complément Famille
BRUT_LANOLET = 3046.68
#: Total des cotisations salariales, complément Famille et CSG/CRDS compris.
COTISATIONS_LANOLET = 706.63
TRANSPORT_LANOLET = [{"libelle": "Indemnite de transport", "montant": 100.0}]
#: Quadra : le complément n'est pas retranché (contraire au BOSS, II.A.2).
MNS_QUADRA_LANOLET = 2538.18
#: La règle : le complément est retranché comme le reste de la mutuelle.
MNS_AVEC_FAMILLE_RETRANCHEE = 2440.05

# --- Dumarel, janvier 2026 : Isolé seul, témoin
BRUT_DUMAREL = 3023.40
COTISATIONS_DUMAREL = 599.34
FRAIS_DUMAREL = [{"libelle": "Remboursement de notes de frais", "montant": 84.59}]
MNS_QUADRA_DUMAREL = 2508.65

ISOLE = {
    "id": "isole",
    "montant_salarial": 29.24,
    "montant_patronal": 29.23,
    "part_patronale_soumise_a_csg": True,
}
FAMILLE = {
    "id": "famille",
    "montant_salarial": 98.13,
    "montant_patronal": 0.0,
    "part_patronale_soumise_a_csg": True,
    "part_salariale_deductible_impot": False,
}


def _contexte(mutuelle_type_ids, lignes_specifiques=None):
    return SimpleNamespace(
        month=1,
        cumuls={},
        contrat={
            "specificites_paie": {
                "mutuelle": {
                    "adhesion": True,
                    "mutuelle_type_ids": mutuelle_type_ids,
                    "lignes_specifiques": lignes_specifiques or [],
                }
            }
        },
    )


def _client_factice(lignes):
    class _Requete:
        def select(self, *_a, **_k):
            return self

        def in_(self, _colonne, ids):
            self._ids = ids
            return self

        def eq(self, *_a, **_k):
            return self

        def execute(self):
            return SimpleNamespace(
                data=[l for l in lignes if l["id"] in getattr(self, "_ids", [])]
            )

    class _Client:
        def table(self, _nom):
            return _Requete()

    return _Client()


def _mns(monkeypatch, lignes_mutuelle, brut, cotisations, primes, contexte=None):
    import app.core.database as database

    monkeypatch.setattr(
        database, "get_supabase_admin_client", lambda: _client_factice(lignes_mutuelle)
    )
    return calcul_net.calculer_montant_net_social(
        contexte or _contexte([l["id"] for l in lignes_mutuelle]),
        brut,
        cotisations,
        primes,
    )


class TestMontantNetSocialEtMutuelleFacultative:
    def test_le_complement_famille_reduit_le_net_social(self, monkeypatch):
        """Même marqué « non obligatoire », le complément Famille se retire."""
        famille = {**FAMILLE, "part_salariale_obligatoire": False}
        assert _mns(
            monkeypatch, [ISOLE, famille], BRUT_LANOLET, COTISATIONS_LANOLET,
            TRANSPORT_LANOLET,
        ) == MNS_AVEC_FAMILLE_RETRANCHEE

    def test_sans_le_drapeau_meme_resultat(self, monkeypatch):
        assert _mns(
            monkeypatch, [ISOLE, FAMILLE], BRUT_LANOLET, COTISATIONS_LANOLET,
            TRANSPORT_LANOLET,
        ) == MNS_AVEC_FAMILLE_RETRANCHEE

    def test_la_mutuelle_isole_reste_retranchee(self, monkeypatch):
        """Témoin : Dumarel n'a que la formule Isolé, financée pour moitié par
        l'employeur. Elle est obligatoire et reste déduite du net social."""
        assert _mns(
            monkeypatch, [ISOLE], BRUT_DUMAREL, COTISATIONS_DUMAREL, FRAIS_DUMAREL
        ) == MNS_QUADRA_DUMAREL

    def test_une_ligne_specifique_famille_se_retire_aussi(self, monkeypatch):
        contexte = _contexte(
            ["isole"],
            lignes_specifiques=[
                {"montant_salarial": 98.13, "part_salariale_obligatoire": False}
            ],
        )
        assert _mns(
            monkeypatch, [ISOLE], BRUT_LANOLET, COTISATIONS_LANOLET,
            TRANSPORT_LANOLET, contexte=contexte,
        ) == MNS_AVEC_FAMILLE_RETRANCHEE

    def test_sans_adhesion_mutuelle_aucun_effet(self, monkeypatch):
        contexte = SimpleNamespace(
            month=1, cumuls={},
            contrat={"specificites_paie": {"mutuelle": {"adhesion": False}}},
        )
        assert _mns(
            monkeypatch, [], BRUT_DUMAREL, COTISATIONS_DUMAREL, FRAIS_DUMAREL,
            contexte=contexte,
        ) == MNS_QUADRA_DUMAREL
