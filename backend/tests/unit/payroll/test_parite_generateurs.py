"""Parité des deux générateurs de bulletins : heures et forfait jours.

Le 17/11/2026, à Lyon, l'activité partielle était branchée dans le générateur des
heures et pas dans celui du forfait jours : jours chômés payés en entier, sans
alerte. Rien n'obligeait à tenir les deux chemins ensemble. Ce test le fait.

Il lit les appels de chaque générateur (sans les exécuter) et range chaque
étape de l'un des deux dans une liste :

- `COMMUNES` : appelée par les deux ; elle doit le rester ;
- `TROUS_DU_FORFAIT` : appelée côté heures seulement alors qu'elle concerne aussi
  le forfait jours ; en échec attendu strict tant que le trou existe ;
- `HEURES_SEULEMENT` / `FORFAIT_SEULEMENT` : propre à un chemin, avec sa raison.

Une étape nouvelle, ajoutée à un seul générateur, fait échouer
`test_toute_etape_d_un_seul_generateur_est_rangee` : il faut la brancher dans
l'autre, ou écrire ici en une phrase pourquoi elle ne le concerne pas.
Une ligne par étape, une phrase par ligne : quelques secondes par lot.
"""

from __future__ import annotations

import ast
import inspect
from types import ModuleType

import pytest

from app.modules.payroll.documents import (
    payslip_generator,
    payslip_generator_forfait,
    payslip_run_forfait,
    payslip_run_heures,
)

pytestmark = pytest.mark.unit


def _appels_metier(module: ModuleType, fonction: str) -> set[str]:
    """Noms des fonctions de l'application appelées par `fonction`.

    Seuls comptent les appels à une fonction importée d'un module `app.` ou
    définie au niveau du module ; la plomberie (dict, json, Path, supabase…)
    et les petites fonctions locales sont ignorées.
    """
    arbre = ast.parse(inspect.getsource(module))
    importees: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom) and (noeud.module or "").startswith("app."):
            importees.update(alias.asname or alias.name for alias in noeud.names)
        if isinstance(noeud, ast.ImportFrom) and noeud.level and noeud.module:
            importees.update(alias.asname or alias.name for alias in noeud.names)
    du_module = {n.name for n in arbre.body if isinstance(n, ast.FunctionDef)}
    cible = next(
        n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef) and n.name == fonction
    )
    appels: set[str] = set()
    for noeud in ast.walk(cible):
        if not isinstance(noeud, ast.Call):
            continue
        f = noeud.func
        if isinstance(f, ast.Name) and (f.id in importees or f.id in du_module):
            appels.add(f.id)
        elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in importees:
            # `planning_apres_sortie.ecarter_apres_la_sortie(...)`
            appels.add(f.attr)
    # Les classes (BacASable, FenetreVariables…) sont des données, pas des étapes.
    return {a for a in appels if not a[:1].isupper()} - {fonction}


CHEMINS = {
    "generateur": (
        (payslip_generator, "process_payslip_generation"),
        (payslip_generator_forfait, "process_payslip_generation_forfait"),
    ),
    "moteur": (
        (payslip_run_heures, "run_payslip_generation_heures"),
        (payslip_run_forfait, "run_payslip_generation_forfait"),
    ),
}

