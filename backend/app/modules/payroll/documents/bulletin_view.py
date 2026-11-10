"""Vue de présentation du bulletin de paie — gabarit Cegid.

Transforme le `bulletin_final` produit par le moteur en boîtes prêtes à
afficher. Fonction pure : aucun accès base, fichier ou horloge, tout vient du
dictionnaire reçu. C'est le seul endroit où vivent les replis, les agrégations
et le formatage — le template ne fait que parcourir le résultat.
"""

from __future__ import annotations

import calendar
from typing import Any, Dict, List, Optional

from app.modules.payroll.domain.report_nap_negatif import (
    CLE_BULLETIN as CLE_REPORTS_NAP_NEGATIF,
)
from app.modules.payroll.engine.corrections_manuelles import mentions_des_regularisations
from app.modules.payroll.engine.corrections_du_bulletin import mentions_des_corrections
from app.modules.payroll.domain.ijss_deduites import mention_ijss_deduites

CIVILITES_MASCULINES = {"M", "H", "MR", "MASCULIN", "1"}
CIVILITES_FEMININES = {"F", "MME", "FEMININ", "FÉMININ", "2"}

# Découpage du NIR tel que Cegid l'imprime : 1 80 01 75 200 456 78
GROUPES_NIR = (1, 2, 2, 2, 3, 3, 2)

# Codes de rubriques du bulletin Cegid. Vérifiés sur les bulletins de juin 2026
# des sept sociétés : ce sont les seuls utilisés, il n'existe pas de Q700.
# La prévoyance et la mutuelle n'ont pas de code chez Cegid (références de
# contrat internes à son paramétrage) : elles restent sans code chez nous.
CODES_CEGID: Dict[str, str] = {
    "sante": "Q100",
    "at_mp": "Q200",
    "retraite": "Q300",
    "famille": "Q400",
    "chomage": "Q500",
    "autres_contributions_employeur": "Q600",
    "csg_deductible": "Q800",
    "csg_non_deductible": "Q801",
    "exonerations": "Q802",
}

LIBELLES_CEGID: Dict[str, str] = {
    "sante": "SANTÉ",
    "at_mp": "AT-MP",
    "retraite": "RETRAITE",
    "famille": "FAMILLE",
    "chomage": "ASSURANCE CHÔMAGE",
    "autres_contributions_employeur": "AUTRES CONTRIB. DUES PAR EMPL.",
    "cotisations_statutaires": "COTISATIONS STATUTAIRES ET CONVENTIONNELLES",
    "csg_deductible": "CSG DÉDUCTIBLE À L'IR",
    "csg_non_deductible": "CSG/CRDS NON DÉDUCTIBLE À L'IR",
    "exonerations": "EXO., ÉCRÊT. ET ALLÈG. COTIS",
}

# La CSG/CRDS non déductible est imprimée après le net imposable et n'entre pas
# dans le total des retenues (vérifié sur CARTOL juin 2026 : 308,14 sans elle).
RUBRIQUE_APRES_NET_IMPOSABLE = "csg_non_deductible"

# Cotisations salariales supprimées en 2018 (maladie 0,75 % + chômage 2,40 %)
# et hausse de CSG qui les a compensées (1,7 %). Formule retrouvée sur le
# bulletin CARTOL de juin 2026, exacte au centime.
TAUX_COTISATIONS_SUPPRIMEES = 0.0315
TAUX_HAUSSE_CSG = 0.017

MENTION_EVOLUTION_REMUNERATION = (
    "dont évolution de la rémunération liée à la suppression des cotisations "
    "salariales chômage et maladie"
)

#: Modèle du bulletin : article 1er de l'arrêté du 25/02/2016 modifié par l'arrêté
#: du 31/01/2023 (JORF du 07/02/2023, texte 18, lu le 09/11/2026). Le modèle dit
#: adapté de son article 2, avec la ligne « dont évolution… », reste permis jusqu'au
#: 01/01/2027 (arrêté du 11/08/2025, JO du 14/08/2025 ; Éditions Tissot, PayFit,
#: Légifrance refusant la lecture). Aucune date plus tardive trouvée au 09/11/2026 ;
#: un bulletin de décembre 2026 et les précédents restent inchangés.
PREMIER_MOIS_MODELE_DEFINITIF = (2027, 1)

LIBELLES_MODELE_DEFINITIF: Dict[str, str] = {
    "sante": "Santé",
    "at_mp": "Accidents du travail & maladies professionnelles",
    "retraite": "Retraite",
    "famille": "Famille",
    "chomage": "Assurance chômage",
    "autres_contributions_employeur": "Autres charges dues par l'employeur",
    "cotisations_statutaires": "Cotisations statutaires ou prévues par la convention collective",
    "csg_deductible": "CSG déductible de l'impôt sur le revenu",
    "csg_non_deductible": "CSG/CRDS non déductible de l'impôt sur le revenu",
}

#: Lignes de la section « facultatives » du modèle. La prévoyance d'un cadre ou
#: d'une convention reste dans « Cotisations statutaires ou prévues par la
#: convention collective », là où le moteur la range.
COTI_FACULTATIVES = frozenset({"prevoyance", "retraite_sup"})


def modele_definitif(bulletin: Dict[str, Any]) -> bool:
    """Ce bulletin suit-il le modèle définitif (paie de janvier 2027 et après) ?"""
    en_tete = bulletin.get("en_tete") or {}
    try:
        return (int(en_tete.get("annee")), int(en_tete.get("mois"))) >= PREMIER_MOIS_MODELE_DEFINITIF
    except (TypeError, ValueError):
        return False


MODES_PAIEMENT = {
    "virement": "par Virement",
    "cheque": "par Chèque",
    "chèque": "par Chèque",
    "especes": "en Espèces",
    "espèces": "en Espèces",
}


def _civilite(sexe: Any) -> Optional[str]:
    valeur = str(sexe or "").strip().upper()
    if valeur in CIVILITES_MASCULINES:
        return "MR"
    if valeur in CIVILITES_FEMININES:
        return "MME"
    return None


def _formater_nir(valeur: Any) -> str:
    brut = "".join(c for c in str(valeur or "") if c.isalnum()).upper()
    if len(brut) != 15:
        return brut
    morceaux: List[str] = []
    position = 0
    for taille in GROUPES_NIR:
        morceaux.append(brut[position : position + taille])
        position += taille
    return " ".join(morceaux)


