"""Construction d'une DSN P26V01 depuis données société / salariés / bulletins."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.modules.dsn_export.domain.settings import (
    DsnSettings,
    normaliser_idcc,
    normaliser_naf,
)
from app.modules.dsn_export.domain.contract_map import (
    iso_to_dsn_date,
    map_codification_ue,
    map_contract_nature_to_dsn,
    map_modalite_temps,
    map_sexe_to_dsn,
    map_statut_categoriel_rc,
    map_statut_to_dsn,
    period_bounds,
    period_to_mois_principal,
)
from app.modules.dsn_export.domain.agregats import (
    bordereau_urssaf,
    montant_retraite_complementaire,
)
from app.modules.dsn_export.domain.cotisation_mapping import build_bases_and_cotisations
from app.modules.dsn_export.domain.evenements import (
    bloc_fin_contrat,
    blocs_arret,
    blocs_suspension,
    date_de_fin,
    date_dsn,
    dsn as en_date_dsn,
    indemnites_de_rupture,
    jours_hors_plafond,
    primes_partage_valeur,
)
from app.modules.dsn_export.domain.remuneration_map import (
    build_remunerations_from_payslip,
    jours_calendaires,
)
from app.modules.dsn_import.domain.model import (
    AffiliationBlock,
    ArretTravailBlock,
    BordereauBlock,
    ContratBlock,
    FinContratBlock,
    PrimeBlock,
    SuspensionContratBlock,
    DeclarationBlock,
    DsnFile,
    EtablissementBlock,
    EntrepriseBlock,
    EnvoiBlock,
    IndividuBlock,
    OrganismePscBlock,
    VersementBlock,
    VersementOrganismeBlock,
)
from app.shared.dsn_validation import build_siret_from_siren_nic


def _extracteurs_bulletin():
    """Import différé : ``exports.infrastructure`` importe ce module en retour."""
    from app.modules.exports.infrastructure.payslip_accounting_extract import (
        extract_cotisations_from_payslip,
        extract_pas_amount,
    )

    return extract_cotisations_from_payslip, extract_pas_amount


# Version déclarée dans S10.G00.00.003 : celle de notre générateur DSN, à
# incrémenter quand la sortie change de forme.
VERSION_LOGICIEL = "1.0"

# Rubriques que le cabinet déclare à valeur fixe sur la totalité de nos
# fichiers : 1654 contrats, 43 DSN, 7 sociétés, aucune variation. Ce sont les
# valeurs « non concerné » de la norme. Elles restent regroupées ici pour être
# revues d'un coup le jour où le cahier technique les contredit.
CONSTANTES_INDIVIDU = {
    "S21.G00.30.023": "01",
}
CONSTANTES_CONTRAT = {
    "S21.G00.40.016": "99",
    "S21.G00.40.024": "99",
    "S21.G00.40.026": "99",
    "S21.G00.40.036": "01",
    "S21.G00.40.037": "01",
}


class DsnBuildError(ValueError):
    """Donnée obligatoire manquante pour générer la DSN."""


def _voie_dsn(valeur: str) -> str:
    """Nettoie un libellé de voie pour la DSN.

    La norme refuse la virgule dans les adresses (CSL-11) — l'apostrophe, elle,
    est admise : le cabinet déclare « ZA L'OUSSON NORD » sans encombre. On ne
    corrige que ce qui est interdit, on ne réécrit pas l'adresse.
    """
    texte = str(valeur or "").replace(",", " ")
    return " ".join(texte.split())


def _ville_dsn(valeur: str) -> str:
    """Nettoie une localité (S21.G00.30.010, CSL-00).

    La regex de la norme n'y admet ni apostrophe ni trait d'union : le cabinet
    déclare « L ABSIE » et « LE BOURGET DU LAC ». On remplace l'interdit par
    une espace, rien d'autre.
    """
    texte = re.sub(r"[',/-]", " ", str(valeur or ""))
    return " ".join(texte.split())


def _texte_dsn(valeur: str) -> str:
    """Nettoie un texte libre soumis à CSL-11 (30.007, 30.016…).

    Apostrophe, espace, trait d'union et point n'y sont admis qu'« à bon
    escient » : jamais accolés à un autre séparateur, ni en bord de champ.
    Vu chez le cabinet : virgule et barre oblique retirées, « SAINT PAUL -
    REUNION » resserré en « SAINT PAUL REUNION ». On ne corrige que l'interdit.
    """
    texte = str(valeur or "").replace(",", " ").replace("/", " ")
    texte = re.sub(r"\s+-\s+", " ", texte)
    return " ".join(texte.split()).strip(" .'-")


def _addr(obj: Any) -> Dict[str, str]:
    if not isinstance(obj, dict):
        return {"rue": "", "code_postal": "", "ville": ""}
    return {
        "rue": _voie_dsn(obj.get("rue") or obj.get("street") or ""),
        "code_postal": str(obj.get("code_postal") or obj.get("postal_code") or ""),
        "ville": _ville_dsn(obj.get("ville") or obj.get("city") or ""),
    }


def _siren_nic(siret: str) -> Tuple[str, str]:
    clean = (siret or "").replace(" ", "")
    if len(clean) >= 14:
        return clean[:9], clean[9:14]
    if len(clean) == 9:
        return clean, "00000"
    return clean[:9], (clean[9:] or "00000").zfill(5)[:5]


def _net_imposable(payslip_data: Dict[str, Any]) -> float:
    synthese = payslip_data.get("synthese_net")
    if isinstance(synthese, dict):
        return float(synthese.get("net_imposable") or 0)
    return float(payslip_data.get("net_imposable") or 0)


def _net_a_payer(payslip_data: Dict[str, Any]) -> float:
    """Net versé DSN (S21.G00.50.004).

    Si le bulletin stocke un solde après acomptes (net racine << net imposable),
    on réintègre les acomptes. Sinon on garde le net racine tel quel.
    """
    synthese = payslip_data.get("synthese_net")
    acompte = 0.0
    pas = 0.0
    if isinstance(synthese, dict):
        acompte = float(synthese.get("acompte_verse") or 0)
        pas_obj = synthese.get("impot_prelevement_a_la_source")
        if isinstance(pas_obj, dict):
            pas = float(pas_obj.get("montant") or 0)

    net_imp = _net_imposable(payslip_data)
    top = payslip_data.get("net_a_payer")
    top_val = None
    if top is not None and top != "":
        try:
            top_val = float(top)
        except (TypeError, ValueError):
            top_val = None

    if top_val is not None:
        if acompte > 0 and net_imp > 100 and top_val < 0.5 * net_imp:
            return round(top_val + acompte, 2)
        return top_val

    if isinstance(synthese, dict):
        for key in ("net_a_payer", "net_verse"):
            if synthese.get(key) is not None:
                try:
                    return float(synthese[key])
                except (TypeError, ValueError):
                    pass
        for key in ("montant_net_social", "net_social_avant_impot"):
            if synthese.get(key) is not None:
                try:
                    val = float(synthese[key])
                    if key == "montant_net_social":
                        val -= pas
                    return round(val, 2)
                except (TypeError, ValueError):
                    pass
    return 0.0


#: Contributions patronales déclarées en autres éléments de revenu brut
#: (S21.G00.54) : 92 la santé, 93 la prévoyance et la retraite supplémentaire.
COTI_SANTE = {"mutuelle", "complementaire_sante"}
COTI_PREVOYANCE_RETRAITE_SUP = {
    "prevoyance",
    "prevoyance_cadre",
    "prevoyance_non_cadre",
    "retraite_sup",
}


def _arrondi(valeur: float) -> float:
    from decimal import ROUND_HALF_UP, Decimal

    return float(Decimal(str(round(valeur, 6))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _famille_psc(ligne: Dict[str, Any]) -> str:
    """« sante », « prevoyance » ou « » pour une ligne de cotisation."""
    coti_id = str(ligne.get("coti_id") or "")
    if coti_id in COTI_SANTE:
        return "sante"
    if coti_id in COTI_PREVOYANCE_RETRAITE_SUP:
        return "prevoyance"
    if coti_id:
        return ""
    libelle = str(ligne.get("libelle") or "").lower()
    if "mutuelle" in libelle or "santé" in libelle or "sante" in libelle:
        return "sante"
    if "prévoyance" in libelle or "prevoyance" in libelle or "retraite sup" in libelle:
        return "prevoyance"
    return ""


def _parts_patronales_psc(lignes: List[Dict[str, Any]]) -> Tuple[float, float]:
    """(santé, prévoyance + retraite supplémentaire), parts patronales."""
    sante = prevoyance = 0.0
    for ligne in lignes:
        famille = _famille_psc(ligne)
        montant = float(ligne.get("montant_patronal") or 0)
        if famille == "sante":
            sante += montant
        elif famille == "prevoyance":
            prevoyance += montant
    return round(sante, 2), round(prevoyance, 2)


def _epargne_salariale(payslip_data: Dict[str, Any], period: str) -> List[Tuple[str, float, int]]:
    """(type 54, montant, exercice) de la participation et de l'intéressement versés.

    11 participation, 12 intéressement, sur leur montant brut ; 37 la part
    versée directement par l'employeur (hors part placée). L'exercice est
    celui du libellé (« Participation 2025 »), à défaut l'année précédente.
    Un acompte déjà versé ne réduit pas le montant déclaré (ancien
    logiciel, mai 2026).
    """
    annee_precedente = int(period[:4]) - 1
    elements: List[Tuple[str, float, float, str]] = []
    for ligne in payslip_data.get("participations") or []:
        if isinstance(ligne, dict) and float(ligne.get("brut") or 0) > 0:
            elements.append(
                (
                    str(ligne.get("libelle") or ""),
                    float(ligne["brut"]),
                    float(ligne.get("part_pee") or 0),
                    "participations",
                )
            )
    if not elements:
        for ligne in payslip_data.get("primes_non_soumises") or []:
            if not isinstance(ligne, dict):
                continue
            libelle = str(ligne.get("libelle") or "")
            texte = libelle.lower().strip()
            if not (texte.startswith("participation") or texte.startswith("intéressement") or texte.startswith("interessement")):
                continue
            montant = float(ligne.get("montant") or 0)
            if montant > 0:
                elements.append((libelle, montant, 0.0, "primes"))
    cumuls: Dict[Tuple[str, int], float] = {}
    for libelle, brut, place, _ in elements:
        texte = libelle.lower()
        type_54 = "12" if "intéressement" in texte or "interessement" in texte else "11"
        annee = re.search(r"\b(20\d{2})\b", libelle)
        exercice = int(annee.group(1)) if annee else annee_precedente
        cumuls[(type_54, exercice)] = cumuls.get((type_54, exercice), 0.0) + brut
        if brut - place > 0:
            cumuls[("37", exercice)] = cumuls.get(("37", exercice), 0.0) + brut - place
    return [(t, round(m, 2), e) for (t, e), m in sorted(cumuls.items())]


def _net_verse(net_fiscal: float, lignes: List[Dict[str, Any]]) -> float:
    """Montant net versé (S21.G00.50.004), formule du CT 2026.

    RNF - fraction de CSG non déductible (2,40 %) - CRDS (0,50 %) - part
    patronale « frais de santé » réintégrée dans la base fiscale. Ni le
    prélèvement à la source, ni les heures sup exonérées (hors RNF), ni les
    remboursements de frais, acomptes, prêts ou saisies n'y entrent : ce n'est
    pas le net à payer. Les deux fractions s'appliquent à l'assiette de chaque
    ligne non déductible (2,90 % comme 9,70 %), chacune arrondie : c'est le
    calcul de l'ancien logiciel, au centime sur 146 salariés-mois de 2026.
    """
    non_deductible = 0.0
    for ligne in lignes:
        coti_id = str(ligne.get("coti_id") or "")
        libelle = str(ligne.get("libelle") or "").lower()
        base = float(ligne.get("base") or 0)
        if coti_id == "crds":
            non_deductible += float(ligne.get("montant_salarial") or 0)
        elif coti_id == "csg_non_deductible" or (
            not coti_id and "csg" in libelle and "non d" in libelle
        ):
            non_deductible += _arrondi(base * 0.024) + _arrondi(base * 0.005)
    sante, _ = _parts_patronales_psc(lignes)
    return round(net_fiscal - non_deductible - sante, 2)


def _smic_reduction_generale(
    lignes: List[Dict[str, Any]], synthese_net: Dict[str, Any], reprise: Dict[str, Any]
) -> Optional[float]:
    """SMIC retenu pour la réduction générale du mois (S21.G00.79 type 01).

    Le moteur le pose sur la ligne de réduction (`smic_reference_mois`) ; les
    bulletins plus anciens n'en ont pas, la reprise des DSN du cabinet sert
    alors de repli.
    """
    for ligne in lignes:
        if str(ligne.get("coti_id") or "") == "reduction_generale" and ligne.get(
            "smic_reference_mois"
        ) is not None:
            # Zéro est une vraie valeur : un mois sans heure payée.
            return float(ligne["smic_reference_mois"])
    valeur = synthese_net.get("montant_smic_reduction_generale") or reprise.get(
        "smic_retenu"
    )
    return float(valeur) if valeur else None


#: Plafond mensuel de la Sécurité sociale, pour les bulletins qui ne portent
#: pas encore leur plafond plein (`parametres.pss_mensuel_plein`, depuis le
#: 04/10/2026).
PSS_MENSUEL = {2024: 3864.0, 2025: 3925.0, 2026: 4005.0}


def _jours_plafond(
    payslip_data: Dict[str, Any],
    period: str,
    period_start: str,
    period_end: str,
    absences: List[Dict[str, Any]],
) -> int:
    """Jours calendaires retenus pour le plafond (S21.G00.53 unité 40).

    Ceux de la paie d'abord : elle proratise le plafond au jour près (entrée,
    sortie, arrêt, absence non rémunérée) et garde le plafond retenu ; le ratio
    au plafond plein, rapporté aux jours du mois, les redonne. À défaut, la
    période d'emploi moins les arrêts et les absences non rémunérées.
    """
    import calendar

    year, month = (int(x) for x in period.split("-")[:2])
    nb_jours = calendar.monthrange(year, month)[1]
    parametres = payslip_data.get("parametres") or {}
    pss = parametres.get("pss_mensuel") if isinstance(parametres, dict) else None
    plein = (
        parametres.get("pss_mensuel_plein") if isinstance(parametres, dict) else None
    ) or PSS_MENSUEL.get(year)
    if pss not in (None, "") and plein:
        return int(round(float(pss) / float(plein) * nb_jours))
    jours = jours_calendaires(period_start, period_end)
    debut, fin = date_dsn(period_start), date_dsn(period_end)
    if debut and fin:
        jours -= jours_hors_plafond(absences, payslip_data, debut, fin)
    return max(0, jours)


def _cdd_court_ou_imprecis(nature: str, employee: Dict[str, Any]) -> bool:
    """CDD dont le terme initial n'excède pas deux mois, ou à terme imprécis."""
    import calendar
    from datetime import date as _date

    if nature != "02":
        return False
    try:
        debut = _date.fromisoformat(str(employee.get("hire_date") or "")[:10])
    except ValueError:
        return False
    fin_texte = str(employee.get("contract_end_date") or "")[:10]
    if not fin_texte:
        return True
    try:
        fin = _date.fromisoformat(fin_texte)
    except ValueError:
        return False
    mois, an = debut.month + 2, debut.year
    if mois > 12:
        mois, an = mois - 12, an + 1
    limite = _date(an, mois, min(debut.day, calendar.monthrange(an, mois)[1]))
    return fin <= limite


