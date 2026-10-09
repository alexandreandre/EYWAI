"""Colonne MARTINE de Comitech et de Mont-Blanc : le moteur en bac à sable, mis en cache.

Complément du contrôleur, tâche 9, point 5. Pour chaque salarié et chaque mois où Quadra a
imprimé un bulletin, le moteur calcule le bulletin en bac à sable
(`colonne_eywai.depuis_le_bac_a_sable`), à partir des cumuls de Quadra à la fin du mois
précédent (`colonne_eywai.cumuls_quadra_avant` : la DSN d'abord, l'implicite ensuite). Rien
n'est écrit en base : le piège à écritures est posé avant tout import d'`app`.

Règles du plan (`plan_des_appels`) :
- mois d'embauche (le bulletin porte une entrée ce mois-là) : cumuls à zéro ;
- janvier, hors embauche : pas d'appel, `smic_eywai=None` (complément, point 5) ;
- autre mois : cumuls de Quadra ; si `cumuls_quadra_avant` renvoie None, pas d'appel ;
- clé Quadra sans salarié en base : pas d'appel.
Les mois d'avant l'embauche comptent pour un SMIC nul dans la DSN du salarié : sans cela, un
salarié embauché en cours d'année ne pourrait jamais partir de sa DSN.

Les résultats vont dans `data/_rapports/rgdu-2026/eywai_<societe>.json` (hors git, clés
nominatives), réécrit après chaque appel : une relance reprend là où le script s'est arrêté.
Les appels se font un par un (la base de test porte la vraie paie de Gaëlle). Une écriture
tentée hors de `employee_cp_seniority_grants` arrête le script (code 2).

Usage (depuis backend/) :
    APP_ENV=development PYTHONPATH=. .venv/bin/python -m scripts.verification_rgdu.eywai_bac_a_sable \\
        comitech mbc [--refaire-erreurs]
"""
from __future__ import annotations

import sys

from scripts.verification_rgdu import piege

if __name__ == "__main__":
    # Avant tout import d'app : quadra_mois l'importe (via reprise_colorplast_solde_ouverture).
    piege.poser_le_piege()

import json  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

from scripts.verification_rgdu.chemins import ANNEE, RAPPORT, SOCIETES, parametres_de  # noqa: E402
from scripts.verification_rgdu.colonne_eywai import cumuls_quadra_avant  # noqa: E402
from scripts.verification_rgdu.dsn_quadra import BaseReduction, dsn_du_mois  # noqa: E402
from scripts.verification_rgdu.implicite import smic_quadra_par_mois  # noqa: E402
from scripts.verification_rgdu.oracle import Parametres  # noqa: E402
from scripts.verification_rgdu.quadra_mois import MoisQuadra  # noqa: E402

#: Seule table où une écriture tentée (et bloquée) est connue et tolérée : le droit à congés
#: d'ancienneté, recalculé au passage par le moteur. Toute autre cible arrête le script.
TABLE_TOLEREE = "employee_cp_seniority_grants"
MOIS_DSN = tuple(range(1, 7))   # les DSN de Quadra couvrent janvier à juin

#: Départ à zéro, comme `bac_a_sable.cumuls_de_depart(BacASable(None), 2026)`.
CUMULS_A_ZERO = {
    "periode": {"annee_en_cours": ANNEE, "dernier_mois_calcule": 0},
    "cumuls": {
        "brut_total": 0.0, "heures_remunerees": 0.0, "reduction_generale_patronale": 0.0,
        "net_imposable": 0.0, "impot_preleve_a_la_source": 0.0, "heures_supplementaires_remunerees": 0.0,
    },
}


@dataclass
class Tache:
    """Un salarié-mois du plan. `statut` : « a_calculer » (appel au moteur, `cumuls` fournis),
    ou la raison de ne pas appeler : « janvier », « sans_cumuls », « sans_employe ».
    `depart` : « quadra » (cumuls reconstruits) ou « embauche » (cumuls à zéro)."""
    cle: str
    mois: int
    employee_id: str | None
    statut: str
    cumuls: dict | None = None
    depart: str = ""
    raison: str = ""
    jointure: str = ""


def cle_cache(cle: str, mois: int) -> str:
    return f"{cle}|{mois}"


def smic_dsn_du_salarie(bases_par_mois: dict[int, list[BaseReduction]], nir: str) -> dict[int, float]:
    """SMIC retenu de la base 03 du mois (`debut.month == mois`) pour ce NIR, par mois. Les
    blocs de continuité du mois précédent sont écartés. Un mois sans SMIC retenu est absent."""
    sortie: dict[int, float] = {}
    for mois, bases in bases_par_mois.items():
        smic = [b.smic_retenu for b in bases if b.nir == nir and b.debut.month == mois and b.smic_retenu is not None]
        if smic:
            sortie[mois] = round(sum(smic), 2)
    return sortie


