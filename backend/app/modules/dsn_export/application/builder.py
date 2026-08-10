"""Construction d'une DSN P26V01 depuis données société / salariés / bulletins."""

from __future__ import annotations

import re
from datetime import date, datetime
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
from app.modules.dsn_export.domain.cotisation_mapping import build_bases_and_cotisations
from app.modules.dsn_export.domain.remuneration_map import build_remunerations_from_payslip
from app.modules.dsn_import.domain.model import (
    AffiliationBlock,
    ContratBlock,
    DeclarationBlock,
    DsnFile,
    EtablissementBlock,
    EntrepriseBlock,
    EnvoiBlock,
    IndividuBlock,
    OrganismePscBlock,
    VersementBlock,
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


def _addr(obj: Any) -> Dict[str, str]:
    if not isinstance(obj, dict):
        return {"rue": "", "code_postal": "", "ville": ""}
    return {
        "rue": _voie_dsn(obj.get("rue") or obj.get("street") or ""),
        "code_postal": str(obj.get("code_postal") or obj.get("postal_code") or ""),
        "ville": str(obj.get("ville") or obj.get("city") or ""),
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


def _pas_details(payslip_data: Dict[str, Any]) -> Tuple[float, float, float]:
    """Retourne (montant, taux, assiette)."""
    synthese = payslip_data.get("synthese_net")
    if not isinstance(synthese, dict):
        return 0.0, 0.0, 0.0
    pas_obj = synthese.get("impot_prelevement_a_la_source")
    if isinstance(pas_obj, dict):
        return (
            float(pas_obj.get("montant") or 0),
            float(pas_obj.get("taux") or 0),
            float(pas_obj.get("base") or pas_obj.get("assiette") or 0),
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
    pays = ""
    if departement in DEPARTEMENTS_METROPOLE_ET_DOM:
        pays = "FR"
    elif departement:
        # 99 = né à l'étranger : le code pays ISO n'est pas dans la fiche.
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
) -> Tuple[IndividuBlock, List[str]]:
    warnings: List[str] = []
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

    brut = float(payslip_data.get("salaire_brut") or 0)
    if brut <= 0:
        raise DsnBuildError(f"Brut ≤ 0 pour NIR {nir_dsn}")

    net_fiscal = _net_imposable(payslip_data)
    net_verse = _net_a_payer(payslip_data)
    pas_montant, pas_taux, pas_assiette = _pas_details(payslip_data)

    # Données de reprise DSN posées sur la fiche par les scripts de reprise :
    # affiliations prévoyance/santé du salarié, type et identifiant du taux
    # PAS, SMIC retenu — tout ce qui ne se déduit ni du bulletin ni du contrat.
    reprise = employee.get("dsn_reprise") or {}
    affiliations_psc = [
        a for a in (employee.get("affiliations_psc") or []) if isinstance(a, dict)
    ]

    synthese_net = payslip_data.get("synthese_net") or {}
    smic_retenu = synthese_net.get("montant_smic_reduction_generale") or reprise.get(
        "smic_retenu"
    )

    extract_cotisations_from_payslip, _ = _extracteurs_bulletin()
    cot_sal, cot_pat, cot_lines, meta = extract_cotisations_from_payslip(payslip_data)
    warnings.extend(meta.get("warnings") or [])
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
    rem_build = build_remunerations_from_payslip(
        payslip_data,
        brut=brut,
        period_start=period_start,
        period_end=period_end,
        period=period,
        contrat_ref="00000",
    )

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

    rubriques_versement = {
        "S21.G00.50.001": period_end,
        "S21.G00.50.002": f"{net_fiscal:.2f}",
        "S21.G00.50.003": "01",
        "S21.G00.50.004": f"{net_verse:.2f}",
        "S21.G00.50.006": f"{pas_taux:.2f}",
        "S21.G00.50.007": pas_type,
        "S21.G00.50.009": f"{pas_montant:.2f}",
        "S21.G00.50.013": f"{(pas_assiette or net_fiscal):.2f}",
        "activites": rem_build.activites,
    }
    if pas_type == "01" and pas_identifiant:
        rubriques_versement["S21.G00.50.008"] = pas_identifiant

    # Montant net social (bloc 58 type 03), obligatoire depuis 2023. La paie le
    # calcule déjà : seul manquait le bloc.
    montant_net_social = synthese_net.get("montant_net_social")
    if montant_net_social is not None:
        rubriques_versement["_blocs_58"] = [
            {
                "debut": period_start,
                "fin": period_end,
                "type": "03",
                "montant": f"{float(montant_net_social):.2f}",
            }
        ]

    versement = VersementBlock(
        date_versement=period_end,
        net_fiscal=round(net_fiscal, 2),
        net_verse=round(net_verse, 2),
        pas=round(pas_montant, 2),
        pas_taux=round(pas_taux, 2),
        pas_type=pas_type,
        pas_identifiant=pas_identifiant,
        montant_soumis_pas=round(pas_assiette or net_fiscal, 2),
        remunerations=rem_build.remunerations,
        bases_assujetties=bases,
        cotisations_individuelles=cotisations,
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
    specs = employee.get("specificites_paie") or {}
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
    idcc = normaliser_idcc(classification.get("idcc") or employee.get("idcc") or "")
    if not idcc:
        warnings.append(
            f"Code convention collective (IDCC) manquant pour le NIR {nir_dsn}"
        )
    dispositif = str(
        classification.get("dispositif_politique_publique")
        or employee.get("dispositif_politique")
        or "99"
    )
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
    )
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
    # Position, niveau et classification conventionnelle du salarié.
    for rubrique in ("S21.G00.40.018", "S21.G00.40.020", "S21.G00.40.039"):
        if position:
            rubriques_contrat[rubrique] = position
    if classification.get("classification_dsn"):
        rubriques_contrat["S21.G00.40.040"] = str(classification["classification_dsn"])
    if classification.get("niveau_dsn"):
        rubriques_contrat["S21.G00.40.041"] = str(classification["niveau_dsn"])
    if classification.get("taux_at_individuel_dsn"):
        rubriques_contrat["S21.G00.40.043"] = str(
            classification["taux_at_individuel_dsn"]
        )
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
    # Régime de retraite complémentaire : RUAA, le régime unifié AGIRC-ARRCO,
    # celui de tout le secteur privé. Le cabinet ne déclare rien d'autre sur les
    # sept sociétés, cadres compris.
    ctr.rubriques["_regime_retraite_complementaire"] = "RUAA"

    # Ancienneté dans l'entreprise, en mois révolus depuis la date d'entrée.
    mois_anciennete = _anciennete_en_mois(date_debut, period_end)
    if mois_anciennete is not None:
        ctr.rubriques["_anciennete_entreprise"] = {
            "unite": "02",  # mois
            "valeur": str(mois_anciennete),
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
    if departement_naissance:
        rubriques_individu["S21.G00.30.014"] = departement_naissance
    if pays_naissance:
        rubriques_individu["S21.G00.30.015"] = pays_naissance
    complement = (employee.get("adresse") or employee.get("address") or {})
    if isinstance(complement, dict) and complement.get("complement"):
        rubriques_individu["S21.G00.30.016"] = str(complement["complement"])
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


def _anciennete_en_mois(date_debut_dsn: str, fin_periode: str) -> Optional[int]:
    """Mois révolus entre l'entrée et la fin du mois déclaré (S21.G00.86.003).

    Les deux dates arrivent au format DSN `JJMMAAAA`. Contrôlé sur les DSN du
    cabinet : une entrée au 01/12/2022 déclarée sur mai 2026 donne 41 mois.
    """
    try:
        debut = datetime.strptime(date_debut_dsn, "%d%m%Y")
        fin = datetime.strptime(fin_periode, "%d%m%Y")
    except (TypeError, ValueError):
        return None
    mois = (fin.year - debut.year) * 12 + (fin.month - debut.month)
    if fin.day < debut.day:
        mois -= 1
    return mois if mois >= 0 else None


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
            )
            warnings.extend(w)
            etab.individus.append(ind)
        except DsnBuildError as exc:
            # Erreurs bloquantes individuelles (NIR, embauche…) : skip + warning
            warnings.append(str(exc))
            continue

    if not etab.individus:
        raise DsnBuildError("Aucun salarié avec bulletin pour la période")

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