def _jours_forfait(
    payslip_data: Dict[str, Any],
    period_start: str,
    period_end: str,
    absences: List[Dict[str, Any]],
) -> float:
    """Jours travaillés d'un forfait jours (53 type 01, en jours).

    Ceux de la paie quand le bulletin les porte ; sinon les jours ouvrés de la
    période, hors fériés, moins les jours d'arrêt ou d'absence non rémunérée —
    22 en juin 2026, comme l'ancien logiciel.
    """
    from datetime import timedelta

    from app.modules.absences.domain.rtt_forfait import french_public_holiday_dates
    from app.modules.dsn_export.domain.evenements import (
        MOTIF_CONGE_NON_REMUNERE,
        periodes_d_arret,
        suspensions_du_bulletin,
    )

    stocke = payslip_data.get("nombre_jours_travailles")
    if stocke not in (None, ""):
        return float(stocke)
    debut, fin = date_dsn(period_start), date_dsn(period_end)
    if not debut or not fin:
        return 0.0
    feries = set(french_public_holiday_dates(debut.year))
    absents = set()
    for periode in periodes_d_arret(absences):
        jour = periode.debut
        while jour <= periode.fin:
            absents.add(jour)
            jour += timedelta(days=1)
    for motif, debut_s, fin_s in suspensions_du_bulletin(payslip_data):
        if motif == MOTIF_CONGE_NON_REMUNERE:
            jour = debut_s
            while jour <= fin_s:
                absents.add(jour)
                jour += timedelta(days=1)
    jours = 0
    jour = debut
    while jour <= fin:
        if jour.weekday() < 5 and jour not in feries and jour not in absents:
            jours += 1
        jour += timedelta(days=1)
    return float(jours)


