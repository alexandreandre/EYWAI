"""Sérialisation NEODeS plat P26V01 depuis le modèle dsn_import."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

from app.modules.dsn_import.domain.model import (
    AffiliationBlock,
    AncienneteBlock,
    ArretTravailBlock,
    BaseAssujettieBlock,
    BordereauBlock,
    ComposantBaseBlock,
    ComposantCotisationEtabBlock,
    CompteurAnnuelBlock,
    ContratBlock,
    CotisationAgregeeBlock,
    CotisationIndividuelleBlock,
    DeclarationBlock,
    DsnFile,
    EtablissementBlock,
    EntrepriseBlock,
    EnvoiBlock,
    FinContratBlock,
    IndividuBlock,
    OrganismePscBlock,
    ParsedDsnSet,
    PrimeBlock,
    RemunerationBlock,
    RubriqueLine,
    SuspensionContratBlock,
    VersementBlock,
    VersementOrganismeBlock,
)
from app.modules.dsn_import.domain.rubriques import (
    R_S10_NORME,
    R_S10_PERIODE,
    R_S10_TYPE,
    R_S20_DECL_MOIS,
    R_S20_DECL_NATURE,
    R_S20_DECL_TYPE,
    R_S21_ACT_MESURE,
    R_S21_ACT_TYPE,
    R_S21_ACT_UNITE,
    R_S21_ANC86_CONTRAT,
    R_S21_ANC86_TYPE,
    R_S21_ANC86_UNITE,
    R_S21_ANC86_VALEUR,
    R_S21_ANC_DEB,
    R_S21_ANC_FIN,
    R_S21_ANC_TYPE,
    R_S21_ARRET_CAISSE,
    R_S21_ARRET_DEB,
    R_S21_ARRET_FIN,
    R_S21_ARRET_MOTIF,
    R_S21_BA_CODE,
    R_S21_BA_MONTANT,
    R_S21_BORD_DATE_DEB,
    R_S21_BORD_DATE_FIN,
    R_S21_BORD_IDENT,
    R_S21_BORD_MONTANT,
    R_S21_CA_BASE,
    R_S21_CA_CODE,
    R_S21_CA_MONTANT,
    R_S21_CA_TAUX,
    R_S21_CB_CODE,
    R_S21_CB_MONTANT,
    R_S21_CCET_ASSIETTE,
    R_S21_CCET_CODE,
    R_S21_CCET_MONTANT,
    R_S21_CCET_REGIME,
    R_S21_CCET_TAUX,
    R_S21_CPT_ANNEE,
    R_S21_CPT_CODE,
    R_S21_CPT_MONTANT,
    R_S21_CTR_DATE_DEBUT,
    R_S21_CTR_DATE_FIN,
    R_S21_CTR_DISPOSITIF,
    R_S21_CTR_IDCC,
    R_S21_CTR_LIBELLE_EMPLOI,
    R_S21_CTR_MODALITE_TEMPS,
    R_S21_CTR_NATURE,
    R_S21_CTR_NUMERO,
    R_S21_CTR_PCS,
    R_S21_CTR_REGIME_RC,
    R_S21_CTR_POSITION,
    R_S21_CTR_QUOTITE,
    R_S21_CTR_QUOTITE_REF,
    R_S21_CTR_STATUT,
    R_S21_CTR_UNITE_QUOTITE,
    R_S21_ENT_CP,
    R_S21_ENT_NAF,
    R_S21_ENT_NIC_SIEGE,
    R_S21_ENT_RUE,
    R_S21_ENT_SIREN,
    R_S21_ENT_VILLE,
    R_S21_ETAB_CP,
    R_S21_ETAB_NAF,
    R_S21_ETAB_NIC,
    R_S21_ETAB_RUE,
    R_S21_ETAB_VILLE,
    R_S21_FIN_DATE,
    R_S21_FIN_MOTIF,
    R_S21_FIN_NOTIF,
    R_S21_IND_CP,
    R_S21_IND_LIEU_NAISS,
    R_S21_IND_MATRICULE,
    R_S21_IND_NAISSANCE,
    R_S21_IND_NIR,
    R_S21_IND_NOM,
    R_S21_IND_NOM_USAGE,
    R_S21_IND_NTT,
    R_S21_IND_PRENOM,
    R_S21_IND_RUE,
    R_S21_IND_SEXE,
    R_S21_IND_VILLE,
    R_S21_ORG_CODE,
    R_S21_ORG_NATURE,
    R_S21_ORG_RANG,
    R_S21_ORG_REF,
    R_S21_PRIME_CODE,
    R_S21_PRIME_MONTANT,
    R_S21_REM_HEURES,
    R_S21_REM_MONTANT,
    R_S21_REM_PERIODE_DEB,
    R_S21_REM_PERIODE_FIN,
    R_S21_REM_TYPE,
    R_S21_SUSP_DEB,
    R_S21_SUSP_FIN,
    R_S21_SUSP_MOTIF,
    R_S21_SUSP_TYPE,
    R_S21_VER_DATE,
    R_S21_VER_NET_FISCAL,
    R_S21_VER_NET_VERSE,
    R_S21_VER_NUMERO,
    R_S21_VER_PAS,
    R_S21_VER_PAS_ASSIETTE,
    R_S21_VER_PAS_ID,
    R_S21_VER_PAS_TAUX,
    R_S21_VER_PAS_TYPE,
    R_S21_VO_BIC,
    R_S21_VO_DATE_DEB,
    R_S21_VO_DATE_FIN,
    R_S21_VO_IBAN,
    R_S21_VO_IDENT,
    R_S21_VO_LIBELLE,
    R_S21_VO_MODE,
    R_S21_VO_MONTANT,
)

DSN_ENCODING = "iso-8859-15"
FORBIDDEN_CHARS = ("<", ">", "&")
# NEODeS sépare les lignes en CRLF ; c'est ce que contiennent les fichiers
# déposés et acceptés.
FIN_DE_LIGNE = "\r\n"
RUB_TOTAL_LIGNES = "S90.G00.90.001"
RUB_TOTAL_DECLARATIONS = "S90.G00.90.002"


class DsnWriterError(ValueError):
    """Valeur incompatible avec la sérialisation NEODeS plate."""


def quote_value(value: str) -> str:
    """Encadre la valeur d'apostrophes, sans échapper celles qu'elle contient.

    NEODeS ne prévoit pas d'échappement : une adresse comme
    ``ZA L'OUSSON NORD`` s'écrit telle quelle entre apostrophes, et c'est ainsi
    que la déclarent les fichiers acceptés par net-entreprises. Doubler
    l'apostrophe fabriquerait une valeur fausse.
    """
    text = "" if value is None else str(value)
    for ch in FORBIDDEN_CHARS:
        if ch in text:
            raise DsnWriterError(
                f"Caractère interdit '{ch}' dans une rubrique DSN : {text[:80]}"
            )
    if "\n" in text or "\r" in text:
        raise DsnWriterError(
            f"Retour à la ligne interdit dans une rubrique DSN : {text[:80]}"
        )
    return "'" + text + "'"


def format_rubrique_line(rubrique: str, valeur: str) -> str:
    return f"{rubrique},{quote_value(valeur)}"


def _emit(rubrique: str, valeur: Optional[str], out: List[str]) -> None:
    if valeur is None:
        return
    text = str(valeur).strip()
    if text == "":
        return
    out.append(format_rubrique_line(rubrique, text))


def _emit_rubriques_dict(rubriques: dict, out: List[str], skip: Optional[set] = None) -> None:
    """Émet les rubriques brutes conservées, **par numéro croissant**.

    L'ordre n'est pas cosmétique : la norme NEODeS impose des rubriques
    croissantes à l'intérieur d'un bloc. Un lecteur qui rencontre un numéro
    inférieur au précédent considère le bloc terminé, et tient pour absentes
    toutes les rubriques qui suivent — même écrites juste en dessous. Émettre
    dans l'ordre d'insertion du dictionnaire suffisait à rendre nos DSN
    non déposables : DSN-VAL relevait 10 575 « absences » de rubriques du bloc
    contrat qui étaient toutes présentes, mais mal placées.

    Les codes sont de longueur fixe et à chiffres cadrés (`S21.G00.40.003`),
    l'ordre lexicographique est donc l'ordre numérique.
    """
    ignored = skip or set()
    retenues = [
        (str(key), val)
        for key, val in (rubriques or {}).items()
        if key
        and key not in ignored
        and str(key).startswith("S")
        and not isinstance(val, (list, dict))
    ]
    for key, val in sorted(retenues, key=lambda paire: paire[0]):
        _emit(key, str(val), out)


def _fmt_amount(value: float) -> str:
    return f"{float(value):.2f}"


def _fmt_rate(value: float) -> str:
    return f"{float(value):.3f}"


def write_envoi(envoi: EnvoiBlock, out: List[str]) -> None:
    if envoi.rubriques:
        _emit_rubriques_dict(envoi.rubriques, out)
        return
    _emit("S10.G00.00.001", "EYWAI Paie", out)
    _emit("S10.G00.00.002", "EYWAI", out)
    _emit("S10.G00.00.003", "1.0", out)
    _emit("S10.G00.00.004", "0", out)
    _emit(R_S10_PERIODE, envoi.periode or "01", out)
    _emit(R_S10_NORME, envoi.norme or "P26V01", out)
    _emit(R_S10_TYPE, envoi.type_envoi or "01", out)
    _emit("S10.G00.00.008", "01", out)


def write_declaration(declaration: DeclarationBlock, out: List[str]) -> None:
    if declaration.rubriques:
        _emit_rubriques_dict(declaration.rubriques, out)
    else:
        _emit(R_S20_DECL_NATURE, declaration.nature or "01", out)
        _emit(R_S20_DECL_TYPE, declaration.type_declaration or "01", out)
        _emit("S20.G00.05.003", "11", out)
        _emit("S20.G00.05.004", "1", out)
        _emit(R_S20_DECL_MOIS, declaration.mois_principal, out)
        _emit("S20.G00.05.008", "01", out)
        _emit("S20.G00.05.010", "01", out)
    for contact in declaration.contacts or []:
        _emit_rubriques_dict(contact, out)


def write_entreprise(entreprise: EntrepriseBlock, out: List[str]) -> None:
    if entreprise.rubriques:
        _emit_rubriques_dict(entreprise.rubriques, out)
        return
    _emit(R_S21_ENT_SIREN, entreprise.siren, out)
    _emit(R_S21_ENT_NIC_SIEGE, entreprise.nic_siege, out)
    _emit(R_S21_ENT_NAF, entreprise.code_naf, out)
    _emit(R_S21_ENT_RUE, entreprise.adresse_rue, out)
    _emit(R_S21_ENT_CP, entreprise.adresse_cp, out)
    _emit(R_S21_ENT_VILLE, entreprise.adresse_ville, out)


def write_organisme_psc(org: OrganismePscBlock, out: List[str]) -> None:
    if org.rubriques:
        _emit_rubriques_dict(org.rubriques, out)
        return
    _emit(R_S21_ORG_REF, org.reference_contrat, out)
    _emit(R_S21_ORG_CODE, org.code_organisme, out)
    _emit(R_S21_ORG_NATURE, org.code_nature, out)
    _emit(R_S21_ORG_RANG, org.rang, out)


def write_versement_organisme(vo: VersementOrganismeBlock, out: List[str]) -> None:
    if vo.rubriques:
        _emit_rubriques_dict(vo.rubriques, out)
        return
    _emit(R_S21_VO_IDENT, vo.identifiant, out)
    _emit(R_S21_VO_LIBELLE, vo.libelle, out)
    _emit(R_S21_VO_BIC, vo.bic, out)
    _emit(R_S21_VO_IBAN, vo.iban, out)
    if vo.montant:
        _emit(R_S21_VO_MONTANT, _fmt_amount(vo.montant), out)
    _emit(R_S21_VO_DATE_DEB, vo.date_debut, out)
    _emit(R_S21_VO_DATE_FIN, vo.date_fin, out)
    _emit(R_S21_VO_MODE, vo.mode_paiement, out)


def write_bordereau(bord: BordereauBlock, out: List[str]) -> None:
    if bord.rubriques:
        _emit_rubriques_dict(bord.rubriques, out)
        return
    _emit(R_S21_BORD_IDENT, bord.identifiant, out)
    _emit(R_S21_BORD_DATE_DEB, bord.date_debut, out)
    _emit(R_S21_BORD_DATE_FIN, bord.date_fin, out)
    if bord.montant:
        _emit(R_S21_BORD_MONTANT, _fmt_amount(bord.montant), out)


def write_composant_etab(cc: ComposantCotisationEtabBlock, out: List[str]) -> None:
    if cc.rubriques:
        _emit_rubriques_dict(cc.rubriques, out)
        return
    _emit(R_S21_CCET_CODE, cc.code, out)
    _emit(R_S21_CCET_REGIME, cc.regime, out)
    if cc.taux:
        _emit(R_S21_CCET_TAUX, _fmt_rate(cc.taux), out)
    if cc.assiette:
        _emit(R_S21_CCET_ASSIETTE, _fmt_amount(cc.assiette), out)
    if cc.montant_pat:
        _emit(R_S21_CCET_MONTANT, _fmt_amount(cc.montant_pat), out)


def write_compteur(cpt: CompteurAnnuelBlock, out: List[str]) -> None:
    if cpt.rubriques:
        _emit_rubriques_dict(cpt.rubriques, out)
        return
    _emit(R_S21_CPT_CODE, cpt.code, out)
    _emit(R_S21_CPT_MONTANT, _fmt_amount(cpt.montant), out)
    _emit(R_S21_CPT_ANNEE, cpt.annee, out)


def write_etablissement_header(etab: EtablissementBlock, out: List[str]) -> None:
    if etab.rubriques:
        # Ne pas rejouer les sous-blocs stockés ailleurs
        skip = set()
        _emit_rubriques_dict(etab.rubriques, out, skip=skip)
    else:
        _emit(R_S21_ETAB_NIC, etab.nic or (etab.siret[-5:] if etab.siret else ""), out)
        _emit(R_S21_ETAB_NAF, etab.code_naf, out)
        _emit(R_S21_ETAB_RUE, etab.adresse_rue, out)
        _emit(R_S21_ETAB_CP, etab.adresse_cp, out)
        _emit(R_S21_ETAB_VILLE, etab.adresse_ville, out)
    for org in etab.organismes_psc:
        write_organisme_psc(org, out)
    for vo in etab.versements_organismes:
        write_versement_organisme(vo, out)
    for bord in etab.bordereaux:
        write_bordereau(bord, out)
    for cc in etab.composants_cotisation:
        write_composant_etab(cc, out)
    for cpt in etab.compteurs_annuels:
        write_compteur(cpt, out)


def write_individu(ind: IndividuBlock, out: List[str]) -> None:
    if ind.rubriques:
        _emit_rubriques_dict(ind.rubriques, out)
    else:
        _emit(R_S21_IND_NIR, ind.nir, out)
        _emit(R_S21_IND_NOM, ind.nom, out)
        _emit(R_S21_IND_NOM_USAGE, ind.nom_usage, out)
        _emit(R_S21_IND_PRENOM, ind.prenom, out)
        _emit(R_S21_IND_SEXE, ind.sexe, out)
        _emit(R_S21_IND_NAISSANCE, ind.date_naissance, out)
        _emit(R_S21_IND_LIEU_NAISS, ind.lieu_naissance, out)
        _emit(R_S21_IND_RUE, ind.adresse_rue, out)
        _emit(R_S21_IND_CP, ind.adresse_cp, out)
        _emit(R_S21_IND_VILLE, ind.adresse_ville, out)
        _emit(R_S21_IND_MATRICULE, ind.matricule, out)
        _emit(R_S21_IND_NTT, ind.ntt, out)
    for ctr in ind.contrats:
        write_contrat(ctr, out)


def write_affiliation(aff: AffiliationBlock, out: List[str]) -> None:
    if aff.rubriques:
        _emit_rubriques_dict(aff.rubriques, out)
        return
    _emit("S21.G00.70.001", aff.reference_contrat, out)
    _emit("S21.G00.70.002", aff.code_organisme, out)
    _emit("S21.G00.70.003", aff.code_delegataire, out)
    _emit("S21.G00.70.004", aff.code_option, out)
    _emit("S21.G00.70.005", aff.code_population, out)
    if aff.nb_enfants:
        _emit("S21.G00.70.012", str(aff.nb_enfants), out)
    if aff.nb_adultes:
        _emit("S21.G00.70.013", str(aff.nb_adultes), out)
    _emit("S21.G00.70.015", aff.identifiant_affiliation, out)


def write_arret(arret: ArretTravailBlock, out: List[str]) -> None:
    if arret.rubriques:
        _emit_rubriques_dict(arret.rubriques, out)
        return
    _emit(R_S21_ARRET_DEB, arret.date_debut, out)
    _emit(R_S21_ARRET_MOTIF, arret.motif, out)
    _emit(R_S21_ARRET_FIN, arret.date_fin, out)
    _emit(R_S21_ARRET_CAISSE, arret.siret_caisse, out)


def write_suspension(susp: SuspensionContratBlock, out: List[str]) -> None:
    if susp.rubriques:
        _emit_rubriques_dict(susp.rubriques, out)
        return
    _emit(R_S21_SUSP_TYPE, susp.type_suspension, out)
    _emit(R_S21_SUSP_DEB, susp.date_debut, out)
    _emit(R_S21_SUSP_FIN, susp.date_fin, out)
    _emit(R_S21_SUSP_MOTIF, susp.motif, out)


def write_fin_contrat(fin: FinContratBlock, out: List[str]) -> None:
    if fin.rubriques:
        _emit_rubriques_dict(fin.rubriques, out)
        return
    _emit(R_S21_FIN_DATE, fin.date_fin, out)
    _emit(R_S21_FIN_MOTIF, fin.motif, out)
    _emit(R_S21_FIN_NOTIF, fin.date_notification, out)


def write_anciennete(anc: AncienneteBlock, out: List[str]) -> None:
    if anc.rubriques:
        _emit_rubriques_dict(anc.rubriques, out)
        return
    _emit(R_S21_ANC_TYPE, anc.type_unite, out)
    _emit(R_S21_ANC_DEB, anc.date_debut, out)
    _emit(R_S21_ANC_FIN, anc.date_fin, out)


def write_remuneration(rem: RemunerationBlock, out: List[str]) -> None:
    if rem.rubriques:
        _emit_rubriques_dict(rem.rubriques, out)
        return
    _emit(R_S21_REM_TYPE, rem.type_code, out)
    if rem.heures:
        _emit(R_S21_REM_HEURES, _fmt_amount(rem.heures), out)
    if rem.montant:
        _emit(R_S21_REM_MONTANT, _fmt_amount(rem.montant), out)


def write_prime(prime: PrimeBlock, out: List[str]) -> None:
    if prime.rubriques:
        _emit_rubriques_dict(prime.rubriques, out)
        return
    _emit(R_S21_PRIME_CODE, prime.code, out)
    if prime.montant:
        _emit(R_S21_PRIME_MONTANT, _fmt_amount(prime.montant), out)
    _emit("S21.G00.52.003", prime.date_debut, out)
    _emit("S21.G00.52.004", prime.date_fin, out)


def write_base(base: BaseAssujettieBlock, out: List[str]) -> None:
    if base.rubriques:
        _emit_rubriques_dict(base.rubriques, out)
        # Composants de base assujettie (S21.G00.79) portés par la base :
        # le SMIC retenu sous la base 03, l'assiette réelle sous une base 31.
        for composant in base.rubriques.get("_composants_79") or []:
            _emit(R_S21_CB_CODE, str(composant.get("type") or ""), out)
            _emit(R_S21_CB_MONTANT, str(composant.get("montant") or ""), out)
        return
    _emit(R_S21_BA_CODE, base.code, out)
    _emit("S21.G00.78.002", base.date_debut, out)
    _emit("S21.G00.78.003", base.date_fin, out)
    if base.montant:
        _emit(R_S21_BA_MONTANT, _fmt_amount(base.montant), out)


def write_composant_base(cb: ComposantBaseBlock, out: List[str]) -> None:
    if cb.rubriques:
        _emit_rubriques_dict(cb.rubriques, out)
        return
    _emit(R_S21_CB_CODE, cb.code, out)
    if cb.montant:
        _emit(R_S21_CB_MONTANT, _fmt_amount(cb.montant), out)


def write_cotisation_individuelle(cot: CotisationIndividuelleBlock, out: List[str]) -> None:
    if cot.rubriques:
        _emit_rubriques_dict(cot.rubriques, out)
        return
    _emit("S21.G00.81.001", cot.code, out)
    _emit("S21.G00.81.002", cot.identifiant_affiliation, out)
    if cot.montant_assiette:
        _emit("S21.G00.81.003", _fmt_amount(cot.montant_assiette), out)
    montant = cot.montant_patronal or cot.montant_salarial
    if montant:
        _emit("S21.G00.81.004", _fmt_amount(montant), out)


def write_cotisation_agregee(ca: CotisationAgregeeBlock, out: List[str]) -> None:
    if ca.rubriques:
        _emit_rubriques_dict(ca.rubriques, out)
        return
    _emit(R_S21_CA_CODE, ca.code, out)
    _emit(R_S21_CA_BASE, ca.code_base, out)
    if ca.taux:
        _emit(R_S21_CA_TAUX, _fmt_rate(ca.taux), out)
    if ca.montant:
        _emit(R_S21_CA_MONTANT, _fmt_amount(ca.montant), out)


def write_versement(ver: VersementBlock, out: List[str]) -> None:
    if ver.rubriques and any(k.startswith("S21.G00.50.") for k in ver.rubriques):
        # Émettre d'abord le bloc 50 depuis rubriques, puis enfants structurés.
        # Trié : même exigence d'ordre croissant que partout ailleurs — un
        # 50.008 inséré après le 50.013 ouvrait un bloc 50 fantôme.
        for key in sorted(ver.rubriques):
            val = ver.rubriques[key]
            if str(key).startswith("S21.G00.50.") and not isinstance(val, (list, dict)):
                _emit(str(key), str(val), out)
    else:
        _emit(R_S21_VER_DATE, ver.date_versement, out)
        if ver.net_fiscal:
            _emit(R_S21_VER_NET_FISCAL, _fmt_amount(ver.net_fiscal), out)
        _emit(R_S21_VER_NUMERO, "01", out)
        if ver.net_verse:
            _emit(R_S21_VER_NET_VERSE, _fmt_amount(ver.net_verse), out)
        if ver.pas_taux or ver.pas:
            _emit(R_S21_VER_PAS_TAUX, _fmt_amount(ver.pas_taux), out)
        _emit(R_S21_VER_PAS_TYPE, ver.pas_type or "01", out)
        _emit(R_S21_VER_PAS_ID, ver.pas_identifiant, out)
        if ver.pas:
            _emit(R_S21_VER_PAS, _fmt_amount(ver.pas), out)
        if ver.montant_soumis_pas:
            _emit(R_S21_VER_PAS_ASSIETTE, _fmt_amount(ver.montant_soumis_pas), out)

    # Le bloc activité (S21.G00.53) en unité « 40 - jours calendaires du
    # plafond » n'est admis que sous la rémunération brute non plafonnée
    # (type 001) : émis juste après elle, pas en fin de liste (CCH-12).
    activites = ver.rubriques.get("activites") if ver.rubriques else None
    for rem in ver.remunerations:
        write_remuneration(rem, out)
        type_rem = str(
            (rem.rubriques or {}).get("S21.G00.51.011") or rem.type_code or ""
        )
        if type_rem == "001" and isinstance(activites, list):
            for act in activites:
                if not isinstance(act, dict):
                    continue
                _emit(R_S21_ACT_TYPE, str(act.get("type") or ""), out)
                if act.get("mesure") is not None:
                    _emit(R_S21_ACT_MESURE, _fmt_amount(float(act["mesure"])), out)
                unite = str(act.get("unite") or "").strip()
                if unite:
                    _emit(R_S21_ACT_UNITE, unite, out)
            activites = None  # émises une seule fois

    for prime in ver.primes:
        write_prime(prime, out)

    # Éléments de revenu calculés en net (S21.G00.58) — le type 03, montant net
    # social, est obligatoire sur tout versement du mois principal (CCH-14).
    for bloc in (ver.rubriques.get("_blocs_58") if ver.rubriques else None) or []:
        _emit("S21.G00.58.001", str(bloc.get("debut") or ""), out)
        _emit("S21.G00.58.002", str(bloc.get("fin") or ""), out)
        _emit("S21.G00.58.003", str(bloc.get("type") or ""), out)
        _emit("S21.G00.58.004", str(bloc.get("montant") or ""), out)

    # Bases + cotisations imbriquées (comme Cegid : 81 sous le 78 courant)
    cots_by_base: Dict[str, List] = {}
    orphan_cots: List = []
    for cot in ver.cotisations_individuelles:
        base_key = ""
        if cot.rubriques:
            base_key = str(cot.rubriques.get("_base") or "")
        if base_key:
            cots_by_base.setdefault(base_key, []).append(cot)
        else:
            orphan_cots.append(cot)

    for base in ver.bases_assujetties:
        write_base(base, out)
        for cot in cots_by_base.get(base.code, []):
            write_cotisation_individuelle(cot, out)
    for cot in orphan_cots:
        write_cotisation_individuelle(cot, out)

    if ver.bases_assujetties:
        for cb in ver.composants_base:
            write_composant_base(cb, out)
    elif ver.composants_base:
        for cb in ver.composants_base:
            write_composant_base(cb, out)
    for ca in ver.cotisations_agregees:
        write_cotisation_agregee(ca, out)


def write_contrat(ctr: ContratBlock, out: List[str]) -> None:
    if ctr.rubriques:
        _emit_rubriques_dict(ctr.rubriques, out)
        # Ordre du cabinet, que le validateur exige : contrat (40), puis les
        # affiliations (70), puis la retraite complémentaire (71), puis le
        # versement (50). Sans bloc 71, le statut catégoriel S21.G00.40.003 est
        # refusé quelle que soit sa valeur. Les clés « _* » ne commencent pas
        # par « S » : `_emit_rubriques_dict` les ignore, rien ne fuit.
        for aff in ctr.affiliations:
            write_affiliation(aff, out)
        regime = str(ctr.rubriques.get("_regime_retraite_complementaire") or "")
        if regime:
            _emit(R_S21_CTR_REGIME_RC, regime, out)
    else:
        _emit(R_S21_CTR_DATE_DEBUT, ctr.date_debut, out)
        _emit(R_S21_CTR_STATUT, ctr.statut, out)
        _emit(R_S21_CTR_DATE_FIN, ctr.date_fin, out)
        _emit(R_S21_CTR_PCS, ctr.pcs, out)
        _emit(R_S21_CTR_LIBELLE_EMPLOI, ctr.libelle_emploi, out)
        _emit(R_S21_CTR_NATURE, ctr.nature, out)
        _emit(R_S21_CTR_DISPOSITIF, ctr.dispositif, out)
        _emit(R_S21_CTR_NUMERO, ctr.numero_contrat, out)
        _emit(R_S21_CTR_UNITE_QUOTITE, ctr.unite_quotite, out)
        _emit(R_S21_CTR_QUOTITE_REF, ctr.quotite_reference, out)
        _emit(R_S21_CTR_QUOTITE, ctr.quotite, out)
        _emit(R_S21_CTR_MODALITE_TEMPS, ctr.modalite_temps, out)
        _emit(R_S21_CTR_IDCC, ctr.idcc, out)
        _emit(R_S21_CTR_POSITION, ctr.position_conv, out)
    for arret in ctr.arrets:
        write_arret(arret, out)
    if not ctr.rubriques:
        for aff in ctr.affiliations:
            write_affiliation(aff, out)
    for susp in ctr.suspensions:
        write_suspension(susp, out)
    if ctr.fin_contrat:
        write_fin_contrat(ctr.fin_contrat, out)
    for ver in ctr.versements:
        write_versement(ver, out)
    # L'ancienneté ferme le contrat, après le versement : c'est la place que lui
    # donne le cabinet, et le validateur la réclame à ce niveau.
    for anc in ctr.anciennetes:
        write_anciennete(anc, out)
    anciennete_86 = ctr.rubriques.get("_anciennete_entreprise") if ctr.rubriques else None
    if isinstance(anciennete_86, dict) and anciennete_86.get("valeur"):
        _emit(R_S21_ANC86_TYPE, "07", out)
        _emit(R_S21_ANC86_UNITE, str(anciennete_86.get("unite") or "02"), out)
        _emit(R_S21_ANC86_VALEUR, str(anciennete_86["valeur"]), out)
        _emit(R_S21_ANC86_CONTRAT, str(anciennete_86.get("contrat") or ""), out)


def serialize_dsn_file(dsn_file: DsnFile) -> str:
    """Sérialise un DsnFile en texte plat NEODeS.

    Si ``raw_rubriques`` est renseigné (fichier parsé), on le rejoue tel quel
    pour un round-trip fidèle. Sinon on reconstruit depuis le modèle structuré.
    """
    if dsn_file.raw_rubriques:
        lines = [
            format_rubrique_line(line.rubrique, line.valeur)
            for line in dsn_file.raw_rubriques
        ]
        return FIN_DE_LIGNE.join(lines) + FIN_DE_LIGNE

    out: List[str] = []
    write_envoi(dsn_file.envoi, out)
    write_declaration(dsn_file.declaration, out)
    write_entreprise(dsn_file.entreprise, out)
    write_etablissement_header(dsn_file.etablissement, out)
    for ind in dsn_file.etablissement.individus:
        write_individu(ind, out)
    write_total_fichier(out)
    return FIN_DE_LIGNE.join(out) + (FIN_DE_LIGNE if out else "")


def write_total_fichier(out: List[str], *, nb_declarations: int = 1) -> None:
    """Clôt l'envoi par le bloc total, sans lequel le dépôt est rejeté.

    ``S90.G00.90.001`` compte toutes les lignes du fichier, les deux lignes du
    bloc total comprises — c'est ainsi que le comptent les fichiers déposés.
    """
    total = len(out) + 2
    out.append(format_rubrique_line(RUB_TOTAL_LIGNES, str(total)))
    out.append(format_rubrique_line(RUB_TOTAL_DECLARATIONS, str(nb_declarations)))


def encode_dsn_bytes(dsn_file: DsnFile, *, encoding: str = DSN_ENCODING) -> bytes:
    text = serialize_dsn_file(dsn_file)
    try:
        return text.encode(encoding)
    except UnicodeEncodeError as exc:
        raise DsnWriterError(
            f"Encodage {encoding} impossible pour le fichier DSN : {exc}"
        ) from exc


def encode_parsed_dsn(parsed: ParsedDsnSet, *, encoding: str = DSN_ENCODING) -> bytes:
    """Concatène les fichiers d'un ParsedDsnSet (usage mono-fichier attendu)."""
    if not parsed.files:
        raise DsnWriterError("Aucune DSN à sérialiser")
    if len(parsed.files) == 1:
        return encode_dsn_bytes(parsed.files[0], encoding=encoding)
    chunks = [serialize_dsn_file(f) for f in parsed.files]
    return ("\n".join(chunks)).encode(encoding)
