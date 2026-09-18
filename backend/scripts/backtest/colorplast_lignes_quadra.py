"""Lecture ligne à ligne d'un bulletin Quadra (PDF du cabinet), colonne par colonne.

`pdftotext -layout` conserve l'alignement : chaque nombre est aligné à droite
sous l'en-tête de sa colonne — Base, Taux salarial, Montant salarial (deux
positions : retenues et cotisations à gauche, gains à droite), Mt patronal —
et la colonne de droite (SMIC, plafond, heures, cumuls) est au-delà. Chaque
page porte son propre en-tête ; les positions sont relevées page par page.

Un bulletin tient sur une ou deux pages, repérées par « Matricule : X ».

Usage : python -m scripts.backtest.colorplast_lignes_quadra 2026 6 [BUGNY]
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

RACINE_DATA = Path(__file__).resolve().parents[3] / "data"

NOMBRE = re.compile(r"-?\d+\.\d{2,4}")
MATRICULE = re.compile(r"Matricule\s*:\s*([A-Z]+)")
CODE = re.compile(r"^\s{0,4}([A-Z][A-Z0-9]{2,3})\s+(\S.*)$")

#: Étiquettes de la colonne de droite (libellé → clé), dans l'ordre du bulletin.
DROITE = {
    "SMIC Horaire": "smic", "Plafond Sécu": "plafond", "Heures période": "heures_periode",
    "Cumul heures": "cumul_heures", "Cumul h.sup": "cumul_hs", "Solde rep.remp.": "solde_rep_remp",
    "Solde rep.récup.": "solde_rep_recup", "Bases": "cumul_bases", "Bruts": "cumul_bruts",
    "Hrs majorées": "cumul_hrs_majorees", "Cotis. employeur": "allegement_mois",
    "Versé employeur": "verse_employeur",
}


@dataclass
class Ligne:
    code: str | None
    libelle: str
    base: float | None = None
    taux: float | None = None
    montant_sal: float | None = None   # retenue ou cotisation salariale (sous-colonne gauche)
    gain: float | None = None          # gain (sous-colonne droite)
    montant_pat: float | None = None
    section: str | None = None
    page: int = 0

    def valeurs(self) -> dict:
        return {k: v for k, v in (("base", self.base), ("taux", self.taux), ("montant_sal", self.montant_sal),
                                  ("gain", self.gain), ("montant_pat", self.montant_pat)) if v is not None}


@dataclass
class Bulletin:
    matricule: str
    lignes: list = field(default_factory=list)
    droite: dict = field(default_factory=dict)
    net: dict = field(default_factory=dict)
    cp: dict = field(default_factory=dict)
    pages: list = field(default_factory=list)


def _f(s: str) -> float:
    return round(float(s.replace(" ", "")), 4)


def pdf_du_mois(annee: int, mois: int) -> Path:
    dossier = RACINE_DATA / "colorplast" / "bulletins" / f"{annee:04d}-{mois:02d}"
    pdfs = sorted(dossier.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(dossier)
    return pdfs[0]


def pages_texte(pdf: Path) -> list[str]:
    n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout).group(1))
    return [
        subprocess.run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), str(pdf), "-"],
                       capture_output=True, text=True).stdout
        for p in range(1, n + 1)
    ]


def _colonnes(ligne_entete: str) -> dict:
    """Bord droit de chaque colonne, relevé sur la ligne « Rubriques … Mt patronal »."""
    def fin(mot):
        i = ligne_entete.find(mot)
        return i + len(mot) if i >= 0 else None
    return {
        "base": fin("Base"), "taux": fin("Taux salarial"),
        "msal_debut": ligne_entete.find("Montant salarial"), "msal": fin("Montant salarial"),
        "mpat": fin("Mt patronal"),
    }


def _affecter(ligne: str, col: dict) -> tuple[dict, list]:
    """Répartit les nombres d'une ligne entre les colonnes ; renvoie aussi ceux de la colonne de droite.

    Les nombres sont alignés à droite, quelques caractères après le bord droit
    de leur en-tête (mesuré sur les bulletins : +5/+6 pour Base, +2 pour Taux,
    +5/+6 pour un gain, −1 pour Mt patronal) ; les retenues et cotisations
    salariales s'alignent au début de « Montant salarial » (+7).
    """
    valeurs, droite = {}, []
    for m in NOMBRE.finditer(ligne):
        fin = m.end()
        v = _f(m.group(0))
        if fin >= col["mpat"] + 8:
            droite.append(v)
        elif col["mpat"] - 4 <= fin <= col["mpat"] + 2:
            valeurs["montant_pat"] = v
        elif col["msal"] + 3 <= fin <= col["msal"] + 8:
            valeurs["gain"] = v
        elif col["msal_debut"] + 3 <= fin <= col["msal_debut"] + 10:
            valeurs["montant_sal"] = v
        elif col["taux"] - 1 <= fin <= col["taux"] + 4:
            valeurs["taux"] = v
        elif col["base"] + 2 <= fin <= col["base"] + 9:
            valeurs["base"] = v
        else:
            droite.append(v)
    return valeurs, droite


def lire_page(texte: str, numero: int, bulletin: Bulletin) -> None:
    lignes = texte.splitlines()
    col = None
    section = None
    attente_droite: str | None = None
    zone_net = False
    for brut in lignes:
        if "Rubriques" in brut and "Mt patronal" in brut:
            col = _colonnes(brut)
            continue
        m = re.match(r"\s*(Acquis|Total pris|Solde)\s*:\s*([\d.]+)\s*/\s*([\d.]+)\s*/", brut)
        if m:
            bulletin.cp[m.group(1)] = (_f(m.group(2)), _f(m.group(3)))
            continue
        if col is None:
            continue
        # --- colonne de droite : une étiquette, puis sa valeur sur la ligne suivante
        partie_droite = brut[col["mpat"] + 3:] if col["mpat"] else ""
        etiquette = next((cle for lib, cle in DROITE.items() if lib in partie_droite), None)
        if etiquette:
            attente_droite = etiquette
        # --- bloc net (bas de page)
        gauche = brut[: col["mpat"] + 3] if col["mpat"] else brut
        texte_gauche = gauche.strip()
        if texte_gauche.startswith("MONTANT NET SOCIAL"):
            zone_net = True
        if zone_net:
            nombres = [_f(x.group(0)) for x in NOMBRE.finditer(brut)]
            if texte_gauche.startswith("MONTANT NET SOCIAL") and nombres:
                bulletin.net["mns"] = nombres[-1]
            elif texte_gauche.startswith("NET A PAYER AVANT IMPOT") and nombres:
                bulletin.net["net_avant_impot"] = nombres[-1]
            elif texte_gauche.startswith("dont évolution") and nombres:
                bulletin.net["evolution_remuneration"] = nombres[-1]
            elif texte_gauche.startswith("Montant net imposable") and nombres:
                bulletin.net["net_imposable"] = nombres[0]
                if len(nombres) > 1:
                    bulletin.net["net_imposable_cumul"] = nombres[1]
            elif texte_gauche.startswith("Impôt sur le revenu prélevé") and nombres:
                cles = ["pas_base", "pas_taux", "pas_montant", "pas_cumul"]
                for cle, v in zip(cles, nombres):
                    bulletin.net[cle] = v
            elif texte_gauche.startswith("Montant net des heures") and nombres:
                bulletin.net["net_hs_exo"] = nombres[0]
                if len(nombres) > 1:
                    bulletin.net["net_hs_exo_cumul"] = nombres[1]
            elif not texte_gauche and nombres and "net_a_payer" not in bulletin.net and "net_avant_impot" in bulletin.net:
                # « Net à payer au salarié » : la valeur est seule sur sa ligne, à droite
                m2 = list(NOMBRE.finditer(brut))[-1]
                if m2.start() > 60:
                    bulletin.net["net_a_payer"] = _f(m2.group(0))
            if texte_gauche.startswith("Rubriques"):
                zone_net = False
            continue
        # --- rubriques
        valeurs, droite = _affecter(brut, col)
        if attente_droite and droite:
            bulletin.droite[attente_droite] = droite[-1]
            attente_droite = None
        if not texte_gauche or texte_gauche.startswith(("Pour plus d'informations", "Dans votre intérêt", "Convention collective", "matières plastiques", "A défaut de Convention")):
            continue
        code, libelle = None, texte_gauche
        mc = CODE.match(gauche)
        if mc and not NOMBRE.match(mc.group(1)):
            code, libelle = mc.group(1), mc.group(2).strip()
        # retirer les nombres du libellé
        premier = NOMBRE.search(libelle)
        if premier and premier.start() > 3:
            libelle = libelle[: premier.start()].strip()
        elif premier and premier.start() <= 3 and not valeurs:
            libelle = libelle  # ex. « 16,46 H.sup exo… » : mention, pas de valeur
        libelle = re.sub(r"\s{2,}", " ", libelle)
        if code and code.startswith("Q") and not valeurs:
            section = f"{code} {libelle}"
            continue
        bulletin.lignes.append(Ligne(code=code, libelle=libelle, section=section, page=numero, **valeurs))


def lire_bulletins(annee: int, mois: int) -> dict[str, Bulletin]:
    pages = pages_texte(pdf_du_mois(annee, mois))
    bulletins: dict[str, Bulletin] = {}
    for numero, texte in enumerate(pages, 1):
        m = MATRICULE.search(texte)
        if not m:
            continue
        mat = m.group(1)
        b = bulletins.setdefault(mat, Bulletin(matricule=mat))
        b.pages.append(numero)
        lire_page(texte, numero, b)
    return bulletins


def afficher(b: Bulletin) -> None:
    print(f"=== {b.matricule} (pages {b.pages})")
    for lig in b.lignes:
        vals = " ".join(f"{k}={v}" for k, v in (("base", lig.base), ("taux", lig.taux), ("sal", lig.montant_sal), ("gain", lig.gain), ("pat", lig.montant_pat)) if v is not None)
        print(f"  [{(lig.code or ''):4s}] {lig.libelle[:44]:44s} {vals}")
    print("  droite :", b.droite)
    print("  net    :", b.net)
    print("  cp     :", b.cp)


if __name__ == "__main__":
    annee, mois = int(sys.argv[1]), int(sys.argv[2])
    bulletins = lire_bulletins(annee, mois)
    for mat, b in bulletins.items():
        if len(sys.argv) > 3 and mat not in sys.argv[3:]:
            continue
        afficher(b)