def taux_pas_du_mois(lignes: List[Dict[str, Any]], periode: str) -> Dict[str, str]:
    """Type et identifiant du taux PAS en vigueur pour le mois déclaré.

    `employee_pas_rates` garde chaque taux reçu (CRM de la DGFiP, ou repris
    des DSN de l'ancien logiciel) daté de sa période : on retient le dernier
    reçu au plus tard le mois déclaré. Un taux « 01 - transmis par la DGFiP »
    exige son identifiant (50.008, CCH-11) ; un barème n'en a pas.
    """
    retenus = [
        l
        for l in lignes
        if isinstance(l, dict) and str(l.get("periode") or "") <= periode and l.get("type_taux")
    ]
    if not retenus:
        return {}
    dernier = max(retenus, key=lambda l: str(l.get("periode") or ""))
    resultat = {"pas_type_taux": str(dernier["type_taux"])}
    if dernier.get("identifiant_taux"):
        resultat["pas_identifiant_taux"] = str(dernier["identifiant_taux"])
    return resultat


def _defauts_contrat(
    company: Dict[str, Any],
    employees_data: List[Dict[str, Any]],
    settings: Optional[DsnSettings],
) -> Dict[str, str]:
    """Ce que l'établissement fixe pour tous ses contrats.

    L'IDCC déclaré de l'établissement, son taux AT, et le code risque AT
    quand tous les contrats qui en portent un portent le même — un
    établissement à plusieurs risques ne se devine pas.
    """
    defauts: Dict[str, str] = {}
    idcc = normaliser_idcc((settings.idcc if settings else "") or company.get("idcc") or "")
    if idcc:
        defauts["idcc"] = idcc
    taux_at = company.get("taux_at_mp")
    if taux_at not in (None, ""):
        try:
            defauts["taux_at"] = f"{float(taux_at):.2f}"
        except (TypeError, ValueError):
            pass
    codes = set()
    for row in employees_data:
        employe = (row or {}).get("employee") or row or {}
        classification = employe.get("classification_conventionnelle")
        if isinstance(classification, dict) and classification.get("classification_dsn"):
            codes.add(str(classification["classification_dsn"]))
    if len(codes) == 1:
        defauts["code_risque_at"] = codes.pop()
    # Dispositif de l'apprentissage (40.008) : 64 sous 11 salariés (ou
    # entreprise artisanale), 65 au-delà pour une entreprise non inscrite au
    # répertoire des métiers.
    try:
        effectif = int(company.get("effectif") or len(employees_data))
    except (TypeError, ValueError):
        effectif = len(employees_data)
    defauts["dispositif_apprentissage"] = "65" if effectif >= 11 else "64"
    return defauts


#: Code régime de base (maladie, vieillesse, accident du travail) du régime
#: général : 40.018, 40.020, 40.039.
REGIME_GENERAL = "200"


def _pas_details(payslip_data: Dict[str, Any]) -> Tuple[float, float, Optional[float]]:
    """Retourne (montant, taux, assiette) ; assiette None si la paie ne la dit pas.

    Une assiette à zéro est une vraie valeur : l'apprenti sous le seuil
    d'exonération n'a rien de soumis au PAS (50.013 = 0.00).
    """
    synthese = payslip_data.get("synthese_net")
    if not isinstance(synthese, dict):
        return 0.0, 0.0, None
    pas_obj = synthese.get("impot_prelevement_a_la_source")
    if isinstance(pas_obj, dict):
        assiette = pas_obj.get("base")
        if assiette is None:
            assiette = pas_obj.get("assiette")
        return (
            float(pas_obj.get("montant") or 0),
            float(pas_obj.get("taux") or 0),
            float(assiette) if assiette not in (None, "") else None,
        )
    _, extract_pas_amount = _extracteurs_bulletin()
    montant = extract_pas_amount(synthese)
    return montant, 0.0, _net_imposable(payslip_data)


def _heures_remunerees(payslip_data: Dict[str, Any]) -> float:
    for key in ("heures_remunerees", "heures_travaillees", "heures"):
        if payslip_data.get(key) is not None:
            try:
                return float(payslip_data[key])
            except (TypeError, ValueError):
                pass
    calcul = payslip_data.get("calcul_du_brut")
    if isinstance(calcul, dict):
        for key in ("heures_remunerees", "heures_base", "heures"):
            if calcul.get(key) is not None:
                try:
                    return float(calcul[key])
                except (TypeError, ValueError):
                    pass
    return 151.67


def _classification(employee: Dict[str, Any]) -> Dict[str, Any]:
    """Classification conventionnelle de la fiche, déjà codée pour la DSN."""
    valeur = employee.get("classification_conventionnelle")
    return valeur if isinstance(valeur, dict) else {}


DEPARTEMENT_DANS_LIBELLE = re.compile(r"\s*\((\d{2}[AB]?|\d{3})\)\s*$")
DEPARTEMENTS_METROPOLE_ET_DOM = set(f"{n:02d}" for n in range(1, 96)) | {
    "2A",
    "2B",
    "971",
    "972",
    "973",
    "974",
    "976",
}


def _reprise_dsn(employee: Dict[str, Any]) -> Dict[str, Any]:
    """La reprise DSN du salarié : au niveau racine dans les jeux de
    conformité, sous specificites_paie en base réelle (dsn_reprise_loader)."""
    specs = employee.get("specificites_paie") or {}
    if not isinstance(specs, dict):
        specs = {}
    reprise = employee.get("dsn_reprise") or specs.get("dsn_reprise") or {}
    return reprise if isinstance(reprise, dict) else {}


def _naissance(employee: Dict[str, Any], nir: str) -> Tuple[str, str, str, List[str]]:
    """Retourne (lieu, département, pays, avertissements).

    Le cabinet déclare le libellé de commune seul, le département dans sa propre
    rubrique et le pays en code ISO. Notre fiche stocke ``BOURG SAINT MAURICE
    (73)`` : on sépare les deux, et on retombe sur le NIR si le libellé ne porte
    pas le département.
    """
    avertissements: List[str] = []
    libelle = str(employee.get("lieu_naissance") or "").strip()
    departement = ""
    trouve = DEPARTEMENT_DANS_LIBELLE.search(libelle)
    if trouve:
        departement = trouve.group(1)
        libelle = DEPARTEMENT_DANS_LIBELLE.sub("", libelle).strip()
    if not departement and len(nir) >= 7:
        departement = nir[5:7]
    libelle = _texte_dsn(libelle)
    pays = ""
    if departement in DEPARTEMENTS_METROPOLE_ET_DOM:
        pays = "FR"
    elif departement:
        # Né à l'étranger ou dans les DOM : ni le département déclarable ni le
        # pays ne se déduisent du NIR. Ils viennent de la fiche ou de la
        # reprise des DSN du cabinet — qui déclare '99' + pays (souvent 'FR')
        # pour l'étranger, '97' + 'FR' pour les DOM, Mayotte comprise.
        reprise = _reprise_dsn(employee)
        pays = str(
            employee.get("pays_naissance") or reprise.get("pays_naissance") or ""
        ).strip().upper()
        if pays:
            departement = str(
                reprise.get("departement_naissance") or ""
            ).strip() or "99"
        else:
            avertissements.append(
                f"Code pays de naissance inconnu pour le NIR {nir[:13]} "
                f"(né hors de France, département {departement})"
            )
            departement = ""
    return libelle, departement, pays, avertissements


def _sexe_declare(employee: Dict[str, Any], nir: str) -> Tuple[str, List[str]]:
    """Sexe déclaré : le NIR fait foi quand la fiche le contredit.

    Le premier chiffre du NIR porte le sexe et il est contrôlé par la clé ; une
    fiche qui le contredit est une erreur de saisie, pas une source.
    """
    depuis_fiche = map_sexe_to_dsn(employee.get("sexe") or employee.get("gender"))
    if not nir or nir[0] not in ("1", "2"):
        return depuis_fiche, []
    depuis_nir = "01" if nir[0] == "1" else "02"
    if depuis_nir != depuis_fiche:
        return depuis_nir, [
            f"Sexe de la fiche contredit par le NIR {nir[:13]} : "
            f"c'est le NIR qui est déclaré"
        ]
    return depuis_fiche, []


def _is_cadre(employee: Dict[str, Any]) -> bool:
    statut = str(employee.get("statut") or "").lower()
    if "cadre" in statut and "non" not in statut:
        return True
    cat = str(employee.get("statut_categoriel") or employee.get("categorie") or "").lower()
    return "cadre" in cat and "non" not in cat


