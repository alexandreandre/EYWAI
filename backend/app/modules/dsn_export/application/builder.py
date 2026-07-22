"""Construction d'une DSN P26V01 depuis données société / salariés / bulletins."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.modules.dsn_export.domain.contract_map import (
    iso_to_dsn_date,
    map_contract_nature_to_dsn,
    map_modalite_temps,
    map_sexe_to_dsn,
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
from app.modules.exports.infrastructure.payslip_accounting_extract import (
    extract_cotisations_from_payslip,
    extract_pas_amount,
)
from app.shared.dsn_validation import build_siret_from_siren_nic


class DsnBuildError(ValueError):
    """Donnée obligatoire manquante pour générer la DSN."""


def _addr(obj: Any) -> Dict[str, str]:
    if not isinstance(obj, dict):
        return {"rue": "", "code_postal": "", "ville": ""}
    return {
        "rue": str(obj.get("rue") or obj.get("street") or ""),
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


def _is_cadre(employee: Dict[str, Any]) -> bool:
    statut = str(employee.get("statut") or "").lower()
    if "cadre" in statut and "non" not in statut:
        return True
    cat = str(employee.get("statut_categoriel") or employee.get("categorie") or "").lower()
    return "cadre" in cat and "non" not in cat


def build_envoi(*, dsn_type: str = "dsn_mensuelle_normale") -> EnvoiBlock:
    mode = "01"  # réel
    if "test" in (dsn_type or "").lower():
        mode = "02"
    return EnvoiBlock(
        periode="01",
        norme="P26V01",
        type_envoi=mode,
        rubriques={
            "S10.G00.00.001": "EYWAI Paie",
            "S10.G00.00.002": "EYWAI",
            "S10.G00.00.003": "1.0",
            "S10.G00.00.004": "0",
            "S10.G00.00.005": "01",
            "S10.G00.00.006": "P26V01",
            "S10.G00.00.007": mode,
            "S10.G00.00.008": "01",
        },
    )


def build_declaration(period: str) -> DeclarationBlock:
    mois = period_to_mois_principal(period)
    return DeclarationBlock(
        nature="01",
        type_declaration="01",
        mois_principal=mois,
        rubriques={
            "S20.G00.05.001": "01",
            "S20.G00.05.002": "01",
            "S20.G00.05.003": "11",
            "S20.G00.05.004": "1",
            "S20.G00.05.005": mois,
            "S20.G00.05.008": "01",
            "S20.G00.05.010": "01",
        },
    )


def build_entreprise(company: Dict[str, Any]) -> EntrepriseBlock:
    siret = str(company.get("siret") or "")
    siren, nic = _siren_nic(siret)
    if not siren or len(siren) != 9:
        raise DsnBuildError("SIREN/SIRET société manquant ou invalide")
    addr = _addr(company.get("address") or company.get("adresse"))
    naf = str(company.get("code_naf") or company.get("naf") or "")
    if not naf:
        raise DsnBuildError("Code NAF manquant pour l'établissement")
    return EntrepriseBlock(
        siren=siren,
        nic_siege=nic,
        raison_sociale=str(company.get("name") or company.get("raison_sociale") or ""),
        code_naf=naf,
        adresse_rue=addr["rue"],
        adresse_cp=addr["code_postal"],
        adresse_ville=addr["ville"],
        rubriques={
            "S21.G00.06.001": siren,
            "S21.G00.06.002": nic,
            "S21.G00.06.003": naf,
            "S21.G00.06.004": addr["rue"],
            "S21.G00.06.005": addr["code_postal"],
            "S21.G00.06.006": addr["ville"],
        },
    )


def build_etablissement(company: Dict[str, Any], entreprise: EntrepriseBlock) -> EtablissementBlock:
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
        rubriques={
            "S21.G00.11.001": nic,
            "S21.G00.11.002": entreprise.code_naf,
            "S21.G00.11.003": addr["rue"],
            "S21.G00.11.004": addr["code_postal"],
            "S21.G00.11.005": addr["ville"],
        },
    )
    # Organismes PSC éventuels depuis company settings
    mutuelle_types = company.get("mutuelle_types") or company.get("psc_contracts") or []
    if isinstance(mutuelle_types, list):
        for idx, mt in enumerate(mutuelle_types, start=1):
            if not isinstance(mt, dict):
                continue
            ref = str(mt.get("reference_contrat") or mt.get("code") or "")
            org = str(mt.get("code_organisme") or mt.get("organisme") or "")
            if not ref and not org:
                continue
            etab.organismes_psc.append(
                OrganismePscBlock(
                    reference_contrat=ref,
                    code_organisme=org,
                    code_nature=str(mt.get("nature") or "01"),
                    rang=str(idx),
                    rubriques={
                        "S21.G00.15.001": ref,
                        "S21.G00.15.002": org,
                        "S21.G00.15.004": str(mt.get("nature") or "01"),
                        "S21.G00.15.005": str(idx),
                    },
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

    cot_sal, cot_pat, cot_lines, meta = extract_cotisations_from_payslip(payslip_data)
    warnings.extend(meta.get("warnings") or [])
    bases, cotisations, map_warnings = build_bases_and_cotisations(
        cot_lines,
        brut=brut,
        period_start=period_start,
        period_end=period_end,
        require_codes=require_cotisation_codes,
        default_ops=default_ops,
    )
    warnings.extend(map_warnings)

    numero = str(
        employee.get("numero_contrat")
        or employee.get("contract_number")
        or employee.get("matricule")
        or "00001"
    )
    rem_build = build_remunerations_from_payslip(
        payslip_data,
        brut=brut,
        period_start=period_start,
        period_end=period_end,
        period=period,
        contrat_ref="00000",
    )

    versement = VersementBlock(
        date_versement=period_end,
        net_fiscal=round(net_fiscal, 2),
        net_verse=round(net_verse, 2),
        pas=round(pas_montant, 2),
        pas_taux=round(pas_taux, 2),
        pas_type="01",
        pas_identifiant="",
        montant_soumis_pas=round(pas_assiette or net_fiscal, 2),
        remunerations=rem_build.remunerations,
        bases_assujetties=bases,
        cotisations_individuelles=cotisations,
        rubriques={
            "S21.G00.50.001": period_end,
            "S21.G00.50.002": f"{net_fiscal:.2f}",
            "S21.G00.50.003": "01",
            "S21.G00.50.004": f"{net_verse:.2f}",
            "S21.G00.50.006": f"{pas_taux:.2f}",
            "S21.G00.50.007": "01",
            "S21.G00.50.009": f"{pas_montant:.2f}",
            "S21.G00.50.013": f"{(pas_assiette or net_fiscal):.2f}",
            "activites": rem_build.activites,
        },
    )

    # Affiliation PSC si présente sur la fiche
    affiliations: List[AffiliationBlock] = []
    specs = employee.get("specificites_paie") or {}
    if isinstance(specs, dict):
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

    ctr = ContratBlock(
        nature=nature,
        statut=statut,
        pcs=str(employee.get("pcs") or employee.get("code_pcs") or ""),
        date_debut=date_debut,
        idcc=str(employee.get("idcc") or ""),
        modalite_temps=modalite,
        quotite=quotite,
        quotite_reference=q_ref,
        unite_quotite=unite,
        dispositif=str(employee.get("dispositif_politique") or "99"),
        numero_contrat=numero,
        libelle_emploi=str(employee.get("job_title") or employee.get("poste") or ""),
        affiliations=affiliations,
        versements=[versement],
        rubriques={
            "S21.G00.40.001": date_debut,
            "S21.G00.40.002": statut,
            "S21.G00.40.004": str(employee.get("pcs") or ""),
            "S21.G00.40.006": str(employee.get("job_title") or employee.get("poste") or ""),
            "S21.G00.40.007": nature,
            "S21.G00.40.008": str(employee.get("dispositif_politique") or "99"),
            "S21.G00.40.009": numero,
            "S21.G00.40.011": unite,
            "S21.G00.40.012": q_ref,
            "S21.G00.40.013": quotite,
            "S21.G00.40.014": modalite,
            "S21.G00.40.017": str(employee.get("idcc") or ""),
            "S21.G00.40.019": company_siret.replace(" ", "")[:14],
        },
    )
    # BOETH éventuel
    boeth = employee.get("boeth_code") or employee.get("statut_boeth")
    if boeth:
        ctr.rubriques["S21.G00.40.072"] = str(boeth)

    ind = IndividuBlock(
        nom=str(employee.get("last_name") or "").upper(),
        prenom=str(employee.get("first_name") or "").upper(),
        sexe=map_sexe_to_dsn(employee.get("sexe") or employee.get("gender")),
        nir=nir_dsn,
        matricule=str(employee.get("matricule") or employee.get("time_tracking_id") or ""),
        ntt=str(employee.get("ntt") or ""),
        date_naissance=iso_to_dsn_date(employee.get("date_naissance") or employee.get("birth_date")),
        lieu_naissance=str(employee.get("lieu_naissance") or ""),
        adresse_rue=addr["rue"],
        adresse_cp=addr["code_postal"],
        adresse_ville=addr["ville"],
        contrats=[ctr],
        rubriques={
            "S21.G00.30.001": nir_dsn,
            "S21.G00.30.002": str(employee.get("last_name") or "").upper(),
            "S21.G00.30.004": str(employee.get("first_name") or "").upper(),
            "S21.G00.30.005": map_sexe_to_dsn(employee.get("sexe") or employee.get("gender")),
            "S21.G00.30.006": iso_to_dsn_date(
                employee.get("date_naissance") or employee.get("birth_date")
            ),
            "S21.G00.30.007": str(employee.get("lieu_naissance") or ""),
            "S21.G00.30.008": addr["rue"],
            "S21.G00.30.009": addr["code_postal"],
            "S21.G00.30.010": addr["ville"],
            "S21.G00.30.019": str(
                employee.get("matricule") or employee.get("time_tracking_id") or ""
            ),
        },
    )
    # Totaux cotisations stockés pour contrôles
    ind.rubriques["_cot_sal"] = f"{cot_sal:.2f}"
    ind.rubriques["_cot_pat"] = f"{cot_pat:.2f}"
    return ind, warnings


def build_parsed_dsn_from_payroll(
    company: Dict[str, Any],
    employees_data: List[Dict[str, Any]],
    period: str,
    *,
    dsn_type: str = "dsn_mensuelle_normale",
    file_name: str = "dsn_mensuelle.dsn",
    require_cotisation_codes: bool = False,
) -> Tuple[DsnFile, List[str]]:
    """Construit un DsnFile P26 à partir de données déjà chargées (sans DB).

    ``employees_data`` : liste de dicts
    ``{employee: {...}, payslip_data: {...}}`` ou format ``get_dsn_employees_data``.
    """
    warnings: List[str] = []
    envoi = build_envoi(dsn_type=dsn_type)
    declaration = build_declaration(period)
    entreprise = build_entreprise(company)
    etab = build_etablissement(company, entreprise)
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