COMMUNES: dict[str, dict[str, str]] = {
    "generateur": {
        "fiche_du_mois": "la fiche du contrat du mois, et celle d'un contrat rangé",
        "resolve_date_sortie": "la date de sortie retenue (fin de contrat ou départ)",
        "payslip_employment_period_block_reason": "pas de bulletin hors du contrat",
        "variables_du_bulletin": "les saisies du mois du bulletin",
        "saisies_du_mois": "les saisies en mémoire du bac à sable",
        "alertes_plafond_transport": "plafond annuel des frais de transport : alerte (17/11)",
        "ranger_les_saisies": "primes, frais, participations, IJSS et acomptes saisis : une seule fonction (17/11)",
        "_stamp_source_absence_conges": "les absences validées du calendrier",
        "_heures_sup_conjoncturelles_from_monthly_inputs": "les heures sup saisies au mois",
        "notes_de_frais_dans_le_mns": "le réglage des notes de frais",
        "entree_de_note_de_frais": "les notes de frais validées",
        "donnees_ppv_du_mois": "la prime de partage de la valeur",
        "raison_de_cumul_manquant": "un cumul absent ne vaut pas zéro",
        "detail_du_refus": "le refus structuré d'un cumul manquant",
        "alerte_depart_a_zero": "« générer quand même » depuis zéro",
        "cumuls_de_depart": "les cumuls du bac à sable",
        "cumuls_precedents_du_contrat": "premier mois d'un contrat : ses cumuls",
        "preparer_cumuls_dixieme": "la base du dixième des congés",
        "base_precarite_du_bulletin": "la base de l'indemnité de fin de CDD",
        "prepare_salary_evolution_for_payslip": "le salaire daté du mois",
        "inject_loan_benefit_in_kind": "l'avantage d'un prêt",
        "normalize_classification_for_payroll": "la classification",
        "build_convention_collective_payload": "la convention collective",
        "resolve_monthly_specificites": "les spécificités de paie du mois",
        "get_jei_settings_raw": "le réglage JEI",
        "get_prime_anciennete_overrides_for_payslip": "le réglage de prime d'ancienneté",
        "effectif_retenu": "l'effectif des seuils de l'année",
        "alerte_effectif": "l'alerte d'effectif",
        "alerte_franchissement_seuil": "l'alerte de franchissement de seuil",
        "resoudre_fenetre_variables": "la fenêtre des variables de la société",
        "payroll_engine_root": "le dossier du moteur",
        "nouveau_dossier_de_travail": "un dossier par génération",
        "supprimer_dossier_de_travail": "le dossier effacé après",
        "ouvrir_collecte": "les replis notés pendant le calcul",
        "fermer_collecte": "fin de la collecte des replis",
        "fusionner_replis": "les replis sur le bulletin",
        "alertes_de_doublon_de_prime": "une prime saisie deux fois",
        "alertes_d_entree_courantes": "ce que la fiche oublie (prévoyance, mutuelle)",
        "poser_empreinte_depuis_lectures": "l'empreinte des entrées",
        "empreinte_cumuls": "l'empreinte des cumuls lus",
        "poser_empreinte_cumuls": "l'empreinte des cumuls sur le bulletin",
        "poser_empreinte_complementaire_depuis_lectures": "l'empreinte complémentaire",
        "alerte_mois_passe_fiche_du_jour": "un mois passé relu sur la fiche du jour",
        "avertissements_de_generation": "les avertissements rendus à l'écran",
        "montants_du_bulletin": "les montants rendus à l'écran",
        "suffixe_du_pdf": "le nom du PDF d'un contrat rangé",
        "chemin_enregistre": "le PDF remplacé",
        "chemin_horodate": "le chemin du nouveau PDF",
        "retirer_pdf_remplace": "l'ancien PDF retiré",
        "html_imprime": "le HTML imprimé gardé",
        "enrich_payslip_after_upsert": "prêts et avances après l'enregistrement",
        "ecrire_colonnes_paie_du_mois": "les cumuls du mois écrits",
        "noter_repli": "un repli de calcul noté",
        "_parse_if_json_string": "les colonnes JSON lues en texte",
        "is_forfait_jour": "la lecture du forfait jours",
        "lignes_du_calendrier": "l'activité partielle posée au calendrier (Lyon, 17/11)",
        "alerte_arret_sans_demande": "arrêt posé au calendrier sans demande, ou sans type : alerte",
        "alerte_arrets_contradictoires": "subrogation contradictoire entre deux arrêts : alerte",
        "ecarter_apres_la_sortie": "rien après la sortie (au forfait : pour l'activité partielle)",
        "date_de_sortie": "la date de sortie du planning",
        "alerte_planning_apres_sortie": "le planning laissé après la sortie est dit (17/11)",
        "variables_automatiques_avant_bulletin": "variables automatiques avant le bulletin, réglage de la société (17/11)",
    },
    "moteur": {
        "baremes_de_l_annee": "les barèmes de l'année du bulletin",
        "controler_annee_des_baremes": "barèmes d'une autre année : alerte",
        "controler_baremes_sans_annee": "barèmes sans année : alerte",
        "controler_jour_solidarite": "la journée de solidarité",
        "definir_periode_de_paie": "la période de paie de la société",
        "bornes_mois_civil": "le mois civil du bulletin",
        "creer_calendrier_etendu": "le calendrier de la période",
        "frais_et_reintegration": "les frais professionnels au net, et leur part réintégrée",
        "panier_non_soumis_plafonne": "le panier non soumis au-delà du plafond Urssaf",
        "heures_et_taux": "indemnité d'activité partielle : heures et taux sur la ligne",
        "build_rappel_ijss_net_prime": "le rappel d'IJSS au net",
        "appliquer_exoneration_note_frais": "le plafond d'une note de frais",
        "lier_a_la_saisie": "la ligne liée à sa saisie",
        "est_une_ppv": "la PPV reconnue",
        "classer_ppv": "la PPV rangée (exonérée, imposable, cotisée)",
        "alerte_prime_soumise_imposee": "prime cotisée non imposable : alerte",
        "compute_participation_csg": "la CSG de la participation",
        "_extraire_arret_pour_maintien": "l'arrêt du mois pour le maintien",
        "poser_les_arrets_connus": "les arrêts enregistrés",
        "prefetch_jours_maintien_prime": "les jours maintenus des primes",
        "get_maintenance_settings": "le réglage du maintien",
        "poser_salaires_de_reference": "les salaires de référence des IJSS",
        "calculer_maintien": "le maintien de salaire",
        "signaler_repli": "un repli signalé sur le bulletin",
        "_appliquer_maintien_arret_maladie": "maintien et IJSS dans le brut et le net",
        "corriger_les_lignes_de_gain": "corrections des lignes de gain",
        "synchroniser_le_maintien": "maintien corrigé à la main",
        "ratio_plafond_periode": "le plafond de la sécurité sociale au prorata",
        "jours_maintenus_du_mois": "jours maintenus dans le plafond",
        "calculer_cotisations": "les cotisations",
        "heures_retablies_par_les_rappels_de_maintien": "rappels de maintien et SMIC de référence",
        "signaler_rappels_de_maintien_en_prime_libre": "rappel de maintien saisi en prime : alerte",
        "calculer_exoneration_jei": "l'exonération JEI",
        "jei_applicable": "JEI ou réduction générale",
        "calculer_reduction_generale": "la réduction générale",
        "signaler_ecart_d_ouverture_au_premier_mois": "écart d'ouverture de la réduction",
        "corriger_les_lignes_de_cotisation": "corrections des cotisations",
        "ajouter_regularisations": "régularisations de cotisation",
        "calculer_net_et_impot": "le net et l'impôt",
        "comparer_taux_vm_entreprise": "le versement mobilité de la commune",
        "commune_entreprise_depuis_donnees": "la commune de la société",
        "creer_bulletin_final": "le bulletin",
        "creer_bulletin_sortie": "le bulletin de sortie",
        "poser_les_corrections_en_attente": "correction sans ligne : reste sur le bulletin",
        "mettre_a_jour_cumuls": "les cumuls du mois",
        "imprimer_le_bulletin": "le PDF",
        "arrets_de_l_annee": "carence payée N jours par an : les arrêts de l'année (17/11)",
        "fin_de_la_reprise_au_premier_mois": "premier mois après une reprise : absences déjà traitées (17/11)",
    },
}

