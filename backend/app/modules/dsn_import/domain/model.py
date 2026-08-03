"""Modèle intermédiaire normalisé après parsing DSN."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RubriqueLine:
    rubrique: str
    valeur: str
    line_no: int


@dataclass
class CotisationBlock:
    code: str = ""
    base: float = 0.0
    taux_salarial: float = 0.0
    taux_patronal: float = 0.0
    montant_salarial: float = 0.0
    montant_patronal: float = 0.0
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class BaseAssujettieBlock:
    """Bloc S21.G00.78 en norme P22+ (dates + montant assiette)."""

    code: str = ""
    date_debut: str = ""
    date_fin: str = ""
    montant: float = 0.0
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class ComposantBaseBlock:
    """Bloc S21.G00.79 — composant de base assujettie."""

    code: str = ""
    montant: float = 0.0
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class CotisationAgregeeBlock:
    """Bloc S21.G00.86 — cotisation agrégée."""

    code: str = ""
    code_base: str = ""
    taux: float = 0.0
    montant: float = 0.0
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class PrimeBlock:
    """Bloc S21.G00.52 / S21.G00.54 — prime ou avantage."""

    code: str = ""
    montant: float = 0.0
    date_debut: str = ""
    date_fin: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class ComposantCotisationEtabBlock:
    """Bloc S21.G00.23 — composant cotisation établissement (ex. taux AT/MP)."""

    code: str = ""
    regime: str = ""
    taux: float = 0.0
    assiette: float = 0.0
    montant_pat: float = 0.0
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class VersementOrganismeBlock:
    """Bloc S21.G00.20 — versement organisme."""

    identifiant: str = ""
    libelle: str = ""
    bic: str = ""
    iban: str = ""
    montant: float = 0.0
    date_debut: str = ""
    date_fin: str = ""
    mode_paiement: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class BordereauBlock:
    """Bloc S21.G00.22 — bordereau de cotisation."""

    identifiant: str = ""
    date_debut: str = ""
    date_fin: str = ""
    montant: float = 0.0
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class CompteurAnnuelBlock:
    """Bloc S21.G00.44 — compteur annuel (pas une période d'absence)."""

    code: str = ""
    montant: float = 0.0
    annee: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class ArretTravailBlock:
    """Bloc S21.G00.41 — arrêt de travail."""

    date_debut: str = ""
    date_fin: str = ""
    motif: str = ""
    siret_caisse: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class SuspensionContratBlock:
    """Bloc S21.G00.60 — suspension de contrat."""

    type_suspension: str = ""
    date_debut: str = ""
    date_fin: str = ""
    motif: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class FinContratBlock:
    """Bloc S21.G00.62 — fin de contrat."""

    date_fin: str = ""
    motif: str = ""
    date_notification: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class AncienneteBlock:
    """Bloc S21.G00.65 — ancienneté."""

    type_unite: str = ""
    date_debut: str = ""
    date_fin: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class CotisationIndividuelleBlock:
    """Bloc S21.G00.81 — cotisation individuelle (ex. code 059 PSC)."""

    code: str = ""
    montant_assiette: float = 0.0
    montant_salarial: float = 0.0
    montant_patronal: float = 0.0
    identifiant_affiliation: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class AffiliationBlock:
    """Bloc S21.G00.70 — affiliation salarié mutuelle / prévoyance."""

    reference_contrat: str = ""
    code_organisme: str = ""
    code_delegataire: str = ""
    code_option: str = ""
    code_population: str = ""
    nb_enfants: int = 0
    nb_adultes: int = 0
    identifiant_affiliation: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class OrganismePscBlock:
    """Bloc S21.G00.15 — contrat collectif mutuelle / prévoyance (niveau établissement)."""

    reference_contrat: str = ""
    code_organisme: str = ""
    code_nature: str = ""
    rang: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class RemunerationBlock:
    type_code: str = ""
    montant: float = 0.0
    heures: float = 0.0
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class VersementBlock:
    date_versement: str = ""
    net_fiscal: float = 0.0
    net_verse: float = 0.0
    pas: float = 0.0
    pas_taux: float = 0.0
    pas_type: str = ""
    pas_identifiant: str = ""
    montant_soumis_pas: float = 0.0
    remunerations: List[RemunerationBlock] = field(default_factory=list)
    cotisations: List[CotisationBlock] = field(default_factory=list)
    bases_assujetties: List[BaseAssujettieBlock] = field(default_factory=list)
    composants_base: List[ComposantBaseBlock] = field(default_factory=list)
    cotisations_agregees: List[CotisationAgregeeBlock] = field(default_factory=list)
    primes: List[PrimeBlock] = field(default_factory=list)
    cotisations_individuelles: List[CotisationIndividuelleBlock] = field(
        default_factory=list
    )
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class ContratBlock:
    nature: str = ""
    statut: str = ""
    pcs: str = ""
    date_debut: str = ""
    date_fin: str = ""
    idcc: str = ""
    modalite_temps: str = ""
    quotite: str = ""
    quotite_reference: str = ""
    unite_quotite: str = ""
    dispositif: str = ""
    numero_contrat: str = ""
    position_conv: str = ""
    libelle_emploi: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)
    affiliations: List[AffiliationBlock] = field(default_factory=list)
    arrets: List[ArretTravailBlock] = field(default_factory=list)
    suspensions: List[SuspensionContratBlock] = field(default_factory=list)
    fin_contrat: Optional[FinContratBlock] = None
    anciennetes: List[AncienneteBlock] = field(default_factory=list)
    versements: List[VersementBlock] = field(default_factory=list)