def build_envoi(
    *,
    dsn_type: str = "dsn_mensuelle_normale",
    settings: Optional[DsnSettings] = None,
) -> EnvoiBlock:
    mode = "01"  # réel
    if "test" in (dsn_type or "").lower():
        mode = "02"
    parametres = settings or DsnSettings()
    rubriques = {
        "S10.G00.00.001": "EYWAI Paie",
        "S10.G00.00.002": "EYWAI",
        "S10.G00.00.003": VERSION_LOGICIEL,
        "S10.G00.00.004": "0",
        # Aligné sur les fichiers acceptés par net-entreprises.
        "S10.G00.00.005": "02",
        "S10.G00.00.006": "P26V01",
        "S10.G00.00.007": mode,
        "S10.G00.00.008": "01",
    }
    # Émetteur du fichier (S10.G00.01) : peut différer de la société déclarée
    # quand une entité du groupe télétransmet pour les autres.
    if parametres.emetteur_siren:
        rubriques.update(
            {
                "S10.G00.01.001": parametres.emetteur_siren,
                "S10.G00.01.002": parametres.emetteur_nic,
                "S10.G00.01.003": parametres.emetteur_raison_sociale,
                "S10.G00.01.004": parametres.emetteur_rue,
                "S10.G00.01.005": parametres.emetteur_code_postal,
                "S10.G00.01.006": parametres.emetteur_ville,
            }
        )
    if parametres.contact_emetteur_nom:
        rubriques.update(
            {
                "S10.G00.02.001": parametres.contact_emetteur_type or "02",
                "S10.G00.02.002": parametres.contact_emetteur_nom,
                "S10.G00.02.004": parametres.contact_emetteur_email,
                "S10.G00.02.005": parametres.contact_emetteur_telephone,
            }
        )
    return EnvoiBlock(
        periode="01",
        norme="P26V01",
        type_envoi=mode,
        rubriques=rubriques,
    )


def build_declaration(
    period: str,
    *,
    settings: Optional[DsnSettings] = None,
    date_constitution: Optional[str] = None,
) -> DeclarationBlock:
    mois = period_to_mois_principal(period)
    parametres = settings or DsnSettings()
    rubriques = {
        "S20.G00.05.001": "01",
        "S20.G00.05.002": "01",
        "S20.G00.05.003": "11",
        "S20.G00.05.004": "1",
        "S20.G00.05.005": mois,
        "S20.G00.05.007": date_constitution or date.today().strftime("%d%m%Y"),
        "S20.G00.05.008": "01",
        "S20.G00.05.010": "01",
    }
    # Le bloc contact déclaration se répète par organisme destinataire ; les
    # rubriques répétées sont portées à part, un dict ne les tiendrait pas.
    contacts: List[Dict[str, str]] = []
    for contact in parametres.contacts_declaration:
        contacts.append(
            {
                "S20.G00.07.001": contact.nom,
                "S20.G00.07.002": contact.telephone,
                "S20.G00.07.003": contact.email,
                "S20.G00.07.004": contact.code_destinataire,
            }
        )
    return DeclarationBlock(
        nature="01",
        type_declaration="01",
        mois_principal=mois,
        rubriques=rubriques,
        contacts=contacts,
    )


def build_entreprise(
    company: Dict[str, Any], *, settings: Optional[DsnSettings] = None
) -> EntrepriseBlock:
    siret = str(company.get("siret") or "")
    siren, nic = _siren_nic(siret)
    if not siren or len(siren) != 9:
        raise DsnBuildError("SIREN/SIRET société manquant ou invalide")
    parametres = settings or DsnSettings()
    addr = _addr(company.get("address") or company.get("adresse"))
    # Le NAF déclaré prime sur celui de la fiche société : c'est celui que
    # connaît l'URSSAF, et il s'écrit sans séparateur.
    naf = parametres.naf or normaliser_naf(
        str(company.get("code_naf") or company.get("naf") or "")
    )
    if not naf:
        raise DsnBuildError("Code NAF manquant pour l'établissement")
    rubriques = {
        "S21.G00.06.001": siren,
        "S21.G00.06.002": nic,
        "S21.G00.06.003": naf,
        "S21.G00.06.004": addr["rue"],
        "S21.G00.06.005": addr["code_postal"],
        "S21.G00.06.006": addr["ville"],
    }
    if parametres.complement_adresse:
        rubriques["S21.G00.06.007"] = parametres.complement_adresse
    if parametres.commune_implantation:
        rubriques["S21.G00.06.008"] = parametres.commune_implantation
    if parametres.idcc:
        rubriques["S21.G00.06.015"] = parametres.idcc
    return EntrepriseBlock(
        siren=siren,
        nic_siege=nic,
        raison_sociale=str(company.get("name") or company.get("raison_sociale") or ""),
        code_naf=naf,
        adresse_rue=addr["rue"],
        adresse_cp=addr["code_postal"],
        adresse_ville=addr["ville"],
        rubriques=rubriques,
    )


def _rubriques_etablissement(
    nic: str,
    entreprise: EntrepriseBlock,
    addr: Dict[str, str],
    settings: Optional[DsnSettings],
) -> Dict[str, str]:
    parametres = settings or DsnSettings()
    rubriques = {
        "S21.G00.11.001": nic,
        "S21.G00.11.002": entreprise.code_naf,
        "S21.G00.11.003": addr["rue"],
        "S21.G00.11.004": addr["code_postal"],
        "S21.G00.11.005": addr["ville"],
    }
    if parametres.complement_adresse:
        rubriques["S21.G00.11.006"] = parametres.complement_adresse
    if parametres.commune_implantation:
        rubriques["S21.G00.11.007"] = parametres.commune_implantation
    if parametres.idcc:
        rubriques["S21.G00.11.022"] = parametres.idcc
    for code, valeur in sorted((parametres.rubriques_etablissement or {}).items()):
        if valeur:
            rubriques.setdefault(code, valeur)
    return rubriques


def build_etablissement(
    company: Dict[str, Any],
    entreprise: EntrepriseBlock,
    *,
    settings: Optional[DsnSettings] = None,
) -> EtablissementBlock:
    siret = str(company.get("siret") or "")
    siren, nic = _siren_nic(siret)
    if len(siret.replace(" ", "")) != 14:
        siret = build_siret_from_siren_nic(siren, nic)
    addr = _addr(company.get("address") or company.get("adresse"))
    etab = EtablissementBlock(
        siret=siret,
        nic=nic,
        raison_sociale=entreprise.raison_sociale,
        code_naf=entreprise.code_naf,
        adresse_rue=addr["rue"],
        adresse_cp=addr["code_postal"],
        adresse_ville=addr["ville"],
        rubriques=_rubriques_etablissement(nic, entreprise, addr, settings),
    )
    # Contrats collectifs (bloc S21.G00.15). Priorité au paramétrage DSN de la
    # société, repris des fiches de paramétrage OC ; l'ancien chemin
    # company.mutuelle_types reste en repli.
    contrats_psc = (settings.organismes_complementaires if settings else None) or [
        mt
        for mt in (company.get("mutuelle_types") or company.get("psc_contracts") or [])
        if isinstance(mt, dict)
    ]
    for idx, mt in enumerate(contrats_psc, start=1):
        if not isinstance(mt, dict):
            continue
        ref = str(mt.get("reference") or mt.get("reference_contrat") or mt.get("code") or "")
        org = str(mt.get("organisme") or mt.get("code_organisme") or "")
        if not ref and not org:
            continue
        deleg = str(mt.get("delegataire") or mt.get("code_delegataire") or "")
        nature = str(mt.get("nature") or "01")
        # L'ordre déclaré dans le paramétrage prime : c'est lui que les blocs 70
        # des salariés référencent, il survit aux réordonnancements de la liste.
        ordre = str(mt.get("ordre") or idx)
        rubriques = {
            "S21.G00.15.001": ref,
            "S21.G00.15.002": org,
            "S21.G00.15.004": nature,
            "S21.G00.15.005": ordre,
        }
        if deleg:
            rubriques["S21.G00.15.003"] = deleg
        etab.organismes_psc.append(
            OrganismePscBlock(
                reference_contrat=ref,
                code_organisme=org,
                code_nature=nature,
                rang=ordre,
                rubriques=rubriques,
            )
        )
    return etab


