"""Le théorème de la correction à la main sur les 7 sociétés (R-177, R-178, R-180, R-182, R-184).

Pour une société : joue tous ses salariés sur le premier mois calculé après la
reprise (corrections directes et régularisations, valeurs attendues hors du
moteur), au bac à sable, sous piège à écritures ; rejoue un salarié sous chaque
erreur injectée ; écrit un JSON par tranche. Le dernier mois repris lui-même ne
se joue pas : l'écran et la route refusent de le corriger (R-178).

Usage depuis backend/ (rien n'est écrit en base) :

    PYTHONPATH=. .venv/bin/python scripts/theoreme_sept_societes.py jouer "<Société>" <dossier> [i/n]
    PYTHONPATH=. .venv/bin/python scripts/theoreme_sept_societes.py rapport <dossier> <sortie.txt>

Le rapport par société ne porte ni nom, ni NIR, ni IBAN : identifiants courts seulement.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, "scripts/verification_rgdu")
sys.path.insert(0, "scripts")

SOCIETES = (
    "Colorplast",
    "Comitech Composite",
    "MAJI",
    "Zone 404 Mars",
    "Cartol Industrie",
    "LEWIS",
    "Mont Blanc Composite",
)
#: Écritures tolérées au bac à sable : jamais émises vers la base (lecture seule), listées comme dans le filet.
TABLES_TOLEREES = ("employee_cp_seniority_grants", "salary_advances")


def _ecrire(chemin: Path, contenu: object) -> None:
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def _court(societe: str) -> str:
    return societe.replace(" ", "_")


def _salaries_pour_les_mutants(rapport: list[dict]) -> list[str]:
    """Le plus riche en lignes, un salarié à cotisation en double, puis les suivants : de quoi donner prise à chaque injection."""
    par_salarie: dict[str, set[str]] = {}
    for cas in rapport:
        if cas.get("code") and not cas.get("variante"):
            par_salarie.setdefault(str(cas["salarie"]), set()).add(str(cas["code"]))
    if not par_salarie:
        return []
    ordre = sorted(
        par_salarie,
        key=lambda salarie: (sum("reduction_generale" in code for code in par_salarie[salarie]), len(par_salarie[salarie]), salarie),
        reverse=True,
    )
    doublons = [s for s in ordre if any(c.startswith("cotisation:") and "#" in c for c in par_salarie[s])]
    choisis = [*ordre[:1], *doublons[:1], *ordre[1:4]]
    return list(dict.fromkeys(choisis))


def _mutants_sur_plusieurs(theoreme, company_id: str, salaries: list[str], annee: int, mois: int, mutants: tuple) -> dict:
    """Chaque injection sans effet sur un salarié est rejouée sur le suivant, jusqu'à avoir prise."""
    bilan: dict | None = None
    restants = list(mutants)
    for salarie in salaries:
        print(f"mutants sur {salarie[:8]} : {len(restants)}", flush=True)
        resultat = theoreme.jouer_mutants(company_id, salarie, annee, mois, tuple(restants))
        for detail in resultat["mutants"].values():
            detail["salarie"] = salarie[:8]
        if bilan is None:
            bilan = resultat
        else:
            bilan["mutants"].update(resultat["mutants"])
            bilan["rouges_sans_mutant"] = sorted(set(bilan["rouges_sans_mutant"]) | set(resultat["rouges_sans_mutant"]))
        restants = [m for m in restants if resultat["mutants"][m.nom]["verdict"] == "sans effet"]
        if not restants:
            break
    return bilan or {"erreur": "aucun salarié joué : mutants non joués"}


