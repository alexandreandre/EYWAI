"""Fiche individuelle d'un salarié : les cumuls mois par mois (lot L18, 27/11).

Rubriques en lignes, mois en colonnes, total ; lue sur les bulletins
enregistrés, rien n'est recalculé. Un mois sans bulletin le dit.
"""

import io
from datetime import date

import pytest
from openpyxl import load_workbook

from app.modules.exports.infrastructure.fiche_individuelle import (
    MOIS_A_VENIR,
    MOIS_AVANT_ENTREE,
    MOIS_NON_PAYE,
    construire_fiche,
    periode_par_defaut,
    lire_periode,
)
from app.modules.exports.infrastructure.export_fiche_individuelle import fiche_en_xlsx
from app.modules.payroll.engine.salaire_reference_sortie import (
    calculer_salaire_de_reference,
    mois_de_salaire_du_bulletin,
)

pytestmark = pytest.mark.unit

EMPLOYE = {
    "id": "e1",
    "first_name": "Jean",
    "last_name": "Exemple",
    "matricule": "M042",
    "hire_date": "2024-03-01",
    "job_title": "Régleur",
    "statut": "Non-Cadre",
    "contract_type": "CDI",
    "salaire_de_base": {"valeur": 2000},
    "duree_hebdomadaire": 35,
}


def _bulletin(
    annee: int,
    mois: int,
    *,
    base: float = 2000.0,
    hs: float = 0.0,
    prime: float = 0.0,
    libelle_prime: str = "Prime exceptionnelle",
    absence: float = 0.0,
):
    brut = base + hs + prime - absence
    calcul = [
        {"libelle": "Salaire de base", "gain": base, "quantite": 151.67, "taux": round(base / 151.67, 4)},
    ]
    if hs:
        calcul.append({"libelle": "Heures suppl. majorées à 25%", "gain": hs, "quantite": 4.0})
    if prime:
        calcul.append({"libelle": libelle_prime, "gain": prime})
    calcul.append({"libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL", "gain": base + hs, "quantite": 155.67, "is_sous_total": True})
    salarial, patronal, rg = round(brut * 0.22, 2), round(brut * 0.40, 2), -150.0
    return {
        "year": annee,
        "month": mois,
        "payslip_data": {
            "salaire_brut": brut,
            "net_a_payer": round(brut * 0.78 - 30, 2),
            "calcul_du_brut": calcul,
            "details_absences": (
                [{"libelle": f"Absence non rémunérée du 12/{mois:02d}/26", "perte": absence, "quantite": 7}]
                if absence
                else []
            ),
            "structure_cotisations": {
                "total_salarial": salarial,
                "total_patronal": patronal,
                "bloc_principales": [{"coti_id": "x", "libelle": "Retraite", "montant_salarial": salarial, "montant_patronal": patronal - rg}],
                "bloc_allegements": [
                    {"coti_id": "reduction_generale", "libelle": "Réduction générale de cotisations patronales", "montant_patronal": rg, "montant_salarial": 0}
                ],
            },
            "synthese_net": {
                "net_imposable": round(brut * 0.80, 2),
                "impot_prelevement_a_la_source": {"base": brut * 0.8, "taux": 1.9, "montant": 30.0},
            },
        },
    }


def _ligne(fiche, libelle):
    return next(l for l in fiche["lignes"] if l["libelle"] == libelle)


def test_les_mois_en_colonnes_et_les_rubriques_en_lignes():
    bulletins = [_bulletin(2026, m) for m in range(1, 10)]
    bulletins[2] = _bulletin(2026, 3, hs=100.0)
    bulletins[5] = _bulletin(2026, 6, absence=92.31)
    fiche = construire_fiche(EMPLOYE, bulletins, (2026, 1), (2026, 12), aujourd_hui=date(2026, 11, 27))

    assert fiche["mois"] == [(2026, m) for m in range(1, 13)]
    base = _ligne(fiche, "Salaire de base")
    assert base["valeurs"][(2026, 1)] == 2000.0
    assert base["total"] == 18000.0
    assert _ligne(fiche, "Heures suppl. majorées à 25%")["valeurs"][(2026, 3)] == 100.0
    # L'absence se regroupe sans ses dates, en négatif comme sur le bulletin.
    assert _ligne(fiche, "Absence non rémunérée")["valeurs"][(2026, 6)] == -92.31
    # Le sous-total du bulletin n'est pas une rubrique : il compterait deux fois.
    assert all(not l["libelle"].startswith("SOUS-TOTAL") for l in fiche["lignes"])

    brut = _ligne(fiche, "SALAIRE BRUT")
    assert brut["valeurs"][(2026, 3)] == 2100.0
    assert brut["total"] == round(9 * 2000 + 100 - 92.31, 2)
    assert _ligne(fiche, "Cotisations salariales")["valeurs"][(2026, 1)] == 440.0
    assert _ligne(fiche, "Cotisations patronales")["valeurs"][(2026, 1)] == 800.0
    assert _ligne(fiche, "dont réduction générale")["valeurs"][(2026, 1)] == -150.0
    assert _ligne(fiche, "NET IMPOSABLE")["valeurs"][(2026, 1)] == 1600.0
    assert _ligne(fiche, "Prélèvement à la source")["valeurs"][(2026, 1)] == 30.0
    assert _ligne(fiche, "NET A PAYER")["valeurs"][(2026, 1)] == 1530.0
    assert _ligne(fiche, "Heures du salaire de base")["valeurs"][(2026, 1)] == 151.67
    assert _ligne(fiche, "Heures supplémentaires")["valeurs"][(2026, 3)] == 4.0