@dataclass
class IndividuBlock:
    nom: str = ""
    prenom: str = ""
    nom_usage: str = ""
    sexe: str = ""
    nir: str = ""
    matricule: str = ""
    ntt: str = ""
    date_naissance: str = ""
    lieu_naissance: str = ""
    nationalite: str = ""
    adresse_rue: str = ""
    adresse_cp: str = ""
    adresse_ville: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)
    contrats: List[ContratBlock] = field(default_factory=list)

    @property
    def identifiant(self) -> str:
        """Clé stable pour fusion / références (NIR, NTT ou matricule)."""
        return self.nir or self.ntt or self.matricule or ""


@dataclass
class EtablissementBlock:
    siret: str = ""
    nic: str = ""
    raison_sociale: str = ""
    code_naf: str = ""
    adresse_rue: str = ""
    adresse_cp: str = ""
    adresse_ville: str = ""
    effectif: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)
    organismes_psc: List[OrganismePscBlock] = field(default_factory=list)
    composants_cotisation: List[ComposantCotisationEtabBlock] = field(
        default_factory=list
    )
    versements_organismes: List[VersementOrganismeBlock] = field(default_factory=list)
    bordereaux: List[BordereauBlock] = field(default_factory=list)
    compteurs_annuels: List[CompteurAnnuelBlock] = field(default_factory=list)
    individus: List[IndividuBlock] = field(default_factory=list)


@dataclass
class DeclarationBlock:
    """Bloc S20.G00.05 — déclaration (norme courante)."""

    nature: str = ""
    type_declaration: str = ""
    mois_principal: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)
    # Bloc S20.G00.07, répété par organisme destinataire.
    contacts: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class EntrepriseBlock:
    siren: str = ""
    nic_siege: str = ""
    raison_sociale: str = ""
    code_naf: str = ""
    adresse_rue: str = ""
    adresse_cp: str = ""
    adresse_ville: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class EnvoiBlock:
    periode: str = ""
    norme: str = ""
    type_envoi: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class DsnFile:
    """Une DSN parsée (un fichier, un mois typiquement)."""

    file_name: str
    envoi: EnvoiBlock = field(default_factory=EnvoiBlock)
    declaration: DeclarationBlock = field(default_factory=DeclarationBlock)
    etablissement_s20: EtablissementBlock = field(default_factory=EtablissementBlock)
    entreprise: EntrepriseBlock = field(default_factory=EntrepriseBlock)
    etablissement: EtablissementBlock = field(default_factory=EtablissementBlock)
    raw_rubriques: List[RubriqueLine] = field(default_factory=list)
    parse_warnings: List[str] = field(default_factory=list)
    dsn_format: str = "modern"


