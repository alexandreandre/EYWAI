"""Reprise des arrêts de l'année depuis les bulletins Quadra.

Les mois repris sont verrouillés, mais le calcul d'un mois suivant relit les
arrêts de l'année : crédit de carence payée une fois par an, continuité d'un
arrêt qui se prolonge. Chez Comitech, l'import DSN avait fait des arrêts maladie
des congés « sans solde » (bloc S21.G00.60 mal lu), avec un jour d'avance, et
rien n'était repris après juin : saisi au 01/09, l'arrêt en cours depuis mai
aurait repayé trois jours de carence déjà payés par Quadra en mai.

Les bulletins Quadra impriment chaque arrêt avec ses dates (« Absence maladie
040526-310526 ») : on les lit, on recolle les morceaux coupés à chaque période,
on annule les absences importées de la DSN qu'ils recouvrent, et on crée les
arrêts, qui s'inscrivent au planning avec leurs vraies bornes.

Usage (depuis backend/) :
    python -m scripts.reprise_arrets_quadra --societe comitech --jusqu-a 8            # simulation
    python -m scripts.reprise_arrets_quadra --societe comitech --jusqu-a 8 --apply    # écrit
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest.colorplast_lignes_quadra import lire_bulletins  # noqa: E402
from scripts.reprise_comitech import _nir  # noqa: E402

ANNEE = 2026
SOCIETES = {
    "comitech": "12cd8c71-da13-43f9-9151-475c4d5e8812",
    "colorplast": "dbe2b9f5-44dd-41bc-a625-36ed33d160f7",
}
#: Compte qui signe les absences reprises (Alexandre).
AUTEUR = "8300cc71-87a7-4d3f-8aef-8393de0ebc4f"
#: Libellé Quadra → (type d'absence, type d'arrêt).
NATURES = (
    (re.compile(r"^absence maladie\b", re.I), "arret_maladie", "maladie_simple"),
    (re.compile(r"^absence a\.?\s?t\.?(\s|$)|accident du travail", re.I), "arret_at", "accident_travail"),
    (re.compile(r"^abs\.?\s+paternit", re.I), "arret_paternite", None),
    (re.compile(r"^abs\.?\s+maternit", re.I), "arret_maternite", None),
)
DATES = re.compile(r"(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})")
#: Écart maximal entre deux morceaux d'un même arrêt (un week-end en fin de période).
RECOLLE_JOURS = 2
IMPORT_DSN = "Import DSN historique"

Arret = tuple  # (type, arret_type, début, fin)


def arrets_des_bulletins(lus: dict[int, dict]) -> dict[str, list[Arret]]:
    """Les morceaux d'arrêt imprimés sur les bulletins, par matricule."""
    trouves: dict[str, set] = defaultdict(set)
    for bulletins in lus.values():
        for mat, b in bulletins.items():
            for ligne in b.lignes:
                libelle = ligne.libelle.strip()
                dates = DATES.search(libelle)
                if not dates:
                    continue
                for motif, type_absence, type_arret in NATURES:
                    if motif.search(libelle):
                        j1, m1, a1, j2, m2, a2 = (int(x) for x in dates.groups())
                        trouves[mat].add(
                            (type_absence, type_arret, date(2000 + a1, m1, j1), date(2000 + a2, m2, j2))
                        )
                        break
    return {mat: sorted(v, key=lambda a: (a[2], a[0])) for mat, v in trouves.items()}


def recoller(morceaux: list[Arret]) -> list[Arret]:
    """Un arrêt coupé à chaque fin de période redevient un seul arrêt."""
    par_nature: dict[tuple, list[Arret]] = defaultdict(list)
    for m in sorted(morceaux, key=lambda a: a[2]):
        par_nature[(m[0], m[1])].append(m)
    recolles: list[Arret] = []
    for suite in par_nature.values():
        courant = suite[0]
        for m in suite[1:]:
            if (m[2] - courant[3]).days <= RECOLLE_JOURS:
                courant = (courant[0], courant[1], courant[2], max(courant[3], m[3]))
            else:
                recolles.append(courant)
                courant = m
        recolles.append(courant)
    return sorted(recolles, key=lambda a: (a[2], a[0]))


def _jours(debut: date, fin: date) -> list[str]:
    return [(debut + timedelta(days=n)).isoformat() for n in range((fin - debut).days + 1)]


