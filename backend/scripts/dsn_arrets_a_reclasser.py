"""Rattrapage des absences rangées à tort par l'import DSN : lecture seule, ou écriture avec --ecrire.

L'ancien import lisait le bloc S21.G00.60 (arrêt de travail) comme une
« suspension » : tout arrêt devenait un congé « sans solde », du dernier jour
travaillé à la fin prévisionnelle, donc un jour trop tôt. Il lisait aussi le
bloc S21.G00.41 (changements contrat) comme un arrêt : chaque changement de
contrat devenait un arrêt maladie d'un jour. Les blocs S21.G00.65 (autres
suspensions : congé sans solde, congé parental, évènement familial) n'étaient
pas importés. Source : cahier technique DSN 2026.1,
https://www.net-entreprises.fr/media/documentation/dsn-cahier-technique-2026.1.pdf
(p. 215, 265-269, 280-283).

Repérage en base : les demandes créées par l'import portent le commentaire
« Import DSN historique » (create_reconciliation_absence) ; les lignes
`dsn_import_items` (absence, committed) gardent le bloc lu (`dsn_block`) et les
jours, et leur lot le nom du fichier DSN. Le fichier lui-même n'est pas en base :
on relit `data/<société>/dsn/AAAA-MM.dsn` avec le nouvel import.

Pour chaque demande importée : le bloc d'origine, ce qu'elle deviendrait (type,
type d'arrêt, dates), et les doublons avec les absences déjà saisies (reprise
Quadra, saisie RH). Sortie en initiales. Sans --ecrire, AUCUNE écriture : piège
posé avant l'import de l'application, vérifié à la fin.

Avec --ecrire (accord d'Alexandre du 24/10) : chaque arrêt du bloc 60 sans
doublon remplace les demandes importées à tort (annulées, puis l'arrêt est créé
par create_reconciliation_absence) ; chaque faux arrêt d'un jour du bloc 41 est
annulé. Rien n'est écrit pour un salarié sorti, un arrêt qui recouvre une absence
saisie ou reprise, une source introuvable, ni pour les blocs 65 jamais importés.

Usage (depuis backend/) :
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python -B scripts/dsn_arrets_a_reclasser.py \
        [--data /chemin/data] [--env /chemin/backend/.env] [--json sortie.json] [--ecrire] \
        colorplast comitech mbc cartol lewis
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verification_rgdu import piege  # noqa: E402

IMPORT_DSN = "Import DSN historique"
#: Types d'absence qui sont des arrêts de travail (attestation, IJSS).
ARRETS = {"arret_maladie", "arret_at", "arret_maladie_pro", "arret_maternite", "arret_paternite"}
FICHIER_DU_LOT = re.compile(r"_(\d{2})(\d{2})_")
#: Compte qui signe les absences corrigées (Alexandre), comme scripts/reprise_arrets_quadra.py.
AUTEUR = "8300cc71-87a7-4d3f-8aef-8393de0ebc4f"
SORTIS = ("parti", "en_sortie")


def _racine_principale() -> Optional[Path]:
    """Le dépôt principal (le worktree n'a pas `data/` ni `.env`)."""
    try:
        commun = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, check=True, cwd=Path(__file__).parent,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(commun).parent if commun else None


def _premier_existant(*chemins: Optional[Path]) -> Optional[Path]:
    return next((c for c in chemins if c and c.exists()), None)


def _initiales(emp: Dict[str, Any]) -> str:
    prenom = (emp.get("first_name") or "?").strip()[:1].upper()
    nom = (emp.get("last_name") or "?").strip()[:1].upper()
    return f"{prenom}.{nom}."


def _jours(row: Dict[str, Any]) -> List[str]:
    return sorted(str(d)[:10] for d in row.get("selected_days") or [])


def _bornes(jours: List[str]) -> str:
    if not jours:
        return "—"
    d1, d2 = date.fromisoformat(jours[0]), date.fromisoformat(jours[-1])
    return f"{d1:%d/%m}" if d1 == d2 else f"{d1:%d/%m}→{d2:%d/%m}"


def _origine(row: Dict[str, Any]) -> str:
    commentaire = (row.get("comment") or "").strip()
    if commentaire.startswith(IMPORT_DSN):
        return "import DSN"
    if commentaire.startswith("Reprise Quadra"):
        return "reprise Quadra"
    if commentaire.startswith("Saisie RH au calendrier"):
        return "planning"
    return "saisie"


def _tout(requete) -> List[Dict[str, Any]]:
    lignes: List[Dict[str, Any]] = []
    debut = 0
    while True:
        page = requete.range(debut, debut + 999).execute().data or []
        lignes.extend(page)
        if len(page) < 1000:
            return lignes
        debut += 1000


def _lire_dsn(dossier: Path):
    from app.modules.dsn_import.domain.parser import parse_dsn_files

    fichiers = sorted(dossier.glob("*.dsn"))
    return parse_dsn_files([(f.name, f.read_bytes()) for f in fichiers]), [f.name for f in fichiers]


def analyser(societe: str, data: Path, sb) -> Dict[str, Any]:
    from app.modules.dsn_import.domain.dsn_absence_exit_mapping import (
        bornes_arret,
        bornes_suspension,
        build_absence_payload_from_arret,
        build_absence_payload_from_suspension,
        derniere_declaration,
        map_arret_motif,
        map_suspension_to_absence,
    )
    from app.modules.dsn_import.domain.normalize import nir_match_key, normalize_date_dsn

    parsed, fichiers = _lire_dsn(data / societe / "dsn")
    etabs = parsed.etablissements_by_siret()
    sirets = list(etabs)
    societes = sb.table("companies").select("id, company_name, siret").in_("siret", sirets).execute().data
    if not societes:
        return {"societe": societe, "erreur": f"aucune société en base pour les SIRET {sirets}"}
    company_id = societes[0]["id"]

    employes = _tout(
        sb.table("employees")
        .select("id, first_name, last_name, nir, hire_date, seniority_reference_date, specificites_paie, employment_status")
        .eq("company_id", company_id)
    )
    par_nir = {nir_match_key(e.get("nir")): e for e in employes if e.get("nir")}
    absences = _tout(
        sb.table("absence_requests")
        .select("id, employee_id, type, arret_type, status, selected_days, comment")
        .eq("company_id", company_id)
    )
    par_employe: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for a in absences:
        par_employe[str(a["employee_id"])].append(a)

    # Trace d'import : (clé NIR, jours) → bloc lu et fichier du lot.
    items = _tout(
        sb.table("dsn_import_items")
        .select("batch_id, mapped_payload")
        .eq("item_type", "absence")
        .eq("status", "committed")
        .in_("mapped_payload->>siret", sirets)
    )
    lots = {
        b["id"]: b.get("file_names") or []
        for b in (
            sb.table("dsn_import_batches").select("id, file_names")
            .in_("id", sorted({i["batch_id"] for i in items})).execute().data
            if items else []
        )
    }
    trace: Dict[Tuple[str, Tuple[str, ...]], Dict[str, Any]] = {}
    for item in items:
        p = item.get("mapped_payload") or {}
        noms = lots.get(item["batch_id"]) or []
        mois = [f"20{m.group(2)}-{m.group(1)}" for n in noms if (m := FICHIER_DU_LOT.search(n))]
        trace[(nir_match_key(p.get("nir")), tuple(sorted(p.get("selected_days") or [])))] = {
            "bloc": p.get("dsn_block"), "fichiers": mois or noms,
        }

    # Blocs de la DSN par salarié.
    blocs: Dict[str, Dict[str, list]] = defaultdict(lambda: {"60": [], "65": [], "41": []})
    for etab in etabs.values():
        for ind in etab.individus:
            cle = nir_match_key(ind.nir or ind.identifiant)
            for ctr in ind.contrats:
                blocs[cle]["60"].extend(ctr.arrets)
                blocs[cle]["65"].extend(ctr.suspensions)
                blocs[cle]["41"].extend(ctr.changements)

    def cle_arret(a):
        return (a.motif or "").strip().zfill(2), normalize_date_dsn(a.dernier_jour_travaille)

    lignes: List[Dict[str, Any]] = []
    compteurs: Counter = Counter()
    for cle_nir, b in blocs.items():
        emp = par_nir.get(cle_nir)
        if not emp:
            if b["60"]:
                compteurs["salarie_sans_fiche"] += 1
            continue
        ini = _initiales(emp)
        sorti = (emp.get("employment_status") or "actif").lower() in SORTIS
        siennes = par_employe.get(str(emp["id"]), [])
        importees = [a for a in siennes if _origine(a) == "import DSN" and a["status"] == "validated"]
        annulees = [a for a in siennes if _origine(a) == "import DSN" and a["status"] == "cancelled"]
        compteurs["import_dsn_annulees"] += len(annulees)
        fusionnes = {cle_arret(a): a for a in derniere_declaration(b["60"], cle_arret, bornes_arret)}
        expliquees: set = set()

        # 1. Les arrêts (bloc 60) : ce qu'ils deviennent, et ce qu'ils remplacent.
        for cle, arret in fusionnes.items():
            nouveau = build_absence_payload_from_arret(arret, siret="", nir=cle_nir, employee_label=ini)
            if nouveau is None:
                continue
            jours_nouveaux = set(nouveau["selected_days"])
            sources = [x for x in b["60"] if cle_arret(x) == cle]
            anciennes_bornes = {
                (normalize_date_dsn(x.dernier_jour_travaille), normalize_date_dsn(x.fin_previsionnelle))
                for x in sources
            }
            remplacees = [
                a for a in importees
                if a["id"] not in expliquees and _jours(a)
                and ((_jours(a)[0], _jours(a)[-1]) in anciennes_bornes or set(_jours(a)) & jours_nouveaux)
            ]
            # Une demande importée peut couvrir deux arrêts : déjà prise par le
            # premier, elle sera annulée, et le second doit quand même être créé.
            deja_prises = [
                a for a in importees if a["id"] in expliquees and set(_jours(a)) & jours_nouveaux
            ]
            if not remplacees and not deja_prises:
                continue
            expliquees |= {a["id"] for a in remplacees}
            deja_juste = any(
                a["type"] == nouveau["absence_type"]
                and (a.get("arret_type") or None) == nouveau["arret_type"]
                and set(_jours(a)) == jours_nouveaux
                for a in remplacees
            ) and len(remplacees) == 1
            doublons = [
                a for a in siennes
                if a["status"] == "validated" and _origine(a) != "import DSN" and set(_jours(a)) & jours_nouveaux
            ]
            trace_lue = [trace.get((cle_nir, tuple(_jours(a)))) for a in remplacees]
            for a in remplacees:
                compteurs[f"{a['type']}→{nouveau['absence_type']}/{nouveau['arret_type']}"] += 1
            compteurs["doublons"] += len(doublons)
            compteurs["arrets_deja_justes"] += int(deja_juste)
            lignes.append({
                "salarie": ini,
                "bloc": "S21.G00.60",
                "motif": nouveau["motif_dsn"],
                "deviendrait": f"{nouveau['absence_type']}/{nouveau['arret_type']} {_bornes(sorted(jours_nouveaux))}",
                "remplace": [f"{a['type']} {_bornes(_jours(a))}" for a in remplacees],
                "trace": sorted({f"{t['bloc']} {','.join(t['fichiers'])}" for t in trace_lue if t}),
                "deja_juste": deja_juste,
                "action": None if deja_juste or doublons or sorti else {
                    "employee_id": emp["id"], "company_id": company_id,
                    "annuler": [a["id"] for a in remplacees],
                    "creer": {
                        "absence_type": nouveau["absence_type"], "arret_type": nouveau["arret_type"],
                        "selected_days": sorted(jours_nouveaux),
                        "comment": f"Import DSN corrigé : bloc S21.G00.60, motif {nouveau['motif_dsn']}",
                    },
                },
                "doublons": [
                    f"{a['type']}{'/' + a['arret_type'] if a.get('arret_type') else ''} {_bornes(_jours(a))} ({_origine(a)})"
                    for a in doublons
                ],
            })

        # 2. Les faux arrêts d'un jour, lus dans un changement de contrat (bloc 41).
        dates_41 = {normalize_date_dsn(c.date_modification) for c in b["41"]}
        for a in importees:
            if a["id"] in expliquees:
                continue
            j = _jours(a)
            t = trace.get((cle_nir, tuple(j))) or {}
            if a["type"] in ARRETS and len(j) == 1 and (j[0] in dates_41 or t.get("bloc") == "G00.41"):
                expliquees.add(a["id"])
                compteurs["faux_arrets_bloc_41"] += 1
                lignes.append({
                    "salarie": ini, "bloc": "S21.G00.41",
                    "deviendrait": "rien : changement de contrat, demande à annuler",
                    "remplace": [f"{a['type']} {_bornes(j)}"],
                    "trace": [f"{t['bloc']} {','.join(t['fichiers'])}"] if t else [],
                    "deja_juste": False, "doublons": [],
                    "action": None if sorti else {
                        "employee_id": emp["id"], "company_id": company_id, "annuler": [a["id"]], "creer": None,
                    },
                })

        # 3. Ce qui reste importé sans source retrouvée.
        for a in importees:
            if a["id"] not in expliquees:
                compteurs[f"sans_source_{a['type']}"] += 1
                t = trace.get((cle_nir, tuple(_jours(a)))) or {}
                lignes.append({
                    "salarie": ini, "bloc": t.get("bloc") or "?",
                    "deviendrait": "source introuvable dans data/ : à voir",
                    "remplace": [f"{a['type']} {_bornes(_jours(a))}"],
                    "trace": [f"{t['bloc']} {','.join(t['fichiers'])}"] if t else [],
                    "deja_juste": False, "doublons": [],
                })

        # 4. Les autres suspensions (bloc 65), jamais importées jusqu'ici.
        def cle_susp(s):
            return (s.motif or "").strip().zfill(3), normalize_date_dsn(s.date_debut)

        validees = [a for a in siennes if a["status"] == "validated"]
        for s in derniere_declaration(b["65"], cle_susp, bornes_suspension):
            p = build_absence_payload_from_suspension(s, siret="", nir=cle_nir, employee_label=ini)
            if p is None:
                if map_suspension_to_absence(s.motif) is None:
                    compteurs[f"bloc65_non_repris_{(s.motif or '').strip()}"] += 1
                continue
            jours_s = set(p["selected_days"])
            if any(set(_jours(a)) & jours_s for a in validees):
                compteurs[f"bloc65_{p['absence_type']}_deja_couvert"] += 1
            else:
                compteurs[f"bloc65_{p['absence_type']}_a_creer"] += 1
        for a in b["60"]:
            if map_arret_motif(a.motif) is None:
                compteurs[f"bloc60_non_repris_{(a.motif or '').strip()}"] += 1

    # 5. L'ancienneté prise sur une suspension (bloc 65 lu comme ancienneté).
    anciennete_faussee = []
    for e in employes:
        dsn = (e.get("specificites_paie") or {}).get("dsn_anciennete") or {}
        d = dsn.get("date_anciennete") if isinstance(dsn, dict) else None
        if d and str(d)[:10] != str(e.get("hire_date") or "")[:10] and not e.get("seniority_reference_date"):
            anciennete_faussee.append(f"{_initiales(e)} {str(d)[:10]} au lieu de {str(e.get('hire_date'))[:10]}")

    return {
        "societe": societe,
        "company": societes[0]["company_name"],
        "fichiers_dsn": fichiers,
        "compteurs": dict(sorted(compteurs.items())),
        "anciennete_prise_sur_une_suspension": anciennete_faussee,
        "lignes": sorted(lignes, key=lambda ligne: (ligne["salarie"], ligne["deviendrait"])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("societes", nargs="*", default=["colorplast", "comitech", "mbc", "cartol", "lewis"])
    parser.add_argument("--data", type=Path)
    parser.add_argument("--env", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--ecrire", action="store_true", help="applique les corrections (accord d'Alexandre)")
    args = parser.parse_args()

    principale = _racine_principale()
    ici = Path(__file__).resolve().parents[2]
    data = args.data or _premier_existant(ici / "data", principale and principale / "data")
    env = args.env or _premier_existant(ici / "backend" / ".env", principale and principale / "backend" / ".env")
    if not data or not env:
        print("data/ ou backend/.env introuvable : passer --data et --env", file=sys.stderr)
        return 2

    from dotenv import load_dotenv

    load_dotenv(env)
    if not args.ecrire:
        piege.poser_le_piege()  # avant tout import de l'application
    from app.core.database import get_supabase_admin_client

    sb = get_supabase_admin_client()
    resultats = [analyser(s, data, sb) for s in args.societes]

    for r in resultats:
        print(f"\n=== {r['societe']} — {r.get('company', '')}")
        if r.get("erreur"):
            print("  ", r["erreur"])
            continue
        for cle, n in r["compteurs"].items():
            print(f"   {cle:45s} {n}")
        for ligne in r["lignes"]:
            marque = " (déjà juste)" if ligne["deja_juste"] else ""
            print(
                f"   {ligne['salarie']:6s} {ligne['bloc']:11s} {' + '.join(ligne['remplace'])}"
                f" ⇒ {ligne['deviendrait']}{marque}"
                + (f" | doublons : {'; '.join(ligne['doublons'])}" if ligne["doublons"] else "")
                + (f" | trace : {'; '.join(ligne['trace'])}" if ligne["trace"] else "")
            )
        if r["anciennete_prise_sur_une_suspension"]:
            print("   ancienneté prise sur une suspension :", "; ".join(r["anciennete_prise_sur_une_suspension"]))

    if args.ecrire:
        ecrire(resultats)
    else:
        print("\nécritures piégées :", piege.ECRITURES)
    if args.json:
        args.json.write_text(json.dumps(
            {"ecritures_piegees": piege.ECRITURES, "resultats": resultats}, ensure_ascii=False, indent=1
        ))
    return 0 if piege.ECRITURES == [] else 1


def ecrire(resultats: List[Dict[str, Any]]) -> None:
    """Annule les demandes importées à tort, puis crée l'arrêt qui les remplace."""
    from app.modules.absences.application.commands import (
        create_reconciliation_absence,
        update_absence_request_status,
    )
    from app.modules.absences.infrastructure.repository import absence_repository

    jour = date.today().strftime("%d/%m/%Y")
    for r in resultats:
        annulees = creees = laissees = 0
        for ligne in r.get("lignes", []):
            action = ligne.get("action")
            if not action:
                laissees += 1
                continue
            for absence_id in action["annuler"]:
                update_absence_request_status(absence_id, "cancelled")
                absence_repository.update(absence_id, {
                    "comment": f"{IMPORT_DSN} — annulée le {jour} : {ligne['bloc']} mal lu par l'ancien import"
                               f" (remplacée par : {ligne['deviendrait']})",
                })
                annulees += 1
            if action["creer"]:
                c = action["creer"]
                res = create_reconciliation_absence(
                    action["employee_id"], action["company_id"], AUTEUR,
                    absence_type=c["absence_type"], selected_days=c["selected_days"],
                    arret_type=c["arret_type"], comment=c["comment"], source="dsn_import",
                )
                if res.get("skipped"):
                    print(f"   {ligne['salarie']:6s} création ignorée par la base : {res.get('reason')}")
                else:
                    creees += 1
        print(f"=== {r['societe']} : {annulees} demande(s) annulée(s), {creees} arrêt(s) créé(s),"
              f" {laissees} ligne(s) laissée(s) telles quelles")
    print("ÉCRIT")


if __name__ == "__main__":
    raise SystemExit(main())