def joindre_employes(employes: list[dict], cles: set[str]) -> dict[str, tuple[str, str]]:
    """Clé Quadra (« nir/matricule ») → (employee_id, méthode). D'abord le NIR (13 caractères)
    et le matricule ; à défaut, le NIR seul quand une seule clé Quadra le porte. Une clé que
    deux salariés revendiquent n'est pas jointe (jamais deviner)."""
    candidats: dict[str, list[tuple[str, str]]] = {}
    for e in employes:
        nir = str(e.get("nir") or "").replace(" ", "")[:13]
        matricule = str(e.get("matricule") or "").strip()
        if not nir and not matricule:
            continue
        exacte = f"{nir}/{matricule}" if nir else matricule
        if exacte in cles:
            candidats.setdefault(exacte, []).append((e["id"], "nir/matricule"))
            continue
        par_nir = [c for c in cles if nir and c.startswith(f"{nir}/")]
        if len(par_nir) == 1:
            candidats.setdefault(par_nir[0], []).append((e["id"], "nir seul"))
    return {cle: liste[0] for cle, liste in candidats.items() if len(liste) == 1}


def _mois_embauche(mois_quadra: list[MoisQuadra]) -> int | None:
    premier = min(mois_quadra, key=lambda m: m.mois)
    return premier.mois if premier.entree is not None else None


def plan_des_appels(mois_par_cle: dict[str, list[MoisQuadra]], jointure: dict[str, tuple[str, str]],
                    smic_dsn_par_cle: dict[str, dict[int, float]], prm: Parametres) -> list[Tache]:
    """Un `Tache` par clé et par mois de bulletin Quadra (voir la docstring du module)."""
    plan: list[Tache] = []
    for cle, mois_quadra in sorted(mois_par_cle.items()):
        mois_quadra = sorted(mois_quadra, key=lambda m: m.mois)
        eid, methode = jointure.get(cle, (None, ""))
        smic_dsn = dict(smic_dsn_par_cle.get(cle, {}))
        embauche = _mois_embauche(mois_quadra)
        if embauche is not None:
            for m in range(1, embauche):
                smic_dsn.setdefault(m, 0.0)
        implicite = smic_quadra_par_mois(mois_quadra, prm)
        for mq in mois_quadra:
            t = Tache(cle, mq.mois, eid, "", jointure=methode)
            if eid is None:
                t.statut, t.raison = "sans_employe", "clé Quadra sans salarié joint en base"
            elif mq.entree is not None:
                t.statut, t.cumuls, t.depart = "a_calculer", CUMULS_A_ZERO, "embauche"
            elif mq.mois == 1:
                t.statut, t.raison = "janvier", "janvier : hors du bac à sable (complément, point 5)"
            else:
                cumuls = cumuls_quadra_avant(mq.mois, mois_quadra, smic_dsn, implicite)
                if cumuls is None:
                    prec = implicite.get(mq.mois - 1)
                    t.statut = "sans_cumuls"
                    t.raison = (f"mois {mq.mois - 1} absent des bulletins Quadra" if prec is None
                                else f"SMIC cumulé du mois {mq.mois - 1} introuvable : {prec.raison}")
                else:
                    t.statut, t.cumuls, t.depart = "a_calculer", cumuls, "quadra"
            plan.append(t)
    return plan


def a_faire(plan: list[Tache], cache: dict, refaire_erreurs: bool = False) -> list[Tache]:
    """Les appels du plan qui ne sont pas encore en cache (les erreurs, sur demande)."""
    sortie = []
    for t in plan:
        if t.statut != "a_calculer":
            continue
        deja = cache.get(cle_cache(t.cle, t.mois))
        if deja is None or (refaire_erreurs and deja.get("statut") == "erreur"):
            sortie.append(t)
    return sortie


def ecritures_interdites(ecritures: list[str]) -> list[str]:
    """Les écritures tentées qui ne visent pas la table tolérée."""
    return [e for e in ecritures if not e.endswith(f" {TABLE_TOLEREE}")]


def chemin_cache(societe: str) -> Path:
    return RAPPORT / f"eywai_{societe}.json"


def lire_cache(chemin: Path) -> dict:
    if not chemin.exists():
        return {}
    return json.loads(chemin.read_text(encoding="utf-8")).get("resultats", {})