@dataclass
class ParsedDsnSet:
    """Ensemble de DSN (multi-fichiers / multi-mois)."""

    files: List[DsnFile] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def period_min(self) -> Optional[str]:
        periods = [self._period_from_file(f) for f in self.files]
        periods = [p for p in periods if p]
        return min(periods) if periods else None

    @property
    def period_max(self) -> Optional[str]:
        periods = [self._period_from_file(f) for f in self.files]
        periods = [p for p in periods if p]
        return max(periods) if periods else None

    @property
    def siren(self) -> Optional[str]:
        for f in self.files:
            if f.entreprise.siren:
                return f.entreprise.siren
            siret = f.etablissement.siret or f.etablissement_s20.siret
            if siret and len(siret) >= 9:
                return siret[:9]
        return None

    def etablissements_by_siret(self) -> Dict[str, EtablissementBlock]:
        """Fusionne les établissements identifiés par SIRET sur tous les fichiers."""
        out: Dict[str, EtablissementBlock] = {}
        for dsn_file in self.files:
            for etab in self._etablissements_from_file(dsn_file):
                siret = self._resolve_etab_siret(etab, dsn_file)
                if not siret:
                    continue
                etab.siret = siret
                if siret not in out:
                    out[siret] = etab
                else:
                    self._merge_etablissement(out[siret], etab)
        return out

    @staticmethod
    def _resolve_etab_siret(etab: EtablissementBlock, dsn_file: DsnFile) -> str:
        from app.shared.dsn_validation import build_siret_from_siren_nic

        if etab.siret and len(etab.siret.replace(" ", "")) == 14:
            return etab.siret.replace(" ", "")
        siren = dsn_file.entreprise.siren or ""
        if etab.nic and siren:
            return build_siret_from_siren_nic(siren, etab.nic)
        if etab.siret:
            return etab.siret.replace(" ", "")
        if dsn_file.etablissement_s20.siret:
            return dsn_file.etablissement_s20.siret.replace(" ", "")
        return ""

    @staticmethod
    def _period_from_file(dsn_file: DsnFile) -> Optional[str]:
        mois = dsn_file.declaration.mois_principal.replace("-", "").strip()
        if len(mois) == 8 and mois.isdigit() and mois.startswith("01"):
            # Format DSN : 01mmaaaa
            return f"{mois[4:8]}-{mois[2:4]}"

        periode = dsn_file.envoi.periode.replace("-", "").strip()
        if not periode:
            return ParsedDsnSet._period_from_versements(dsn_file)
        # Legacy : YYYYMM en S10.G00.00.005 (exports simplifiés)
        if len(periode) == 6 and periode.isdigit():
            return f"{periode[:4]}-{periode[4:6]}"
        if len(periode) == 7 and "-" in dsn_file.envoi.periode:
            return dsn_file.envoi.periode
        return ParsedDsnSet._period_from_versements(dsn_file)

    @staticmethod
    def _period_from_versements(dsn_file: DsnFile) -> Optional[str]:
        dates: List[str] = []
        for ind in dsn_file.etablissement.individus:
            for ctr in ind.contrats:
                for ver in ctr.versements:
                    d = ver.date_versement.replace("-", "").strip()
                    if len(d) == 8 and d.isdigit():
                        dates.append(f"{d[4:8]}-{d[2:4]}")
        return min(dates) if dates else None

    @staticmethod
    def _etablissements_from_file(dsn_file: DsnFile) -> List[EtablissementBlock]:
        etabs: List[EtablissementBlock] = []
        if dsn_file.etablissement.siret or dsn_file.etablissement.nic:
            etabs.append(dsn_file.etablissement)
        elif dsn_file.etablissement_s20.siret:
            etab = dsn_file.etablissement_s20
            etab.individus = dsn_file.etablissement.individus
            etabs.append(etab)
        elif dsn_file.etablissement.individus:
            etabs.append(dsn_file.etablissement)
        return etabs

    @staticmethod
    def _merge_etablissement(target: EtablissementBlock, source: EtablissementBlock) -> None:
        if not target.raison_sociale and source.raison_sociale:
            target.raison_sociale = source.raison_sociale
        if not target.code_naf and source.code_naf:
            target.code_naf = source.code_naf
        if not target.adresse_rue and source.adresse_rue:
            target.adresse_rue = source.adresse_rue
            target.adresse_cp = source.adresse_cp
            target.adresse_ville = source.adresse_ville
        if not target.effectif and source.effectif:
            target.effectif = source.effectif
        if source.composants_cotisation:
            target.composants_cotisation.extend(source.composants_cotisation)
        if source.versements_organismes:
            target.versements_organismes.extend(source.versements_organismes)
        if source.bordereaux:
            target.bordereaux.extend(source.bordereaux)
        id_index = {i.identifiant: i for i in target.individus if i.identifiant}
        for ind in source.individus:
            key = ind.identifiant
            if key and key in id_index:
                existing = id_index[key]
                if ind.contrats:
                    existing.contrats.extend(ind.contrats)
            else:
                target.individus.append(ind)
                if key:
                    id_index[key] = ind
