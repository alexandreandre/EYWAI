"""L'aperçu d'un signalement DSN (04, 05, 07) avant tout dépôt : le fichier lu
bloc par bloc, chaque rubrique avec son libellé et, pour un code, sa valeur en
mots. Le NIR ne s'affiche jamais en entier. Fonctions pures : rien n'est écrit.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.modules.dsn_export.domain.libelles_rubriques import BLOCS, RUBRIQUES, VALEURS

#: Numéro d'inscription au répertoire (NIR) du salarié.
RUBRIQUE_NIR = "S21.G00.30.001"
MASQUE = "•"

#: Les parties de l'écran, d'après l'identifiant du bloc.
_PARTIES: Tuple[Tuple[str, str], ...] = (
    ("S10.G00.00", "envoi"),
    ("S10.G00.01", "declarant"),
    ("S10.G00.02", "declarant"),
    ("S20.G00.05", "declarant"),
    ("S20.G00.07", "declarant"),
    ("S21.G00.06", "entreprise"),
    ("S21.G00.11", "entreprise"),
    ("S21.G00.15", "entreprise"),
    ("S21.G00.30", "salarie"),
    ("S21.G00.40", "contrat"),
    ("S21.G00.45", "contrat"),
    ("S21.G00.60", "evenement"),
    ("S21.G00.62", "evenement"),
    ("S21.G00.63", "evenement"),
    ("S21.G00.65", "evenement"),
    ("S21.G00.50", "remuneration"),
    ("S21.G00.51", "remuneration"),
    ("S21.G00.52", "remuneration"),
    ("S21.G00.53", "remuneration"),
    ("S21.G00.54", "remuneration"),
    ("S21.G00.78", "remuneration"),
    ("S21.G00.81", "remuneration"),
    ("S21.G00.70", "contrat"),
    ("S21.G00.71", "contrat"),
    ("S21.G00.73", "contrat"),
    ("S21.G00.85", "contrat"),
    ("S21.G00.86", "contrat"),
    ("S90.G00.90", "envoi"),
)
PARTIES: Dict[str, str] = dict(_PARTIES)

LIBELLES_NATURE = {
    "04": "Signalement d'arrêt de travail",
    "05": "Signalement de reprise suite à arrêt de travail",
    "07": "Signalement de fin du contrat de travail unique",
}


def masquer_nir(valeur: str) -> str:
    """Les 2 premiers et les 2 derniers caractères, le reste masqué (longueur gardée)."""
    if len(valeur) <= 4:
        return MASQUE * len(valeur)
    return valeur[:2] + MASQUE * (len(valeur) - 4) + valeur[-2:]


def _lignes(texte: str) -> List[Tuple[str, str]]:
    """(rubrique, valeur sans guillemets) dans l'ordre du fichier."""
    lignes = []
    for ligne in texte.splitlines():
        if "," not in ligne:
            continue
        rubrique, valeur = ligne.split(",", 1)
        if valeur.startswith("'") and valeur.endswith("'") and len(valeur) >= 2:
            valeur = valeur[1:-1]
        lignes.append((rubrique.strip(), valeur))
    return lignes


def brut_masque(texte: str) -> str:
    """Le texte du fichier tel quel, la seule valeur du NIR masquée."""
    sortie = []
    for ligne in texte.splitlines(keepends=True):
        if ligne.startswith(RUBRIQUE_NIR + ","):
            fin = ligne[len(ligne.rstrip("\r\n")):]
            valeur = ligne[len(RUBRIQUE_NIR) + 1:len(ligne) - len(fin)]
            guillemets = valeur.startswith("'") and valeur.endswith("'") and len(valeur) >= 2
            nu = valeur[1:-1] if guillemets else valeur
            masque = f"'{masquer_nir(nu)}'" if guillemets else masquer_nir(nu)
            ligne = f"{RUBRIQUE_NIR},{masque}{fin}"
        sortie.append(ligne)
    return "".join(sortie)


def _rubrique(code: str, valeur: str) -> Dict[str, Optional[str]]:
    affichee = masquer_nir(valeur) if code == RUBRIQUE_NIR else valeur
    return {
        "code": code,
        "libelle": RUBRIQUES.get(code, ""),
        "valeur": affichee,
        "traduction": VALEURS.get(code, {}).get(valeur),
    }


def lire_blocs(texte: str) -> List[Dict[str, Any]]:
    """Les blocs du fichier, dans l'ordre : un bloc s'arrête quand l'identifiant
    change ou que le numéro de rubrique redescend (bloc répété)."""
    blocs: List[Dict[str, Any]] = []
    precedente = ""
    for code, valeur in _lignes(texte):
        bloc = code[:10]
        if not blocs or bloc != precedente[:10] or code <= precedente:
            blocs.append({
                "code": bloc,
                "libelle": BLOCS.get(bloc, ""),
                "partie": PARTIES.get(bloc, "autre"),
                "rubriques": [],
            })
        blocs[-1]["rubriques"].append(_rubrique(code, valeur))
        precedente = code
    return blocs


def apercu(texte: str, *, nature: str, essai: bool) -> Dict[str, Any]:
    """L'aperçu à montrer : les blocs en clair et le texte brut, NIR masqué."""
    return {
        "nature": nature,
        "libelle_nature": LIBELLES_NATURE.get(nature, VALEURS["S20.G00.05.001"].get(nature, nature)),
        "essai": essai,
        "nir_masque": True,
        "blocs": lire_blocs(texte),
        "brut": brut_masque(texte),
    }