def _jouer(societe: str, dossier: Path, tranche: tuple[int, int]) -> int:
    import postgrest._sync.client as _pc  # noqa: PLC0415

    import theoreme_correction_a_la_main as theoreme  # noqa: PLC0415 — pose le piège à l'import
    from piege import ECRITURES, EcritureInterdite  # noqa: PLC0415
    from theoreme_mutants import MUTANTS  # noqa: PLC0415

    def _rpc_interdit(self, fn, *a, **k):  # noqa: ARG001
        ECRITURES.append(f"rpc {fn}")
        raise EcritureInterdite(f"rpc interdit : {fn}")

    _pc.SyncPostgrestClient.rpc = _rpc_interdit
    from app.shared.reprise_paie import lire_bascule  # noqa: PLC0415

    company = theoreme.supabase.table("companies").select("id").eq("company_name", societe).single().execute().data
    bascule = lire_bascule(company["id"], stricte=True)
    if bascule is None:
        print(f"{societe} : pas de reprise, rien à prouver", flush=True)
        return 2
    annee, mois = bascule.premier_mois_calcule
    print(f"{societe} : dernier mois repris {bascule.mois:02d}/{bascule.annee}, joué {mois:02d}/{annee}", flush=True)
    numero, tranches = tranche
    sortie = dossier / f"cas-{_court(societe)}-{numero}.json"
    code = theoreme.main(societe, annee, mois, str(sortie), "tout", tranche)
    resume: dict = {
        "societe": societe,
        "annee": annee,
        "mois": mois,
        "tranche": list(tranche),
        "code": code,
        "fiches": len(theoreme.supabase.table("employees").select("id").eq("company_id", company["id"]).execute().data),
        "ecritures": [e for e in ECRITURES if not any(e.endswith(f" {t}") for t in TABLES_TOLEREES)],
        "ecritures_tolerees": [e for e in ECRITURES if any(e.endswith(f" {t}") for t in TABLES_TOLEREES)],
    }
    if numero == 0:
        rapport = json.loads(sortie.read_text(encoding="utf-8"))
        salaries = _salaries_pour_les_mutants(rapport)
        if not salaries:
            resume["mutants"] = {"erreur": "aucun salarié joué : mutants non joués"}
        else:
            resume["mutants"] = _mutants_sur_plusieurs(theoreme, company["id"], salaries, annee, mois, MUTANTS)
            resume["ecritures"] += [e for e in ECRITURES if not any(e.endswith(f" {t}") for t in TABLES_TOLEREES) and e not in resume["ecritures"]]
    _ecrire(dossier / f"resume-{_court(societe)}-{numero}.json", resume)
    print(f"{societe} tranche {numero}/{tranches} : code {code}, écritures {len(resume['ecritures'])}", flush=True)
    return code


def _familles(code: str) -> str:
    return ":".join(code.split("#", 1)[0].split(":")[:2])


#: Les constats à valeur attendue calculée hors du moteur, sur une correction de gain.
CONSTATS_ATTENDUS = (
    "brut_attendu",
    "cotisations_attendues",
    "net_imposable_attendu",
    "impot_attendu",
    "net_attendu",
    "reduction_suit",
    "dsn_assiettes",
)


def _couverture_des_attendus(joues: list[dict]) -> str:
    """Combien de corrections de gain ont vraiment eu leur valeur attendue, et combien n'étaient pas calculables."""
    gains = [c for c in joues if str(c.get("code") or "").startswith("brut:") and not c.get("variante")]
    morceaux = []
    for constat in CONSTATS_ATTENDUS:
        verifies = sum(1 for c in gains if c.get(constat) is True)
        rouges = sum(1 for c in gains if c.get(constat) is False)
        morceaux.append(f"{constat} {verifies}/{len(gains)}" + (f" ({rouges} rouges)" if rouges else ""))
    return "Valeurs attendues vérifiées sur les corrections de gain (le reste : non calculable sur ce bulletin) : " + ", ".join(morceaux) + "."


#: Ce que ce passage ne prouve pas : à garder dans chaque rapport.
LIMITES = (
    "== Ce que ce passage ne prouve pas",
    "- Route réelle, écriture en base, verrous, restauration : joués sur base en mémoire seulement (test_theoreme_chemin_complet) ; pas de base jetable.",
    "- Écran : aucun parcours e2e joué ici.",
    "- Forfait jours et deux contrats le même mois : pas de scénario dédié ; un forfait jours n'est joué que s'il figure parmi les salariés du mois.",
    "- Mois suivants : un seul mois après la correction (M+1) ; ni décembre → janvier, ni chaînes longues.",
    "- DSN : blocs 78 et 81 issus du mapping ; bloc 50/51 et DSN-VAL non joués sur ces bulletins (DSN complète : test unitaire seulement).",
    "- OD : ligne et résidu du bulletin, sans les saisies du salarié ; `controler()` complet : test unitaire seulement.",
    "- Réduction générale : l'oracle accepte l'un ou l'autre des deux Tdelta (moins de 50 / 50 et plus), l'effectif n'est pas relu.",
    "- Valeurs attendues : la précarité, l'IFM et l'indemnité compensatrice qui suivent un gain sont prises au moteur ; l'assiette CSG hors cas courant (apprentis, régimes particuliers) n'est pas recalculée.",
    "- Variantes zéro, grande et négative : pose, copies, cumuls, résidu, revue ; pas de valeur attendue ligne à ligne.",
    "- Octobre : mois encore peu saisi, d'où les familles absentes des bulletins réels (absences, heures complémentaires, nuit…) ; elles ne sont couvertes que par un petit moteur en mémoire, pas par le moteur réel.",
    "- Mutants : erreurs injectées sur le résultat du calcul, pas dans le code du moteur.",
)


