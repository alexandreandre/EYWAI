"""Complète les fiches salariés dont la valeur juste est connue, sans toucher à la paie.

Lot du 27/10 (écrit) : l'usineur S.B. (Comitech) portait « 9999 », que le
formulaire refuse ; il a reçu 623f, le PCS-ESE de son collègue au même emploi.

Lot du 30/10 (écrit), pour la DSN d'octobre : la revue pré-paie signale les fiches que
DSN-VAL refuserait (« Fiche à compléter (DSN) »). Les valeurs posées ici se
lisent dans les DSN Quadra de janvier à juillet 2026, sans exception :
- PCS-ESE 674a pour les CDD de production de Colorplast et de Comitech ;
- motif de recours 02 (accroissement temporaire d'activité) pour tous les CDD
  des deux sociétés.
Le PCS se range dans la classification, le motif sous
`specificites_paie.dsn_reprise.motif_recours`, là où le formulaire de la fiche
et la reprise DSN les écrivent. Aucun calcul de bulletin ne lit le PCS ; le
moteur ne lit le motif que pour écarter la prime de précarité, et 02 ne
l'écarte pas (engine/motif_recours.py). Tous les bulletins de ces fiches sont
repris de Quadra (« importe ») : aucun ne passe « À recalculer ».

Lot du 31/10 : les trois fiches restées sans source le 30/10, et ce que la DSN
d'octobre doit reprendre de Quadra pour continuer ses contrats au lieu d'en
ouvrir de nouveaux. Chaque valeur se lit à l'exécution dans la DSN Quadra de
septembre 2026 de la société (Drive, déposée le 30/10 ; rangée dans
data/<société>/dsn/2026-09.dsn, hors git : aucune donnée personnelle n'entre
dans le dépôt public), le salarié retrouvé par son NIR :
- date de naissance de X.P. et de F.A. (Colorplast, S21.G00.30.006) ;
- apprenti S.V. (Comitech), dans la reprise DSN de la fiche : fin prévisionnelle
  (S21.G00.40.010), diplôme préparé (S21.G00.30.025) et début du contrat
  d'apprentissage (S21.G00.40.001), commencé chez Quadra après un CDD alors
  que la fiche n'a qu'un contrat ;
- numéro de contrat de D.G. et de T.G. (Comitech, S21.G00.40.009), embauchés
  après le chargement de la reprise DSN du 05/10 (00000 par défaut) ;
- prénoms de D.G. (S21.G00.30.004), « dans l'ordre de l'état civil » (cahier
  technique, § 4.4.8) : la fiche n'a que le premier. Le rapprochement des
  feuilles de pointage accepte un prénom contenu dans celui de la fiche.
Un contrat s'identifie par sa date de début et son numéro (cahier technique
2026.1, § 2.1.2.3.2). Aucun calcul de ces bulletins ne lit ces valeurs : la date
de naissance ne sert qu'au contrôle du salaire d'apprenti et à l'âge de la
retraite, la reprise DSN et le numéro de contrat ne sont lus que par la DSN.

Depuis backend/ :

    PYTHONPATH=. python -m scripts.completer_fiches_formulaire
        Simulation : rien n'est écrit (piège à écritures posé). Affiche
        l'avant/après de chaque clé et l'empreinte des fiches.

    PYTHONPATH=. python -m scripts.completer_fiches_formulaire --ecrire --empreinte <sha>
        Écrit, seulement si l'empreinte est celle de la simulation (la fiche et
        la liste de ses bulletins n'ont pas changé depuis). Sauvegarde les fiches
        en JSON dans data/_sauvegardes/ avant d'écrire, puis relit et contrôle.

Seules les clés listées dans CORRECTIONS sont modifiées, et seulement sur ces
fiches ; une valeur d'avant différente de celle attendue arrête tout.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

#: Même règle que le formulaire (`FORMAT_PCS_ESE`, frontend/src/constants/dsnFiche.ts).
FORMAT_PCS_ESE = re.compile(r"^\d{3}[a-z]$")

#: Les codes que le formulaire propose (`MOTIFS_RECOURS_CDD`, même fichier).
MOTIFS_RECOURS_CDD = frozenset(
    {"01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "12", "13"}
)

#: Les niveaux que le formulaire propose (`NIVEAUX_DIPLOME_PREPARE`, même fichier).
NIVEAUX_DIPLOME_PREPARE = frozenset({"03", "04", "05", "06", "07", "08"})

#: Les colonnes de la fiche que le script peut corriger. La date de naissance
#: est une colonne simple : son chemin est vide.
COLONNES = frozenset(
    {"classification_conventionnelle", "specificites_paie", "date_naissance", "first_name"}
)
#: Les valeurs qui sont des dates (AAAA-MM-JJ), comme le formulaire les écrit.
_DATES = frozenset({
    ("date_naissance", ()),
    ("specificites_paie", ("dsn_reprise", "date_fin_contrat")),
    ("specificites_paie", ("dsn_reprise", "date_debut_contrat")),
})
#: Numéro de contrat DSN (S21.G00.40.009), cinq chiffres comme ceux de Quadra.
FORMAT_NUMERO_CONTRAT = re.compile(r"^\d{5}$")

COLORPLAST = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
COMITECH = "12cd8c71-da13-43f9-9151-475c4d5e8812"


@dataclass(frozen=True)
class Correction:
    employee_id: str
    initiales: str
    societe: str
    #: Colonne de la fiche, et chemin de la clé corrigée dans son JSON.
    colonne: str
    chemin: tuple[str, ...]
    avant: Any
    apres: Any
    source: str


_SOURCE_PCS_COLORPLAST = (
    "PCS-ESE du collègue en CDI au même emploi « Préparateur peintre », et de tous "
    "les CDD de Colorplast déclarés par Quadra (S21.G00.40.004, DSN de mars à juillet 2026)."
)
_SOURCE_PCS_COMITECH = (
    "PCS-ESE des ouvriers de production de Comitech déclarés par Quadra (opérateurs "
    "polyvalents, S21.G00.40.004, DSN de janvier à juillet 2026) ; le seul autre agent "
    "de production, parti le 24/07, portait « 9999 », que le formulaire refuse."
)
_SOURCE_MOTIF = (
    "Motif de tous les CDD déclarés par Quadra chez Colorplast et Comitech "
    "(S21.G00.40.021 = 02, DSN de janvier à juillet 2026, sans exception)."
)


def _pcs(employee_id: str, initiales: str, societe: str, source: str) -> Correction:
    return Correction(employee_id, initiales, societe, "classification_conventionnelle",
                      ("pcs",), None, "674a", source)


def _motif(employee_id: str, initiales: str, societe: str) -> Correction:
    return Correction(employee_id, initiales, societe, "specificites_paie",
                      ("dsn_reprise", "motif_recours"), None, "02", _SOURCE_MOTIF)


@dataclass(frozen=True)
class LueEnDsn:
    """Valeur d'après lue dans la DSN Quadra de septembre de la société."""

    rubrique: str
    #: « date » (JJMMAAAA → AAAA-MM-JJ), « code » (telle quelle), « prenoms ».
    forme: str


