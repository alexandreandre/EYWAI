"""
Chargement des bulletins de référence du cabinet, pour le backtest.

Emplacement : `data/<societe>/bulletins/<AAAA-MM>/`, la convention en
vigueur. L'ancien `Config/<Entreprise>/Compteur CP` reste consulté en
dernier recours — il ne contient plus qu'une société sur sept.

**Le mois demandé est le mois rendu, ou rien.** La version précédente
retombait sur `pdfs[0]`, le premier fichier venu, quand aucun PDF ne
correspondait : un backtest qui compare silencieusement le mauvais mois
produit des écarts ininterprétables, et fait chercher un défaut de moteur
là où il n'y a qu'une erreur de fichier. Un mois absent lève désormais une
erreur qui nomme la société, le mois et les emplacements consultés.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, List

from app.modules.payroll.backtest.models import ReferenceBulletin
from app.modules.payroll.backtest.reference_parser import parse_cegid_text

RACINE_DEPOT = Path(__file__).resolve().parents[2]
RACINE_DATA = RACINE_DEPOT.parent / "data"
CONFIG_ROOT = RACINE_DEPOT.parent / "Config"

#: Nom saisi (minuscules) → dossier sous data/
DOSSIERS_SOCIETES: Dict[str, str] = {
    "colorplast": "colorplast",
    "cartol": "cartol",
    "cartol industrie": "cartol",
    "comitech": "comitech",
    "comitech composite": "comitech",
    "lewis": "lewis",
    "mbc": "mbc",
    "mont blanc composite": "mbc",
    "maji": "maji",
    "zone": "zone",
    "zone 404": "zone",
    "zone 404 mars": "zone",
    "exemple": "exemple",
}

#: Ancien emplacement, conservé le temps de la reprise.
DOSSIERS_CONFIG_LEGACY: Dict[str, str] = {
    "colorplast": "Colorplast",
    "cartol": "Cartol",
    "comitech": "Comitech Composite",
    "lewis": "Lewis",
    "mbc": "MBC",
    "maji": "Maji",
    "zone": "Zone",
    "exemple": "Exemple",
}


def _cle_societe(nom: str) -> str:
    return (nom or "").strip().lower()


def dossier_societe(nom_societe: str) -> str:
    """Nom de dossier sous data/ pour une société — le nom saisi par défaut."""
    cle = _cle_societe(nom_societe)
    return DOSSIERS_SOCIETES.get(cle, cle)


def _candidats_data(nom_societe: str, annee: int, mois: int) -> List[Path]:
    periode = f"{annee:04d}-{mois:02d}"
    dossier = RACINE_DATA / dossier_societe(nom_societe) / "bulletins" / periode
    if not dossier.is_dir():
        return []
    return sorted(dossier.glob("*.pdf"))


def _candidats_config_legacy(nom_societe: str, annee: int, mois: int) -> List[Path]:
    cle = _cle_societe(nom_societe)
    dossier = CONFIG_ROOT / DOSSIERS_CONFIG_LEGACY.get(cle, nom_societe)
    if not dossier.is_dir():
        return []
    attendu = f"{mois:02d}-{annee:04d}"
    trouves: List[Path] = []
    for compteur in sorted(dossier.glob("Compteur CP*")):
        # Correspondance STRICTE mois-année : un simple « 07 » dans le nom
        # peut désigner juillet d'une autre année, ou un numéro de dossier.
        trouves.extend(p for p in sorted(compteur.glob("*.pdf")) if attendu in p.name)
    return trouves


def find_reference_pdf(nom_societe: str, annee: int, mois: int) -> Path:
    """Bulletin de référence du mois demandé. Lève si ce mois est absent."""
    for candidats in (
        _candidats_data(nom_societe, annee, mois),
        _candidats_config_legacy(nom_societe, annee, mois),
    ):
        if candidats:
            return candidats[0]

    periode = f"{annee:04d}-{mois:02d}"
    emplacements = [
        str(RACINE_DATA / dossier_societe(nom_societe) / "bulletins" / periode),
        str(CONFIG_ROOT / DOSSIERS_CONFIG_LEGACY.get(_cle_societe(nom_societe), nom_societe)),
    ]
    raise FileNotFoundError(
        f"Aucun bulletin de référence pour '{nom_societe}' sur {periode}. "
        "Le mois demandé est le mois rendu : rien n'est substitué. "
        f"Emplacements consultés : {' ; '.join(emplacements)}"
    )


def extract_pdf_text(chemin_pdf: Path) -> str:
    """Texte du PDF. `-layout` est indispensable : les bulletins Cegid
    tiennent sur deux pages et perdent leur alignement sans lui."""
    resultat = subprocess.run(
        ["pdftotext", "-layout", str(chemin_pdf), "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    return resultat.stdout


def load_reference_bulletins(
    nom_societe: str,
    annee: int,
    mois: int,
    *,
    pdf_path: Path | None = None,
) -> Dict[str, ReferenceBulletin]:
    pdf = pdf_path or find_reference_pdf(nom_societe, annee, mois)
    return parse_cegid_text(extract_pdf_text(pdf))


# --- Compatibilité : anciens noms utilisés par les scripts de backtest ---


def resolve_company_folder(nom_societe: str) -> Path:
    """Dossier de la société, en Path — `export_reference_md` y appelle
    `.glob()`. Priorité à data/, repli sur l'ancien Config/."""
    dossier = RACINE_DATA / dossier_societe(nom_societe) / "bulletins"
    if dossier.is_dir():
        return dossier
    cle = _cle_societe(nom_societe)
    legacy = CONFIG_ROOT / DOSSIERS_CONFIG_LEGACY.get(cle, nom_societe)
    if legacy.is_dir():
        return legacy
    raise FileNotFoundError(
        f"Aucun dossier de bulletins pour '{nom_societe}' "
        f"(cherché : {dossier} ; {legacy})"
    )


COMPANY_FOLDER_ALIASES = DOSSIERS_CONFIG_LEGACY