def build_individu_from_payroll(
    employee: Dict[str, Any],
    payslip_data: Dict[str, Any],
    *,
    period: str,
    company_siret: str,
    require_cotisation_codes: bool = False,
    default_ops: str = "",
    settings: Optional[DsnSettings] = None,
    defauts_contrat: Optional[Dict[str, str]] = None,
) -> Tuple[IndividuBlock, List[str]]:
    warnings: List[str] = []
    defauts = defauts_contrat or {}
    nir = str(employee.get("nir") or "").replace(" ", "")
    if not nir:
        raise DsnBuildError(
            f"NIR manquant pour {employee.get('last_name')} {employee.get('first_name')}"
        )
    # DSN P26 : S21.G00.30.001 = 13 chiffres (sans clé)
    nir_dsn = nir[:13] if len(nir) >= 13 else nir
    addr = _addr(employee.get("adresse") or employee.get("address"))
    period_start, period_end = period_bounds(period)
    unite, q_ref, quotite, modalite = map_modalite_temps(
        is_temps_partiel=bool(employee.get("is_temps_partiel")),
        duree_hebdo=(
            float(employee["duree_hebdomadaire"])
            if employee.get("duree_hebdomadaire") is not None
            else None
        ),
        is_forfait_jour=bool(employee.get("is_forfait_jour")),
        quotite_forfait_jours=(settings or DsnSettings()).quotite_forfait_jours,
    )
    nature = map_contract_nature_to_dsn(employee.get("contract_type"))
    statut = map_statut_to_dsn(employee.get("statut"), is_cadre=_is_cadre(employee))
    date_debut = iso_to_dsn_date(employee.get("hire_date") or employee.get("date_entree"))
    if not date_debut:
        raise DsnBuildError(f"Date d'embauche manquante pour NIR {nir_dsn}")

    # Embauché en cours de mois : les périodes des rémunérations (51.001), des
    # bases assujetties (78.002) et du net social (58.001) démarrent au premier
    # jour du contrat, pas au premier du mois — c'est ce que déclare le cabinet
    # et ce que le validateur attend (CCH-11 sur 51.001, SIG-17 sur 78.003).
    try:
        if datetime.strptime(date_debut, "%d%m%Y") > datetime.strptime(
            period_start, "%d%m%Y"
        ):
            period_start = date_debut
    except ValueError:
        pass
    # Sortie en cours de mois : les périodes s'arrêtent au dernier jour du
    # contrat (CCH-13 sur 51.002). Le versement reste daté de la fin du mois.
    debut_mois = date_dsn(period_bounds(period)[0])
    fin_mois = date_dsn(period_bounds(period)[1])
    date_versement = period_end
    fin_du_contrat = date_de_fin(employee, debut_mois, fin_mois) if debut_mois else None
    if fin_du_contrat and fin_du_contrat < fin_mois:
        period_end = en_date_dsn(fin_du_contrat)

    brut = float(payslip_data.get("salaire_brut") or 0)
    if brut <= 0:
        raise DsnBuildError(f"Brut ≤ 0 pour NIR {nir_dsn}")

    net_fiscal = _net_imposable(payslip_data)
    pas_montant, pas_taux, pas_assiette = _pas_details(payslip_data)

    # Données de reprise DSN : affiliations prévoyance/santé du salarié, type
    # et identifiant du taux PAS, SMIC retenu, naissance hors de France — tout
    # ce qui ne se déduit ni du bulletin ni du contrat. Posées au niveau racine
    # par les jeux de conformité, dans specificites_paie par le loader
    # (scripts/dsn_reprise_loader.py) pour la base réelle.
    specs = employee.get("specificites_paie") or {}
    if not isinstance(specs, dict):
        specs = {}
    reprise = _reprise_dsn(employee)
    affiliations_psc = [
        a
        for a in (
            employee.get("affiliations_psc") or specs.get("affiliations_psc") or []
        )
        if isinstance(a, dict)
    ]

    synthese_net = payslip_data.get("synthese_net") or {}

    extract_cotisations_from_payslip, _ = _extracteurs_bulletin()
    cot_sal, cot_pat, cot_lines, meta = extract_cotisations_from_payslip(payslip_data)
    warnings.extend(meta.get("warnings") or [])
    net_verse = _net_verse(net_fiscal, cot_lines)
    smic_retenu = _smic_reduction_generale(cot_lines, synthese_net, reprise)
    if smic_retenu is None and any(
        str(l.get("coti_id") or "") == "reduction_generale" for l in cot_lines
    ):
        warnings.append(
            f"SMIC retenu pour la réduction générale inconnu pour le NIR {nir_dsn} : "
            "composant 79 type 01 absent (CCH-17), bulletin à recalculer"
        )
    if not affiliations_psc and any(
        _famille_psc(l) and (float(l.get("montant_salarial") or 0) or float(l.get("montant_patronal") or 0))
        for l in cot_lines
    ):
        warnings.append(
            f"Cotisations prévoyance / santé sans affiliation (bloc 70) pour le NIR "
            f"{nir_dsn} : base 31 refusée (CCH-11 / CCH-12), affiliations à reprendre"
        )
    bases, cotisations, map_warnings = build_bases_and_cotisations(
        cot_lines,
        brut=brut,
        period_start=period_start,
        period_end=period_end,
        require_codes=require_cotisation_codes,
        default_ops=default_ops,
        smic_retenu=smic_retenu,
        affiliation_ids=[
            str(a.get("id_affiliation") or "") for a in affiliations_psc
        ]
        or None,
    )
    warnings.extend(map_warnings)

    classification = _classification(employee)
    numero = str(
        classification.get("numero_contrat_dsn")
        or employee.get("numero_contrat")
        or employee.get("contract_number")
        or "00000"
    )
    # Événements du contrat : arrêts (60), autres suspensions (65), fin (62)
    # et indemnités de rupture (52), qui sortent du salaire brut chômage.
    absences = [a for a in (employee.get("absences_dsn") or []) if isinstance(a, dict)]
    compte = next(
        (
            (str(v.get("iban") or ""), str(v.get("bic") or ""))
            for v in (settings.versements if settings else [])
            if v.get("iban")
        ),
        None,
    )
    subrogation_paie = synthese_net.get("subrogation_active")
    blocs_60 = (
        blocs_arret(
            absences,
            debut_mois,
            fin_mois,
            date_dsn(date_debut),
            compte_employeur=compte,
            subrogation_paie=subrogation_paie if isinstance(subrogation_paie, bool) else None,
        )
        if debut_mois
        else []
    )
    if any(b.get("S21.G00.60.004") == "01" and "S21.G00.60.007" not in b for b in blocs_60):
        warnings.append(
            f"Arrêt subrogé sans IBAN / BIC de l'employeur pour le NIR {nir_dsn} "
            "(60.007 / 60.008 obligatoires) : paramétrer les versements"
        )
    blocs_65 = blocs_suspension(payslip_data)
    dispositif_contrat = str(classification.get("dispositif_politique_publique") or "")
    apprentissage = dispositif_contrat in {"64", "65", "66"} or "apprenti" in str(
        employee.get("contract_type") or ""
    ).lower()
    bloc_62, avertissements_fin = (
        bloc_fin_contrat(employee, debut_mois, fin_mois, apprentissage=apprentissage)
        if debut_mois
        else (None, [])
    )
    warnings.extend(avertissements_fin)
    indemnites = indemnites_de_rupture(payslip_data, sortie=bool(bloc_62))
    indemnites_dans_le_brut = round(sum(m for _, m, dans in indemnites if dans), 2)
    duree_hebdo = employee.get("duree_hebdomadaire")
    heures_contrat_mois = (
        round(float(duree_hebdo) * 52 / 12, 2) if duree_hebdo not in (None, "") else None
    )
    mois_incomplet = period_start != period_bounds(period)[0] or (
        period_end != period_bounds(period)[1]
    )
    mesure_activite = (
        _jours_forfait(payslip_data, period_start, period_end, absences)
        if employee.get("is_forfait_jour")
        else None
    )

    rem_build = build_remunerations_from_payslip(
        payslip_data,
        brut=brut,
        period_start=period_start,
        period_end=period_end,
        period=period,
        contrat_ref=numero,
        jours_plafond=_jours_plafond(
            payslip_data, period, period_start, period_end, absences
        ),
        indemnites_rupture=indemnites_dans_le_brut,
        heures_contrat_mois=heures_contrat_mois,
        mois_incomplet=mois_incomplet,
        mesure_activite=mesure_activite,
    )

    # Composants de la base 03 : parts patronales santé (04) et retraite
    # supplémentaire (05), après le SMIC de la réduction (01) — ce que déclare
    # l'ancien logiciel sur 146 salariés-mois sur 146.
    sante_pat, _ = _parts_patronales_psc(cot_lines)
    retraite_sup_pat = round(
        sum(
            float(l.get("montant_patronal") or 0)
            for l in cot_lines
            if str(l.get("coti_id") or "") == "retraite_sup"
        ),
        2,
    )
    for base in bases:
        if (base.rubriques or {}).get("S21.G00.78.001") != "03":
            continue
        composants = list(base.rubriques.get("_composants_79") or [])
        for type_79, montant in (("04", sante_pat), ("05", retraite_sup_pat)):
            if montant > 0:
                composants.append({"type": type_79, "montant": f"{montant:.2f}"})
        if composants:
            base.rubriques["_composants_79"] = composants

    # Type et identifiant du taux PAS : « 01 - taux transmis par la DGFiP »
    # exige l'identifiant du compte rendu (50.008) ; sans lui, le type honnête
    # est « 13 - barème ». L'identifiant vient de la reprise des DSN du cabinet
    # aujourd'hui, du CRM via Cegid demain.
    pas_type = str(employee.get("pas_type_taux") or reprise.get("pas_type") or "")
    pas_identifiant = str(
        employee.get("pas_identifiant_taux") or reprise.get("pas_identifiant") or ""
    )
    if not pas_type:
        pas_type = "01" if pas_identifiant else "13"
    if pas_type != "01" and not pas_identifiant and _cdd_court_ou_imprecis(
        nature, employee
    ):
        # CT 50.008 : CDD de deux mois au plus, ou à terme imprécis : « -1 ».
        pas_identifiant = "-1"

    rubriques_versement = {
        "S21.G00.50.001": date_versement,
        "S21.G00.50.002": f"{net_fiscal:.2f}",
        "S21.G00.50.003": "01",
        "S21.G00.50.004": f"{net_verse:.2f}",
        "S21.G00.50.006": f"{pas_taux:.2f}",
        "S21.G00.50.007": pas_type,
        "S21.G00.50.009": f"{pas_montant:.2f}",
        "S21.G00.50.013": f"{(net_fiscal if pas_assiette is None else pas_assiette):.2f}",
        "activites": rem_build.activites,
    }
    if pas_identifiant and (pas_type == "01" or pas_identifiant == "-1"):
        rubriques_versement["S21.G00.50.008"] = pas_identifiant

    # Éléments de revenu calculés en net (bloc 58) : les heures sup exonérées
    # (type 01, loi MUES), puis le montant net social (type 03, obligatoire,
    # CCH-14). La paie calcule les deux.
    blocs_58: List[Dict[str, str]] = []
    hs_exonerees = float(synthese_net.get("montant_net_hs_exonerees") or 0)
    if hs_exonerees > 0:
        blocs_58.append(
            {
                "debut": period_start,
                "fin": period_end,
                "type": "01",
                "montant": f"{hs_exonerees:.2f}",
            }
        )
    montant_net_social = synthese_net.get("montant_net_social")
    if montant_net_social is not None:
        blocs_58.append(
            {
                "debut": period_start,
                "fin": period_end,
                "type": "03",
                "montant": f"{float(montant_net_social):.2f}",
            }
        )
    if blocs_58:
        rubriques_versement["_blocs_58"] = blocs_58

    # Autres éléments de revenu brut (bloc 54) : parts patronales santé (92),
    # prévoyance et retraite supplémentaire (93), datées de la période.
    sante, prevoyance = _parts_patronales_psc(cot_lines)
    # Participation et intéressement versés (11, 12, 37), datés de l'exercice.
    blocs_54 = [
        {
            "type": type_54,
            "montant": f"{montant:.2f}",
            "debut": f"0101{exercice}",
            "fin": f"3112{exercice}",
            "contrat": numero,
        }
        for type_54, montant, exercice in _epargne_salariale(payslip_data, period)
    ]
    blocs_54 += [
        {
            "type": type_54,
            "montant": f"{montant:.2f}",
            "debut": period_start,
            "fin": period_end,
            "contrat": numero,
        }
        for type_54, montant in (("92", sante), ("93", prevoyance))
        if montant > 0
    ]
    if blocs_54:
        rubriques_versement["_blocs_54"] = blocs_54

    # Indemnités de rupture (bloc 52, codes 001 à 025), rattachées au contrat.
    primes = [
        PrimeBlock(
            code=code,
            montant=montant,
            rubriques={
                "S21.G00.52.001": code,
                "S21.G00.52.002": f"{montant:.2f}",
                "S21.G00.52.006": numero,
            },
        )
        for code, montant, _ in indemnites
    ]
    # Prime de partage de la valeur (52.904 / 905), hors brut.
    primes += [
        PrimeBlock(
            code=code,
            montant=montant,
            rubriques={
                "S21.G00.52.001": code,
                "S21.G00.52.002": f"{montant:.2f}",
                "S21.G00.52.006": numero,
            },
        )
        for code, montant in primes_partage_valeur(payslip_data)
    ]

    versement = VersementBlock(
        date_versement=date_versement,
        net_fiscal=round(net_fiscal, 2),
        net_verse=round(net_verse, 2),
        pas=round(pas_montant, 2),
        pas_taux=round(pas_taux, 2),
        pas_type=pas_type,
        pas_identifiant=pas_identifiant,
        montant_soumis_pas=round(net_fiscal if pas_assiette is None else pas_assiette, 2),
        remunerations=rem_build.remunerations,
        bases_assujetties=bases,
        cotisations_individuelles=cotisations,
        primes=primes,
        rubriques=rubriques_versement,
    )

    # Affiliations prévoyance / santé (bloc S21.G00.70). Source première : la
    # reprise des DSN du cabinet (`affiliations_psc`), qui référence les
    # contrats du bloc 15 par leur ordre (70.013) et porte l'identifiant
    # technique (70.012) que les bases 31 citent en 78.005. À défaut, l'ancien
    # chemin `specificites_paie.mutuelle` reste lu.
    affiliations: List[AffiliationBlock] = []
    for entree in affiliations_psc:
        rubriques_aff = {
            "S21.G00.70.004": str(entree.get("option") or ""),
            "S21.G00.70.005": str(entree.get("population") or ""),
            "S21.G00.70.012": str(entree.get("id_affiliation") or ""),
            "S21.G00.70.013": str(entree.get("id_contrat") or ""),
        }
        affiliations.append(
            AffiliationBlock(
                code_option=rubriques_aff["S21.G00.70.004"],
                code_population=rubriques_aff["S21.G00.70.005"],
                identifiant_affiliation=rubriques_aff["S21.G00.70.012"],
                rubriques={k: v for k, v in rubriques_aff.items() if v},
            )
        )
    if not affiliations and isinstance(specs, dict):
        mutuelle = specs.get("mutuelle") or {}
        if isinstance(mutuelle, dict) and mutuelle.get("adhesion"):
            ref = str(mutuelle.get("reference_contrat") or mutuelle.get("contrat") or "")
            org = str(mutuelle.get("code_organisme") or "")
            affiliations.append(
                AffiliationBlock(
                    reference_contrat=ref,
                    code_organisme=org,
                    code_option=str(mutuelle.get("option") or ""),
                    code_population=str(mutuelle.get("population") or ""),
                    rubriques={
                        "S21.G00.70.001": ref,
                        "S21.G00.70.002": org,
                        "S21.G00.70.004": str(mutuelle.get("option") or ""),
                        "S21.G00.70.005": str(mutuelle.get("population") or ""),
                    },
                )
            )

    pcs = str(classification.get("pcs") or employee.get("pcs") or employee.get("code_pcs") or "")
    if not pcs:
        warnings.append(
            f"Code PCS-ESE (S21.G00.40.004) manquant pour le NIR {nir_dsn} : "
            "rubrique obligatoire, fiche à compléter"
        )
    idcc = normaliser_idcc(
        classification.get("idcc") or employee.get("idcc") or defauts.get("idcc") or ""
    )
    if not idcc:
        warnings.append(
            f"Code convention collective (IDCC) manquant pour le NIR {nir_dsn}"
        )
    dispositif = str(
        classification.get("dispositif_politique_publique")
        or employee.get("dispositif_politique")
        or "99"
    )
    if dispositif == "99" and apprentissage and defauts.get("dispositif_apprentissage"):
        # Un apprenti déclaré « sans dispositif » perd ses exonérations et
        # son contrat se lit comme un CDD ordinaire.
        dispositif = defauts["dispositif_apprentissage"]
    libelle_emploi = str(
        classification.get("libelle_emploi")
        or employee.get("job_title")
        or employee.get("poste")
        or ""
    )
    statut_dsn = str(classification.get("code_statut_dsn") or statut)
    position = str(classification.get("position") or "")

    rubriques_contrat = {
        "S21.G00.40.001": date_debut,
        "S21.G00.40.002": statut_dsn,
        "S21.G00.40.003": map_statut_categoriel_rc(statut_dsn),
        "S21.G00.40.004": pcs,
        "S21.G00.40.006": libelle_emploi,
        "S21.G00.40.007": nature,
        "S21.G00.40.008": dispositif,
        "S21.G00.40.009": numero,
        "S21.G00.40.011": unite,
        "S21.G00.40.012": q_ref,
        "S21.G00.40.013": quotite,
        "S21.G00.40.014": modalite,
        "S21.G00.40.019": company_siret.replace(" ", "")[:14],
    }
    # CDD et contrats à terme : la date de fin prévisionnelle est obligatoire
    # (CCH-12), le motif de recours attendu (SIG-11). La date vit déjà sur la
    # fiche ; le motif vient du contrat quand il y est, sinon de la reprise.
    date_fin_prev = iso_to_dsn_date(
        employee.get("contract_end_date") or employee.get("date_fin_contrat")
    ) or str(reprise.get("date_fin_contrat") or "")
    if date_fin_prev:
        rubriques_contrat["S21.G00.40.010"] = date_fin_prev
    motif_recours = str(
        classification.get("motif_recours")
        or employee.get("motif_recours_cdd")
        or (employee.get("dsn_reprise") or {}).get("motif_recours")
        or ""
    )
    if motif_recours:
        rubriques_contrat["S21.G00.40.021"] = motif_recours
    if idcc:
        rubriques_contrat["S21.G00.40.017"] = idcc
    # Codes régime de base maladie, vieillesse et accident du travail : ceux
    # de la fiche (importés sous « position »), le régime général sinon.
    for rubrique in ("S21.G00.40.018", "S21.G00.40.020", "S21.G00.40.039"):
        rubriques_contrat[rubrique] = position or REGIME_GENERAL
    # Code risque et taux AT : ceux de la fiche, ceux de l'établissement sinon.
    code_risque = str(
        classification.get("classification_dsn") or defauts.get("code_risque_at") or ""
    )
    if code_risque:
        rubriques_contrat["S21.G00.40.040"] = code_risque
    else:
        warnings.append(
            f"Code risque accident du travail (S21.G00.40.040) inconnu pour le NIR "
            f"{nir_dsn} : ni sur la fiche, ni commun à l'établissement"
        )
    # Positionnement dans la convention : niveau DSN de la fiche, à défaut son
    # coefficient (plasturgie : 700, 710, 720… sont les deux à la fois).
    niveau = classification.get("niveau_dsn") or classification.get("coefficient")
    if niveau not in (None, ""):
        rubriques_contrat["S21.G00.40.041"] = str(niveau)
    taux_at = str(classification.get("taux_at_individuel_dsn") or defauts.get("taux_at") or "")
    if taux_at:
        rubriques_contrat["S21.G00.40.043"] = taux_at
    rubriques_contrat.update(CONSTANTES_CONTRAT)

    ctr = ContratBlock(
        nature=nature,
        statut=statut,
        pcs=pcs,
        date_debut=date_debut,
        idcc=idcc,
        modalite_temps=modalite,
        quotite=quotite,
        quotite_reference=q_ref,
        unite_quotite=unite,
        dispositif=dispositif,
        numero_contrat=numero,
        libelle_emploi=libelle_emploi,
        affiliations=affiliations,
        versements=[versement],
        rubriques=rubriques_contrat,
    )
    ctr.arrets = [ArretTravailBlock(rubriques=bloc) for bloc in blocs_60]
    ctr.suspensions = [SuspensionContratBlock(rubriques=bloc) for bloc in blocs_65]
    if bloc_62:
        ctr.fin_contrat = FinContratBlock(rubriques=bloc_62)
    # Régime de retraite complémentaire : RUAA, le régime unifié AGIRC-ARRCO,
    # celui de tout le secteur privé. Le cabinet ne déclare rien d'autre sur les
    # sept sociétés, cadres compris.
    ctr.rubriques["_regime_retraite_complementaire"] = "RUAA"

    # Ancienneté dans l'entreprise depuis la date d'entrée : en mois révolus,
    # ou en jours pour un embauché du mois (zéro mois est refusé, CCH-12).
    anciennete = _anciennete_entreprise(date_debut, period_end)
    if anciennete is not None:
        unite_anciennete, valeur_anciennete = anciennete
        ctr.rubriques["_anciennete_entreprise"] = {
            "unite": unite_anciennete,
            "valeur": valeur_anciennete,
            "contrat": numero,
        }

    # BOETH éventuel
    boeth = employee.get("boeth_code") or employee.get("statut_boeth")
    if boeth:
        ctr.rubriques["S21.G00.40.072"] = str(boeth)

    lieu_naissance, departement_naissance, pays_naissance, avertissements = _naissance(
        employee, nir
    )
    warnings.extend(avertissements)
    sexe, avertissements = _sexe_declare(employee, nir)
    warnings.extend(avertissements)
    nom = str(employee.get("last_name") or "").upper()
    prenom = str(employee.get("first_name") or "").strip()
    matricule = str(
        employee.get("matricule") or employee.get("time_tracking_id") or ""
    )

    rubriques_individu = {
        "S21.G00.30.001": nir_dsn,
        "S21.G00.30.002": nom,
        "S21.G00.30.004": prenom,
        "S21.G00.30.005": sexe,
        "S21.G00.30.006": iso_to_dsn_date(
            employee.get("date_naissance") or employee.get("birth_date")
        ),
        "S21.G00.30.007": lieu_naissance,
        "S21.G00.30.008": addr["rue"],
        "S21.G00.30.009": addr["code_postal"],
        "S21.G00.30.010": addr["ville"],
        "S21.G00.30.013": map_codification_ue(
            employee.get("nationality") or employee.get("nationalite")
        ),
        "S21.G00.30.019": matricule,
    }
    if employee.get("nom_usage"):
        rubriques_individu["S21.G00.30.003"] = str(employee["nom_usage"]).upper()
    # Niveau de diplôme préparé (30.025), exigé avec un dispositif de politique
    # publique alternance (40.008 = 64/65/66). Donnée par salarié, reprise du
    # cabinet à défaut de saisie.
    niveau_diplome = str(
        employee.get("niveau_diplome_prepare")
        or reprise.get("niveau_diplome_prepare")
        or ""
    )
    if niveau_diplome:
        rubriques_individu["S21.G00.30.025"] = niveau_diplome
    elif dispositif in {"64", "65", "66"}:
        warnings.append(
            f"Niveau de diplôme préparé (S21.G00.30.025) manquant pour l'apprenti "
            f"NIR {nir_dsn} : obligatoire en apprentissage, fiche à compléter"
        )
    if departement_naissance:
        rubriques_individu["S21.G00.30.014"] = departement_naissance
    if pays_naissance:
        rubriques_individu["S21.G00.30.015"] = pays_naissance
    complement = (employee.get("adresse") or employee.get("address") or {})
    if isinstance(complement, dict) and complement.get("complement"):
        rubriques_individu["S21.G00.30.016"] = _texte_dsn(complement["complement"])
    rubriques_individu.update(CONSTANTES_INDIVIDU)

    ind = IndividuBlock(
        nom=nom,
        prenom=prenom,
        sexe=sexe,
        nir=nir_dsn,
        matricule=matricule,
        ntt=str(employee.get("ntt") or ""),
        date_naissance=iso_to_dsn_date(employee.get("date_naissance") or employee.get("birth_date")),
        lieu_naissance=lieu_naissance,
        adresse_rue=addr["rue"],
        adresse_cp=addr["code_postal"],
        adresse_ville=addr["ville"],
        contrats=[ctr],
        rubriques=rubriques_individu,
    )
    # Totaux cotisations stockés pour contrôles
    ind.rubriques["_cot_sal"] = f"{cot_sal:.2f}"
    ind.rubriques["_cot_pat"] = f"{cot_pat:.2f}"
    return ind, warnings