def _date_fr(valeur: Any) -> str:
    if not valeur:
        return ""
    texte = str(valeur)[:10]
    if len(texte) == 10 and texte[4] == "-" and texte[7] == "-":
        return f"{texte[8:10]}/{texte[5:7]}/{texte[0:4]}"
    return texte


def _lignes_adresse(adresse: Any) -> List[str]:
    """Adresse postale sur deux lignes : rue, puis code postal + ville."""
    if not isinstance(adresse, dict):
        return []
    lignes: List[str] = []
    rue = str(adresse.get("rue") or "").strip()
    if rue:
        lignes.append(rue)
    localite = f"{adresse.get('code_postal') or ''} {adresse.get('ville') or ''}".strip()
    if localite:
        lignes.append(localite)
    return lignes


def construire_bandeau(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    en_tete = bulletin.get("en_tete") or {}
    entreprise = en_tete.get("entreprise") or {}
    annee = en_tete.get("annee")
    mois = en_tete.get("mois")
    du = au = ""
    variables = ""
    # Le bulletin porte le mois civil — c'est ce que la gestionnaire de paie
    # lit et ce que fait le cabinet. La fenêtre des variables (heures sup,
    # paniers) s'affiche à part, et seulement quand elle en diffère.
    debut_periode = _date_fr(en_tete.get("date_debut_periode"))
    fin_periode = _date_fr(en_tete.get("date_fin_periode"))
    if annee and mois:
        dernier_jour = calendar.monthrange(int(annee), int(mois))[1]
        du = f"01/{int(mois):02d}/{int(annee)}"
        au = f"{dernier_jour:02d}/{int(mois):02d}/{int(annee)}"
    elif debut_periode and fin_periode:
        du = debut_periode
        au = fin_periode
    # Bulletin de sortie : la période s'arrête au dernier jour du contrat
    # (C. trav. R3243-1 5°). Ce n'est pas le reçu pour solde de tout compte,
    # document distinct (L1234-20).
    sortie = ""
    date_sortie = _date_fr(en_tete.get("date_sortie"))
    if date_sortie and bulletin.get("bulletin_de_sortie"):
        au = date_sortie
        sortie = f"Bulletin de sortie : dernier jour du contrat le {date_sortie}"
    debut_variables = _date_fr(en_tete.get("date_debut_variables"))
    fin_variables = _date_fr(en_tete.get("date_fin_variables"))
    if (
        debut_variables
        and fin_variables
        and (debut_variables, fin_variables) != (du, au)
    ):
        variables = f"du {debut_variables} au {fin_variables}"
    return {
        "raison_sociale": entreprise.get("raison_sociale") or "",
        "adresse": _lignes_adresse(entreprise.get("adresse")),
        "siret": entreprise.get("siret") or "",
        "naf_ape": entreprise.get("naf_ape") or "",
        "periode": en_tete.get("periode") or "",
        # Le moteur produit une date ISO ; le bulletin s'imprime en français.
        "date_paiement": _date_fr(en_tete.get("date_paiement")),
        "du": du,
        "au": au,
        "variables": variables,
        "sortie": sortie,
    }


def construire_salarie(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    salarie = ((bulletin.get("en_tete") or {}).get("salarie")) or {}
    nom = str(salarie.get("nom") or "").strip()
    prenom = str(salarie.get("prenom") or "").strip()
    if nom:
        nom_ligne = f"{nom.upper()} {prenom}".strip()
    else:
        nom_ligne = str(salarie.get("nom_complet") or "").strip()
    return {
        "civilite": _civilite(salarie.get("sexe")),
        "nom_ligne": nom_ligne,
        "adresse": _lignes_adresse(salarie.get("adresse")),
    }


#: C. trav. R3243-1, 3° : à défaut de convention, « la référence au code du travail
#: pour les dispositions relatives à la durée des congés payés du salarié et à la
#: durée des délais de préavis ». Articles ouverts le 09/11/2026.
REFERENCE_CODE_DU_TRAVAIL = (
    "Sans convention collective : durée des congés payés, C. trav. art. L3141-3 ; "
    "délais de préavis, C. trav. art. L1234-1 et L1237-1."
)


def sans_convention_collective(salarie: Dict[str, Any]) -> bool:
    """Le salarié ne relève d'aucune convention : IDCC 9999, celui de la DSN.

    Une convention simplement absente du bulletin n'est pas ce cas : on ne
    remplace pas un intitulé qu'on n'a pas su lire par le Code du travail.
    """
    convention = str(salarie.get("convention_collective") or "")
    if convention:
        return "9999" in convention
    classification = salarie.get("classification_brute")
    if not isinstance(classification, dict):
        return False
    return str(classification.get("idcc") or "").strip() == "9999"


def construire_identite(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    salarie = ((bulletin.get("en_tete") or {}).get("salarie")) or {}
    classification = salarie.get("classification_brute")
    if not isinstance(classification, dict):
        classification = {}
    # R3243-1, 4° : la position « dans la classification conventionnelle qui lui
    # est applicable ». Sans convention il n'y en a pas : le « 200 » de ces fiches
    # vient d'une valeur par défaut de la DSN, pas d'une classification.
    sans_convention = sans_convention_collective(salarie)
    date_entree = _date_fr(salarie.get("date_entree"))
    return {
        "matricule": salarie.get("matricule") or "",
        "nir": _formater_nir(salarie.get("nir")),
        "date_entree": date_entree,
        "emploi": salarie.get("emploi") or "",
        # Repli documenté : 81 actifs sur 241 n'ont pas de date de reprise
        # d'ancienneté, leur ancienneté part de la date d'entrée.
        "anciennete": _date_fr(salarie.get("date_anciennete")) or date_entree,
        # Volontairement pas de repli sur `statut_categoriel` : il contredit
        # `employees.statut` sur une partie des fiches (salarié 004, opérateur
        # polyvalent, y est « Cadre » alors que la paie le traite en non-cadre).
        # Cegid laisse d'ailleurs la case vide. Mieux vaut rien qu'un faux.
        "qualification": classification.get("qualification") or "",
        # Repli sur la chaîne déjà formatée par le moteur : les vraies fiches
        # ne portent ni « niveau » ni « coefficient » mais des clés DSN
        # (position, niveau_dsn). Ne jamais afficher moins que l'ancien bulletin.
        "classification": ""
        if sans_convention
        else (
            classification.get("niveau")
            or classification.get("niveau_dsn")
            or classification.get("classification")
            or salarie.get("classification")
            or ""
        ),
        "coefficient": "" if sans_convention else classification.get("coefficient") or "",
    }


def _colonne_compteur(titre: str, compteur: Any) -> Dict[str, Any]:
    donnees = compteur if isinstance(compteur, dict) else {}
    return {
        "titre": titre,
        "acquis": float(donnees.get("acquis") or 0.0),
        "pris": float(donnees.get("pris") or 0.0),
        "solde": float(donnees.get("solde") or 0.0),
    }


def _compteur_alimente(compteur: Any) -> bool:
    donnees = compteur if isinstance(compteur, dict) else {}
    return any(float(donnees.get(cle) or 0.0) for cle in ("acquis", "pris", "solde"))


def heures_en_texte(heures: Any) -> str:
    from app.modules.modulation.domain.hour_account_rules import heures_en_texte as texte

    return texte(float(heures or 0))


def _notes_recuperation(recuperation: Dict[str, Any]) -> List[str]:
    """Le détail du mois (acquises, prises avec leur date, payées), et dès 7 h
    la mention de l'ouverture du droit et du délai de deux mois (C. trav.
    D3171-11)."""
    notes: List[str] = []
    morceaux: List[str] = []
    acquis = float(recuperation.get("acquis") or 0.0)
    if acquis > 0:
        morceaux.append(f"{heures_en_texte(acquis)} acquises")
    prises = [p for p in recuperation.get("prises") or [] if isinstance(p, dict)]
    if prises:
        dates = []
        for prise in prises:
            jour = str(prise.get("date") or "")[:10]
            date_courte = f"{jour[8:10]}/{jour[5:7]}" if len(jour) == 10 else jour
            dates.append(f"{heures_en_texte(prise.get('heures') or 0)} prises le {date_courte}")
        morceaux.append(", ".join(dates))
    elif float(recuperation.get("pris") or 0.0) > 0:
        morceaux.append(f"{heures_en_texte(recuperation['pris'])} prises")
    paye = float(recuperation.get("paye") or 0.0)
    if paye > 0:
        morceaux.append(f"{heures_en_texte(paye)} payées")
    if morceaux:
        notes.append("Récupération ce mois-ci : " + ", ".join(morceaux))
    return notes


def _releve_de_la_plasturgie(salarie: Dict[str, Any]) -> bool:
    """IDCC 292, lu sur l'intitulé imprimé ou sur la classification."""
    convention = str(salarie.get("convention_collective") or "").lower()
    if "plasturgie" in convention or "0292" in convention:
        return True
    classification = salarie.get("classification_brute")
    if not isinstance(classification, dict):
        return False
    return str(classification.get("idcc") or "").strip().lstrip("0") == "292"


def _note_droit_a_repos(
    solde_conges: Dict[str, Any], *, plasturgie: bool = False
) -> Optional[str]:
    """C. trav. D3171-11 : dès sept heures de repos compensateur de remplacement et
    de contrepartie obligatoire en repos portées au crédit, cumulées, le document
    notifie l'ouverture du droit et l'obligation de le prendre sous deux mois,
    « à défaut de précision conventionnelle contraire ».

    Plasturgie, repos de remplacement seul (fiche du Code du travail numérique
    292-heures-supplementaires, ouverte le 09/11/2026 ; texte de branche non lu,
    Légifrance refusant la lecture) : règles fixées dans l'entreprise, délai
    « minimum de 2 mois et maximum de 6 mois ». Le repos obligatoire reste à
    deux mois d'après la même fiche : s'il y en a, la mention stricte demeure."""
    recuperation = solde_conges.get("recuperation")
    obligatoire = solde_conges.get("repos_compensateur")
    solde_recup = (
        float(recuperation.get("solde") or 0.0) if isinstance(recuperation, dict) else 0.0
    )
    solde_obligatoire = (
        float(obligatoire.get("solde") or 0.0) if isinstance(obligatoire, dict) else 0.0
    )
    parts = []
    if solde_recup > 0:
        parts.append(f"{heures_en_texte(solde_recup)} de récupération")
    if solde_obligatoire > 0:
        parts.append(f"{heures_en_texte(solde_obligatoire)} de repos obligatoire")
    if max(solde_recup, 0.0) + max(solde_obligatoire, 0.0) < 7:
        return None
    if plasturgie and solde_obligatoire <= 0:
        return (
            f"Droit à repos ouvert : {' et '.join(parts)} à prendre dans le délai "
            "fixé par l'entreprise, de deux à six mois (convention de la plasturgie)."
        )
    return (
        f"Droit à repos ouvert : {' et '.join(parts)} à prendre dans un délai "
        "maximum de deux mois (C. trav. D3171-11)."
    )


def construire_compteurs(bulletin: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    solde = ((bulletin.get("pied_de_page") or {}).get("solde_conges")) or {}
    if not solde:
        return None

    colonnes: List[Dict[str, Any]] = []
    precedente = solde.get("conges_payes_periode_precedente")
    if _compteur_alimente(precedente):
        colonnes.append(_colonne_compteur("CP N-1", precedente))
    colonnes.append(_colonne_compteur("CP N", solde.get("conges_payes")))
    if _compteur_alimente(solde.get("rtt")):
        colonnes.append(_colonne_compteur("RTT", solde.get("rtt")))
    # Compteur distinct, jamais fondu dans le total CP (note JTC, § 7).
    if _compteur_alimente(solde.get("jtc")):
        colonnes.append(_colonne_compteur("JTC", solde.get("jtc")))
    if _compteur_alimente(solde.get("repos_compensateur")):
        colonnes.append(
            _colonne_compteur("Repos comp. (h)", solde.get("repos_compensateur"))
        )
    # Heures de récupération (repos compensateur de remplacement) : présent dès
    # que le réglage de la société est actif, même à zéro (C. trav. D3171-11).
    recuperation = solde.get("recuperation")
    if isinstance(recuperation, dict):
        # Le tableau se lit en cumul, comme les congés : acquis et pris de
        # l'année ; le détail du mois va en note.
        colonnes.append(
            {
                "titre": "Récup. (h)",
                "acquis": float(recuperation.get("acquis_annee", recuperation.get("acquis")) or 0.0),
                "pris": float(recuperation.get("pris_annee", recuperation.get("pris")) or 0.0),
                "solde": float(recuperation.get("solde") or 0.0),
            }
        )

    # Accord CET de Mont Blanc : « l'état des différents compteurs du CET figurera
    # sur le bulletin de paie » (posé quand le salarié a un CET ; R-376).
    cet = solde.get("cet")
    if isinstance(cet, dict):
        colonnes.append(
            {
                "titre": "CET (h)",
                "acquis": float(cet.get("acquis") or 0.0),
                "pris": float(cet.get("pris") or 0.0),
                "solde": float(cet.get("solde") or 0.0),
            }
        )

    notes: List[str] = []
    if isinstance(recuperation, dict):
        notes.extend(_notes_recuperation(recuperation))
    en_tete = bulletin.get("en_tete")
    salarie = (en_tete.get("salarie") if isinstance(en_tete, dict) else None) or {}
    droit_a_repos = _note_droit_a_repos(
        solde, plasturgie=_releve_de_la_plasturgie(salarie)
    )
    if droit_a_repos:
        notes.append(droit_a_repos)
    # Reprise ou recalage : le solde ne se retrouve plus par « acquis − pris ».
    # La clé n'existe que sur les bulletins calculés depuis le 12/10/2026.
    for titre, cle in (("CP N-1", "conges_payes_periode_precedente"), ("CP N", "conges_payes")):
        compteur = solde.get(cle) if isinstance(solde.get(cle), dict) else {}
        indemnise = float(compteur.get("indemnise") or 0.0)
        if indemnise >= 0.01:
            jours = f"{indemnise:.2f}".rstrip("0").rstrip(".").replace(".", ",")
            payes = "payés" if indemnise >= 2 else "payé"
            notes.append(
                f"{titre} : {jours} j {payes} en indemnité compensatrice de congés "
                "payés au départ, solde à zéro"
            )
        ajustement = float(compteur.get("ajustement") or 0.0)
        if abs(ajustement) >= 0.01:
            signe = "+" if ajustement > 0 else "−"
            valeur = f"{abs(ajustement):.2f}".replace(".", ",")
            notes.append(f"{titre} : solde dont ajustement de {signe}{valeur} j (reprise ou recalage)")
    fractionnement = solde.get("fractionnement") or {}
    if float(fractionnement.get("jours_acquis") or 0) > 0:
        libelle = fractionnement.get("libelle") or "Jours de fractionnement"
        reference = fractionnement.get("reference_date")
        notes.append(f"{libelle} (réf. {reference})" if reference else str(libelle))
    jours_anciennete = float(solde.get("cp_seniority_days") or 0)
    if jours_anciennete > 0:
        notes.append(f"Dont {jours_anciennete:.0f} j CP ancienneté conventionnels")
    if solde.get("cp_seniority_forfait_note"):
        notes.append(str(solde["cp_seniority_forfait_note"]))

    return {
        "date_reference": solde.get("date_reference") or "",
        "colonnes": colonnes,
        "notes": notes,
    }


def _ligne(
    type_ligne: str,
    libelle: str,
    *,
    code: Optional[str] = None,
    base: Optional[float] = None,
    taux: Optional[float] = None,
    montant_salarial: Optional[float] = None,
    montant_patronal: Optional[float] = None,
) -> Dict[str, Any]:
    return {
        "type": type_ligne,
        "code": code,
        "libelle": libelle,
        "base": base,
        "taux": taux,
        "montant_salarial": montant_salarial,
        "montant_patronal": montant_patronal,
    }


def _libelle_marque(source: Dict[str, Any]) -> str:
    """Une ligne corrigée à la main porte un astérisque ; sa note suit les cotisations."""
    libelle = source.get("libelle") or ""
    return f"{libelle} *" if isinstance(source.get("correction"), dict) else libelle


def _ligne_brut(source: Dict[str, Any]) -> Dict[str, Any]:
    """Une ligne de rémunération : le gain va au salarial, la perte le diminue."""
    gain = source.get("gain")
    perte = source.get("perte")
    montant = None
    if gain is not None:
        montant = float(gain)
    elif perte is not None:
        montant = -float(perte)
    return _ligne(
        "detail",
        _libelle_marque(source),
        base=source.get("quantite"),
        taux=source.get("taux"),
        montant_salarial=montant,
    )


def _montant_ou_vide(valeur: Any) -> Optional[float]:
    """Cegid laisse la case vide plutôt que d'imprimer un zéro."""
    montant = float(valeur or 0.0)
    return montant if montant else None


def _ligne_cotisation(source: Dict[str, Any]) -> Dict[str, Any]:
    # La colonne est celle du taux salarial : une cotisation purement patronale
    # n'y met rien, comme sur le bulletin du cabinet.
    taux = source.get("taux_salarial")
    return _ligne(
        "detail",
        _libelle_marque(source),
        base=source.get("base"),
        taux=float(taux) * 100 if taux is not None else None,
        montant_salarial=_montant_ou_vide(source.get("montant_salarial")),
        montant_patronal=_montant_ou_vide(source.get("montant_patronal")),
    )


#: C. trav. R3243-2, al. 2 (code.travail.gouv.fr, ouvert le 10/11/2026) : « Les
#: contributions autres que les contributions sociales mentionnées au a du 8° sont
#: également agrégées dans une seule rubrique, qui donne le montant total de cette
#: contribution. » Le modèle de l'arrêté du 25/02/2016 n'en a qu'une ligne. Le
#: détail (formation, CSA, dialogue social, FNAL, taxe d'apprentissage…) reste
#: dans le bulletin enregistré : écran « Bulletin », exports, DSN.
RUBRIQUE_AGREGEE = "autres_contributions_employeur"


def _ligne_agregee(rubrique: dict[str, Any], libelle: str, code: str | None = None) -> dict[str, Any]:
    """Une seule ligne au total de la rubrique, astérisque si une ligne a été corrigée."""
    lignes = [l for l in rubrique.get("lignes") or [] if isinstance(l, dict)]
    if any(isinstance(l.get("correction"), dict) for l in lignes):
        libelle = f"{libelle} *"
    salarial = round(sum(float(l.get("montant_salarial") or 0.0) for l in lignes), 2)
    patronal = round(sum(float(l.get("montant_patronal") or 0.0) for l in lignes), 2)
    return _ligne(
        "detail",
        libelle,
        code=code,
        montant_salarial=salarial or None,
        montant_patronal=patronal or None,
    )


def _lignes_rubrique(rubrique: Dict[str, Any]) -> List[Dict[str, Any]]:
    code = rubrique.get("code") or ""
    if code == RUBRIQUE_AGREGEE:
        return [_ligne_agregee(rubrique, LIBELLES_CEGID[code], CODES_CEGID.get(code))]
    entete = _ligne(
        "rubrique",
        LIBELLES_CEGID.get(code, str(rubrique.get("libelle") or "").upper()),
        code=CODES_CEGID.get(code),
    )
    details = [
        _ligne_cotisation(ligne)
        for ligne in rubrique.get("lignes") or []
        if isinstance(ligne, dict)
    ]
    return [entete, *details]


def _lignes_modele_definitif(
    bulletin: Dict[str, Any], rubriques: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Le corps du bulletin selon l'article 1er de l'arrêté : obligatoires, total,
    exonérations, facultatives. Ce qui suit (remboursements, nets) est au pied."""
    lignes = [_ligne("rubrique", "COTISATIONS ET CONTRIBUTIONS SOCIALES OBLIGATOIRES")]
    facultatives: List[Dict[str, Any]] = []
    total_salarial = total_patronal = 0.0
    exonerations: Optional[Dict[str, Any]] = None
    for rubrique in rubriques:
        code = rubrique.get("code") or ""
        if code == "exonerations":
            exonerations = rubrique
            continue
        gardees = []
        for ligne in rubrique.get("lignes") or []:
            if not isinstance(ligne, dict):
                continue
            if ligne.get("coti_id") in COTI_FACULTATIVES:
                facultatives.append(ligne)
            else:
                gardees.append(ligne)
                total_salarial += float(ligne.get("montant_salarial") or 0.0)
                total_patronal += float(ligne.get("montant_patronal") or 0.0)
        if gardees and code == RUBRIQUE_AGREGEE:
            lignes.append(
                _ligne_agregee({"lignes": gardees}, LIBELLES_MODELE_DEFINITIF[code])
            )
        elif gardees:
            lignes.append(
                _ligne("rubrique", LIBELLES_MODELE_DEFINITIF.get(code, str(rubrique.get("libelle") or "")))
            )
            lignes.extend(_ligne_cotisation(ligne) for ligne in gardees)

    for mention in mentions_des_regularisations(bulletin):
        lignes.append(_ligne("note", mention))
    for mention in mentions_des_corrections(bulletin):
        lignes.append(_ligne("note", mention))

    lignes.append(
        _ligne(
            "total",
            "TOTAL DES COTISATIONS ET CONTRIBUTIONS OBLIGATOIRES",
            montant_salarial=round(total_salarial, 2),
            montant_patronal=round(total_patronal, 2),
        )
    )
    if exonerations is not None:
        lignes.append(
            _ligne(
                "total",
                "EXONÉRATIONS ET ALLÈGEMENTS DE COTISATIONS",
                montant_salarial=exonerations.get("total_salarial"),
                montant_patronal=exonerations.get("total_patronal"),
            )
        )
    if facultatives:
        lignes.append(_ligne("rubrique", "COTISATIONS ET CONTRIBUTIONS SOCIALES FACULTATIVES"))
        lignes.extend(_ligne_cotisation(ligne) for ligne in facultatives)
    return lignes


LIBELLE_NOTES_DE_FRAIS = "Remboursement de frais"


def _est_une_note_de_frais(prime: Any) -> bool:
    """Une note de frais du module : `entree_de_note_de_frais` lui donne
    l'identifiant « remb_<type>_<date> », avec ou sans la marque des frais
    professionnels (Colorplast les garde dans le montant net social)."""
    return isinstance(prime, dict) and str(prime.get("prime_id") or "").startswith("remb_")


def _lignes_hors_brut(bulletin: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Ce qui s'ajoute ou se retient après le net imposable."""
    lignes: List[Dict[str, Any]] = []

    # Les notes de frais du module (« remb_<type>_<date> ») et l'ancienne clé
    # `notes_de_frais` : une seule ligne, à la place de la première note. Un
    # salarié en dépose une vingtaine par mois (retour du 10/11/2026) ; le détail
    # reste dans le bulletin enregistré et l'export comptable.
    total_frais = round(
        sum(
            float(p.get("montant") or 0.0)
            for p in bulletin.get("primes_non_soumises") or []
            if _est_une_note_de_frais(p)
        )
        + sum(
            float(n.get("montant") or 0.0)
            for n in bulletin.get("notes_de_frais") or []
            if isinstance(n, dict)
        ),
        2,
    )
    ligne_frais = _ligne("hors_brut", LIBELLE_NOTES_DE_FRAIS, montant_salarial=total_frais)
    frais_poses = False

    for prime in bulletin.get("primes_non_soumises") or []:
        if not isinstance(prime, dict):
            continue
        if _est_une_note_de_frais(prime):
            if not frais_poses:
                lignes.append(ligne_frais)
                frais_poses = True
            continue
        lignes.append(
            _ligne(
                "hors_brut",
                prime.get("libelle") or "Prime non soumise",
                montant_salarial=prime.get("montant"),
            )
        )

    # Revenus non soumis à cotisations mais imposables : indemnité d'activité
    # partielle, IJSS imposables. Bucket distinct des primes non soumises côté
    # moteur, donc sans risque de doublon ici.
    for revenu in bulletin.get("revenus_hors_brut_imposables") or []:
        if not isinstance(revenu, dict):
            continue
        montant = float(revenu.get("montant") or 0.0)
        if montant == 0:
            continue
        lignes.append(
            _ligne(
                "hors_brut",
                revenu.get("libelle") or "Revenu imposable non soumis",
                base=revenu.get("quantite"),
                taux=revenu.get("taux"),
                montant_salarial=montant,
            )
        )

    # Indemnités de rupture (licenciement, rupture conventionnelle, mise à la
    # retraite) : la part exclue des cotisations s'ajoute au net après elles. Sans
    # cette ligne, le bulletin ne disait pas d'où venait le net (rupture de
    # 5 000 € : 2 500 € au brut, 2 500 € nulle part, relevé du 12/10/2026).
    for indemnite in (bulletin.get("indemnites_sortie") or {}).get("lignes_exonerees") or []:
        if not isinstance(indemnite, dict):
            continue
        montant = float(indemnite.get("montant") or 0.0)
        if montant == 0:
            continue
        libelle = str(indemnite.get("libelle") or "Indemnité de rupture")
        lignes.append(
            _ligne(
                "hors_brut",
                f"{libelle} (part exonérée de cotisations)",
                montant_salarial=montant,
            )
        )

    if not frais_poses and any(isinstance(n, dict) for n in bulletin.get("notes_de_frais") or []):
        lignes.append(ligne_frais)

    synthese = bulletin.get("synthese_net") or {}
    for cle, libelle in (
        ("remboursement_transport", "Indemnité de transport"),
        ("indemnite_transport_fixe", "Indemnité transport contractuelle"),
    ):
        montant = float(synthese.get(cle) or 0.0)
        if montant > 0:
            lignes.append(_ligne("hors_brut", libelle, montant_salarial=montant))

    # L'avantage en nature, entré au brut, a été fourni en nature : il sort du
    # net à payer, et le bulletin le dit (net-entreprises, fiche 827).
    avantages_en_nature = float(synthese.get("avantages_en_nature") or 0.0)
    if avantages_en_nature > 0:
        lignes.append(
            _ligne(
                "hors_brut",
                "Avantages en nature (déduction)",
                montant_salarial=-avantages_en_nature,
            )
        )

    titres_restaurant = float(synthese.get("titres_restaurant") or 0.0)
    if titres_restaurant > 0:
        lignes.append(
            _ligne(
                "hors_brut",
                "Titres-restaurant (part salariale)",
                montant_salarial=-titres_restaurant,
            )
        )

    # Le report d'un net négatif est compté dans `acompte_verse` : il sort sous
    # son propre libellé, et seul le reste garde « Acomptes et avances ».
    reports = [
        r for r in bulletin.get(CLE_REPORTS_NAP_NEGATIF) or [] if isinstance(r, dict)
    ]
    for report in reports:
        valeur = float(report.get("montant") or 0.0)
        if valeur > 0:
            lignes.append(
                _ligne("hors_brut", str(report.get("libelle") or ""), montant_salarial=-valeur)
            )
    total_reports = sum(max(0.0, float(r.get("montant") or 0.0)) for r in reports)

    # Deux sources, deux retenues distinctes, toutes deux sorties du net : les
    # acomptes saisis en variables du mois (`acompte_verse`, retirés par le
    # moteur, reports à part) et les avances du module « Avances » (retirées à
    # l'enrichissement). La ligne ne montrait que les secondes quand il y en avait.
    acomptes = round(
        float((bulletin.get("remboursements_avances") or {}).get("total_rembourse") or 0.0)
        + float(synthese.get("acompte_verse") or 0.0)
        - total_reports,
        2,
    )

    retenues = (
        (acomptes, "Acomptes et avances"),
        (
            (bulletin.get("retenues_saisies") or {}).get("total_preleve"),
            "Retenues sur salaire",
        ),
        (
            (bulletin.get("remboursements_prets") or {}).get("total_rembourse"),
            "Remboursement prêt employeur",
        ),
    )
    # Retenues sur le net : négatives, comme les absences dans le brut, pour
    # qu'on ne confonde pas ce qui s'ajoute et ce qui se retire.
    for montant, libelle in retenues:
        valeur = float(montant or 0.0)
        if valeur > 0:
            lignes.append(_ligne("hors_brut", libelle, montant_salarial=-valeur))

    return lignes


def _heures_fr(valeur: Any) -> str:
    try:
        nombre = round(float(valeur or 0), 2)
    except (TypeError, ValueError):
        nombre = 0.0
    texte = f"{nombre:.2f}".rstrip("0").rstrip(".")
    return texte.replace(".", ",")


def mention_heures_sup_declarees(bulletin: Dict[str, Any]) -> Optional[str]:
    """Une ligne de note quand les heures sup ont été déclarées au bulletin.

    Sans elle, rien ne distinguait sur le bulletin des heures corrigées à la
    main de celles du planning (audit du 28/09).
    """
    declarees = bulletin.get("heures_sup_declarees")
    if not isinstance(declarees, dict):
        return None
    return (
        f"Heures supplémentaires déclarées au bulletin : "
        f"{_heures_fr(declarees.get('hs25'))} h à 25 %, "
        f"{_heures_fr(declarees.get('hs50'))} h à 50 % "
        f"(le planning en donnait {_heures_fr(declarees.get('planning'))} h)."
    )


def mention_volume_du_forfait(bulletin: Dict[str, Any]) -> Optional[str]:
    """C. trav. R3243-1, 5° a) : « La nature et le volume du forfait ».

    Un bulletin calculé avant que le volume soit relevé n'a pas la clé : rien
    n'est inventé pour lui.
    """
    jours = bulletin.get("forfait_jours_annuel")
    if not jours:
        return None
    return f"Forfait annuel en jours : {float(jours):g} jours par an".replace(".", ",")


def _mention_sous_la_ligne(bulletin: Dict[str, Any], detail: Dict[str, Any]) -> Optional[str]:
    """Sous la ligne de maintien : les IJSS déduites sans subrogation.

    Une ligne corrigée à la main a sa propre note, après les cotisations.
    """
    if not detail.get("is_maintien_employeur") or isinstance(detail.get("correction"), dict):
        return None
    bloc = bulletin.get("bloc_maintien")
    return mention_ijss_deduites(bloc.get("maintien") if isinstance(bloc, dict) else None)


def construire_lignes(bulletin: Dict[str, Any]) -> List[Dict[str, Any]]:
    lignes: List[Dict[str, Any]] = []

    # `details_maintien` n'est pas imprimé : ce sont les retenues d'arrêt, déjà
    # dans `details_absences`. Les deux blocs imprimaient chaque ligne d'arrêt
    # deux fois (Colorplast, août 2026 : 30 lignes pour 15 jours).
    for source in (
        "calcul_du_brut",
        "details_conges",
        "details_absences",
    ):
        for detail in bulletin.get(source) or []:
            if isinstance(detail, dict):
                lignes.append(_ligne_brut(detail))
                mention = _mention_sous_la_ligne(bulletin, detail)
                if mention:
                    lignes.append(_ligne("note", mention))
                if str(detail.get("libelle") or "").startswith("Salaire de base (forfait jour)"):
                    volume = mention_volume_du_forfait(bulletin)
                    if volume:
                        lignes.append(_ligne("note", volume))

    # La règle retenue pour les congés (`arbitrage_conges`) et la compensation
    # entre semaines (`compensation_semaines`) ne s'impriment pas : aucune n'est
    # due sur le bulletin (Elsa, 05/11). L'écran RH les montre, « D'où viennent
    # ces lignes ».
    mention_hs = mention_heures_sup_declarees(bulletin)
    if mention_hs:
        lignes.append(_ligne("note", mention_hs))
    fin_contrat = bulletin.get("indemnite_cp_fin_contrat") or {}
    if isinstance(fin_contrat, dict) and fin_contrat.get("mention"):
        lignes.append(_ligne("note", str(fin_contrat["mention"])))

    lignes.append(
        _ligne("total", "SALAIRE BRUT", montant_salarial=bulletin.get("salaire_brut"))
    )

    rubriques = [
        rubrique
        for rubrique in bulletin.get("cotisations_officielles") or []
        if isinstance(rubrique, dict)
    ]
    if modele_definitif(bulletin):
        lignes.extend(_lignes_modele_definitif(bulletin, rubriques))
        return lignes

    rubriques_principales = [
        r for r in rubriques if r.get("code") != RUBRIQUE_APRES_NET_IMPOSABLE
    ]
    rubriques_apres = [
        r for r in rubriques if r.get("code") == RUBRIQUE_APRES_NET_IMPOSABLE
    ]

    for rubrique in rubriques_principales:
        lignes.extend(_lignes_rubrique(rubrique))

    for mention in mentions_des_regularisations(bulletin):
        lignes.append(_ligne("note", mention))
    for mention in mentions_des_corrections(bulletin):
        lignes.append(_ligne("note", mention))

    total_salarial = round(
        sum(float(r.get("total_salarial") or 0.0) for r in rubriques_principales), 2
    )
    total_patronal = round(
        sum(float(r.get("total_patronal") or 0.0) for r in rubriques_principales), 2
    )
    lignes.append(
        _ligne(
            "total",
            "TOTAL DES RETENUES",
            montant_salarial=total_salarial,
            montant_patronal=total_patronal,
        )
    )
    lignes.append(
        _ligne(
            "total",
            "NET IMPOSABLE",
            montant_salarial=(bulletin.get("synthese_net") or {}).get("net_imposable"),
        )
    )

    lignes.extend(_lignes_hors_brut(bulletin))
    for rubrique in rubriques_apres:
        lignes.extend(_lignes_rubrique(rubrique))

    return lignes


def _montant_fr(valeur: Any) -> str:
    """Format français : espace pour les milliers, virgule décimale."""
    nombre = float(valeur or 0.0)
    return f"{nombre:,.2f}".replace(",", " ").replace(".", ",")


def _bloc_lateral(titre: str, valeurs: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    valeurs_utiles = [valeur for valeur in valeurs if valeur["valeur"]]
    if not valeurs_utiles:
        return None
    return {"titre": titre, "valeurs": valeurs_utiles}


LIBELLE_HEURES_FORFAIT_JOURS = "Heures retenues pour la réduction générale"

#: Cumul des jours travaillés de l'année civile, tenu par le moteur forfait
#: (`mettre_a_jour_cumuls`) ; `…_depuis` : mois où le décompte a commencé quand
#: ce n'est pas janvier (premier bulletin calculé par Martine, ou entrée).
CLE_CUMUL_JOURS_FORFAIT = "jours_travailles_forfait"
CLE_CUMUL_JOURS_FORFAIT_DEPUIS = "jours_travailles_forfait_depuis"


def _est_au_forfait_jours(bulletin: dict[str, Any]) -> bool:
    """Le moteur forfait pose le volume du forfait sur chaque bulletin qu'il calcule."""
    return bool(bulletin.get("forfait_jours_annuel"))


def _jours_fr(valeur: Any) -> str:
    return f"{float(valeur):g}".replace(".", ",")


def _bloc_forfait_jours(bulletin: dict[str, Any], cumuls: dict[str, Any]) -> dict[str, Any] | None:
    """R3243-1, 5°, a) : la nature et le volume du forfait. À côté du volume, les
    jours travaillés depuis janvier, pour suivre le forfait (retour du 10/11/2026).
    Un bulletin calculé avant ce cumul n'en a pas : rien n'est inventé."""
    if CLE_CUMUL_JOURS_FORFAIT not in cumuls:
        return None
    libelle = "Jours travaillés"
    depuis = cumuls.get(CLE_CUMUL_JOURS_FORFAIT_DEPUIS)
    annee = (bulletin.get("en_tete") or {}).get("annee")
    if depuis and int(depuis) > 1 and annee:
        libelle = f"Jours travaillés depuis le 01/{int(depuis):02d}/{int(annee)}"
    return {
        "titre": "FORFAIT JOURS",
        "valeurs": [
            {
                "libelle": libelle,
                "valeur": f"{_jours_fr(cumuls.get(CLE_CUMUL_JOURS_FORFAIT) or 0)} sur "
                f"{_jours_fr(bulletin['forfait_jours_annuel'])}",
            }
        ],
    }


def construire_lateral(bulletin: Dict[str, Any]) -> List[Dict[str, Any]]:
    parametres = bulletin.get("parametres") or {}
    cumuls = ((bulletin.get("cumuls") or {}).get("cumuls")) or {}
    pied = bulletin.get("pied_de_page") or {}
    salarie = ((bulletin.get("en_tete") or {}).get("salarie")) or {}
    definitif = modele_definitif(bulletin)

    def valeur(libelle: str, montant: Any) -> Dict[str, str]:
        return {
            "libelle": libelle,
            "valeur": _montant_fr(montant) if montant else "",
        }

    forfait_jours = _est_au_forfait_jours(bulletin)
    blocs = [
        _bloc_lateral(
            "BARÈMES",
            [
                valeur("SMIC horaire", parametres.get("smic_horaire")),
                valeur("Plafond Sécu", parametres.get("pss_mensuel")),
            ],
        ),
        _bloc_forfait_jours(bulletin, cumuls) if forfait_jours else None,
        _bloc_lateral(
            "HEURES",
            [
                # Au forfait jours, ce cumul n'est pas un temps de travail : ce
                # sont les heures que la réduction générale retient
                # (`heures_reduction_du_mois`, payslip_run_forfait).
                valeur(
                    LIBELLE_HEURES_FORFAIT_JOURS if forfait_jours else "Cumul heures",
                    cumuls.get("heures_remunerees"),
                ),
                valeur("Cumul h. sup", cumuls.get("heures_supplementaires_remunerees")),
            ],
        ),
        _bloc_lateral(
            "CUMULS",
            [
                # Cumul de l'année civile ; un bulletin d'avant ce compteur
                # retombe sur `brut_total`, qui l'était alors.
                valeur("Bruts", cumuls.get("brut_annee_civile", cumuls.get("brut_total"))),
                valeur("Net imposable", cumuls.get("net_imposable")),
                # Patronal seul ; les bulletins générés avant l'ajout de la
                # clé retombent sur l'ancien total.
                valeur(
                    "Exonérations et allègements" if definitif else "Allègement cotis. employeur",
                    pied.get("total_allegements_patronaux", pied.get("total_exonerations")),
                ),
                valeur(
                    "Total versé par l'employeur" if definitif else "Total versé employeur",
                    pied.get("cout_total_employeur"),
                ),
            ],
        ),
        _bloc_lateral(
            "PAIEMENT",
            [
                {
                    "libelle": "Mode",
                    "valeur": MODES_PAIEMENT.get(
                        str(salarie.get("mode_paiement") or "").strip().lower(), ""
                    ),
                }
            ],
        ),
    ]
    return [bloc for bloc in blocs if bloc]


def calculer_evolution_remuneration(salaire_brut: float, base_csg: float) -> float:
    """Mention obligatoire de l'article R3243-1 du Code du travail."""
    brut = float(salaire_brut or 0.0)
    base = float(base_csg or 0.0) or brut
    montant = brut * TAUX_COTISATIONS_SUPPRIMEES - base * TAUX_HAUSSE_CSG
    return round(max(0.0, montant), 2)


def _est_stagiaire(bulletin: Dict[str, Any]) -> bool:
    """Même règle que `ContextePaie.is_stagiaire`, lue sur l'en-tête du bulletin."""
    salarie = ((bulletin.get("en_tete") or {}).get("salarie")) or {}
    return "stage" in str(salarie.get("type_contrat") or "").lower()


def _base_exoneree_apprenti(bulletin: Dict[str, Any]) -> Optional[float]:
    """La part du brut d'un apprenti exonérée de cotisations salariales (base
    de la ligne « Exonération cotisations salariales apprenti »), ou None."""
    structure = bulletin.get("structure_cotisations") or {}
    for cle in ("bloc_allegements", "bloc_principales"):
        for ligne in structure.get(cle) or []:
            if isinstance(ligne, dict) and ligne.get("coti_id") == "exoneration_apprenti_salariale":
                return float(ligne.get("base") or 0.0)
    return None


def _evolution_remuneration(bulletin: Dict[str, Any]) -> float:
    """Un stagiaire n'a jamais cotisé à l'assurance chômage ni à la maladie
    salariale, ni avant ni après leur suppression : la mention vaut 0, au lieu
    du repli sur le brut quand le bulletin ne porte pas de CSG.

    Un apprenti ne cotise que sur la part de son salaire au-delà du plafond
    d'exonération, et sa CSG ne porte que sur elle : la mention se calcule sur
    cette assiette, sans repli sur le brut (décision du 12/10/2026)."""
    if _est_stagiaire(bulletin):
        return 0.0
    brut = float(bulletin.get("salaire_brut") or 0.0)
    base_exoneree = _base_exoneree_apprenti(bulletin)
    if base_exoneree is not None:
        cotisable = max(0.0, brut - base_exoneree)
        montant = cotisable * TAUX_COTISATIONS_SUPPRIMEES - _base_csg(bulletin) * TAUX_HAUSSE_CSG
        return round(max(0.0, montant), 2)
    return calculer_evolution_remuneration(brut, _base_csg(bulletin))


def _base_csg(bulletin: Dict[str, Any]) -> float:
    """Base de la CSG, prise sur la première ligne de la rubrique dédiée."""
    for rubrique in bulletin.get("cotisations_officielles") or []:
        if not isinstance(rubrique, dict):
            continue
        if rubrique.get("code") not in {"csg_deductible", "csg_non_deductible"}:
            continue
        for ligne in rubrique.get("lignes") or []:
            if isinstance(ligne, dict) and ligne.get("base"):
                return float(ligne["base"])
    return 0.0


def construire_pied(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    definitif = modele_definitif(bulletin)
    synthese = bulletin.get("synthese_net") or {}
    pas = synthese.get("impot_prelevement_a_la_source") or {}
    cumuls = ((bulletin.get("cumuls") or {}).get("cumuls")) or {}
    salarie = ((bulletin.get("en_tete") or {}).get("salarie")) or {}
    mentions = ((bulletin.get("pied_de_page") or {}).get("mentions_legales")) or {}

    return {
        "montant_net_social": synthese.get("montant_net_social"),
        "net_avant_impot": synthese.get("net_social_avant_impot"),
        "modele_definitif": definitif,
        # Article 1er : pas de ligne « dont évolution » ; elle n'existe qu'au modèle adapté.
        "evolution_remuneration": None if definitif else _evolution_remuneration(bulletin),
        "remboursements": _lignes_hors_brut(bulletin) if definitif else [],
        "mention_evolution": MENTION_EVOLUTION_REMUNERATION,
        "impot": {
            "net_imposable": synthese.get("net_imposable"),
            "base": pas.get("base"),
            "taux": pas.get("taux"),
            "montant": pas.get("montant"),
            "cumul_net_imposable": cumuls.get("net_imposable"),
            "cumul_impot": cumuls.get("impot_preleve_a_la_source"),
            "net_hs_exonerees": synthese.get("montant_net_hs_exonerees"),
            "cumul_net_hs_exonerees": cumuls.get("montant_net_hs_exonerees_cumul"),
            "exoneration_apprenti": bool(synthese.get("exoneration_ir_apprenti")),
            "exoneration_stagiaire": bool(synthese.get("exoneration_ir_stagiaire")),
        },
        "net_a_payer": bulletin.get("net_a_payer"),
        "convention_collective": REFERENCE_CODE_DU_TRAVAIL
        if sans_convention_collective(salarie)
        else salarie.get("convention_collective") or "",
        "mentions_legales": [
            texte
            for texte in (mentions.get("conservation"), mentions.get("information"))
            if texte
        ],
        "note": bulletin.get("pdf_notes") or "",
    }


def construire_vue_bulletin(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    """Point d'entrée unique : le bulletin du moteur, vu par le gabarit."""
    return {
        "bandeau": construire_bandeau(bulletin),
        "compteurs": construire_compteurs(bulletin),
        "salarie": construire_salarie(bulletin),
        "identite": construire_identite(bulletin),
        "lignes": construire_lignes(bulletin),
        "lateral": construire_lateral(bulletin),
        "pied": construire_pied(bulletin),
    }