def main(societe: str, jusqu_a: int, appliquer: bool) -> int:
    from app.core.database import get_supabase_admin_client
    from app.modules.absences.application.commands import (
        create_reconciliation_absence,
        update_absence_request_status,
    )
    from app.modules.absences.infrastructure.repository import absence_repository

    company_id = SOCIETES[societe]
    admin = get_supabase_admin_client()
    fiches = admin.table("employees").select("id, last_name, nir, employment_status") \
        .eq("company_id", company_id).execute().data
    par_nir = {_nir(f["nir"]): f for f in fiches if f.get("nir")}
    lus = {m: lire_bulletins(ANNEE, m, societe) for m in range(1, jusqu_a + 1)}
    nir_du_mat = {mat: _nir(b.infos.get("nir")) for bs in lus.values() for mat, b in bs.items()}

    creations = annulations = 0
    for mat, morceaux in sorted(arrets_des_bulletins(lus).items()):
        fiche = par_nir.get(nir_du_mat.get(mat))
        if not fiche:
            print(f"{mat:11s} !! aucune fiche : arrêts ignorés")
            continue
        if (fiche.get("employment_status") or "actif").lower() in ("parti", "en_sortie"):
            # La base refuse une absence à un salarié sorti : rien n'est annulé non plus.
            print(f"{mat:11s} .. sorti : arrêts laissés tels quels")
            continue
        existantes = admin.table("absence_requests").select("id, type, status, selected_days, comment") \
            .eq("employee_id", fiche["id"]).eq("status", "validated").execute().data
        for type_absence, type_arret, debut, fin in recoller(morceaux):
            jours = _jours(debut, fin)
            libelle = f"{type_absence}{'/' + type_arret if type_arret else ''} du {debut:%d/%m} au {fin:%d/%m}"
            if any(e["type"] == type_absence and sorted(e["selected_days"] or []) == jours for e in existantes):
                print(f"{mat:11s} = {libelle} déjà en base")
                continue
            a_annuler = [e for e in existantes
                         if set(e["selected_days"] or []) & set(jours) and (e.get("comment") or "").startswith(IMPORT_DSN)]
            autres = [e for e in existantes
                      if set(e["selected_days"] or []) & set(jours) and e not in a_annuler]
            if autres:
                print(f"{mat:11s} !! {libelle} recouvre des absences saisies à la main "
                      + ", ".join(f"{e['type']} {e['id'][:8]}" for e in autres) + " : ignoré, à voir")
                continue
            for e in a_annuler:
                jours_e = sorted(e["selected_days"])
                print(f"{mat:11s} - annule {e['type']} importé de la DSN du {jours_e[0]} au {jours_e[-1]} ({e['id'][:8]})")
                annulations += 1
                if appliquer:
                    update_absence_request_status(e["id"], "cancelled")
                    absence_repository.update(e["id"], {
                        "comment": f"{e.get('comment') or ''} — annulée le {date.today():%d/%m/%Y} : "
                                   f"remplacée par l'arrêt repris des bulletins Quadra ({libelle})"})
                existantes = [x for x in existantes if x["id"] != e["id"]]
            print(f"{mat:11s} + crée {libelle} ({len(jours)} j)")
            creations += 1
            if appliquer:
                res = create_reconciliation_absence(
                    fiche["id"], company_id, AUTEUR,
                    absence_type=type_absence, selected_days=jours, arret_type=type_arret,
                    comment=f"Reprise Quadra : arrêt imprimé sur les bulletins ({libelle})",
                    source="reprise_quadra",
                )
                if res.get("skipped"):
                    print(f"{'':11s}   ignoré par la base : {res.get('reason')}")
    print(f"\n{creations} arrêt(s) à créer, {annulations} absence(s) DSN à annuler.")
    print("ÉCRIT" if appliquer else "Simulation. Relancer avec --apply pour écrire.")
    return 0


if __name__ == "__main__":
    societe = sys.argv[sys.argv.index("--societe") + 1] if "--societe" in sys.argv else "comitech"
    jusqu_a = int(sys.argv[sys.argv.index("--jusqu-a") + 1]) if "--jusqu-a" in sys.argv else 8
    raise SystemExit(main(societe, jusqu_a, "--apply" in sys.argv))