def _anciennete_entreprise(
    date_debut_dsn: str, fin_periode: str
) -> Optional[Tuple[str, str]]:
    """(unité, valeur) de l'ancienneté entreprise (S21.G00.86.002/003).

    Les deux dates arrivent au format DSN `JJMMAAAA`. Contrôlé sur les DSN du
    cabinet : une entrée au 01/12/2022 déclarée sur mai 2026 donne 41 mois
    (unité 02). Moins d'un mois révolu, la valeur 0 est refusée (CCH-12) : le
    cabinet passe en jours (unité 01), comptés du premier jour inclus — une
    entrée au 04/05 déclarée fin mai donne 28 jours.
    """
    try:
        debut = datetime.strptime(date_debut_dsn, "%d%m%Y")
        fin = datetime.strptime(fin_periode, "%d%m%Y")
    except (TypeError, ValueError):
        return None
    mois = (fin.year - debut.year) * 12 + (fin.month - debut.month)
    if fin.day < debut.day:
        mois -= 1
    if mois >= 1:
        return "02", str(mois)
    jours = (fin - debut).days + 1
    if jours < 0:
        return None
    return "01", str(jours)


def _cotisations_du_salarie(ind: IndividuBlock) -> List[Dict[str, Any]]:
    """Cotisations individuelles d'un salarié, à plat pour les agrégats."""
    lignes: List[Dict[str, Any]] = []
    for contrat in ind.contrats:
        for versement in contrat.versements:
            for cotisation in versement.cotisations_individuelles:
                rubriques = cotisation.rubriques or {}
                lignes.append(
                    {
                        "code": rubriques.get("S21.G00.81.001") or cotisation.code,
                        "base": str(rubriques.get("_base") or "").split("#")[0],
                        "assiette": float(rubriques.get("S21.G00.81.003") or 0),
                        "montant": float(rubriques.get("S21.G00.81.004") or 0),
                        "taux": float(rubriques.get("S21.G00.81.007") or 0),
                        "ops": rubriques.get("S21.G00.81.002") or "",
                    }
                )
    return lignes


