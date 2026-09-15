"""Montant net social et complément de mutuelle à la charge du salarié.

Le montant net social est défini par l'arrêté du 31/01/2023 comme les sommes
versées au salarié diminuées des seules cotisations et contributions sociales
**obligatoires**. Un complément « Famille » entièrement à la charge du salarié
n'en est pas une : la couverture collective obligatoire doit être financée pour
moitié au moins par l'employeur (art. L911-7 du code de la sécurité sociale),
et une extension facultative reste hors du champ.

Constat sur les bulletins Quadra de Colorplast, janvier à juillet 2026 : pour
les trois salariés qui paient le complément « GAN Famille », la relation

    montant net social − net à payer avant impôt − acompte = 98,13

se vérifie sur les 21 bulletins concernés, et vaut zéro pour les salariés sans
complément. La retenue réduit donc le net à payer mais jamais le montant net
social. EYWAI la déduisait des deux (Espinosa janvier : 2 440,05 € au lieu de
2 538,18 €).

Le montant net social est transmis aux organismes sociaux : c'est le seul écart
du rapprochement de janvier qui sorte de l'entreprise.

Chiffres repris des bulletins de janvier 2026 (env. de test).
"""

from types import SimpleNamespace

import pytest

from app.modules.payroll.engine import calcul_net

pytestmark = pytest.mark.unit

# --- Espinosa, janvier 2026 : Isolé + complément Famille
BRUT_ESPINOSA = 3046.68
#: Total des cotisations salariales, complément Famille et CSG/CRDS compris.
COTISATIONS_ESPINOSA = 706.63
TRANSPORT_ESPINOSA = [{"libelle": "Indemnite de transport", "montant": 100.0}]
MNS_QUADRA_ESPINOSA = 2538.18
#: Ce que nous produisions : le complément était retranché du net social.
MNS_AVEC_FAMILLE_RETRANCHEE = 2440.05

# --- Bugny, janvier 2026 : Isolé seul, témoin
BRUT_BUGNY = 3023.40
COTISATIONS_BUGNY = 599.34
FRAIS_BUGNY = [{"libelle": "Remboursement de notes de frais", "montant": 84.59}]
MNS_QUADRA_BUGNY = 2508.65

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
    def test_le_complement_famille_ne_reduit_pas_le_net_social(self, monkeypatch):
        famille = {**FAMILLE, "part_salariale_obligatoire": False}
        assert _mns(
            monkeypatch, [ISOLE, famille], BRUT_ESPINOSA, COTISATIONS_ESPINOSA,
            TRANSPORT_ESPINOSA,
        ) == MNS_QUADRA_ESPINOSA

    def test_sans_le_drapeau_rien_ne_bouge(self, monkeypatch):
        """Garde anti-régression : le défaut reste « obligatoire »."""
        assert _mns(
            monkeypatch, [ISOLE, FAMILLE], BRUT_ESPINOSA, COTISATIONS_ESPINOSA,
            TRANSPORT_ESPINOSA,
        ) == MNS_AVEC_FAMILLE_RETRANCHEE

    def test_la_mutuelle_isole_reste_retranchee(self, monkeypatch):
        """Témoin : Bugny n'a que la formule Isolé, financée pour moitié par
        l'employeur. Elle est obligatoire et reste déduite du net social."""
        assert _mns(
            monkeypatch, [ISOLE], BRUT_BUGNY, COTISATIONS_BUGNY, FRAIS_BUGNY
        ) == MNS_QUADRA_BUGNY

    def test_le_drapeau_marche_aussi_sur_une_ligne_specifique(self, monkeypatch):
        """Même levier que pour le net imposable : les lignes saisies à la main
        sur la fiche portent le drapeau comme les types de mutuelle."""
        contexte = _contexte(
            ["isole"],
            lignes_specifiques=[
                {"montant_salarial": 98.13, "part_salariale_obligatoire": False}
            ],
        )
        assert _mns(
            monkeypatch, [ISOLE], BRUT_ESPINOSA, COTISATIONS_ESPINOSA,
            TRANSPORT_ESPINOSA, contexte=contexte,
        ) == MNS_QUADRA_ESPINOSA

    def test_sans_adhesion_mutuelle_aucun_effet(self, monkeypatch):
        contexte = SimpleNamespace(
            month=1, cumuls={},
            contrat={"specificites_paie": {"mutuelle": {"adhesion": False}}},
        )
        assert _mns(
            monkeypatch, [], BRUT_BUGNY, COTISATIONS_BUGNY, FRAIS_BUGNY,
            contexte=contexte,
        ) == MNS_QUADRA_BUGNY