def test_un_mois_sans_bulletin_le_dit():
    bulletins = [_bulletin(2026, m) for m in (1, 2, 4)]
    fiche = construire_fiche(EMPLOYE, bulletins, (2026, 1), (2026, 12), aujourd_hui=date(2026, 11, 27))
    etat = _ligne(fiche, "Bulletin Martine")
    assert etat["valeurs"][(2026, 3)] == MOIS_NON_PAYE == "mois non payé dans Martine"
    assert etat["valeurs"][(2026, 12)] == MOIS_A_VENIR
    assert _ligne(fiche, "SALAIRE BRUT")["valeurs"][(2026, 3)] is None
    assert any("mois non payé dans martine" in note.lower() and "mars 2026" in note for note in fiche["notes"])


def test_avant_l_entree_le_mois_n_est_pas_un_oubli():
    employe = {**EMPLOYE, "hire_date": "2026-04-15"}
    fiche = construire_fiche(employe, [_bulletin(2026, 4)], (2026, 1), (2026, 4), aujourd_hui=date(2026, 11, 27))
    etat = _ligne(fiche, "Bulletin Martine")
    assert etat["valeurs"][(2026, 2)] == MOIS_AVANT_ENTREE
    assert etat["valeurs"][(2026, 4)] == "payé"


def test_deux_bulletins_le_meme_mois_s_additionnent():
    fiche = construire_fiche(
        EMPLOYE, [_bulletin(2026, 5), _bulletin(2026, 5, base=500.0)], (2026, 5), (2026, 5), aujourd_hui=date(2026, 11, 27)
    )
    assert _ligne(fiche, "SALAIRE BRUT")["valeurs"][(2026, 5)] == 2500.0
    assert _ligne(fiche, "Bulletin Martine")["valeurs"][(2026, 5)] == "payé (2 bulletins)"


def test_le_salaire_de_reference_vient_du_calcul_de_sortie():
    # Douze mois, dont une prime exceptionnelle en octobre 2026 : lue sur les
    # bulletins jusqu'au dernier mois de la période, y compris ceux d'avant.
    bulletins = [_bulletin(2025, m) for m in range(11, 13)] + [_bulletin(2026, m) for m in range(1, 10)]
    bulletins.append(_bulletin(2026, 10, prime=1200.0))
    fiche = construire_fiche(EMPLOYE, bulletins, (2026, 1), (2026, 10), aujourd_hui=date(2026, 11, 27))

    attendu = calculer_salaire_de_reference(
        [mois_de_salaire_du_bulletin(b["year"], b["month"], b["payslip_data"]) for b in bulletins],
        repli_contrat=2000.0,
        mois_d_anciennete=32,
    )
    reference = fiche["reference"]
    assert reference.moyenne_douze_mois == attendu.moyenne_douze_mois == 2100.0
    assert reference.tiers_trois_mois == attendu.tiers_trois_mois
    assert reference.retenu == attendu.retenu == 2100.0
    assert reference.formule == "douze_mois"


def test_periode_par_defaut_et_saisie():
    assert periode_par_defaut(date(2026, 11, 27)) == ((2026, 1), (2026, 12))
    assert lire_periode("2026-01", "2026-12", date(2026, 11, 27)) == ((2026, 1), (2026, 12))
    assert lire_periode(None, None, date(2026, 11, 27)) == ((2026, 1), (2026, 12))
    with pytest.raises(ValueError):
        lire_periode("2026-12", "2026-01", date(2026, 11, 27))
    with pytest.raises(ValueError):
        lire_periode("2022-01", "2026-12", date(2026, 11, 27))
    with pytest.raises(ValueError):
        lire_periode("2026-13", "2026-12", date(2026, 11, 27))


