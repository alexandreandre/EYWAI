"""R-182, R-184 : l'inventaire du théorème, famille par famille, bloc par bloc.

Chaque famille de gain (`_MOTIFS_DE_GAIN` et les lignes reconnues par leurs
drapeaux) se corrige ici en valeur courante, nulle, grande et négative, et le
script du théorème voit brut, résidu, cumuls et compteur suivre. Une famille
ajoutée au moteur sans son exemple ici fait rougir la suite.

Les blocs hors inventaire (hors `lignes_corrigeables`) se corrigent à leur source :
chacun doit figurer dans `blocs_a_la_source`, avec sa source, et rester dans le
net et dans l'OD.

Ces cas sont synthétiques : un petit moteur en mémoire, pas le moteur réel (voir
`test_theoreme_mutants`). Sur les vrais bulletins, c'est
`scripts/theoreme_sept_societes.py`.
"""

from __future__ import annotations

import pytest

from app.modules.exports.domain.controle_comptable import residu_du_bulletin
from app.modules.exports.infrastructure.export_ecritures_comptables import ligne_od_du_bulletin
from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT, _MOTIFS_DE_GAIN, code_de_ligne_de_gain, famille_du_code
from app.modules.payroll.engine.corrections_du_bulletin import blocs_a_la_source, lignes_corrigeables
from tests.unit.payslips.test_theoreme_mutants import CUMULS_AVANT, FauxSupabase, _bulletin, script  # noqa: F401 — la fixture

pytestmark = pytest.mark.unit


def _gain(libelle: str, gain: float = 120.0, quantite: float | None = None, taux: float | None = None, **drapeaux) -> dict:
    return {"libelle": libelle, "quantite": quantite, "taux": taux, "gain": gain, "perte": None, **drapeaux}


def _perte(libelle: str, perte: float = 120.0, quantite: float | None = None, taux: float | None = None, **drapeaux) -> dict:
    return {"libelle": libelle, "quantite": quantite, "taux": taux, "gain": None, "perte": perte, **drapeaux}


#: Famille de code (`brut:…`) → ligne d'exemple. `_MOTIFS_DE_GAIN` doit y être en entier.
FAMILLES: dict[str, dict] = {
    "brut:hs_structurelles": _gain("Heures suppl. structurelles majorées à 25%", 266.67, 17.33, 15.39),
    "brut:heures_sup": _gain("Heures suppl. majorées à 25%", 400.0, 20.0, 20.0),
    "brut:heures_complementaires": _gain("Heures complémentaires majorées à 10%", 176.0, 10.0, 17.6),
    "brut:absence_entree_sortie": _perte("Absence pour entrée ou sortie"),
    "brut:absence_injustifiee": _perte("Absence injustifiée du 03/10/26"),
    "brut:absence_non_remuneree": _perte("Absence non rémunérée du 03/10/26"),
    "brut:absence_evenement_familial": _perte("Absence événement familial du 03/10/26"),
    "brut:absence_ferie_non_paye": _perte("Abs. jour férié non payé du 03/10/26"),
    "brut:absence_maladie": _perte("Absence maladie du 03/10/26"),
    "brut:reduction_hs_absence": _perte("Heures sup. du contrat non faites (absence)", 40.6),
    "brut:reduction_hs_evenement_familial": _perte("Heures sup. du contrat non faites (événement familial)", 40.6),
    "brut:maintien_evenement_familial": _gain("Maintien de salaire (événement familial)"),
    "brut:maintien_employeur": _gain("Maintien de salaire employeur", is_maintien_employeur=True),
    "brut:complement_absence_integrale": _gain("Complément retenue absence intégrale du mois"),
    "brut:retenue_absence_integrale": _perte("Retenue absence intégrale du mois limitée au salaire mensuel"),
    "brut:retenue_absence_mois_complet": _perte("Absence sur tout le mois : retenue ramenée au salaire du mois"),
    "brut:lissage_modulation": _gain("Lissage modulation"),
    "brut:absence_conges_payes": _perte("Absence congés payés du 05/10 au 09/10/26", 500.0),
    "brut:indemnite_conges_payes": _gain("Indemnité de congés payés (octobre)", 500.0),
    "brut:iccp": _gain("Indemnité compensatrice de congés payés", 300.0),
    "brut:precarite": _gain("Prime de précarité (CDD)", 240.0),
    "brut:ifm": _gain("Indemnité de fin de mission (intérim)", 240.0),
    "brut:avantages_en_nature": _gain("Avantages en nature", 150.0),
    "brut:prime_anciennete": _gain("Prime d'ancienneté (12 ans, 9,6 %)", 345.31, 3597.0, 0.096),
    "brut:rappel_salaire": _gain("Rappel de salaire de septembre"),
    "brut:reintegration": _gain("Réintégration trop-perçu"),
    "brut:heures_nuit": _gain("Heures de nuit majorées à 25%", 80.0, 5.0, 16.0),
    "brut:pause_remuneree": _gain("Pause rémunérée (planning)"),
    "brut:salaire_base": _gain("Salaire de base", 2426.72, 151.67, 16.0),
    "brut:arret": _perte("Arrêt maladie du 03/10/26", 300.0, is_arret_maladie=True),
    "brut:indemnite_sortie": _gain("Indemnité de licenciement soumise", 800.0, is_indemnite_sortie=True),
    "brut:prime": _gain("Prime exceptionnelle", 200.0),
}