#: La valeur d'avant attendue est le premier des prénoms lus dans la DSN.
PREMIER_PRENOM = "premier prénom de la DSN"

DSN_DE_SEPTEMBRE = {COLORPLAST: "colorplast/dsn/2026-09.dsn", COMITECH: "comitech/dsn/2026-09.dsn"}
_SOURCE_DSN = "DSN Quadra de septembre 2026 de la société, rubrique {rubrique}"

_X_P, _F_A = "d9133249-b420-4b7a-81ef-015fc0e7dc71", "bc90c7bd-b545-4816-965d-a821fb4fc514"
_S_V, _D_G = "b5c25289-c564-4ff8-8906-becb1ae4a88c", "01ea5d95-fda3-46b7-9e22-280bdf7598ca"
_T_G = "adf1ab30-65a7-4b65-9999-7d64528818a1"


def _lue(employee_id, initiales, societe, colonne, chemin, rubrique, forme, avant=None):
    return Correction(employee_id, initiales, societe, colonne, chemin, avant,
                      LueEnDsn(rubrique, forme), _SOURCE_DSN.format(rubrique=rubrique))


_REPRISE = "specificites_paie"
_CLASSIFICATION = "classification_conventionnelle"

#: Lot du 31/10 (les lots écrits restent dans l'historique de git).
CORRECTIONS: tuple[Correction, ...] = (
    _lue(_X_P, "X.P.", COLORPLAST, "date_naissance", (), "S21.G00.30.006", "date"),
    _lue(_F_A, "F.A.", COLORPLAST, "date_naissance", (), "S21.G00.30.006", "date"),
    _lue(_S_V, "S.V.", COMITECH, _REPRISE, ("dsn_reprise", "date_fin_contrat"), "S21.G00.40.010", "date"),
    _lue(_S_V, "S.V.", COMITECH, _REPRISE, ("dsn_reprise", "niveau_diplome_prepare"),
         "S21.G00.30.025", "code"),
    _lue(_S_V, "S.V.", COMITECH, _REPRISE, ("dsn_reprise", "date_debut_contrat"), "S21.G00.40.001", "date"),
    _lue(_D_G, "D.G.", COMITECH, _CLASSIFICATION, ("numero_contrat_dsn",), "S21.G00.40.009", "code"),
    _lue(_T_G, "T.G.", COMITECH, _CLASSIFICATION, ("numero_contrat_dsn",), "S21.G00.40.009", "code"),
    _lue(_D_G, "D.G.", COMITECH, "first_name", (), "S21.G00.30.004", "prenoms", avant=PREMIER_PRENOM),
)


