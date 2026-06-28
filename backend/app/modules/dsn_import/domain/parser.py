"""Parser DSN fichier plat NEODeS."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

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
    CotisationBlock,
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
from app.modules.dsn_import.domain.norm_detect import detect_dsn_format
from app.modules.dsn_import.domain.rubriques import (
    BLOCK_G00,
    R_S10_NORME,
    R_S10_PERIODE,
    R_S10_TYPE,
    R_S20_CP_LEGACY,
    R_S20_DECL_MOIS,
    R_S20_DECL_NATURE,
    R_S20_DECL_TYPE,
    R_S20_NAF_LEGACY,
    R_S20_RAISON_LEGACY,
    R_S20_RUE_LEGACY,
    R_S20_SIRET_LEGACY,
    R_S20_VILLE_LEGACY,
    R_S21_BASE_CODE,
    R_S21_BASE_MONTANT,
    R_S21_COT_CODE,
    R_S21_COT_BASE,
    R_S21_COT_MONTANT_PAT,
    R_S21_COT_MONTANT_SAL,
    R_S21_COT_TAUX_PAT,
    R_S21_COT_TAUX_SAL,
    R_S21_ORG_CODE,
    R_S21_ORG_NATURE,
    R_S21_ORG_RANG,
    R_S21_ORG_REF,
    R_S21_CTR_DATE_DEBUT,
    R_S21_CTR_DATE_FIN,
    R_S21_CTR_DISPOSITIF,
    R_S21_CTR_IDCC,
    R_S21_CTR_LIBELLE_EMPLOI,
    R_S21_CTR_MODALITE_TEMPS,
    R_S21_CTR_NATURE,
    R_S21_CTR_NUMERO,
    R_S21_CTR_PCS,
    R_S21_CTR_POSITION,
    R_S21_CTR_QUOTITE,
    R_S21_CTR_QUOTITE_REF,
    R_S21_CTR_STATUT,
    R_S21_CTR_UNITE_QUOTITE,
    R_S21_ENT_CP,
    R_S21_ENT_NAF,
    R_S21_ENT_NIC_SIEGE,
    R_S21_ENT_RAISON,
    R_S21_ENT_RUE,
    R_S21_ENT_SIREN,
    R_S21_ENT_VILLE,
    R_S21_ETAB_CP,
    R_S21_ETAB_CP_LEGACY,
    R_S21_ETAB_EFFECTIF,
    R_S21_ETAB_NAF,
    R_S21_ETAB_NAF_LEGACY,
    R_S21_ETAB_NIC,
    R_S21_ETAB_RAISON,
    R_S21_ETAB_RUE,
    R_S21_ETAB_RUE_LEGACY,
    R_S21_ETAB_SIRET,
    R_S21_ETAB_VILLE,
    R_S21_ETAB_VILLE_LEGACY,
    R_S21_IND_CP,
    R_S21_IND_LIEU_NAISS,
    R_S21_IND_LIEU_NAISS_LEGACY,
    R_S21_IND_MATRICULE,
    R_S21_IND_NAISSANCE,
    R_S21_IND_NAISSANCE_LEGACY,
    R_S21_IND_NIR,
    R_S21_IND_NIR_LEGACY,
    R_S21_IND_NOM,
    R_S21_IND_NOM_LEGACY,
    R_S21_IND_NOM_USAGE,
    R_S21_IND_NTT,
    R_S21_IND_SEXE,
    R_S21_IND_NATIONALITE_LEGACY,
    R_S21_IND_PRENOM,
    R_S21_IND_PRENOM_LEGACY,
    R_S21_IND_RUE,
    R_S21_IND_VILLE,
    R_S21_REM_HEURES,
    R_S21_REM_HEURES_LEGACY,
    R_S21_REM_MONTANT,
    R_S21_REM_PERIODE_DEB,
    R_S21_REM_PERIODE_FIN,
    R_S21_REM_TYPE,
    R_S21_REM_TYPE_LEGACY,
    R_S21_ACT_MESURE,
    R_S21_ACT_TYPE,
    R_S21_ACT_UNITE,
    R_S21_AFF_CODE_DELEG,
    R_S21_AFF_CODE_OPTION,
    R_S21_AFF_CODE_ORG,
    R_S21_AFF_CODE_POP,
    R_S21_AFF_IDENT,
    R_S21_AFF_NB_ADULTES,
    R_S21_AFF_NB_ENFANTS,
    R_S21_AFF_REF_CONTRAT,
    R_S21_CI_ASSIETTE,
    R_S21_CI_MONTANT,
    R_S21_CI_MONTANT_PAT,
    R_S21_CI_MONTANT_SAL,
    R_S21_CI_OPS_IDENT,
    R_S21_CI_TAUX,
    R_S21_ANC_DEB,
    R_S21_ANC_FIN,
    R_S21_ANC_TYPE,
    R_S21_ARRET_CAISSE,
    R_S21_ARRET_DEB,
    R_S21_ARRET_FIN,
    R_S21_ARRET_MOTIF,
    R_S21_AVANT_CODE,
    R_S21_AVANT_DEB,
    R_S21_AVANT_FIN,
    R_S21_AVANT_MONTANT,
    R_S21_BA_CODE,
    R_S21_BA_DATE_DEB,
    R_S21_BA_DATE_FIN,
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
    R_S21_FIN_DATE,
    R_S21_FIN_MOTIF,
    R_S21_FIN_NOTIF,
    R_S21_PRIME_CODE,
    R_S21_PRIME_MONTANT,
    R_S21_SUSP_DEB,
    R_S21_SUSP_FIN,
    R_S21_SUSP_MOTIF,
    R_S21_SUSP_TYPE,
    R_S21_VO_BIC,
    R_S21_VO_DATE_DEB,
    R_S21_VO_DATE_FIN,
    R_S21_VO_IBAN,
    R_S21_VO_IDENT,
    R_S21_VO_LIBELLE,
    R_S21_VO_MODE,
    R_S21_VO_MONTANT,
    R_S21_CTR_CLASSIF,
    R_S21_CTR_NIVEAU,
    R_S21_CTR_TAUX_AT,
    R_S21_VER_DATE,
    R_S21_VER_NET_FISCAL,
    R_S21_VER_NET_VERSE,
    R_S21_VER_PAS,
    R_S21_CI_IDENT_AFF,
    R_S21_VER_NUMERO,
    R_S21_VER_PAS_ASSIETTE,
    R_S21_VER_PAS_ID,
    R_S21_VER_PAS_LEGACY,
    R_S21_VER_PAS_TAUX,
    R_S21_VER_PAS_TYPE,
)
from app.shared.dsn_validation import build_siret_from_siren_nic

_LINE_RE = re.compile(
    r"^\s*([A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+\.[0-9]+)\s*,\s*('(?:''|[^'])*'|[^,\r\n]*)\s*$"
)


def decode_dsn_bytes(content: bytes) -> str:
    """Décode le fichier DSN (ISO-8859-15 prioritaire, UTF-8 fallback)."""
    for encoding in ("iso-8859-15", "latin-1", "cp1252", "utf-8"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _unquote(value: str) -> str:
    value = value.strip()
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def parse_flat_lines(text: str) -> List[RubriqueLine]:
    """Parse les lignes rubrique,'valeur' du fichier plat."""
    lines: List[RubriqueLine] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _LINE_RE.match(stripped)
        if match:
            lines.append(
                RubriqueLine(
                    rubrique=match.group(1),
                    valeur=_unquote(match.group(2)),
                    line_no=line_no,
                )
            )
            continue
        if "," in stripped:
            parts = stripped.split(",", 1)
            rub = parts[0].strip()
            val = parts[1].strip().strip("'")
            if re.match(r"^S\d+\.", rub):
                lines.append(RubriqueLine(rubrique=rub, valeur=val, line_no=line_no))
    return lines


def _g00_block(rubrique: str) -> Optional[str]:
    parts = rubrique.split(".")
    if len(parts) >= 3 and parts[0].startswith("S") and parts[1] == "G00":
        return parts[2]
    return None


def _float_val(value: str) -> float:
    if not value:
        return 0.0
    try:
        return float(value.replace(",", ".").replace(" ", ""))
    except ValueError:
        return 0.0


def _normalize_rem_type_code(value: str) -> str:
    """Extrait le code type (001) depuis '001' ou '001 - Rémunération brute…'."""
    if not value:
        return ""
    val = value.strip()
    if " - " in val:
        val = val.split(" - ", 1)[0].strip()
    clean = val.replace(" ", "")
    if clean.isdigit() and len(clean) <= 3:
        return clean.zfill(3)[:3]
    if clean.isdigit() and len(clean) == 8:
        return ""
    return val


class _ParseContext:
    def __init__(self, dsn_format: str) -> None:
        self.dsn_format = dsn_format
        self.envoi = EnvoiBlock()
        self.declaration = DeclarationBlock()
        self.etablissement_s20 = EtablissementBlock()
        self.entreprise = EntrepriseBlock()
        self.etablissement = EtablissementBlock()
        self.individu: Optional[IndividuBlock] = None
        self.contrat: Optional[ContratBlock] = None
        self.versement: Optional[VersementBlock] = None
        self.remuneration: Optional[RemunerationBlock] = None
        self.cotisation: Optional[CotisationBlock] = None
        self.cotisation_ind: Optional[CotisationIndividuelleBlock] = None
        self.affiliation: Optional[AffiliationBlock] = None
        self.organisme_psc: Optional[OrganismePscBlock] = None
        self.activite: Optional[Dict[str, Any]] = None
        self.base_assujettie: Optional[BaseAssujettieBlock] = None
        self.composant_base: Optional[ComposantBaseBlock] = None
        self.cotisation_agregee: Optional[CotisationAgregeeBlock] = None
        self.prime: Optional[PrimeBlock] = None
        self.composant_cot_etab: Optional[ComposantCotisationEtabBlock] = None
        self.versement_org: Optional[VersementOrganismeBlock] = None
        self.bordereau: Optional[BordereauBlock] = None
        self.compteur_annuel: Optional[CompteurAnnuelBlock] = None
        self.arret: Optional[ArretTravailBlock] = None
        self.suspension: Optional[SuspensionContratBlock] = None
        self.anciennete: Optional[AncienneteBlock] = None
        self.warnings: List[str] = []

    def _ensure_individu(self) -> IndividuBlock:
        if self.individu is None:
            self.individu = IndividuBlock()
            self.etablissement.individus.append(self.individu)
        return self.individu

    def _ensure_contrat(self) -> ContratBlock:
        ind = self._ensure_individu()
        if self.contrat is None:
            self.contrat = ContratBlock()
            ind.contrats.append(self.contrat)
        return self.contrat

    def _ensure_versement(self) -> VersementBlock:
        ctr = self._ensure_contrat()
        if self.versement is None:
            self.versement = VersementBlock()
            ctr.versements.append(self.versement)
        return self.versement

    def _ensure_remuneration(self) -> RemunerationBlock:
        ver = self._ensure_versement()
        if self.remuneration is None:
            self.remuneration = RemunerationBlock()
            ver.remunerations.append(self.remuneration)
        return self.remuneration

    def _ensure_cotisation(self) -> CotisationBlock:
        ver = self._ensure_versement()
        if self.cotisation is None:
            self.cotisation = CotisationBlock()
            ver.cotisations.append(self.cotisation)
        return self.cotisation

    def _ensure_cotisation_ind(self) -> CotisationIndividuelleBlock:
        ver = self._ensure_versement()
        if self.cotisation_ind is None:
            self.cotisation_ind = CotisationIndividuelleBlock()
            ver.cotisations_individuelles.append(self.cotisation_ind)
        return self.cotisation_ind

    def _ensure_affiliation(self) -> AffiliationBlock:
        ctr = self._ensure_contrat()
        if self.affiliation is None:
            self.affiliation = AffiliationBlock()
            ctr.affiliations.append(self.affiliation)
        return self.affiliation

    def _ensure_organisme_psc(self) -> OrganismePscBlock:
        if self.organisme_psc is None:
            self.organisme_psc = OrganismePscBlock()
            self.etablissement.organismes_psc.append(self.organisme_psc)
        return self.organisme_psc

    def _ensure_activite(self) -> Dict[str, Any]:
        ver = self._ensure_versement()
        if self.activite is None:
            self.activite = {}
            activites = ver.rubriques.setdefault("activites", [])
            if isinstance(activites, list):
                activites.append(self.activite)
        return self.activite

    def _ensure_base_assujettie(self) -> BaseAssujettieBlock:
        ver = self._ensure_versement()
        if self.base_assujettie is None:
            self.base_assujettie = BaseAssujettieBlock()
            ver.bases_assujetties.append(self.base_assujettie)
        return self.base_assujettie

    def _ensure_composant_base(self) -> ComposantBaseBlock:
        ver = self._ensure_versement()
        if self.composant_base is None:
            self.composant_base = ComposantBaseBlock()
            ver.composants_base.append(self.composant_base)
        return self.composant_base

    def _ensure_cotisation_agregee(self) -> CotisationAgregeeBlock:
        ver = self._ensure_versement()
        if self.cotisation_agregee is None:
            self.cotisation_agregee = CotisationAgregeeBlock()
            ver.cotisations_agregees.append(self.cotisation_agregee)
        return self.cotisation_agregee

    def _ensure_prime(self) -> PrimeBlock:
        ver = self._ensure_versement()
        if self.prime is None:
            self.prime = PrimeBlock()
            ver.primes.append(self.prime)
        return self.prime

    def _ensure_composant_cot_etab(self) -> ComposantCotisationEtabBlock:
        if self.composant_cot_etab is None:
            self.composant_cot_etab = ComposantCotisationEtabBlock()
            self.etablissement.composants_cotisation.append(self.composant_cot_etab)
        return self.composant_cot_etab

    def _ensure_versement_org(self) -> VersementOrganismeBlock:
        if self.versement_org is None:
            self.versement_org = VersementOrganismeBlock()
            self.etablissement.versements_organismes.append(self.versement_org)
        return self.versement_org

    def _ensure_bordereau(self) -> BordereauBlock:
        if self.bordereau is None:
            self.bordereau = BordereauBlock()
            self.etablissement.bordereaux.append(self.bordereau)
        return self.bordereau

    def _ensure_compteur_annuel(self) -> CompteurAnnuelBlock:
        if self.compteur_annuel is None:
            self.compteur_annuel = CompteurAnnuelBlock()
            self.etablissement.compteurs_annuels.append(self.compteur_annuel)
        return self.compteur_annuel

    def _ensure_arret(self) -> ArretTravailBlock:
        ctr = self._ensure_contrat()
        if self.arret is None:
            self.arret = ArretTravailBlock()
            ctr.arrets.append(self.arret)
        return self.arret

    def _ensure_suspension(self) -> SuspensionContratBlock:
        ctr = self._ensure_contrat()
        if self.suspension is None:
            self.suspension = SuspensionContratBlock()
            ctr.suspensions.append(self.suspension)
        return self.suspension

    def _ensure_anciennete(self) -> AncienneteBlock:
        ctr = self._ensure_contrat()
        if self.anciennete is None:
            self.anciennete = AncienneteBlock()
            ctr.anciennetes.append(self.anciennete)
        return self.anciennete

    def _reset_contrat_children(self) -> None:
        self.versement = None
        self.remuneration = None
        self.cotisation = None
        self.cotisation_ind = None
        self.base_assujettie = None
        self.composant_base = None
        self.cotisation_agregee = None
        self.prime = None
        self.affiliation = None
        self.arret = None
        self.suspension = None
        self.anciennete = None
        self.activite = None

    def _reset_versement_children(self) -> None:
        self.remuneration = None
        self.cotisation = None
        self.cotisation_ind = None
        self.base_assujettie = None
        self.composant_base = None
        self.cotisation_agregee = None
        self.prime = None
        self.activite = None

    def on_block_start(self, g00: str) -> None:
        block = BLOCK_G00.get(g00)
        if block == "individu":
            self.individu = IndividuBlock()
            self.etablissement.individus.append(self.individu)
            self.contrat = None
            self._reset_contrat_children()
            self.organisme_psc = None
        elif block == "organisme_psc":
            self.organisme_psc = OrganismePscBlock()
            self.etablissement.organismes_psc.append(self.organisme_psc)
        elif block == "versement_organisme":
            self.versement_org = VersementOrganismeBlock()
            self.etablissement.versements_organismes.append(self.versement_org)
        elif block == "bordereau":
            self.bordereau = BordereauBlock()
            self.etablissement.bordereaux.append(self.bordereau)
        elif block == "composant_cotisation_etab":
            self.composant_cot_etab = ComposantCotisationEtabBlock()
            self.etablissement.composants_cotisation.append(self.composant_cot_etab)
        elif block == "compteur_annuel":
            self.compteur_annuel = CompteurAnnuelBlock()
            self.etablissement.compteurs_annuels.append(self.compteur_annuel)
        elif block == "contrat":
            ind = self._ensure_individu()
            self.contrat = ContratBlock()
            ind.contrats.append(self.contrat)
            self._reset_contrat_children()
        elif block == "arret_travail":
            ctr = self._ensure_contrat()
            self.arret = ArretTravailBlock()
            ctr.arrets.append(self.arret)
        elif block == "suspension":
            ctr = self._ensure_contrat()
            self.suspension = SuspensionContratBlock()
            ctr.suspensions.append(self.suspension)
        elif block == "fin_contrat":
            ctr = self._ensure_contrat()
            ctr.fin_contrat = FinContratBlock()
        elif block == "anciennete":
            ctr = self._ensure_contrat()
            self.anciennete = AncienneteBlock()
            ctr.anciennetes.append(self.anciennete)
        elif block == "affiliation":
            ctr = self._ensure_contrat()
            self.affiliation = AffiliationBlock()
            ctr.affiliations.append(self.affiliation)
        elif block == "versement":
            ctr = self._ensure_contrat()
            self.versement = VersementBlock()
            ctr.versements.append(self.versement)
            self._reset_versement_children()
        elif block == "remuneration":
            ver = self._ensure_versement()
            self.remuneration = RemunerationBlock()
            ver.remunerations.append(self.remuneration)
        elif block == "base_assujettie":
            if self.dsn_format == "legacy":
                ver = self._ensure_versement()
                self.cotisation = CotisationBlock()
                ver.cotisations.append(self.cotisation)
                self.base_assujettie = None
            else:
                ver = self._ensure_versement()
                self.base_assujettie = BaseAssujettieBlock()
                ver.bases_assujetties.append(self.base_assujettie)
                self.cotisation = None
        elif block == "composant_base":
            ver = self._ensure_versement()
            self.composant_base = ComposantBaseBlock()
            ver.composants_base.append(self.composant_base)
        elif block == "cotisation_agregee":
            ver = self._ensure_versement()
            self.cotisation_agregee = CotisationAgregeeBlock()
            ver.cotisations_agregees.append(self.cotisation_agregee)
        elif block == "prime" or block == "avantage":
            ver = self._ensure_versement()
            self.prime = PrimeBlock()
            ver.primes.append(self.prime)
        elif block == "cotisation_individuelle":
            ver = self._ensure_versement()
            self.cotisation_ind = CotisationIndividuelleBlock()
            ver.cotisations_individuelles.append(self.cotisation_ind)
        elif block == "activite":
            ver = self._ensure_versement()
            self.activite = {}
            activites = ver.rubriques.setdefault("activites", [])
            if isinstance(activites, list):
                activites.append(self.activite)
        elif block == "etablissement":
            if not self.etablissement.siret and not self.etablissement.nic:
                self.etablissement = EtablissementBlock()
            self.individu = None
            self.contrat = None
            self._reset_contrat_children()
        elif block == "entreprise":
            self.entreprise = EntrepriseBlock()

    def apply_rubrique(self, rubrique: str, valeur: str) -> None:
        if rubrique == R_S10_PERIODE:
            self.envoi.periode = valeur
            self.envoi.rubriques[rubrique] = valeur
        elif rubrique == R_S10_NORME:
            self.envoi.norme = valeur
            self.envoi.rubriques[rubrique] = valeur
        elif rubrique == R_S10_TYPE:
            self.envoi.type_envoi = valeur
            self.envoi.rubriques[rubrique] = valeur

        if self.dsn_format == "legacy":
            self._apply_s20_legacy(rubrique, valeur)
            self._apply_entreprise_legacy(rubrique, valeur)
        else:
            self._apply_s20_modern(rubrique, valeur)
            self._apply_entreprise_modern(rubrique, valeur)

        if self.dsn_format == "legacy":
            self._apply_etablissement_legacy(rubrique, valeur)
            self._apply_individu_legacy(rubrique, valeur)
        else:
            self._apply_etablissement_modern(rubrique, valeur)
            self._apply_individu_modern(rubrique, valeur)

        self._apply_contrat_versement(rubrique, valeur)

    def _apply_s20_legacy(self, rubrique: str, valeur: str) -> None:
        if rubrique == R_S20_SIRET_LEGACY:
            self.etablissement_s20.siret = valeur.replace(" ", "")
            self.etablissement_s20.rubriques[rubrique] = valeur
        elif rubrique == R_S20_RAISON_LEGACY:
            self.etablissement_s20.raison_sociale = valeur
        elif rubrique == R_S20_NAF_LEGACY:
            self.etablissement_s20.code_naf = valeur
        elif rubrique == R_S20_RUE_LEGACY:
            self.etablissement_s20.adresse_rue = valeur
        elif rubrique == R_S20_CP_LEGACY:
            self.etablissement_s20.adresse_cp = valeur
        elif rubrique == R_S20_VILLE_LEGACY:
            self.etablissement_s20.adresse_ville = valeur

    def _apply_s20_modern(self, rubrique: str, valeur: str) -> None:
        if rubrique == R_S20_DECL_NATURE:
            self.declaration.nature = valeur
            self.declaration.rubriques[rubrique] = valeur
        elif rubrique == R_S20_DECL_TYPE:
            self.declaration.type_declaration = valeur
        elif rubrique == R_S20_DECL_MOIS:
            self.declaration.mois_principal = valeur.strip()

    def _apply_entreprise_legacy(self, rubrique: str, valeur: str) -> None:
        if rubrique == R_S21_ENT_SIREN:
            self.entreprise.siren = valeur.replace(" ", "")[:9]
            self.entreprise.rubriques[rubrique] = valeur
        elif rubrique == R_S21_ENT_RAISON:
            if valeur and not _looks_like_code(valeur):
                self.entreprise.raison_sociale = valeur
        elif rubrique == R_S21_ENT_NAF:
            self.entreprise.code_naf = valeur

    def _apply_entreprise_modern(self, rubrique: str, valeur: str) -> None:
        if rubrique == R_S21_ENT_SIREN:
            self.entreprise.siren = valeur.replace(" ", "")[:9]
            self.entreprise.rubriques[rubrique] = valeur
        elif rubrique == R_S21_ENT_NIC_SIEGE:
            self.entreprise.nic_siege = valeur.replace(" ", "")
        elif rubrique == R_S21_ENT_NAF:
            self.entreprise.code_naf = valeur
        elif rubrique == R_S21_ENT_RUE:
            self.entreprise.adresse_rue = valeur
        elif rubrique == R_S21_ENT_CP:
            self.entreprise.adresse_cp = valeur
        elif rubrique == R_S21_ENT_VILLE:
            self.entreprise.adresse_ville = valeur

    def _apply_etablissement_modern(self, rubrique: str, valeur: str) -> None:
        if rubrique == R_S21_ETAB_NIC:
            clean = valeur.replace(" ", "")
            if len(clean) == 14 and clean.isdigit():
                self.etablissement.siret = clean
            else:
                self.etablissement.nic = clean
                self.etablissement.rubriques[rubrique] = valeur
        elif rubrique == R_S21_ETAB_NAF:
            self.etablissement.code_naf = valeur
        elif rubrique == R_S21_ETAB_RUE:
            self.etablissement.adresse_rue = valeur
        elif rubrique == R_S21_ETAB_CP:
            self.etablissement.adresse_cp = valeur
        elif rubrique == R_S21_ETAB_VILLE:
            self.etablissement.adresse_ville = valeur
        elif rubrique == R_S21_ETAB_EFFECTIF:
            self.etablissement.effectif = valeur

    def _apply_etablissement_legacy(self, rubrique: str, valeur: str) -> None:
        if rubrique == R_S21_ETAB_SIRET:
            self.etablissement.siret = valeur.replace(" ", "")
            self.etablissement.rubriques[rubrique] = valeur
        elif rubrique == R_S21_ETAB_RAISON:
            self.etablissement.raison_sociale = valeur
        elif rubrique == R_S21_ETAB_NAF_LEGACY:
            self.etablissement.code_naf = valeur
        elif rubrique == R_S21_ETAB_RUE_LEGACY:
            self.etablissement.adresse_rue = valeur
        elif rubrique == R_S21_ETAB_CP_LEGACY:
            self.etablissement.adresse_cp = valeur
        elif rubrique == R_S21_ETAB_VILLE_LEGACY:
            self.etablissement.adresse_ville = valeur
        elif rubrique == R_S21_ETAB_EFFECTIF:
            self.etablissement.effectif = valeur

    def _apply_individu_modern(self, rubrique: str, valeur: str) -> None:
        if rubrique == R_S21_IND_NIR:
            self._ensure_individu().nir = valeur.replace(" ", "")
        elif rubrique == R_S21_IND_NOM:
            ind = self._ensure_individu()
            ind.nom = valeur
            ind.rubriques[rubrique] = valeur
        elif rubrique == R_S21_IND_NOM_USAGE:
            self._ensure_individu().nom_usage = valeur
        elif rubrique == R_S21_IND_SEXE:
            self._ensure_individu().sexe = valeur.strip()
        elif rubrique == R_S21_IND_PRENOM:
            self._ensure_individu().prenom = valeur
        elif rubrique == R_S21_IND_NAISSANCE:
            self._ensure_individu().date_naissance = valeur
        elif rubrique == R_S21_IND_LIEU_NAISS:
            self._ensure_individu().lieu_naissance = valeur
        elif rubrique == R_S21_IND_RUE:
            self._ensure_individu().adresse_rue = valeur
        elif rubrique == R_S21_IND_CP:
            self._ensure_individu().adresse_cp = valeur
        elif rubrique == R_S21_IND_VILLE:
            self._ensure_individu().adresse_ville = valeur
        elif rubrique == R_S21_IND_MATRICULE:
            self._ensure_individu().matricule = valeur.strip()
        elif rubrique == R_S21_IND_NTT:
            self._ensure_individu().ntt = valeur.replace(" ", "")

    def _apply_individu_legacy(self, rubrique: str, valeur: str) -> None:
        if rubrique == R_S21_IND_NOM_LEGACY:
            ind = self._ensure_individu()
            ind.nom = valeur
            ind.rubriques[rubrique] = valeur
        elif rubrique == R_S21_IND_PRENOM_LEGACY:
            self._ensure_individu().prenom = valeur
        elif rubrique == R_S21_IND_NIR_LEGACY:
            self._ensure_individu().nir = valeur.replace(" ", "")
        elif rubrique == R_S21_IND_NAISSANCE_LEGACY:
            self._ensure_individu().date_naissance = valeur
        elif rubrique == R_S21_IND_LIEU_NAISS_LEGACY:
            self._ensure_individu().lieu_naissance = valeur
        elif rubrique == R_S21_IND_NATIONALITE_LEGACY:
            self._ensure_individu().nationalite = valeur
        elif rubrique == R_S21_IND_RUE:
            self._ensure_individu().adresse_rue = valeur
        elif rubrique == R_S21_IND_CP:
            self._ensure_individu().adresse_cp = valeur
        elif rubrique == R_S21_IND_VILLE:
            self._ensure_individu().adresse_ville = valeur
        elif rubrique == R_S21_IND_MATRICULE:
            self._ensure_individu().matricule = valeur.strip()
        elif rubrique == R_S21_IND_NTT:
            self._ensure_individu().ntt = valeur.replace(" ", "")

    def _apply_contrat_versement(self, rubrique: str, valeur: str) -> None:
        if rubrique == R_S21_CTR_NATURE:
            self._ensure_contrat().nature = valeur
            self._ensure_contrat().rubriques[rubrique] = valeur
        elif rubrique == R_S21_CTR_STATUT:
            self._ensure_contrat().statut = valeur
        elif rubrique == R_S21_CTR_PCS:
            self._ensure_contrat().pcs = valeur
        elif rubrique == R_S21_CTR_DATE_DEBUT:
            self._ensure_contrat().date_debut = valeur
        elif rubrique == R_S21_CTR_DATE_FIN:
            self._ensure_contrat().date_fin = valeur
        elif rubrique == R_S21_CTR_DISPOSITIF:
            self._ensure_contrat().dispositif = valeur.strip()
        elif rubrique == R_S21_CTR_NUMERO:
            self._ensure_contrat().numero_contrat = valeur.strip()
        elif rubrique == R_S21_CTR_IDCC:
            self._ensure_contrat().idcc = valeur
        elif rubrique == R_S21_CTR_POSITION:
            self._ensure_contrat().position_conv = valeur.strip()
        elif rubrique == R_S21_CTR_MODALITE_TEMPS:
            self._ensure_contrat().modalite_temps = valeur.strip()
        elif rubrique == R_S21_CTR_QUOTITE:
            self._ensure_contrat().quotite = valeur
        elif rubrique == R_S21_CTR_QUOTITE_REF:
            self._ensure_contrat().quotite_reference = valeur
        elif rubrique == R_S21_CTR_UNITE_QUOTITE:
            self._ensure_contrat().unite_quotite = valeur.strip()
        elif rubrique == R_S21_CTR_LIBELLE_EMPLOI:
            self._ensure_contrat().libelle_emploi = valeur
        elif rubrique == R_S21_VER_DATE:
            self._ensure_versement().date_versement = valeur
        elif rubrique == R_S21_VER_NET_FISCAL:
            self._ensure_versement().net_fiscal = _float_val(valeur)
        elif rubrique == R_S21_VER_NET_VERSE:
            self._ensure_versement().net_verse = _float_val(valeur)
        elif rubrique == R_S21_VER_PAS:
            self._ensure_versement().pas = _float_val(valeur)
        elif rubrique == R_S21_VER_PAS_TAUX:
            self._ensure_versement().pas_taux = _float_val(valeur)
        elif rubrique == R_S21_VER_PAS_TYPE:
            self._ensure_versement().pas_type = valeur.strip()
        elif rubrique == R_S21_VER_PAS_ID:
            self._ensure_versement().pas_identifiant = valeur.strip()
        elif rubrique == R_S21_VER_PAS_ASSIETTE:
            self._ensure_versement().montant_soumis_pas = _float_val(valeur)
        elif rubrique == R_S21_VER_PAS_LEGACY:
            if self.dsn_format == "legacy":
                self._ensure_versement().pas = _float_val(valeur)
            else:
                self._ensure_versement().rubriques[rubrique] = valeur
        elif rubrique == R_S21_ACT_TYPE:
            self._ensure_activite()["type"] = valeur
        elif rubrique == R_S21_ACT_MESURE:
            self._ensure_activite()["mesure"] = _float_val(valeur)
        elif rubrique == R_S21_ACT_UNITE:
            act = self._ensure_activite()
            act["unite"] = valeur.split(" - ", 1)[0].strip() if " - " in valeur else valeur.strip()
        elif rubrique == R_S21_REM_PERIODE_DEB:
            rem = self._ensure_remuneration()
            rem.rubriques[rubrique] = valeur
            clean = valeur.replace(" ", "").replace("-", "")
            if len(clean) == 8 and clean.isdigit():
                pass
            else:
                code = _normalize_rem_type_code(valeur)
                if code:
                    rem.type_code = code
        elif rubrique == R_S21_REM_PERIODE_FIN:
            rem = self._ensure_remuneration()
            rem.rubriques[rubrique] = valeur
        elif rubrique == R_S21_REM_TYPE:
            rem = self._ensure_remuneration()
            rem.type_code = _normalize_rem_type_code(valeur)
            rem.rubriques[rubrique] = valeur
        elif rubrique == R_S21_REM_HEURES:
            self._ensure_remuneration().heures = _float_val(valeur)
        elif rubrique == R_S21_REM_MONTANT:
            self._ensure_remuneration().montant = _float_val(valeur)
        elif rubrique == R_S21_REM_TYPE_LEGACY and self.dsn_format == "legacy":
            rem = self._ensure_remuneration()
            rem.type_code = _normalize_rem_type_code(valeur)
            rem.rubriques[rubrique] = valeur
        elif rubrique == R_S21_REM_HEURES_LEGACY and self.dsn_format == "legacy":
            self._ensure_remuneration().heures = _float_val(valeur)
        elif rubrique.startswith("S21.G00.51."):
            self._ensure_remuneration().rubriques[rubrique] = valeur
        elif rubrique == R_S21_BA_CODE:
            if self.dsn_format == "legacy":
                self._ensure_cotisation().code = valeur
                self._ensure_cotisation().rubriques[rubrique] = valeur
            else:
                ba = self._ensure_base_assujettie()
                ba.code = valeur.strip()
                ba.rubriques[rubrique] = valeur
        elif rubrique == R_S21_BA_DATE_DEB:
            if self.dsn_format == "legacy":
                self._ensure_cotisation().base = _float_val(valeur)
            else:
                self._ensure_base_assujettie().date_debut = valeur.strip()
        elif rubrique == R_S21_BA_DATE_FIN:
            if self.dsn_format == "legacy":
                self._ensure_cotisation().taux_salarial = _float_val(valeur)
            else:
                self._ensure_base_assujettie().date_fin = valeur.strip()
        elif rubrique == R_S21_BA_MONTANT:
            if self.dsn_format == "legacy":
                self._ensure_cotisation().taux_patronal = _float_val(valeur)
            else:
                ba = self._ensure_base_assujettie()
                ba.montant = _float_val(valeur)
                ver = self._ensure_versement()
                bases = ver.rubriques.setdefault("bases", {})
                if isinstance(bases, dict) and ba.code:
                    bases[ba.code] = ba.montant
        elif rubrique == R_S21_COT_MONTANT_SAL and self.dsn_format == "legacy":
            self._ensure_cotisation().montant_salarial = _float_val(valeur)
        elif rubrique == R_S21_COT_MONTANT_PAT and self.dsn_format == "legacy":
            self._ensure_cotisation().montant_patronal = _float_val(valeur)
        elif rubrique == R_S21_CB_CODE:
            cb = self._ensure_composant_base()
            cb.code = valeur.strip()
            cb.rubriques[rubrique] = valeur
        elif rubrique == R_S21_CB_MONTANT:
            cb = self._ensure_composant_base()
            cb.montant = _float_val(valeur)
            ver = self._ensure_versement()
            bases = ver.rubriques.setdefault("bases", {})
            if isinstance(bases, dict) and cb.code:
                bases[cb.code] = cb.montant
        elif rubrique == R_S21_CA_CODE:
            ca = self._ensure_cotisation_agregee()
            ca.code = valeur.strip()
            ca.rubriques[rubrique] = valeur
        elif rubrique == R_S21_CA_BASE:
            self._ensure_cotisation_agregee().code_base = valeur.strip()
        elif rubrique == R_S21_CA_TAUX:
            self._ensure_cotisation_agregee().taux = _float_val(valeur)
        elif rubrique == R_S21_CA_MONTANT:
            self._ensure_cotisation_agregee().montant = _float_val(valeur)
        elif rubrique == R_S21_CCET_CODE:
            cc = self._ensure_composant_cot_etab()
            cc.code = valeur.strip()
            cc.rubriques[rubrique] = valeur
        elif rubrique == R_S21_CCET_REGIME:
            self._ensure_composant_cot_etab().regime = valeur.strip()
        elif rubrique == R_S21_CCET_TAUX:
            self._ensure_composant_cot_etab().taux = _float_val(valeur)
        elif rubrique == R_S21_CCET_ASSIETTE:
            self._ensure_composant_cot_etab().assiette = _float_val(valeur)
        elif rubrique == R_S21_CCET_MONTANT:
            self._ensure_composant_cot_etab().montant_pat = _float_val(valeur)
        elif rubrique == R_S21_VO_IDENT:
            vo = self._ensure_versement_org()
            vo.identifiant = valeur.strip()
            vo.rubriques[rubrique] = valeur
        elif rubrique == R_S21_VO_LIBELLE:
            self._ensure_versement_org().libelle = valeur.strip()
        elif rubrique == R_S21_VO_BIC:
            self._ensure_versement_org().bic = valeur.strip()
        elif rubrique == R_S21_VO_IBAN:
            self._ensure_versement_org().iban = valeur.strip()
        elif rubrique == R_S21_VO_MONTANT:
            self._ensure_versement_org().montant = _float_val(valeur)
        elif rubrique == R_S21_VO_DATE_DEB:
            self._ensure_versement_org().date_debut = valeur.strip()
        elif rubrique == R_S21_VO_DATE_FIN:
            self._ensure_versement_org().date_fin = valeur.strip()
        elif rubrique == R_S21_VO_MODE:
            self._ensure_versement_org().mode_paiement = valeur.strip()
        elif rubrique == R_S21_BORD_IDENT:
            b = self._ensure_bordereau()
            b.identifiant = valeur.strip()
            b.rubriques[rubrique] = valeur
        elif rubrique == R_S21_BORD_DATE_DEB:
            self._ensure_bordereau().date_debut = valeur.strip()
        elif rubrique == R_S21_BORD_DATE_FIN:
            self._ensure_bordereau().date_fin = valeur.strip()
        elif rubrique == R_S21_BORD_MONTANT:
            self._ensure_bordereau().montant = _float_val(valeur)
        elif rubrique == R_S21_CPT_CODE:
            cpt = self._ensure_compteur_annuel()
            cpt.code = valeur.strip()
            cpt.rubriques[rubrique] = valeur
        elif rubrique == R_S21_CPT_MONTANT:
            self._ensure_compteur_annuel().montant = _float_val(valeur)
        elif rubrique == R_S21_CPT_ANNEE:
            self._ensure_compteur_annuel().annee = valeur.strip()
        elif rubrique == R_S21_ARRET_DEB:
            ar = self._ensure_arret()
            ar.date_debut = valeur.strip()
            ar.rubriques[rubrique] = valeur
        elif rubrique == R_S21_ARRET_MOTIF:
            self._ensure_arret().motif = valeur.strip()
        elif rubrique == R_S21_ARRET_FIN:
            self._ensure_arret().date_fin = valeur.strip()
        elif rubrique == R_S21_ARRET_CAISSE:
            self._ensure_arret().siret_caisse = valeur.strip()
        elif rubrique == R_S21_SUSP_TYPE:
            sus = self._ensure_suspension()
            sus.type_suspension = valeur.strip()
            sus.rubriques[rubrique] = valeur
        elif rubrique == R_S21_SUSP_DEB:
            self._ensure_suspension().date_debut = valeur.strip()
        elif rubrique == R_S21_SUSP_FIN:
            self._ensure_suspension().date_fin = valeur.strip()
        elif rubrique == R_S21_SUSP_MOTIF:
            self._ensure_suspension().motif = valeur.strip()
        elif rubrique == R_S21_FIN_DATE:
            ctr = self._ensure_contrat()
            if ctr.fin_contrat is None:
                ctr.fin_contrat = FinContratBlock()
            ctr.fin_contrat.date_fin = valeur.strip()
            ctr.fin_contrat.rubriques[rubrique] = valeur
        elif rubrique == R_S21_FIN_MOTIF:
            ctr = self._ensure_contrat()
            if ctr.fin_contrat is None:
                ctr.fin_contrat = FinContratBlock()
            ctr.fin_contrat.motif = valeur.strip()
        elif rubrique == R_S21_FIN_NOTIF:
            ctr = self._ensure_contrat()
            if ctr.fin_contrat is None:
                ctr.fin_contrat = FinContratBlock()
            ctr.fin_contrat.date_notification = valeur.strip()
        elif rubrique == R_S21_ANC_TYPE:
            anc = self._ensure_anciennete()
            anc.type_unite = valeur.strip()
            anc.rubriques[rubrique] = valeur
        elif rubrique == R_S21_ANC_DEB:
            self._ensure_anciennete().date_debut = valeur.strip()
        elif rubrique == R_S21_ANC_FIN:
            self._ensure_anciennete().date_fin = valeur.strip()
        elif rubrique == R_S21_PRIME_CODE:
            pr = self._ensure_prime()
            pr.code = valeur.strip()
            pr.rubriques[rubrique] = valeur
        elif rubrique == R_S21_PRIME_MONTANT:
            self._ensure_prime().montant = _float_val(valeur)
        elif rubrique == R_S21_AVANT_CODE:
            pr = self._ensure_prime()
            pr.code = valeur.strip()
            pr.rubriques[rubrique] = valeur
        elif rubrique == R_S21_AVANT_MONTANT:
            self._ensure_prime().montant = _float_val(valeur)
        elif rubrique == R_S21_AVANT_DEB:
            self._ensure_prime().date_debut = valeur.strip()
        elif rubrique == R_S21_AVANT_FIN:
            self._ensure_prime().date_fin = valeur.strip()
        elif rubrique == R_S21_CTR_CLASSIF:
            self._ensure_contrat().rubriques[rubrique] = valeur.strip()
        elif rubrique == R_S21_CTR_NIVEAU:
            self._ensure_contrat().rubriques[rubrique] = valeur.strip()
        elif rubrique == R_S21_CTR_TAUX_AT:
            self._ensure_contrat().rubriques[rubrique] = valeur.strip()
        elif rubrique == R_S21_AFF_REF_CONTRAT:
            aff = self._ensure_affiliation()
            aff.reference_contrat = valeur.strip()
            aff.rubriques[rubrique] = valeur
        elif rubrique == R_S21_AFF_CODE_ORG:
            self._ensure_affiliation().code_organisme = valeur.strip()
        elif rubrique == R_S21_AFF_CODE_DELEG:
            self._ensure_affiliation().code_delegataire = valeur.strip()
        elif rubrique == R_S21_AFF_CODE_OPTION:
            self._ensure_affiliation().code_option = valeur.strip()
        elif rubrique == R_S21_AFF_CODE_POP:
            if self.affiliation is not None and (self.affiliation.code_population or "").strip():
                self.on_block_start("70")
            self._ensure_affiliation().code_population = valeur.strip()
        elif rubrique == R_S21_AFF_NB_ENFANTS:
            try:
                self._ensure_affiliation().nb_enfants = int(float(valeur.replace(",", ".")))
            except ValueError:
                pass
        elif rubrique == R_S21_AFF_NB_ADULTES:
            try:
                self._ensure_affiliation().nb_adultes = int(float(valeur.replace(",", ".")))
            except ValueError:
                pass
        elif rubrique == R_S21_AFF_IDENT:
            self._ensure_affiliation().identifiant_affiliation = valeur.strip()
        elif rubrique == R_S21_BASE_CODE:
            if self.cotisation_ind is not None:
                ci = self._ensure_cotisation_ind()
                ci.code = valeur.strip()
                ci.rubriques[rubrique] = valeur
            else:
                ver = self._ensure_versement()
                ver.rubriques.setdefault("bases", {})
                if isinstance(ver.rubriques["bases"], dict):
                    ver.rubriques["bases"][valeur] = 0.0
        elif rubrique in (R_S21_BASE_MONTANT, R_S21_CI_OPS_IDENT):
            if self.cotisation_ind is not None:
                ci = self._ensure_cotisation_ind()
                if self.dsn_format == "modern":
                    ci.rubriques["ops_ident"] = valeur.strip()
                else:
                    ci.montant_assiette = _float_val(valeur)
            else:
                ver = self._ensure_versement()
                bases = ver.rubriques.get("bases")
                if isinstance(bases, dict) and bases:
                    last_key = list(bases.keys())[-1]
                    bases[last_key] = _float_val(valeur)
        elif rubrique in (R_S21_CI_ASSIETTE, R_S21_CI_MONTANT_SAL):
            ci = self._ensure_cotisation_ind()
            if self.dsn_format == "modern":
                ci.montant_assiette = _float_val(valeur)
            else:
                ci.montant_salarial = _float_val(valeur)
        elif rubrique in (R_S21_CI_MONTANT, R_S21_CI_MONTANT_PAT):
            self._ensure_cotisation_ind().montant_patronal = _float_val(valeur)
        elif rubrique == R_S21_CI_TAUX:
            self._ensure_cotisation_ind().rubriques[rubrique] = valeur.strip()
        elif rubrique == R_S21_CI_IDENT_AFF:
            self._ensure_cotisation_ind().identifiant_affiliation = valeur.strip()
        elif rubrique == R_S21_ORG_REF:
            org = self._ensure_organisme_psc()
            org.reference_contrat = valeur.strip()
            org.rubriques[rubrique] = valeur
        elif rubrique == R_S21_ORG_CODE:
            self._ensure_organisme_psc().code_organisme = valeur.strip()
        elif rubrique == R_S21_ORG_NATURE:
            self._ensure_organisme_psc().code_nature = valeur.strip()
        elif rubrique == R_S21_ORG_RANG:
            self._ensure_organisme_psc().rang = valeur.strip()


def _normalize_psc_cotisations_contrat(contrat: ContratBlock) -> None:
    """Répartit salarial/patronal sur les blocs PSC (code 059) G00.81 après parse P26."""
    for ver in contrat.versements:
        for ci in ver.cotisations_individuelles:
            if (ci.code or "").strip() != "059":
                continue
            if ci.montant_salarial > 0:
                continue
            if ci.montant_patronal > 0 and ci.montant_assiette == 0:
                # Export Cegid : montant unique en .004 → part salariale.
                ci.montant_salarial = ci.montant_patronal
                ci.montant_patronal = 0.0
            elif ci.montant_patronal > 0 and ci.montant_assiette > 0:
                # P26 : .003 = part salariale, .004 = part patronale (pas assiette paie).
                ci.montant_salarial = ci.montant_assiette
                ci.montant_assiette = 0.0


def _sync_bases_from_blocks(etab: EtablissementBlock) -> None:
    """Alimente versement.rubriques['bases'] depuis G00.78/G00.79 parsés."""
    for ind in etab.individus:
        for contrat in ind.contrats:
            for ver in contrat.versements:
                bases = ver.rubriques.setdefault("bases", {})
                if not isinstance(bases, dict):
                    continue
                for ba in ver.bases_assujetties:
                    if ba.code and ba.montant > 0:
                        bases[ba.code] = ba.montant
                for cb in ver.composants_base:
                    if cb.code and cb.montant > 0:
                        bases[cb.code] = cb.montant


def _normalize_parsed_etablissement(etab: EtablissementBlock) -> None:
    for ind in etab.individus:
        for contrat in ind.contrats:
            _normalize_psc_cotisations_contrat(contrat)
    _sync_bases_from_blocks(etab)


def _looks_like_code(value: str) -> bool:
    clean = value.replace(" ", "")
    if not clean:
        return True
    if clean.isdigit() and len(clean) <= 5:
        return True
    if len(clean) <= 6 and any(c.isdigit() for c in clean) and any(c.isalpha() for c in clean):
        return True
    return False


def _finalize_etablissement(
    ctx: _ParseContext,
) -> None:
    """Assemble SIRET et complète adresse depuis S20 legacy ou entreprise."""
    etab = ctx.etablissement
    siren = ctx.entreprise.siren or (ctx.etablissement_s20.siret[:9] if ctx.etablissement_s20.siret else "")

    if not etab.siret and etab.nic and siren:
        etab.siret = build_siret_from_siren_nic(siren, etab.nic)

    if not etab.siret and ctx.etablissement_s20.siret:
        etab.siret = ctx.etablissement_s20.siret
        if not etab.raison_sociale:
            etab.raison_sociale = ctx.etablissement_s20.raison_sociale
        if not etab.code_naf:
            etab.code_naf = ctx.etablissement_s20.code_naf
        if not etab.adresse_rue:
            etab.adresse_rue = ctx.etablissement_s20.adresse_rue
            etab.adresse_cp = ctx.etablissement_s20.adresse_cp
            etab.adresse_ville = ctx.etablissement_s20.adresse_ville

    if ctx.dsn_format == "legacy" and not etab.raison_sociale:
        raison = ctx.entreprise.raison_sociale or ctx.etablissement_s20.raison_sociale
        if raison and not _looks_like_code(raison):
            etab.raison_sociale = raison

    if not etab.adresse_rue and ctx.entreprise.adresse_rue:
        etab.adresse_rue = ctx.entreprise.adresse_rue
        etab.adresse_cp = etab.adresse_cp or ctx.entreprise.adresse_cp
        etab.adresse_ville = etab.adresse_ville or ctx.entreprise.adresse_ville


def parse_dsn_content(content: bytes, file_name: str = "dsn.txt") -> DsnFile:
    """Parse un fichier DSN plat en modèle structuré."""
    text = decode_dsn_bytes(content)
    rubriques = parse_flat_lines(text)
    dsn_format = detect_dsn_format(rubriques)
    ctx = _ParseContext(dsn_format=dsn_format)

    for line in rubriques:
        g00 = _g00_block(line.rubrique)
        if g00 in BLOCK_G00 and line.rubrique.endswith(".001"):
            ctx.on_block_start(g00)
        ctx.apply_rubrique(line.rubrique, line.valeur)

    _finalize_etablissement(ctx)
    _normalize_parsed_etablissement(ctx.etablissement)

    if dsn_format == "modern":
        ctx.warnings.append(f"Norme détectée : NEODeS courante ({ctx.envoi.norme or 'P22+'})")
    else:
        ctx.warnings.append("Norme détectée : format legacy (SIRET complet en S21.G00.11.001)")

    return DsnFile(
        file_name=file_name,
        envoi=ctx.envoi,
        declaration=ctx.declaration,
        etablissement_s20=ctx.etablissement_s20,
        entreprise=ctx.entreprise,
        etablissement=ctx.etablissement,
        raw_rubriques=rubriques,
        parse_warnings=ctx.warnings,
        dsn_format=dsn_format,
    )


def parse_dsn_files(files: List[Tuple[str, bytes]]) -> ParsedDsnSet:
    """Parse plusieurs fichiers DSN et les agrège."""
    parsed = ParsedDsnSet()
    for file_name, content in files:
        try:
            dsn_file = parse_dsn_content(content, file_name=file_name)
            parsed.files.append(dsn_file)
        except Exception as exc:
            parsed.warnings.append(f"{file_name} : erreur de parsing ({exc})")
    return parsed