def test_le_classeur_porte_identite_colonnes_et_reference():
    bulletins = [_bulletin(2026, m) for m in (1, 2, 4)]
    fiche = construire_fiche(EMPLOYE, bulletins, (2026, 1), (2026, 12), aujourd_hui=date(2026, 11, 27))
    classeur = load_workbook(io.BytesIO(fiche_en_xlsx(fiche)))
    feuille = classeur.active
    valeurs = [[c for c in ligne] for ligne in feuille.iter_rows(values_only=True)]
    texte = [str(c) for ligne in valeurs for c in ligne if c is not None]

    assert "Fiche individuelle — Jean EXEMPLE" in texte
    assert "M042" in texte and "Régleur" in texte and "01/03/2024" in texte
    entete = next(l for l in valeurs if l[0] == "Rubrique")
    assert entete[1] == "janv. 2026" and entete[12] == "déc. 2026" and entete[13] == "Total"
    brut = next(l for l in valeurs if l[0] == "SALAIRE BRUT")
    assert brut[1] == 2000.0 and brut[3] is None and brut[13] == 6000.0
    etat = next(l for l in valeurs if l[0] == "Bulletin Martine")
    assert etat[3] == "mois non payé dans Martine"
    assert any(str(c).startswith("Salaire de référence de l'indemnité de départ") for c in texte)
    assert any("Moyenne des 12 derniers mois" in c for c in texte)
    assert any("Tiers des 3 derniers mois" in c for c in texte)


# --- Route : droits des exports RH, salarié de la société --------------------

from types import SimpleNamespace  # noqa: E402
from unittest.mock import patch  # noqa: E402

from fastapi import HTTPException  # noqa: E402

from app.modules.exports.api.router import fiche_individuelle as route_fiche  # noqa: E402


def _utilisateur(rh: bool):
    return SimpleNamespace(
        id="u1",
        is_platform_admin=False,
        active_company_id="c1",
        consultation=False,
        has_rh_access_in_company=lambda cid: rh and cid == "c1",
    )


def test_la_route_exige_le_profil_rh():
    with pytest.raises(HTTPException) as exc:
        route_fiche("e1", None, None, current_user=_utilisateur(False), company_id="c1")
    assert exc.value.status_code == 403


def test_un_salarie_d_une_autre_societe_est_introuvable():
    with patch(
        "app.modules.exports.application.service.generate_fiche_individuelle",
        side_effect=ValueError("Salarié non trouvé dans cette société."),
    ):
        with pytest.raises(HTTPException) as exc:
            route_fiche("e2", None, None, current_user=_utilisateur(True), company_id="c1")
    assert exc.value.status_code == 404


def test_la_route_rend_le_classeur():
    with patch(
        "app.modules.exports.application.service.generate_fiche_individuelle",
        return_value=(b"xlsx", "fiche-individuelle-Jean-EXEMPLE-2026-01-2026-12.xlsx"),
    ):
        reponse = route_fiche("e1", "2026-01", "2026-12", current_user=_utilisateur(True), company_id="c1")
    assert reponse.body == b"xlsx"
    assert "spreadsheetml" in reponse.media_type
    assert "fiche-individuelle-Jean-EXEMPLE" in reponse.headers["content-disposition"]


def test_le_nom_du_fichier_est_sans_accent():
    from app.modules.exports.infrastructure.export_fiche_individuelle import nom_du_fichier

    assert nom_du_fichier({"first_name": "Zoé", "last_name": "Exemple"}, (2026, 1), (2026, 12)) == (
        "fiche-individuelle-Zoe-EXEMPLE-2026-01-2026-12.xlsx"
    )


def test_les_dates_collees_des_bulletins_repris_sortent_du_libelle():
    repris = _bulletin(2026, 9)
    repris["payslip_data"]["calcul_du_brut"] += [
        {"libelle": "Act. partiel. 250926", "perte": 174.15, "quantite": 1},
        {"libelle": "Act. partiel. 180926", "perte": 174.15, "quantite": 1},
        {"libelle": "Absence maladie 220926-230926", "perte": 348.31, "quantite": 2},
    ]
    fiche = construire_fiche(EMPLOYE, [repris], (2026, 9), (2026, 9), aujourd_hui=date(2026, 11, 27))
    assert _ligne(fiche, "Act. partiel.")["valeurs"][(2026, 9)] == -348.3
    assert _ligne(fiche, "Absence maladie")["valeurs"][(2026, 9)] == -348.31


def test_au_forfait_jours_les_heures_le_disent():
    forfait = _bulletin(2026, 10)
    forfait["payslip_data"]["calcul_du_brut"][0] = {"libelle": "Salaire de base (forfait jour)", "gain": 2000.0}
    fiche = construire_fiche(EMPLOYE, [forfait], (2026, 10), (2026, 10), aujourd_hui=date(2026, 11, 27))
    assert _ligne(fiche, "Heures du salaire de base")["valeurs"][(2026, 10)] == "forfait jours"