TROUS_DU_FORFAIT: dict[str, dict[str, str]] = {
    # Tous comblés le 17/11 au soir ; une étape ajoutée aux heures seulement,
    # qui concerne aussi le forfait, s'inscrit ici en attendant d'être branchée.
    "generateur": {},
    "moteur": {},
}

HEURES_SEULEMENT: dict[str, dict[str, str]] = {
    "generateur": {
        "ecarter_heures_sur_arret": "heures pointées sur un arrêt : le forfait ne paie pas d'heures",
        "alerte_heures_ecartees": "idem, l'alerte des heures écartées",
        "appliquer_repli_sans_pointage_par_mois": "mois sans pointage : le forfait ne pointe pas",
        "alerte_mois_sans_pointage": "idem",
        "resolve_effective_weekly_hours_map": "modulation des heures hebdomadaires",
        "payroll_analyzer_analyser": "analyse des heures ; le forfait analyse ses jours dans le moteur",
        "regularisation_events_from_calendar": "régularisations d'heures d'un mois passé",
        "option_active": "compensation des heures entre semaines",
        "s_applique_au_contrat": "idem",
        "bornes_du_contrat": "idem",
        "debut_du_contrat_en_cours": "idem",
        "alerte_semaines_a_zero": "idem",
        "appliquer_aux_mois": "idem",
        "aggregate_shift_payroll_metrics": "heures de nuit et pauses du planning d'équipe",
        "est_declaration_bulletin": "heures sup déclarées depuis le bulletin",
        "enrich_payroll_events_metadata": "compteur de modulation",
        "recalculer_credits_repos_employe": "repos compensateur des heures sup",
        "avec_repli": "repli du repos compensateur",
        "_build_temps_travail_payload": "temps de travail en heures (le forfait a le sien)",
        "log_payroll_debug": "traces de mise au point",
        "run_payslip_generation_heures": "le moteur des heures",
        "fin_au_depart": "mois de sortie, fenêtre des variables jusqu'au départ : le forfait calcule sur la période de paie et le départ au mois civil",
    },
    "moteur": {
        "apply_modulation_hour_account_to_calendar": "compteur de récupération des heures sup",
        "finalize_modulation_payroll_application": "idem",
        "compute_pay_smoothing_gain": "lissage de la modulation",
        "etat_recuperation_du_bulletin": "pied du bulletin : compteur de récupération",
        "apply_cet_deposits_to_calendar": "CET en heures",
        "apply_cet_withdrawals_to_calendar": "idem",
        "apply_cet_cp_debits_for_payroll": "idem",
        "finalize_cet_payroll_application": "idem",
        "get_cet_settings_row": "idem",
        "etat_cet_du_bulletin": "idem",
        "get_company_planning_settings": "pauses payées du planning",
        "calculer_salaire_brut": "le brut en heures (le forfait a le sien)",
        "evenements_de_la_periode": "idem",
        "jours_prevus_autour_du_mois": "horaire d'un mois d'entrée ou de sortie",
        "poser_le_depart_du_mois": "le forfait passe par poser_le_depart_du_forfait",
        "heures_sup_saisies": "heures sup saisies",
        "_taux_majoration_hs": "majoration des heures sup",
        "_get_salaire_horaire_base": "taux horaire",
        "salaire_du_mois_complet": "complément d'absence intégrale en heures",
        "saisie_paiement_solde": "paiement du solde du compteur",
    },
}