def rapport_texte(dossier: Path) -> str:
    """Le rapport par société, sans nom de salarié. Le JSON détaillé reste hors du dépôt."""
    from app.modules.payroll.engine.codes_des_lignes import _MOTIFS_DE_GAIN  # noqa: PLC0415 — import tardif : `rapport` tourne sans base.

    lignes: list[str] = []
    verts = True
    familles_vues: set[str] = set()
    blocs_vus: set[str] = set()
    for societe in SOCIETES:
        resumes = sorted(dossier.glob(f"resume-{_court(societe)}-*.json"))
        cas_fichiers = sorted(dossier.glob(f"cas-{_court(societe)}-*.json"))
        if not resumes or not cas_fichiers:
            lignes += [f"== {societe} : NON JOUÉ (aucun résultat)", ""]
            verts = False
            continue
        cas: list[dict] = []
        for chemin in cas_fichiers:
            cas += json.loads(chemin.read_text(encoding="utf-8"))
        resume0 = json.loads(resumes[0].read_text(encoding="utf-8"))
        ecritures = [e for chemin in resumes for e in json.loads(chemin.read_text(encoding="utf-8"))["ecritures"]]
        reels = [c for c in cas if not c.get("information")]
        sautes = [c for c in reels if c.get("saute")]
        joues = [c for c in reels if not c.get("saute")]
        echecs = [c for c in joues if not c.get("ok")]
        salaries = sorted({str(c["salarie"])[:8] for c in reels})
        sautes_salaries = sorted({str(c["salarie"])[:8] for c in sautes})
        familles = Counter(_familles(str(c["code"])) for c in joues if c.get("code") and not c.get("variante"))
        familles_vues |= {f for f in familles if f.startswith("brut:")}
        defauts = Counter(k for c in joues for k, v in c.items() if k.startswith("defaut_connu") and v)
        variantes = Counter(str(c.get("variante")) for c in joues if c.get("variante"))
        blocs = Counter(b for c in cas if c.get("cas") == "blocs à la source" for b in c.get("blocs") or [])
        blocs_vus |= set(blocs)
        natures = Counter(
            n for c in echecs for n in (c.get("echecs") or [c.get("cas") or ("refus" if c.get("refus") else "?")])
        )
        causes = Counter(cause for _, cause in {(c["salarie"], str(c["cause"])) for c in sautes if "cause" in c})
        ligne_sautes = ", ".join(sautes_salaries) if sautes_salaries else "aucun"
        if causes:
            ligne_sautes += " ; " + ", ".join(f"{cause} : {n}" for cause, n in causes.items())
        lignes += [
            f"== {societe} : {resume0['mois']:02d}/{resume0['annee']} (premier mois calculé)",
            f"Fiches {resume0.get('fiches')}, présents dans le mois et lus {len(salaries)}, sautés {len(sautes_salaries)} ({ligne_sautes}). "
            f"Cas joués {len(joues)}, échecs {len(echecs)}{' ' + str(dict(natures)) if echecs else ''}.",
            f"Écritures en base (hors tables tolérées) : {len(ecritures)}.",
            f"Variantes de valeur jouées : {dict(variantes)}.",
            "Familles de ligne jouées : " + ", ".join(f"{f} ({n})" for f, n in sorted(familles.items())),
            "Blocs à la source vus : " + (", ".join(f"{b} ({n})" for b, n in sorted(blocs.items())) or "aucun"),
            *([f"Défauts connus rencontrés : {dict(defauts)}."] if defauts else []),
            _couverture_des_attendus(joues),
        ]
        if not echecs and not ecritures and joues:
            pass
        else:
            verts = False
        mutants = resume0.get("mutants") or {}
        if "mutants" not in mutants:
            lignes += [f"Mutants : {mutants}", ""]
            verts = False
            continue
        resultats = mutants["mutants"]
        vus = sum(1 for m in resultats.values() if m["verdict"] == "vu")
        sans_effet = {n: m for n, m in resultats.items() if m["verdict"] == "sans effet"}
        non_vus = [n for n, m in resultats.items() if m["verdict"] == "NON VU"]
        lignes.append(
            f"Mutants (salarié principal {mutants['salarie']}) : {vus}/{len(resultats)} vus, {len(sans_effet)} sans effet"
            + (" (" + " ; ".join(f"{n} : {m.get('sans_effet_si') or '?'}" for n, m in sans_effet.items()) + ")" if sans_effet else "")
            + (f" ; NON VUS : {non_vus}" if non_vus else "")
            + (f" ; déjà rouge sans mutant : {mutants['rouges_sans_mutant']}" if mutants.get("rouges_sans_mutant") else "")
        )
        for nom, m in resultats.items():
            lignes.append(f"  {nom} — {m['quoi']} : {m['verdict']} sur {m.get('salarie', '?')} ({', '.join(m['rouges'][:6])})")
        if non_vus:
            verts = False
        revue = mutants.get("revue") or {}
        vues = {n: r for n, r in revue.items() if r}
        pas_vues = [n for n, r in revue.items() if r == []]
        sans_objet = [n for n, r in revue.items() if r is None]
        lignes.append(
            "Revue, erreur posée sur un bulletin juste (R-170) : vues "
            + (", ".join(f"{n} ({'+'.join(r)})" for n, r in vues.items()) or "aucune")
            + (f" ; PAS VUES : {', '.join(pas_vues)}" if pas_vues else "")
            + (f" ; sans objet sur ce bulletin : {', '.join(sans_objet)}" if sans_objet else "")
        )
        lignes.append("")
    inventaire = {f"brut:{f}" for f, _ in _MOTIFS_DE_GAIN} | {"brut:arret", "brut:indemnite_sortie", "brut:prime"}
    jamais = sorted(inventaire - familles_vues)
    lignes += [
        "== Couverture de l'inventaire (R-182, R-184), sur les 7 sociétés",
        "Familles de gain portées par aucun bulletin réel de ce mois : "
        + (", ".join(jamais) or "aucune")
        + ". Elles se corrigent dans test_theoreme_familles.py (cas synthétiques, petit moteur en mémoire).",
        "Blocs hors inventaire vus sur un bulletin réel : " + (", ".join(sorted(blocs_vus)) or "aucun")
        + " ; les autres ne sont portés par aucune fiche de ce mois (test_theoreme_familles.py, source exigée par bloc).",
        "",
    ]
    lignes += [*LIMITES, ""]
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False).stdout.strip()
    entete = [
        f"Preuve du théorème de la correction à la main sur 7 sociétés — {time.strftime('%d/%m/%Y %H:%M')} — commit {commit}",
        "Bac à sable sous piège à écritures : rien n'est écrit en base. Un mois repris de l'ancien logiciel ne se",
        "corrige pas à l'écran (R-178) : on joue le premier mois calculé après la reprise, cumuls de reprise en entrée.",
        f"Verdict global : {'VERT' if verts else 'ROUGE'}.",
        "",
    ]
    return "\n".join(entete + lignes)


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[1] == "jouer":
        societe, dossier = argv[2], Path(argv[3])
        dossier.mkdir(parents=True, exist_ok=True)
        tranche = tuple(int(x) for x in argv[4].split("/")) if len(argv) > 4 else (0, 1)
        return _jouer(societe, dossier, tranche)  # type: ignore[arg-type]
    if len(argv) >= 4 and argv[1] == "rapport":
        Path(argv[3]).write_text(rapport_texte(Path(argv[2])), encoding="utf-8")
        print("écrit", argv[3], flush=True)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