def lire_dsn(chemin: Path) -> dict[str, dict[str, Any]]:
    """Chaque individu de la DSN par NIR (13 caractères) : ses rubriques 30, et
    les rubriques 40 de chacun de ses contrats."""
    individus: dict[str, dict[str, Any]] = {}
    courant: dict[str, Any] | None = None
    for ligne in chemin.read_text(encoding="latin-1").splitlines():
        if "," not in ligne:
            continue
        rubrique, valeur = ligne.split(",", 1)
        valeur = valeur.strip().strip("'")
        if rubrique == "S21.G00.30.001":
            courant = individus.setdefault(valeur[:13], {"contrats": []})
        elif courant is None:
            continue
        elif rubrique.startswith("S21.G00.30."):
            courant.setdefault(rubrique, valeur)
        elif rubrique == "S21.G00.40.001":
            courant["contrats"].append({rubrique: valeur})
        elif rubrique.startswith("S21.G00.40.") and courant["contrats"]:
            courant["contrats"][-1].setdefault(rubrique, valeur)
    return individus


def _mise_en_forme(valeur: str, forme: str) -> str:
    if forme == "date":
        return datetime.strptime(valeur, "%d%m%Y").date().isoformat()
    if forme == "prenoms":
        return " ".join("-".join(p.capitalize() for p in mot.split("-")) for mot in valeur.split())
    return valeur


def _sans_accents_ni_casse(texte: str) -> str:
    import unicodedata

    texte = unicodedata.normalize("NFKD", texte or "")
    return " ".join("".join(c for c in texte if not unicodedata.combining(c)).lower().split())


def resoudre(c: Correction, fiche: dict[str, Any], individus: dict[str, dict[str, Any]]) -> Correction:
    """La correction, la valeur d'après lue dans la DSN ; arrête tout si le
    salarié n'y est pas, si la rubrique manque ou si son contrat est ambigu."""
    if not isinstance(c.apres, LueEnDsn):
        return c
    nir = str(fiche.get("nir") or "").replace(" ", "")[:13]
    individu = individus.get(nir)
    if not nir or individu is None:
        raise SystemExit(f"{c.initiales} : absent de la DSN de septembre, rien n'est écrit.")
    rubrique = c.apres.rubrique
    if rubrique.startswith("S21.G00.40."):
        if len(individu["contrats"]) != 1:
            raise SystemExit(f"{c.initiales} : {len(individu['contrats'])} contrats en septembre, rien n'est écrit.")
        brute = individu["contrats"][0].get(rubrique)
    else:
        brute = individu.get(rubrique)
    if not brute:
        raise SystemExit(f"{c.initiales} : {rubrique} absente de la DSN de septembre, rien n'est écrit.")
    apres = _mise_en_forme(brute, c.apres.forme)
    avant = c.avant
    if avant == PREMIER_PRENOM:
        avant = fiche.get(c.colonne)
        if _sans_accents_ni_casse(str(avant)) != _sans_accents_ni_casse(apres).split(" ")[0]:
            raise SystemExit(f"{c.initiales} : le prénom de la fiche n'est pas le premier de la DSN, rien n'est écrit.")
    return Correction(c.employee_id, c.initiales, c.societe, c.colonne, c.chemin, avant, apres, c.source)


def dossier_sauvegardes() -> Path:
    """data/_sauvegardes du dépôt principal (hors git), même depuis un worktree."""
    commun = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=Path(__file__).resolve().parent,
        text=True,
    ).strip()
    return Path(commun).parent / "data" / "_sauvegardes"


def lire_fiche(employee_id: str) -> dict[str, Any]:
    from app.core.database import supabase

    rows = supabase.table("employees").select("*").eq("id", employee_id).execute().data or []
    if len(rows) != 1:
        raise SystemExit(f"Fiche {employee_id} introuvable (ou en double) : rien n'est écrit.")
    return rows[0]