FORFAIT_SEULEMENT: dict[str, dict[str, str]] = {
    "generateur": {
        "_periode_de_paie_company": "période de paie de la société",
        "bornes_periode_de_paie": "activité partielle sur la période de paie (aux heures : la fenêtre des variables)",
        "message_pas_forfait_jour": "refus d'un salarié qui n'est pas au forfait",
        "run_payslip_generation_forfait": "le moteur du forfait jours",
    },
    "moteur": {
        "analyser_jours_forfait_du_mois": "les jours du forfait",
        "calculer_salaire_brut_forfait": "le brut du forfait",
        "bornes_de_la_sortie": "prorata de sortie au forfait",
        "get_forfait_annual_days_adjusted": "forfait réduit des congés d'ancienneté",
        "jours_du_forfait_pour_reduction": "jours du forfait pour la réduction générale",
        "heures_reduction_du_mois": "SMIC de référence du forfait",
        "heures_reduction_forfait_jours": "idem",
        "poser_le_depart_du_forfait": "le départ au mois civil",
        "message_pas_forfait_jour": "refus d'un salarié qui n'est pas au forfait",
        "absences_hors_reprise": "la période du forfait déborde sur le mois repris : ses absences en sortent (aux heures : dans calcul_brut)",
    },
}


def _cas(listes: dict[str, dict[str, str]]):
    return [
        pytest.param(chemin, etape, id=f"{chemin}:{etape}")
        for chemin, etapes in listes.items()
        for etape in etapes
    ]


