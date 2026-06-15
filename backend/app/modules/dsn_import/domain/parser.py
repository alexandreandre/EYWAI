"""Parser DSN fichier plat NEODeS."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from app.modules.dsn_import.domain.model import (
    ContratBlock,
    CotisationBlock,
    DsnFile,
    EtablissementBlock,
    EntrepriseBlock,
    EnvoiBlock,
    IndividuBlock,
    ParsedDsnSet,
    RemunerationBlock,
    RubriqueLine,
    VersementBlock,
)
from app.modules.dsn_import.domain.rubriques import (
    BLOCK_G00,
    R_S10_NORME,
    R_S10_PERIODE,
    R_S10_TYPE,
    R_S20_CP,
    R_S20_NAF,
    R_S20_RAISON,
    R_S20_RUE,
    R_S20_SIRET,
    R_S20_VILLE,
    R_S21_BASE_CODE,
    R_S21_BASE_MONTANT,
    R_S21_COT_CODE,
    R_S21_COT_BASE,
    R_S21_COT_MONTANT_PAT,
    R_S21_COT_MONTANT_SAL,
    R_S21_COT_TAUX_PAT,
    R_S21_COT_TAUX_SAL,
    R_S21_CTR_DATE_DEBUT,
    R_S21_CTR_DATE_FIN,
    R_S21_CTR_IDCC,
    R_S21_CTR_LIBELLE_EMPLOI,
    R_S21_CTR_MODALITE_TEMPS,
    R_S21_CTR_NATURE,
    R_S21_CTR_PCS,
    R_S21_CTR_QUOTITE,
    R_S21_CTR_STATUT,
    R_S21_ENT_NAF,
    R_S21_ENT_RAISON,
    R_S21_ENT_SIREN,
    R_S21_ETAB_CP,
    R_S21_ETAB_EFFECTIF,
    R_S21_ETAB_NAF,
    R_S21_ETAB_RAISON,
    R_S21_ETAB_RUE,
    R_S21_ETAB_SIRET,
    R_S21_ETAB_VILLE,
    R_S21_IND_CP,
    R_S21_IND_NAISSANCE,
    R_S21_IND_LIEU_NAISS,
    R_S21_IND_NATIONALITE,
    R_S21_IND_NIR,
    R_S21_IND_NOM,
    R_S21_IND_PRENOM,
    R_S21_IND_RUE,
    R_S21_IND_VILLE,
    R_S21_REM_HEURES,
    R_S21_REM_MONTANT,
    R_S21_REM_TYPE,
    R_S21_VER_DATE,
    R_S21_VER_NET_FISCAL,
    R_S21_VER_PAS,
)

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
        # Format alternatif sans quotes
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


class _ParseContext:
    def __init__(self) -> None:
        self.envoi = EnvoiBlock()
        self.etablissement_s20 = EtablissementBlock()
        self.entreprise = EntrepriseBlock()
        self.etablissement = EtablissementBlock()
        self.individu: Optional[IndividuBlock] = None
        self.contrat: Optional[ContratBlock] = None
        self.versement: Optional[VersementBlock] = None
        self.remuneration: Optional[RemunerationBlock] = None
        self.cotisation: Optional[CotisationBlock] = None
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

    def on_block_start(self, g00: str) -> None:
        block = BLOCK_G00.get(g00)
        if block == "individu":
            self.individu = IndividuBlock()
            self.etablissement.individus.append(self.individu)
            self.contrat = None
            self.versement = None
            self.remuneration = None
            self.cotisation = None
        elif block == "contrat":
            ind = self._ensure_individu()
            self.contrat = ContratBlock()
            ind.contrats.append(self.contrat)
            self.versement = None
            self.remuneration = None
            self.cotisation = None
        elif block == "versement":
            ctr = self._ensure_contrat()
            self.versement = VersementBlock()
            ctr.versements.append(self.versement)
            self.remuneration = None
            self.cotisation = None
        elif block == "remuneration":
            ver = self._ensure_versement()
            self.remuneration = RemunerationBlock()
            ver.remunerations.append(self.remuneration)
        elif block == "cotisation":
            ver = self._ensure_versement()
            self.cotisation = CotisationBlock()
            ver.cotisations.append(self.cotisation)
        elif block == "etablissement":
            if not self.etablissement.siret:
                self.etablissement = EtablissementBlock()
            self.individu = None
            self.contrat = None
            self.versement = None
            self.remuneration = None
            self.cotisation = None
        elif block == "entreprise":
            self.entreprise = EntrepriseBlock()

    def apply_rubrique(self, rubrique: str, valeur: str) -> None:
        # S10
        if rubrique == R_S10_PERIODE:
            self.envoi.periode = valeur
            self.envoi.rubriques[rubrique] = valeur
        elif rubrique == R_S10_NORME:
            self.envoi.norme = valeur
            self.envoi.rubriques[rubrique] = valeur
        elif rubrique == R_S10_TYPE:
            self.envoi.type_envoi = valeur
            self.envoi.rubriques[rubrique] = valeur

        # S20
        elif rubrique == R_S20_SIRET:
            self.etablissement_s20.siret = valeur.replace(" ", "")
            self.etablissement_s20.rubriques[rubrique] = valeur
        elif rubrique == R_S20_RAISON:
            self.etablissement_s20.raison_sociale = valeur
        elif rubrique == R_S20_NAF:
            self.etablissement_s20.code_naf = valeur
        elif rubrique == R_S20_RUE:
            self.etablissement_s20.adresse_rue = valeur
        elif rubrique == R_S20_CP:
            self.etablissement_s20.adresse_cp = valeur
        elif rubrique == R_S20_VILLE:
            self.etablissement_s20.adresse_ville = valeur

        # Entreprise S21.G00.06
        elif rubrique == R_S21_ENT_SIREN:
            self.entreprise.siren = valeur.replace(" ", "")[:9]
            self.entreprise.rubriques[rubrique] = valeur
        elif rubrique == R_S21_ENT_RAISON:
            self.entreprise.raison_sociale = valeur
        elif rubrique == R_S21_ENT_NAF:
            self.entreprise.code_naf = valeur

        # Établissement S21.G00.11
        elif rubrique == R_S21_ETAB_SIRET:
            self.etablissement.siret = valeur.replace(" ", "")
            self.etablissement.rubriques[rubrique] = valeur
        elif rubrique == R_S21_ETAB_RAISON:
            self.etablissement.raison_sociale = valeur
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

        # Individu
        elif rubrique == R_S21_IND_NOM:
            self._ensure_individu().nom = valeur
            self._ensure_individu().rubriques[rubrique] = valeur
        elif rubrique == R_S21_IND_PRENOM:
            self._ensure_individu().prenom = valeur
        elif rubrique == R_S21_IND_NIR:
            self._ensure_individu().nir = valeur.replace(" ", "")
        elif rubrique == R_S21_IND_NAISSANCE:
            self._ensure_individu().date_naissance = valeur
        elif rubrique == R_S21_IND_LIEU_NAISS:
            self._ensure_individu().lieu_naissance = valeur
        elif rubrique == R_S21_IND_NATIONALITE:
            self._ensure_individu().nationalite = valeur
        elif rubrique == R_S21_IND_RUE:
            self._ensure_individu().adresse_rue = valeur
        elif rubrique == R_S21_IND_CP:
            self._ensure_individu().adresse_cp = valeur
        elif rubrique == R_S21_IND_VILLE:
            self._ensure_individu().adresse_ville = valeur

        # Contrat
        elif rubrique == R_S21_CTR_NATURE:
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
        elif rubrique == R_S21_CTR_IDCC:
            self._ensure_contrat().idcc = valeur
        elif rubrique == R_S21_CTR_MODALITE_TEMPS:
            self._ensure_contrat().modalite_temps = valeur
        elif rubrique == R_S21_CTR_QUOTITE:
            self._ensure_contrat().quotite = valeur
        elif rubrique == R_S21_CTR_LIBELLE_EMPLOI:
            self._ensure_contrat().libelle_emploi = valeur

        # Versement
        elif rubrique == R_S21_VER_DATE:
            self._ensure_versement().date_versement = valeur
        elif rubrique == R_S21_VER_NET_FISCAL:
            self._ensure_versement().net_fiscal = _float_val(valeur)
        elif rubrique == R_S21_VER_PAS:
            self._ensure_versement().pas = _float_val(valeur)

        # Rémunération
        elif rubrique == R_S21_REM_TYPE:
            self._ensure_remuneration().type_code = valeur
            self._ensure_remuneration().rubriques[rubrique] = valeur
        elif rubrique == R_S21_REM_MONTANT:
            self._ensure_remuneration().montant = _float_val(valeur)
        elif rubrique == R_S21_REM_HEURES:
            self._ensure_remuneration().heures = _float_val(valeur)

        # Cotisation
        elif rubrique == R_S21_COT_CODE:
            self._ensure_cotisation().code = valeur
            self._ensure_cotisation().rubriques[rubrique] = valeur
        elif rubrique == R_S21_COT_BASE:
            self._ensure_cotisation().base = _float_val(valeur)
        elif rubrique == R_S21_COT_TAUX_SAL:
            self._ensure_cotisation().taux_salarial = _float_val(valeur)
        elif rubrique == R_S21_COT_TAUX_PAT:
            self._ensure_cotisation().taux_patronal = _float_val(valeur)
        elif rubrique == R_S21_COT_MONTANT_SAL:
            self._ensure_cotisation().montant_salarial = _float_val(valeur)
        elif rubrique == R_S21_COT_MONTANT_PAT:
            self._ensure_cotisation().montant_patronal = _float_val(valeur)

        # Base assujettie (stockée sur versement courant)
        elif rubrique == R_S21_BASE_CODE:
            ver = self._ensure_versement()
            ver.rubriques.setdefault("bases", {})
            if isinstance(ver.rubriques["bases"], dict):
                ver.rubriques["bases"][valeur] = 0.0
        elif rubrique == R_S21_BASE_MONTANT:
            ver = self._ensure_versement()
            bases = ver.rubriques.get("bases")
            if isinstance(bases, dict) and bases:
                last_key = list(bases.keys())[-1]
                bases[last_key] = _float_val(valeur)


def parse_dsn_content(content: bytes, file_name: str = "dsn.txt") -> DsnFile:
    """Parse un fichier DSN plat en modèle structuré."""
    text = decode_dsn_bytes(content)
    rubriques = parse_flat_lines(text)
    ctx = _ParseContext()

    for line in rubriques:
        g00 = _g00_block(line.rubrique)
        if g00 in BLOCK_G00 and line.rubrique.endswith(".001"):
            ctx.on_block_start(g00)
        ctx.apply_rubrique(line.rubrique, line.valeur)

    # Fallback SIRET S20 -> S21 établissement
    if not ctx.etablissement.siret and ctx.etablissement_s20.siret:
        ctx.etablissement.siret = ctx.etablissement_s20.siret
        if not ctx.etablissement.raison_sociale:
            ctx.etablissement.raison_sociale = ctx.etablissement_s20.raison_sociale
        if not ctx.etablissement.code_naf:
            ctx.etablissement.code_naf = ctx.etablissement_s20.code_naf

    return DsnFile(
        file_name=file_name,
        envoi=ctx.envoi,
        etablissement_s20=ctx.etablissement_s20,
        entreprise=ctx.entreprise,
        etablissement=ctx.etablissement,
        raw_rubriques=rubriques,
        parse_warnings=ctx.warnings,
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