def _paiements(
    etab: EtablissementBlock,
    period: str,
    ops_urssaf: str,
    parametres: DsnSettings,
) -> List[str]:
    """Bordereau Urssaf (22 / 23), versements (20) et assujettissements (44).

    Les montants viennent des cotisations individuelles déclarées ; les
    organismes, l'entité d'affectation et les coordonnées bancaires du
    paramétrage repris du cabinet. Un versement à un organisme
    complémentaire (prévoyance, santé, retraite supplémentaire) n'est pas
    produit : son appel est trimestriel et ventilé par contrat (bloc 55).
    """
    avertissements: List[str] = []
    debut, fin = period_bounds(period)
    salaries = [_cotisations_du_salarie(ind) for ind in etab.individus]
    urssaf = [[l for l in lignes if ops_urssaf and l["ops"] == ops_urssaf] for lignes in salaries]
    lignes_23, total_urssaf, inconnus = bordereau_urssaf(urssaf)
    for code in inconnus:
        avertissements.append(
            f"Cotisation {code} sans code type de personnel connu : absente du bordereau Urssaf"
        )
    if ops_urssaf and lignes_23:
        etab.bordereaux.append(
            BordereauBlock(
                identifiant=ops_urssaf,
                date_debut=debut,
                date_fin=fin,
                montant=float(total_urssaf),
                rubriques={
                    "S21.G00.22.001": ops_urssaf,
                    "S21.G00.22.003": debut,
                    "S21.G00.22.004": fin,
                    "S21.G00.22.005": f"{total_urssaf:.2f}",
                    "_cotisations_agregees": lignes_23,
                },
            )
        )

    pas = sum(
        float(v.pas or 0)
        for ind in etab.individus
        for contrat in ind.contrats
        for v in contrat.versements
    )
    montants = {
        "DGFIP": float(int(Decimal(str(round(pas, 6))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))),
        ops_urssaf: float(total_urssaf),
    }
    retraite = montant_retraite_complementaire(salaries)
    oc_ignores = []
    for versement in parametres.versements:
        organisme = str(versement.get("organisme") or "")
        if organisme in montants and organisme:
            montant = montants[organisme]
        elif organisme.isdigit() and len(organisme) == 14:
            montant = retraite  # caisse de retraite complémentaire (Agirc-Arrco)
        else:
            oc_ignores.append(organisme)
            continue
        rubriques = {
            "S21.G00.20.001": organisme,
            "S21.G00.20.002": str(versement.get("entite") or ""),
            "S21.G00.20.003": str(versement.get("bic") or ""),
            "S21.G00.20.004": str(versement.get("iban") or ""),
            "S21.G00.20.005": f"{montant:.2f}",
            "S21.G00.20.006": debut,
            "S21.G00.20.007": fin,
            "S21.G00.20.010": str(versement.get("mode") or "05"),
        }
        etab.versements_organismes.append(
            VersementOrganismeBlock(
                identifiant=organisme,
                montant=montant,
                rubriques={k: v for k, v in rubriques.items() if v},
            )
        )
    if not parametres.versements:
        avertissements.append(
            "Versements aux organismes non paramétrés (bloc S21.G00.20) : "
            "reprendre le paramétrage DSN du cabinet"
        )
    if oc_ignores:
        avertissements.append(
            "Versements aux organismes complémentaires non produits ("
            + ", ".join(oc_ignores)
            + ") : appel trimestriel par contrat, à régler hors DSN ou à paramétrer"
        )
    annee = period[:4]
    etab.rubriques["_blocs_44"] = [
        {"S21.G00.44.001": code, "S21.G00.44.002": "0.00", "S21.G00.44.003": annee}
        for code in parametres.assujettissements_fiscaux
    ]
    return avertissements