def _appels(chemin: str) -> tuple[set[str], set[str]]:
    (mod_h, fn_h), (mod_f, fn_f) = CHEMINS[chemin]
    return _appels_metier(mod_h, fn_h), _appels_metier(mod_f, fn_f)


@pytest.mark.parametrize(("chemin", "etape"), _cas(COMMUNES))
def test_une_etape_commune_est_appelee_des_deux_cotes(chemin, etape):
    heures, forfait = _appels(chemin)
    assert etape in heures, f"{etape} n'est plus appelée côté heures ({chemin})"
    assert etape in forfait, f"{etape} n'est plus appelée côté forfait jours ({chemin})"


@pytest.mark.parametrize(
    ("chemin", "etape"),
    [
        pytest.param(
            *p.values,
            id=p.id,
            marks=pytest.mark.xfail(strict=True, reason="trou connu du forfait jours (audit du 17/11)"),
        )
        for p in _cas(TROUS_DU_FORFAIT)
    ],
)
def test_un_trou_du_forfait_est_comble(chemin, etape):
    """XPASS = le trou est comblé : passer l'étape dans `COMMUNES`."""
    heures, forfait = _appels(chemin)
    assert etape in heures
    assert etape in forfait


@pytest.mark.parametrize("chemin", list(CHEMINS))
def test_toute_etape_d_un_seul_generateur_est_rangee(chemin):
    heures, forfait = _appels(chemin)
    rangees_heures = set(TROUS_DU_FORFAIT[chemin]) | set(HEURES_SEULEMENT[chemin])
    non_rangees = sorted((heures - forfait) - rangees_heures)
    assert not non_rangees, (
        f"Étapes appelées côté heures seulement, sans décision ({chemin}) : {non_rangees}. "
        "Branchez-les aussi au forfait jours, ou ajoutez-les à HEURES_SEULEMENT avec leur raison."
    )
    non_rangees = sorted((forfait - heures) - set(FORFAIT_SEULEMENT[chemin]))
    assert not non_rangees, (
        f"Étapes appelées côté forfait jours seulement, sans décision ({chemin}) : {non_rangees}. "
        "Branchez-les aussi aux heures, ou ajoutez-les à FORFAIT_SEULEMENT avec leur raison."
    )


@pytest.mark.parametrize("chemin", list(CHEMINS))
def test_les_listes_ne_portent_que_des_etapes_reelles(chemin):
    """Une étape renommée ou retirée sort des listes : elles restent vraies."""
    heures, forfait = _appels(chemin)
    tout = heures | forfait
    for nom, liste in (
        ("COMMUNES", COMMUNES),
        ("TROUS_DU_FORFAIT", TROUS_DU_FORFAIT),
        ("HEURES_SEULEMENT", HEURES_SEULEMENT),
        ("FORFAIT_SEULEMENT", FORFAIT_SEULEMENT),
    ):
        fantomes = sorted(set(liste[chemin]) - tout)
        assert not fantomes, f"{nom}[{chemin}] cite des étapes qui n'existent plus : {fantomes}"