def lire_bulletins(employee_id: str) -> list[dict[str, Any]]:
    from app.core.database import supabase

    rows = (
        supabase.table("payslips")
        .select("id, year, month, status, origine, updated_at")
        .eq("employee_id", employee_id)
        .execute()
        .data
        or []
    )
    return sorted(rows, key=lambda r: (r["year"], r["month"], r["id"]))


def empreinte(etats: dict[str, dict[str, Any]]) -> str:
    """Hash de chaque fiche entière et de la liste de ses bulletins."""
    texte = json.dumps(etats, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def _valider(c: Correction) -> None:
    if c.colonne not in COLONNES:
        raise SystemExit(f"{c.initiales} : colonne {c.colonne} hors du formulaire de la fiche, rien n'est écrit.")
    if c.chemin == ("pcs",) and not FORMAT_PCS_ESE.match(str(c.apres)):
        raise SystemExit(f"{c.initiales} : PCS {c.apres!r} refusé par le formulaire, rien n'est écrit.")
    if c.chemin[-1:] == ("motif_recours",) and c.apres not in MOTIFS_RECOURS_CDD:
        raise SystemExit(f"{c.initiales} : motif {c.apres!r} hors de la liste DSN, rien n'est écrit.")
    if c.chemin[-1:] == ("niveau_diplome_prepare",) and c.apres not in NIVEAUX_DIPLOME_PREPARE:
        raise SystemExit(f"{c.initiales} : diplôme {c.apres!r} hors de la liste DSN, rien n'est écrit.")
    if c.chemin == ("numero_contrat_dsn",) and not FORMAT_NUMERO_CONTRAT.match(str(c.apres)):
        raise SystemExit(f"{c.initiales} : numéro de contrat {c.apres!r} refusé, rien n'est écrit.")
    if (c.colonne, c.chemin) in _DATES:
        try:
            date.fromisoformat(str(c.apres))
        except ValueError:
            raise SystemExit(f"{c.initiales} : date {c.apres!r} illisible, rien n'est écrit.") from None
    elif not c.chemin and not (c.colonne == "first_name" and str(c.apres).strip()):
        raise SystemExit(f"{c.initiales} : {c.colonne} sans chemin, rien n'est écrit.")


def _lire(valeur: Any, chemin: tuple[str, ...]) -> Any:
    for cle in chemin:
        if not isinstance(valeur, dict):
            return None
        valeur = valeur.get(cle)
    return valeur


def _feuilles(valeur: Any, prefixe: tuple[str, ...] = ()) -> dict[tuple[str, ...], Any]:
    """Chaque valeur du JSON qui n'est pas un objet, avec son chemin."""
    if not isinstance(valeur, dict):
        return {prefixe: valeur}
    feuilles: dict[tuple[str, ...], Any] = {}
    for cle, sous in valeur.items():
        feuilles.update(_feuilles(sous, prefixe + (cle,)))
    return feuilles


def colonnes_corrigees(fiche: dict[str, Any], corrections: list[Correction]) -> dict[str, Any]:
    """Les colonnes de la fiche, seules les clés corrigées changées.

    Arrête tout si une valeur d'avant n'est pas celle attendue, si une valeur
    corrigée ne passe pas le formulaire, ou si une autre clé changerait.
    """
    nouvelles: dict[str, Any] = {}
    for c in corrections:
        _valider(c)
        origine = fiche.get(c.colonne)
        if not c.chemin:
            if origine != c.avant:
                raise SystemExit(
                    f"{c.initiales} : {c.colonne} vaut {origine!r}, {c.avant!r} attendu — "
                    "la fiche a changé, rien n'est écrit."
                )
            nouvelles[c.colonne] = c.apres
            continue
        if origine is not None and not isinstance(origine, dict):
            raise SystemExit(f"{c.initiales} : {c.colonne} n'est pas un objet, rien n'est écrit.")
        if _lire(origine, c.chemin) != c.avant:
            raise SystemExit(
                f"{c.initiales} : {c.colonne}.{'.'.join(c.chemin)} vaut {_lire(origine, c.chemin)!r}, "
                f"{c.avant!r} attendu — la fiche a changé, rien n'est écrit."
            )
        noeud = nouvelles.setdefault(c.colonne, copy.deepcopy(origine or {}))
        for cle in c.chemin[:-1]:
            noeud = noeud.setdefault(cle, {})
            if not isinstance(noeud, dict):
                raise SystemExit(f"{c.initiales} : {c.colonne}.{cle} n'est pas un objet, rien n'est écrit.")
        noeud[c.chemin[-1]] = c.apres
    for colonne, nouvelle in nouvelles.items():
        if not isinstance(nouvelle, dict):
            continue
        avant, apres = _feuilles(fiche.get(colonne) or {}), _feuilles(nouvelle)
        changees = {p for p in set(avant) | set(apres) if avant.get(p) != apres.get(p)}
        attendues = {c.chemin for c in corrections if c.colonne == colonne}
        if changees != attendues:
            raise SystemExit(f"Clés changées {sorted(changees)} au lieu de {sorted(attendues)} : rien n'est écrit.")
    return nouvelles


def par_fiche(corrections: tuple[Correction, ...] = CORRECTIONS) -> dict[str, list[Correction]]:
    groupes: dict[str, list[Correction]] = {}
    for c in corrections:
        groupes.setdefault(c.employee_id, []).append(c)
    return groupes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ecrire", action="store_true", help="écrire (sinon simulation)")
    parser.add_argument("--empreinte", help="empreinte affichée par la simulation (obligatoire avec --ecrire)")
    args = parser.parse_args()

    if args.ecrire and not args.empreinte:
        parser.error("--ecrire demande --empreinte <sha> : lancez d'abord la simulation.")
    if not args.ecrire:
        from scripts.verification_rgdu import piege

        piege.poser_le_piege()

    fiches = {eid: lire_fiche(eid) for eid in par_fiche()}
    dossier_data = dossier_sauvegardes().parent
    individus = {societe: lire_dsn(dossier_data / chemin) for societe, chemin in DSN_DE_SEPTEMBRE.items()}
    groupes = par_fiche(tuple(
        resoudre(c, fiches[c.employee_id], individus.get(c.societe, {})) for c in CORRECTIONS
    ))
    etats = {eid: {"fiche": fiches[eid], "bulletins": lire_bulletins(eid)} for eid in groupes}
    actuelle = empreinte(etats)

    plan: dict[str, dict[str, Any]] = {}
    for eid, corrections in groupes.items():
        fiche = fiches[eid]
        if fiche.get("company_id") != corrections[0].societe:
            raise SystemExit(f"{corrections[0].initiales} : société inattendue, rien n'est écrit.")
        plan[eid] = colonnes_corrigees(fiche, corrections)
        calcules = [b for b in etats[eid]["bulletins"] if (b.get("origine") or "calcule") != "importe"]
        for c in corrections:
            cle = ".".join((c.colonne, *c.chemin))
            print(f"{c.initiales} {cle} : {c.avant!r} -> {c.apres!r}")
            print(f"    source : {c.source}")
        print(
            f"    bulletins : {len(etats[eid]['bulletins'])}, dont {len(calcules)} calculés par Martine"
            + (" — ils passeront « À recalculer » (montants inchangés)" if calcules else "")
        )
    print(f"empreinte : {actuelle}")

    if not args.ecrire:
        print("Simulation : rien n'a été écrit. Pour écrire :")
        print(f"    PYTHONPATH=. python -m scripts.completer_fiches_formulaire --ecrire --empreinte {actuelle}")
        return 0

    if args.empreinte != actuelle:
        raise SystemExit(
            "Une fiche ou ses bulletins ont changé depuis la simulation (empreinte différente) : "
            "rien n'est écrit. Relancez la simulation et relisez l'avant/après."
        )

    dossier = dossier_sauvegardes()
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / f"fiches-formulaire-{datetime.now().astimezone():%Y%m%d-%H%M%S}.json"
    fichier.write_text(json.dumps(etats, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"sauvegarde : {fichier}")

    from app.core.database import supabase

    for eid, colonnes in plan.items():
        fiche = fiches[eid]
        initiales = groupes[eid][0].initiales
        reponse = (
            supabase.table("employees")
            .update(colonnes)
            .eq("id", eid)
            .eq("updated_at", fiche["updated_at"])
            .execute()
        )
        if len(reponse.data or []) != 1:
            raise SystemExit(f"{initiales} : fiche modifiée entre la lecture et l'écriture, arrêt.")
        relue = lire_fiche(eid)
        ignorees = set(colonnes) | {"updated_at"}
        attendu = {k: v for k, v in fiche.items() if k not in ignorees}
        obtenu = {k: v for k, v in relue.items() if k not in ignorees}
        if any(relue.get(k) != v for k, v in colonnes.items()) or attendu != obtenu:
            raise SystemExit(f"{initiales} : relecture différente de l'attendu, voir {fichier}.")
        print(f"{initiales} : écrit et relu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