def build_parsed_dsn_from_payroll(
    company: Dict[str, Any],
    employees_data: List[Dict[str, Any]],
    period: str,
    *,
    dsn_type: str = "dsn_mensuelle_normale",
    file_name: str = "dsn_mensuelle.dsn",
    require_cotisation_codes: bool = False,
    settings: Optional[DsnSettings] = None,
) -> Tuple[DsnFile, List[str]]:
    """Construit un DsnFile P26 à partir de données déjà chargées (sans DB).

    ``employees_data`` : liste de dicts
    ``{employee: {...}, payslip_data: {...}}`` ou format ``get_dsn_employees_data``.
    """
    warnings: List[str] = []
    parametres = settings or DsnSettings()
    envoi = build_envoi(dsn_type=dsn_type, settings=parametres)
    declaration = build_declaration(period, settings=parametres)
    entreprise = build_entreprise(company, settings=parametres)
    etab = build_etablissement(company, entreprise, settings=parametres)
    warnings.extend(
        f"Paramétrage DSN incomplet : {manque}" for manque in parametres.manques()
    )
    default_ops = str(
        company.get("urssaf_number")
        or company.get("urssaf_siret")
        or company.get("ops_urssaf")
        or ""
    ).replace(" ", "")
    defauts_contrat = _defauts_contrat(company, employees_data, parametres)

    for row in employees_data:
        employee = row.get("employee") or row
        payslip_data = row.get("payslip_data")
        if payslip_data is None:
            payslip = row.get("payslip") or {}
            payslip_data = (
                payslip.get("payslip_data")
                if isinstance(payslip, dict)
                else {}
            ) or {}
        if not isinstance(payslip_data, dict):
            payslip_data = {}
        # Enrichir depuis totaux pré-calculés si présents
        if row.get("brut") and not payslip_data.get("salaire_brut"):
            payslip_data = {**payslip_data, "salaire_brut": row["brut"]}
        if row.get("net_imposable") is not None:
            synthese = dict(payslip_data.get("synthese_net") or {})
            synthese.setdefault("net_imposable", row["net_imposable"])
            if row.get("pas") is not None and "impot_prelevement_a_la_source" not in synthese:
                synthese["impot_prelevement_a_la_source"] = {
                    "montant": row["pas"],
                    "taux": 0,
                    "base": row.get("net_imposable") or 0,
                }
            payslip_data = {**payslip_data, "synthese_net": synthese}
        if row.get("cotisations_detail") and not (
            isinstance(payslip_data.get("structure_cotisations"), dict)
            and (
                payslip_data["structure_cotisations"].get("cotisations")
                or payslip_data["structure_cotisations"].get("bloc_principales")
            )
        ):
            payslip_data = {
                **payslip_data,
                "structure_cotisations": {
                    "cotisations": row["cotisations_detail"],
                    "total_salarial": row.get("cotisations_salariales") or 0,
                    "total_patronal": row.get("cotisations_patronales") or 0,
                },
            }

        # Bulletins à brut ≤ 0 (régularisations) : on saute sans bloquer le fichier.
        brut_preview = float(payslip_data.get("salaire_brut") or row.get("brut") or 0)
        if brut_preview <= 0:
            nir = str((employee or {}).get("nir") or "")[:13]
            warnings.append(
                f"Salarié exclu de la DSN (brut ≤ 0) NIR={nir or '?'} brut={brut_preview}"
            )
            continue

        try:
            ind, w = build_individu_from_payroll(
                employee,
                payslip_data,
                period=period,
                company_siret=etab.siret,
                require_cotisation_codes=require_cotisation_codes,
                default_ops=default_ops,
                settings=parametres,
                defauts_contrat=defauts_contrat,
            )
            warnings.extend(w)
            etab.individus.append(ind)
        except DsnBuildError as exc:
            # Erreurs bloquantes individuelles (NIR, embauche…) : skip + warning
            warnings.append(str(exc))
            continue

    if not etab.individus:
        raise DsnBuildError("Aucun salarié avec bulletin pour la période")

    warnings.extend(_paiements(etab, period, default_ops, parametres))

    return (
        DsnFile(
            file_name=file_name,
            envoi=envoi,
            declaration=declaration,
            entreprise=entreprise,
            etablissement=etab,
            dsn_format="modern",
            parse_warnings=list(warnings),
        ),
        warnings,
    )