#: Le salaire de base est déjà la ligne du petit moteur.
SANS_LIGNE_EN_PLUS = {"brut:salaire_base"}


def _familles_du_moteur() -> set[str]:
    return {f"brut:{famille}" for famille, _ in _MOTIFS_DE_GAIN}


def test_chaque_famille_du_moteur_a_son_exemple():
    assert _familles_du_moteur() <= set(FAMILLES), "famille de gain sans exemple : ajouter la ligne ici"


@pytest.mark.parametrize("famille", sorted(FAMILLES))
def test_l_exemple_est_bien_range_dans_sa_famille(famille):
    code = code_de_ligne_de_gain(FAMILLES[famille])
    assert famille_du_code(code) == famille


def _jouer(module, monkeypatch, gains_en_plus):
    monkeypatch.setattr(
        module,
        "_generer_moteur",
        lambda employee_id, year, month, cumuls, saisies_en_plus=(): _bulletin(
            saisies_en_plus, (cumuls or {}).get("cumuls", cumuls or {}) if isinstance(cumuls, dict) else {}, month, gains_en_plus
        ),
    )
    monkeypatch.setattr(module, "_cumuls_precedents", lambda *a, **k: dict(CUMULS_AVANT))
    monkeypatch.setattr(module, "supabase", FauxSupabase(employees=[{"id": "e1"}]))
    rapport: list[dict] = []
    module._corrections_directes("c1", "e1", 2026, 10, rapport)
    return rapport


@pytest.mark.parametrize("famille", sorted(FAMILLES))
def test_la_famille_se_corrige_et_tout_suit(script, monkeypatch, famille):  # noqa: F811
    gains = [] if famille in SANS_LIGNE_EN_PLUS else [FAMILLES[famille]]
    rapport = _jouer(script, monkeypatch, gains)
    joues = [c for c in rapport if c.get("code") and famille_du_code(str(c["code"])) == famille]
    assert joues, f"{famille} n'a pas été jouée"
    principal = [c for c in joues if not c.get("variante")]
    variantes = {c.get("variante") for c in joues if c.get("variante")}
    assert principal, f"{famille} : pas de correction principale"
    assert "zero" in variantes and "grande" in variantes, variantes
    # Toutes les valeurs de la famille, et tout le reste du bulletin avec.
    echecs = [(c.get("code"), c.get("variante"), c.get("echecs") or c.get("refus") or c.get("cas")) for c in rapport if not c["ok"]]
    assert echecs == [], echecs


def test_l_avantage_en_nature_corrige_ne_se_paie_pas_en_argent(script, monkeypatch):  # noqa: F811
    rapport = _jouer(script, monkeypatch, [FAMILLES["brut:avantages_en_nature"]])
    principal = next(c for c in rapport if c.get("code") == "brut:avantages_en_nature" and not c.get("variante"))
    assert principal["avantage_non_paye_en_argent"] is True


# --- Blocs hors inventaire (R-184) -------------------------------------------------------