def ecrire_cache(chemin: Path, societe: str, resultats: dict) -> None:
    """Écriture atomique : un fichier temporaire, puis un renommage."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.with_suffix(".json.tmp")
    contenu = {"societe": societe, "maj": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "resultats": resultats}
    tmp.write_text(json.dumps(contenu, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, chemin)


def _sans_appel(t: Tache) -> dict:
    return {"cle": t.cle, "mois": t.mois, "employee_id": t.employee_id, "statut": t.statut,
            "raison": t.raison, "jointure": t.jointure}


def _company_id(client, societe: str) -> str:
    cid = SOCIETES[societe]["company_id"]
    if cid:
        return cid
    r = client.table("companies").select("id, company_name").ilike("company_name", "%mont%blanc%").execute()
    if len(r.data or []) != 1:
        raise SystemExit(f"{societe} : {len(r.data or [])} société(s) trouvée(s) pour « mont blanc », une attendue")
    return r.data[0]["id"]


def rejouer_societe(societe: str, refaire_erreurs: bool = False) -> int:
    """Calcule et met en cache la colonne MARTINE d'une société. 0 si tout s'est déroulé,
    2 si une écriture hors de la table tolérée a été tentée (arrêt immédiat)."""
    from app.core.database import get_supabase_admin_client
    from scripts.verification_rgdu.colonne_eywai import depuis_le_bac_a_sable
    from scripts.verification_rgdu.quadra_mois import lire_societe

    t0 = time.time()
    client = get_supabase_admin_client()
    company_id = _company_id(client, societe)
    employes = client.table("employees").select("id, nir, matricule").eq("company_id", company_id).execute().data or []
    quadra = lire_societe(societe)
    mois_par_cle: dict[str, list[MoisQuadra]] = {}
    for (cle, _m), mq in quadra.items():
        mois_par_cle.setdefault(cle, []).append(mq)
    bases = {m: dsn_du_mois(societe, m) for m in MOIS_DSN}
    smic_dsn = {cle: (smic_dsn_du_salarie(bases, mqs[0].nir) if mqs[0].nir else {}) for cle, mqs in mois_par_cle.items()}
    jointure = joindre_employes(employes, set(mois_par_cle))
    plan = plan_des_appels(mois_par_cle, jointure, smic_dsn, parametres_de(societe))

    chemin = chemin_cache(societe)
    resultats = lire_cache(chemin)
    for t in plan:
        if t.statut != "a_calculer":
            resultats[cle_cache(t.cle, t.mois)] = _sans_appel(t)
    ecrire_cache(chemin, societe, resultats)
    restants = a_faire(plan, resultats, refaire_erreurs)
    n_calc = sum(1 for t in plan if t.statut == "a_calculer")
    print(f"{societe} : {len(employes)} salariés en base, {len(mois_par_cle)} clés Quadra, {len(jointure)} jointes ; "
          f"{len(plan)} salarié-mois, {n_calc} à calculer, {len(restants)} restants "
          f"(lecture {time.time() - t0:.0f} s)", flush=True)

    for i, t in enumerate(restants, 1):
        avant = len(piege.ECRITURES)
        debut = time.time()
        entree = {"cle": t.cle, "mois": t.mois, "employee_id": t.employee_id, "depart": t.depart,
                  "cumuls_injectes": t.cumuls["cumuls"], "jointure": t.jointure}
        try:
            r = depuis_le_bac_a_sable(t.employee_id, t.mois, t.cumuls)
            entree.update(statut="ok", heures_reduction=r.heures_reduction, smic=r.smic,
                          reduction_ligne=r.reduction_ligne)
        except Exception as exc:  # une erreur du moteur n'arrête pas le rejeu : elle est notée
            entree.update(statut="erreur", erreur=f"{type(exc).__name__}: {str(exc)[:300]}")
        nouvelles = piege.ECRITURES[avant:]
        entree.update(duree_s=round(time.time() - debut, 1), ecritures=nouvelles)
        resultats[cle_cache(t.cle, t.mois)] = entree
        ecrire_cache(chemin, societe, resultats)
        print(f"[{societe} {i}/{len(restants)}] {t.cle[:3]} m{t.mois} {entree['statut']} "
              f"{entree.get('heures_reduction', '')} {entree['duree_s']} s"
              + (f" écritures {nouvelles}" if nouvelles else "")
              + (f" {entree['erreur'][:120]}" if entree["statut"] == "erreur" else ""), flush=True)
        interdites = ecritures_interdites(nouvelles)
        if interdites:
            print(f"ARRÊT : écriture tentée hors de {TABLE_TOLEREE} : {interdites}", flush=True)
            return 2
    ok = sum(1 for v in resultats.values() if v.get("statut") == "ok")
    err = sum(1 for v in resultats.values() if v.get("statut") == "erreur")
    print(f"{societe} terminé : {ok} ok, {err} erreurs, {time.time() - t0:.0f} s", flush=True)
    return 0


def main(argv: list[str]) -> int:
    piege.poser_le_piege()   # déjà posé sous __main__ ; sans effet s'il l'est
    refaire = "--refaire-erreurs" in argv
    societes = [a for a in argv if not a.startswith("--")] or ["comitech", "mbc"]
    for societe in societes:
        code = rejouer_societe(societe, refaire)
        if code:
            print(f"ECRITURES {piege.ECRITURES}", flush=True)
            return code
    print(f"ECRITURES {piege.ECRITURES}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
