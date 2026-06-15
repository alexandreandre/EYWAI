"""Modèle intermédiaire normalisé après parsing DSN."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
class RemunerationBlock:
    type_code: str = ""
    montant: float = 0.0
    heures: float = 0.0
    rubriques: Dict[str, str] = field(default_factory=dict)


@dataclass
class VersementBlock:
    date_versement: str = ""
    net_fiscal: float = 0.0
    pas: float = 0.0
    remunerations: List[RemunerationBlock] = field(default_factory=list)
    cotisations: List[CotisationBlock] = field(default_factory=list)
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
    libelle_emploi: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)
    versements: List[VersementBlock] = field(default_factory=list)


@dataclass
class IndividuBlock:
    nom: str = ""
    prenom: str = ""
    nir: str = ""
    date_naissance: str = ""
    lieu_naissance: str = ""
    nationalite: str = ""
    adresse_rue: str = ""
    adresse_cp: str = ""
    adresse_ville: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)
    contrats: List[ContratBlock] = field(default_factory=list)


@dataclass
class EtablissementBlock:
    siret: str = ""
    raison_sociale: str = ""
    code_naf: str = ""
    adresse_rue: str = ""
    adresse_cp: str = ""
    adresse_ville: str = ""
    effectif: str = ""
    rubriques: Dict[str, str] = field(default_factory=dict)
    individus: List[IndividuBlock] = field(default_factory=list)


@dataclass
class EntrepriseBlock:
    siren: str = ""
    raison_sociale: str = ""
    code_naf: str = ""
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
    etablissement_s20: EtablissementBlock = field(default_factory=EtablissementBlock)
    entreprise: EntrepriseBlock = field(default_factory=EntrepriseBlock)
    etablissement: EtablissementBlock = field(default_factory=EtablissementBlock)
    raw_rubriques: List[RubriqueLine] = field(default_factory=list)
    parse_warnings: List[str] = field(default_factory=list)


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
                siret = etab.siret
                if not siret:
                    continue
                if siret not in out:
                    out[siret] = etab
                else:
                    self._merge_etablissement(out[siret], etab)
        return out

    @staticmethod
    def _period_from_file(dsn_file: DsnFile) -> Optional[str]:
        periode = dsn_file.envoi.periode
        if not periode:
            return None
        clean = periode.replace("-", "").strip()
        if len(clean) == 6 and clean.isdigit():
            return f"{clean[:4]}-{clean[4:6]}"
        if len(clean) == 7 and "-" in periode:
            return periode
        return periode if len(periode) == 7 else None

    @staticmethod
    def _etablissements_from_file(dsn_file: DsnFile) -> List[EtablissementBlock]:
        etabs: List[EtablissementBlock] = []
        if dsn_file.etablissement.siret:
            etabs.append(dsn_file.etablissement)
        elif dsn_file.etablissement_s20.siret:
            etab = dsn_file.etablissement_s20
            etab.individus = dsn_file.etablissement.individus
            etabs.append(etab)
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
        nir_index = {i.nir: i for i in target.individus if i.nir}
        for ind in source.individus:
            if ind.nir and ind.nir in nir_index:
                existing = nir_index[ind.nir]
                if ind.contrats:
                    existing.contrats.extend(ind.contrats)
            else:
                target.individus.append(ind)
                if ind.nir:
                    nir_index[ind.nir] = ind