BLOCS = {
    "primes_non_soumises": ({"primes_non_soumises": [{"libelle": "Prime de panier", "montant": 30.0}]}, 30.0),
    "revenus_hors_brut_imposables": ({"revenus_hors_brut_imposables": [{"libelle": "Activité partielle", "montant": 45.0}]}, 45.0),
    "participations": ({"participations": [{"libelle": "Participation", "montant": 150.0}]}, None),
    "remboursements_avances": ({"remboursements_avances": {"total_rembourse": 40.0}}, -40.0),
    "retenues_saisies": ({"retenues_saisies": {"total_preleve": 50.0}}, -50.0),
    "remboursements_prets": ({"remboursements_prets": {"total_rembourse": 20.0}}, -20.0),
    "indemnites_sortie": ({"indemnites_sortie": {"lignes_exonerees": [{"libelle": "Indemnité de rupture", "montant": 1000.0}]}}, 1000.0),
    # Information du bulletin (`synthese_net.ijss_net`), déjà dans le maintien ou la subrogation : ne s'ajoute pas au net.
    "ijss_net": ({"synthese_net": {"ijss_net": 200.0}}, None),
    "acompte_verse": ({"synthese_net": {"acompte_verse": 100.0}}, -100.0),
}


def _bulletin_avec(bloc: dict) -> dict:
    base = {
        "salaire_brut": 2000.0,
        "calcul_du_brut": [{"libelle": "Salaire de base", "quantite": 151.67, "taux": 13.19, "gain": 2000.0, "perte": None}],
        "details_conges": [],
        "details_absences": [],
        "cotisations_officielles": [{"code": "x", "lignes": [{"coti_id": "maladie", "libelle": "Maladie", "base": 2000.0, "taux_salarial": 0.1, "taux_patronal": None, "montant_salarial": 200.0, "montant_patronal": 0.0}], "total_salarial": 200.0, "total_patronal": 0.0}],
        "structure_cotisations": {
            "bloc_principales": [{"coti_id": "maladie", "libelle": "Maladie", "base": 2000.0, "taux_salarial": 0.1, "taux_patronal": None, "montant_salarial": 200.0, "montant_patronal": 0.0}],
            "total_salarial": 200.0,
            "total_patronal": 0.0,
        },
        "synthese_net": {"net_imposable": 1800.0, "montant_net_social": 1800.0, "impot_prelevement_a_la_source": {"base": 1800.0, "taux": 0.0, "montant": 0.0}},
    }
    for cle, valeur in bloc.items():
        if isinstance(valeur, dict) and cle == "synthese_net":
            base["synthese_net"] = {**base["synthese_net"], **valeur}
        else:
            base[cle] = valeur
    return base


@pytest.mark.parametrize("nom", sorted(BLOCS))
def test_chaque_bloc_hors_inventaire_a_sa_source(nom):
    bloc, _effet = BLOCS[nom]
    donnees = _bulletin_avec(bloc)
    trouves = blocs_a_la_source(donnees)
    assert trouves, f"{nom} : bloc porteur d'argent absent de la carte « à la source »"
    assert all(t["source"] and t["montant"] for t in trouves), trouves
    # Hors `lignes_corrigeables` : le bloc n'est pas sur la carte comme ligne de bulletin.
    assert all("primes" not in str(l.code) and l.libelle != trouves[0]["libelle"] for l in lignes_corrigeables(donnees) if l.bloc != "impot")


@pytest.mark.parametrize("nom", [n for n, (_, effet) in sorted(BLOCS.items()) if effet is not None])
def test_le_bloc_entre_dans_l_od_au_centime(nom):
    bloc, effet = BLOCS[nom]
    donnees = _bulletin_avec(bloc)
    donnees["net_a_payer"] = round(1800.0 + effet, 2)
    ligne = ligne_od_du_bulletin(
        payslip_id="p",
        employee={"id": "e1", "first_name": "", "last_name": ""},
        payslip_data=donnees,
        saisies_du_salarie=[],
        compte_de_saisie=lambda _t: "421000",
    )
    assert residu_du_bulletin(ligne) == 0.0, (nom, ligne["elements_hors_brut"])
