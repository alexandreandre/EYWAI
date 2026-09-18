"""Janvier à juin 2026 de Colorplast rejoués à la régulière, sur le TEST.

Le rejeu (`colorplast_rejeu_test.py`) juge le moteur sur les entrées du
cabinet : heures sup lues sur les bulletins, absences datées comme Quadra les
imprime, mois d'entrée surchargés. Ce script pose l'autre question, celle du
processus réel : avec les seules sources régulières — feuilles de pointage,
calendrier d'absences du cabinet (classeur de Gaëlle), arrêts de la DSN,
variables du mois (primes, acomptes, notes de frais) — que produit le moteur,
et où s'écarte-t-il de ce que le cabinet a payé ?

Déroulé : fiches, plannings, pointages et saisies relevés ; puis, mois après
mois de janvier à juin, le setup pose le mois, le planning est régularisé (les
absences recopiées des bulletins sont retirées, les congés du classeur et des
feuilles posés), les feuilles écrites au calendrier réel de la fenêtre, les
saisies d'heures sup effacées, les surcharges de mois d'entrée retirées, et les
bulletins **calculés en bac à sable** : le générateur reçoit les cumuls du mois
d'avant depuis la chaîne tenue ici en mémoire et ne persiste rien — ni
`payslips`, ni cumuls, ni storage. Ces mois sont importés de Quadra et
verrouillés par la bascule de reprise ; l'audit ne doit pas écrire dans la
chaîne de paie, c'est ce qui a fait casser janvier trois fois. Les six mois
sont ensuite comparés ligne à ligne aux bulletins Quadra
(`scripts.backtest.colorplast_lignes`). Enfin fiches, plannings et saisies sont
remis comme relevés, et le script vérifie que la chaîne de paie n'a pas bougé.

Rien ici n'est ajusté pour coller au bulletin : ce que le moteur donne est
imprimé tel quel, écarts compris, avec les lectures douteuses des feuilles
listées dans `colorplast_feuilles.INCERTITUDES`.

Les bulletins calculés ne vont nulle part ailleurs que dans `--json-dir` : les
bulletins en ligne sont ceux de Quadra, et le resteront.

Le relevé (plannings, saisies, fiches, historique de salaire) est écrit sur
disque au départ : si le processus est tué avant sa remise en état — c'est arrivé
le 18/09, timeout de l'outil qui le lançait, mois de janvier à mai laissés dans
l'état régularisé —, `--remettre-depuis FICHIER` rejoue la remise depuis ce fichier.

Usage : [--apply] [--jusqu-a MOIS] [--json-dir DOSSIER] [--ajuster NOM:MM-JJ=HEURES ...] [--seulement NOM ...]
        --remettre-depuis FICHIER

`--seulement` ne génère que les salariés nommés (les autres ne sont pas touchés) :
un ajustement ne concerne qu'une chaîne, inutile de rejouer les sept.

`--ajuster` remplace une journée pointée par une autre valeur avant de jouer,
pour vérifier une hypothèse : par exemple `--ajuster ESPINOSA:01-05=10.5`
rejoue janvier avec le décompte de Gaëlle (45 h la semaine du 5 janvier) au
lieu de la feuille (44 h). Sans cette option, la feuille est prise telle quelle.
"""

from __future__ import annotations

import copy
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException  # noqa: E402

from app.core.database import get_supabase_admin_client, supabase  # noqa: E402
from app.modules.payslips.application.dto import (  # noqa: E402
    GeneratePayslipResult,
    PayslipBadRequestError,
)
from app.modules.payslips.infrastructure.providers import payslip_generator_provider  # noqa: E402
from scripts.backtest import colorplast_feuilles_janvier as janvier  # noqa: E402
from scripts.backtest import colorplast_feuilles_juin as juin  # noqa: E402
from scripts.backtest.colorplast_calendrier_cabinet import lire as lire_le_classeur  # noqa: E402
from scripts.backtest.colorplast_feuilles import (  # noqa: E402
    FEUILLES,
    INCERTITUDES,
    YEAR,
    heures_par_semaine,
    heures_sup_attendues,
    poser_les_feuilles,
    regulariser_le_planning,
)
from scripts.backtest.colorplast_lignes import comparer_le_mois, imprimer  # noqa: E402
from scripts.backtest.colorplast_setup import MONTH_DATA, apply_month  # noqa: E402
from scripts.colorplast_rejeu_test import (  # noqa: E402
    COMPANY_ID,
    REFERENCES,
    SALARIES,
    _controler,
    _nettoyer_les_doublons_du_cabinet,
    _restaurer,
    _salaries_du_mois,
    _snapshot,
)

MOIS_REGULIERS = (1, 2, 3, 4, 5, 6)
#: Cumuls du dernier mois calculé, par salarié : la chaîne du bac à sable. Un
#: salarié qui n'y est pas encore part de zéro, comme un premier bulletin.
CHAINE: dict[str, dict] = {}
#: Bulletins calculés, par (matricule, mois) : ce que la comparaison lit.
BULLETINS: dict[tuple[str, int], dict] = {}
#: (NOM, mois, jour) → heures, posé à la place de la feuille (option --ajuster).
AJUSTEMENTS: dict[tuple[str, int, int], float] = {}
#: Salariés à générer (option --seulement) ; vide = tous ceux du mois.
SEULEMENT: set[str] = set()
#: (NOM, mois) dont le pointage est ramené à l'horaire prévu (option --sans-heures-sup).
SANS_HEURES_SUP: set[tuple[str, int]] = set()
#: (NOM, mois) dont la surcharge de mois d'entrée du setup est gardée (option --garder-surcharge).
GARDER_SURCHARGE: set[tuple[str, int]] = set()
#: (NOM, mois) → montant de carence versé par l'employeur (option --maintien-prevoyance).
MAINTIEN_PREVOYANCE: dict[tuple[str, int], float] = {}
#: (NOM, mois) laissés sur les entrées du cabinet (option --comme-quadra).
COMME_QUADRA: set[tuple[str, int]] = set()
#: (NOM, mois, jour) → heures d'une journée non payée posée à la main (option --absence).
ABSENCES_POSEES: dict[tuple[str, int, int], float] = {}
#: (NOM, mois) → montant ajouté au brut (négatif = retenue), option --saisie.
SAISIES_POSEES: dict[tuple[str, int], float] = {}


def _poser_les_saisies(emps: dict, mois: int) -> None:
    """Ajoute au brut une ligne que nos règles ne calculent pas (retenue si négatif)."""
    from scripts.backtest.colorplast_setup import _insert_input
    admin = get_supabase_admin_client()
    for nom, emp in emps.items():
        montant = SAISIES_POSEES.get((nom, mois))
        if montant is None:
            continue
        libelle = "Regularisation retenue d absence" if montant < 0 else "Regularisation"
        _insert_input(admin, emp["id"], COMPANY_ID, YEAR, mois, libelle, montant, True, True)
        print(f"  {nom:10s} : {montant:+.2f} € posés au brut ({libelle})")


def _poser_les_absences(emps: dict, mois: int) -> None:
    """Écrit au planning les journées non payées demandées, dans la fenêtre du mois."""
    from scripts.backtest.colorplast_feuilles import _schedule
    admin = get_supabase_admin_client()
    for nom, emp in emps.items():
        posees = {(mm, jj): h for (n, mm, jj), h in ABSENCES_POSEES.items() if n == nom}
        if not posees:
            continue
        for mm in sorted({mm for mm, _ in posees}):
            sched = _schedule(emp["id"], mm)
            if not sched:
                continue
            planned = copy.deepcopy(sched.get("planned_calendar") or {})
            cal = planned.get("calendrier_prevu") or []
            par_jour = {int(j["jour"]): j for j in cal}
            faits = []
            for (m2, jour), heures in sorted(posees.items()):
                if m2 != mm:
                    continue
                j = par_jour.get(jour)
                if j is None:
                    j = {"jour": jour}
                    cal.append(j)
                j.update({"type": "absence_non_remuneree", "manuel": True, "heures_prevues": round(heures, 2)})
                j.pop("arret_type", None)
                faits.append(f"{jour:02d}/{mm:02d}={heures:g}")
            planned["calendrier_prevu"] = sorted(cal, key=lambda x: int(x["jour"]))
            admin.table("employee_schedules").update({"planned_calendar": planned}).eq("id", sched["id"]).execute()
            if faits:
                print(f"  {nom:10s} : journées non payées posées {', '.join(faits)}")


def _couper_le_maintien_legal() -> dict | None:
    """Désactive le maintien légal de l'entreprise le temps du rejeu, et rend l'état d'avant."""
    admin = get_supabase_admin_client()
    avant = (admin.table("company_maintenance_settings").select("*")
             .eq("company_id", COMPANY_ID).maybe_single().execute())
    avant = avant.data if avant else None
    if avant:
        admin.table("company_maintenance_settings").update(
            {"apply_legal_maintenance": False}).eq("id", avant["id"]).execute()
    else:
        admin.table("company_maintenance_settings").insert(
            {"company_id": COMPANY_ID, "apply_legal_maintenance": False}).execute()
    print("  maintien légal désactivé le temps du rejeu (prévoyance supposée prendre le relais)")
    return avant


def _remettre_le_maintien_legal(avant: dict | None) -> None:
    admin = get_supabase_admin_client()
    if avant:
        admin.table("company_maintenance_settings").update(
            {k: v for k, v in avant.items() if k not in ("id", "created_at")}
        ).eq("id", avant["id"]).execute()
    else:
        admin.table("company_maintenance_settings").delete().eq("company_id", COMPANY_ID).execute()
    print("  maintien légal de l'entreprise remis comme avant")


def _poser_la_carence(emps: dict, mois: int) -> None:
    """Verse le seul montant des jours de carence, comme Gaëlle l'a saisi."""
    from scripts.backtest.colorplast_setup import _insert_input
    admin = get_supabase_admin_client()
    for nom, emp in emps.items():
        montant = MAINTIEN_PREVOYANCE.get((nom, mois))
        if montant is None:
            continue
        _insert_input(admin, emp["id"], COMPANY_ID, YEAR, mois,
                      "Maintien de salaire (jours de carence)", montant, True, True)
        print(f"  {nom:10s} : {montant:.2f} € de carence versés (saisie de Gaëlle), maintien légal coupé")


def _ramener_a_l_horaire(emps: dict, mois: int) -> None:
    """Chaque journée pointée de la fenêtre prend l'horaire prévu du jour : la saisie « sans heure sup »."""
    from scripts.backtest.colorplast_feuilles import _mois_de_la_fenetre, _schedule
    for nom, emp in emps.items():
        if (nom, mois) not in SANS_HEURES_SUP:
            continue
        for mm, jours_fenetre in _mois_de_la_fenetre(mois).items():
            sched = _schedule(emp["id"], mm)
            if not sched:
                continue
            prevu = {int(j["jour"]): float(j.get("heures_prevues") or 0.0)
                     for j in (sched.get("planned_calendar") or {}).get("calendrier_prevu", []) if j.get("type") == "travail"}
            actual = copy.deepcopy(sched.get("actual_hours") or {})
            n = 0
            for r in actual.get("calendrier_reel") or []:
                if r.get("type") == "travail" and int(r["jour"]) in jours_fenetre and int(r["jour"]) in prevu:
                    r["heures_faites"] = prevu[int(r["jour"])]
                    n += 1
            supabase.table("employee_schedules").update({"actual_hours": actual}).eq("id", sched["id"]).execute()
            print(f"  {nom:10s} : {n} journée(s) de {mm:02d} ramenées à l'horaire prévu (sans heure sup, saisie de Gaëlle)")


def _feuilles_du_mois(mois: int) -> dict[str, dict[tuple[int, int], float]]:
    if mois == 1:
        # La feuille de janvier porte aussi S05 (26 → 30/01), qui appartient à la fenêtre de février.
        feuilles = {nom: {(1, j): h for j, h in jours.items() if j <= 25} for nom, jours in janvier.FEUILLES.items()}
    elif mois == 6:
        feuilles = {nom: dict(jours) for nom, jours in juin.FEUILLES.items()}
    else:
        feuilles = {nom: dict(jours) for nom, jours in FEUILLES.get(mois, {}).items()}
    for (nom, mm, jj), heures in AJUSTEMENTS.items():
        if nom in feuilles and (mm, jj) in feuilles[nom]:
            feuilles[nom][(mm, jj)] = heures
    return feuilles


def _payees_par_le_cabinet(nom: str, mois: int) -> tuple[float, float]:
    cfg = MONTH_DATA.get(mois, {}).get(nom, {})
    return float(cfg.get("hs25") or 0.0), float(cfg.get("hs50") or 0.0)


def _heures_sup_du_bulletin(data: dict) -> tuple[float, float]:
    hs25 = hs50 = 0.0
    for ligne in data.get("calcul_du_brut") or []:
        lib = str(ligne.get("libelle", "")).lower()
        if "suppl" not in lib or "structur" in lib:
            continue
        quantite = float(ligne.get("quantite") or 0.0)
        if "50" in lib:
            hs50 += quantite
        else:
            hs25 += quantite
    return round(hs25, 2), round(hs50, 2)


# ------------------------------------------------------------------ bac à sable
def _relever(ids: list[str]) -> dict:
    """Ce que le setup du mois écrit et que l'on remettra : plannings et saisies.
    Les bulletins et les cumuls ne sont pas relevés parce qu'ils ne sont jamais
    touchés — le bac à sable n'écrit pas, et `_verifier_la_chaine_intacte` le prouve."""
    sched = supabase.table("employee_schedules").select("*").in_("employee_id", ids).eq("year", YEAR).execute().data or []
    saisies = supabase.table("monthly_inputs").select("*").in_("employee_id", ids).eq("year", YEAR).execute().data or []
    return {"schedules": sched, "inputs": saisies}


def _remettre(ids: list[str], releve: dict) -> None:
    admin = get_supabase_admin_client()
    for row in releve["schedules"]:
        admin.table("employee_schedules").update(
            {k: v for k, v in row.items() if k not in ("id", "created_at")}
        ).eq("id", row["id"]).execute()
    admin.table("monthly_inputs").delete().in_("employee_id", ids).eq("year", YEAR).execute()
    if releve["inputs"]:
        admin.table("monthly_inputs").insert(releve["inputs"]).execute()
    print(f"  {len(releve['schedules'])} plannings et {len(releve['inputs'])} saisies remis comme relevés")


def _sauver_le_releve(dossier: Path | None, releve: dict, emp_avant: dict, hist_avant: list) -> Path:
    """Le relevé sur disque, pour une remise rejouable par `--remettre-depuis`."""
    base = dossier or (Path(__file__).resolve().parents[2] / "data" / "colorplast" / "releves")
    base.mkdir(parents=True, exist_ok=True)
    chemin = base / f"regulier_releve_{datetime.now():%Y%m%d_%H%M%S}.json"
    chemin.write_text(
        json.dumps({"releve": releve, "emp_avant": emp_avant, "hist_avant": hist_avant},
                   ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return chemin


def _empreinte_de_la_chaine(ids: list[str]) -> dict:
    """Bulletins et cumuls de l'année, tels quels : la chaîne de paie que l'audit
    n'a pas le droit de toucher."""
    bulletins = supabase.table("payslips").select("id, updated_at, pdf_storage_path, origine, payslip_data").in_("employee_id", ids).eq("year", YEAR).execute().data or []
    sched = supabase.table("employee_schedules").select("id, cumuls").in_("employee_id", ids).eq("year", YEAR).execute().data or []
    empreinte = {("bulletin", b["id"]): (b["updated_at"], b["pdf_storage_path"], b["origine"],
                                        json.dumps(b["payslip_data"], sort_keys=True)) for b in bulletins}
    empreinte.update({("cumuls", s["id"]): json.dumps(s["cumuls"], sort_keys=True) for s in sched})
    return empreinte


def _verifier_la_chaine_intacte(avant: dict, apres: dict) -> None:
    touches = sorted(f"{genre} {ident[:8]}" for (genre, ident) in set(avant) | set(apres)
                     if avant.get((genre, ident)) != apres.get((genre, ident)))
    if touches:
        print(f"::error::la chaîne de paie a bougé pendant l'audit : {', '.join(touches)}")
    else:
        print(f"  chaîne de paie intacte : {sum(1 for g, _ in avant if g == 'bulletin')} bulletins "
              f"et {sum(1 for g, _ in avant if g == 'cumuls')} cumuls identiques")


def _generer_en_bac_a_sable(nom: str, emp: dict, mois: int) -> tuple[GeneratePayslipResult, dict]:
    """Calcule le bulletin sans rien écrire ; le mois d'avant vient de la chaîne en mémoire."""
    try:
        res = payslip_generator_provider.generate_en_bac_a_sable(
            emp["id"], YEAR, mois, cumuls_precedents=CHAINE.get(nom)
        )
    except HTTPException as exc:
        raise PayslipBadRequestError(str(exc.detail)) from exc
    CHAINE[nom] = res["cumuls"]
    BULLETINS[(nom.upper().replace(" ", ""), mois)] = res["payslip_data"]
    resultat = GeneratePayslipResult(
        status=res["status"], message=res["message"], download_url=None,
        payslip_id=None, warnings=res.get("warnings") or None,
    )
    return resultat, res["payslip_data"]


def _retirer_les_surcharges_d_entree(emps: dict, mois: int) -> None:
    """Le mois d'entrée se calcule seul : la surcharge posée d'après le bulletin est retirée."""
    admin = get_supabase_admin_client()
    for nom, cfg in MONTH_DATA.get(mois, {}).items():
        if "remuneration_mois_partiel" not in cfg or nom not in emps:
            continue
        if (nom, mois) in GARDER_SURCHARGE:
            print(f"  {nom:10s} : surcharge de mois d'entrée gardée ({YEAR:04d}-{mois:02d}), heures réelles saisies dans Quadra")
            continue
        row = admin.table("employees").select("specificites_paie").eq("id", emps[nom]["id"]).single().execute().data
        sp = copy.deepcopy(row.get("specificites_paie") or {})
        overrides = sp.get("overrides_mensuels") or {}
        cle = f"{YEAR:04d}-{mois:02d}"
        if cle in overrides:
            overrides[cle].pop("remuneration_mois_partiel", None)
            if not overrides[cle]:
                overrides.pop(cle)
            admin.table("employees").update({"specificites_paie": sp}).eq("id", emps[nom]["id"]).execute()
            print(f"  {nom:10s} : surcharge de mois d'entrée retirée ({cle})")


# ------------------------------------------------------------------ un mois
def _imprimer_les_feuilles(mois: int) -> None:
    feuilles = _feuilles_du_mois(mois)
    debut, fin = REFERENCES[mois]["fenetre"]
    print(f"\n=== Feuilles de la fenêtre {debut} → {fin} : total pointé par semaine, règle hebdomadaire, cabinet ===")
    for nom in sorted(feuilles):
        semaines = " ".join(f"S{s}={t:g}" for s, t in heures_par_semaine(feuilles[nom]).items())
        a25, a50 = heures_sup_attendues(feuilles[nom])
        c25, c50 = _payees_par_le_cabinet(nom, mois)
        print(f"  {nom:10s} {semaines:52s} → {a25:5.2f} / {a50:5.2f} (cabinet : {c25:g} / {c50:g})")


def _detail(nom: str, mois: int, data: dict, res) -> dict:
    q25, q50 = _heures_sup_du_bulletin(data)
    feuille = _feuilles_du_mois(mois).get(nom)
    a25, a50 = heures_sup_attendues(feuille) if feuille else (0.0, 0.0)
    c25, c50 = _payees_par_le_cabinet(nom, mois)
    brut = float(data.get("salaire_brut") or 0)
    ref_brut = REFERENCES[mois]["brut"][nom]
    print(f"\n--- {nom:10s} {mois:02d}/{YEAR} : moteur {q25:g} / {q50:g} h sup ; feuilles {a25:g} / {a50:g} ; "
          f"cabinet {c25:g} / {c50:g} ; brut {brut:.2f} (Quadra {ref_brut:.2f}, écart {brut - ref_brut:+.2f}) ; {res.status}")
    lignes = []
    for ligne in data.get("calcul_du_brut") or []:
        lib = str(ligne.get("libelle", ""))
        if ("suppl" in lib.lower() and "structur" not in lib.lower()) or "entrée" in lib.lower() or "sortie" in lib.lower():
            print(f"      brut    {lib[:52]:52s} q={ligne.get('quantite')} +{ligne.get('gain')}")
            lignes.append({"zone": "brut", "libelle": lib, "quantite": ligne.get("quantite"), "gain": ligne.get("gain")})
    for cle in ("details_absences", "details_conges"):
        for ligne in data.get(cle) or []:
            print(f"      {cle[8:15]:7s} {str(ligne.get('libelle'))[:52]:52s} q={ligne.get('quantite')} "
                  f"-{ligne.get('perte')} +{ligne.get('gain')}")
            lignes.append({"zone": cle, "libelle": ligne.get("libelle"), "quantite": ligne.get("quantite"),
                           "perte": ligne.get("perte"), "gain": ligne.get("gain")})
    for w in res.warnings or []:
        print(f"      avertissement : {w}")
    return {"hs_moteur": [q25, q50], "hs_feuilles": [a25, a50], "hs_cabinet": [c25, c50],
            "brut": brut, "brut_quadra": ref_brut, "lignes": lignes, "avertissements": list(res.warnings or [])}


def _jouer_le_mois_a_la_reguliere(emps: dict, mois: int, evenements) -> dict:
    print(f"\n{'=' * 70}\n=== {mois:02d}/{YEAR} : posé par le setup, puis régularisé, puis les feuilles\n{'=' * 70}")
    apply_month("Colorplast", YEAR, mois)
    _retirer_les_surcharges_d_entree(emps, mois)
    salaries = {nom: emps[nom] for nom in _salaries_du_mois(mois) if not SEULEMENT or nom in SEULEMENT}
    reguliers = {n: e for n, e in salaries.items() if (n, mois) not in COMME_QUADRA}
    for nom in sorted(set(salaries) - set(reguliers)):
        print(f"  {nom:10s} : mois laissé sur les entrées de Gaëlle (planning, absences et heures sup du cabinet)")
    print("  -- planning régularisé (classeur du cabinet, feuilles, DSN) --")
    regulariser_le_planning(reguliers, mois, evenements)
    print("  -- feuilles posées, saisies d'heures sup effacées --")
    if mois == 1:
        janvier.FEUILLES["ESPINOSA"][5] = 9.5  # la feuille (44 h), pas la saisie dans Quadra (45 h)
        for (nom, mm, jj), heures in AJUSTEMENTS.items():
            if mm == 1 and nom in janvier.FEUILLES:
                janvier.FEUILLES[nom][jj] = heures
                print(f"  {nom:10s} : {jj:02d}/01 posé à {heures:g} h (ajustement demandé)")
        feuilles_janvier = janvier.FEUILLES
        janvier.FEUILLES = {nom: jours for nom, jours in feuilles_janvier.items() if nom in reguliers}
        try:
            janvier.poser_les_feuilles(reguliers)
        finally:
            janvier.FEUILLES = feuilles_janvier
        for emp in reguliers.values():
            supabase.table("monthly_inputs").delete().match(
                {"employee_id": emp["id"], "year": YEAR, "month": 1}).ilike("name", "%suppl%").execute()
    else:
        poser_les_feuilles(reguliers, mois, _feuilles_du_mois(mois))
    _ramener_a_l_horaire(salaries, mois)
    _poser_la_carence(salaries, mois)
    _poser_les_absences(salaries, mois)
    _poser_les_saisies(salaries, mois)
    resultats = {}
    for nom, emp in salaries.items():
        try:
            res, data = _generer_en_bac_a_sable(nom, emp, mois)
        except PayslipBadRequestError as exc:
            print(f"::error::{nom} {mois:02d}/{YEAR} : {exc}")
            resultats[nom] = {"erreur": str(exc)}
            continue
        resultats[nom] = _detail(nom, mois, data, res)
        _controler(nom, mois, data, res)  # les contrôles du rejeu, à titre d'information
    return resultats


def main() -> int:
    apply = "--apply" in sys.argv
    dernier = int(sys.argv[sys.argv.index("--jusqu-a") + 1]) if "--jusqu-a" in sys.argv else max(MOIS_REGULIERS)
    dossier = Path(sys.argv[sys.argv.index("--json-dir") + 1]) if "--json-dir" in sys.argv else None
    if "--remettre-depuis" in sys.argv:
        chemin = Path(sys.argv[sys.argv.index("--remettre-depuis") + 1])
        sauvegarde = json.loads(chemin.read_text(encoding="utf-8"))
        print(f"=== Remise en état depuis {chemin} ===")
        _remettre(list(sauvegarde["emp_avant"]), sauvegarde["releve"])
        _restaurer(sauvegarde["emp_avant"], sauvegarde["hist_avant"])
        return 0
    mois_joues = [m for m in MOIS_REGULIERS if m <= dernier]
    for i, arg in enumerate(sys.argv):
        if arg == "--seulement":
            j = i + 1
            while j < len(sys.argv) and not sys.argv[j].startswith("--"):
                SEULEMENT.add(sys.argv[j].upper())
                j += 1
        if arg == "--saisie":
            nom, reste = sys.argv[i + 1].split(":")
            mm, montant = reste.split("=")
            SAISIES_POSEES[(nom.upper(), int(mm))] = float(montant)
        if arg == "--absence":
            nom, reste = sys.argv[i + 1].split(":")
            date_, heures = reste.split("=")
            mm, jj = (int(x) for x in date_.split("-"))
            ABSENCES_POSEES[(nom.upper(), mm, jj)] = float(heures)
        if arg == "--comme-quadra":
            nom, mm = sys.argv[i + 1].split(":")
            COMME_QUADRA.add((nom.upper(), int(mm)))
        if arg == "--maintien-prevoyance":
            nom, reste = sys.argv[i + 1].split(":")
            mm, montant = reste.split("=")
            MAINTIEN_PREVOYANCE[(nom.upper(), int(mm))] = float(montant)
        if arg == "--garder-surcharge":
            nom, mm = sys.argv[i + 1].split(":")
            GARDER_SURCHARGE.add((nom.upper(), int(mm)))
        if arg == "--sans-heures-sup":
            nom, mm = sys.argv[i + 1].split(":")
            SANS_HEURES_SUP.add((nom.upper(), int(mm)))
        if arg == "--ajuster":
            nom, reste = sys.argv[i + 1].split(":")
            date_, heures = reste.split("=")
            mm, jj = (int(x) for x in date_.split("-"))
            AJUSTEMENTS[(nom.upper(), mm, jj)] = float(heures)
    if SEULEMENT:
        print("Seulement :", ", ".join(sorted(SEULEMENT)))
    if SAISIES_POSEES:
        print("Saisies au brut :", ", ".join(f"{n} {m:02d}/2026 = {v:+.2f} €" for (n, m), v in sorted(SAISIES_POSEES.items())))
    if ABSENCES_POSEES:
        print("Journées non payées posées :", ", ".join(f"{n} {j:02d}/{m:02d} = {h:g} h" for (n, m, j), h in sorted(ABSENCES_POSEES.items())))
    if COMME_QUADRA:
        print("Entrées de Gaëlle gardées :", ", ".join(f"{n} {m:02d}/2026" for n, m in sorted(COMME_QUADRA)))
    if MAINTIEN_PREVOYANCE:
        print("Carence seule :", ", ".join(f"{n} {m:02d}/2026 = {v:.2f} €" for (n, m), v in sorted(MAINTIEN_PREVOYANCE.items())))
    if SANS_HEURES_SUP:
        print("Sans heure sup :", ", ".join(f"{n} {m:02d}/2026" for n, m in sorted(SANS_HEURES_SUP)))
    if AJUSTEMENTS:
        print("Ajustements demandés :", ", ".join(f"{n} {j:02d}/{m:02d} → {h:g} h" for (n, m, j), h in AJUSTEMENTS.items()))
    for mois in mois_joues:
        _imprimer_les_feuilles(mois)
    print("\n=== Lectures douteuses ===")
    for inc in INCERTITUDES:
        print(f"  - {inc}")
    if not apply:
        print("\nSIMULATION : rien n'est écrit. Avec --apply, les mois sont calculés en bac à sable depuis ces "
              "sources (fiches, plannings et saisies posés puis remis ; bulletins et cumuls jamais touchés).")
        return 0

    emps = {
        e["last_name"]: e
        for e in (supabase.table("employees").select("id, last_name")
                  .eq("company_id", COMPANY_ID).in_("last_name", list(SALARIES)).execute()).data or []
    }
    ids = [e["id"] for e in emps.values()]
    evenements = lire_le_classeur(7)
    emp_avant, hist_avant = _snapshot(ids)
    releve = _relever(ids)
    chaine_avant = _empreinte_de_la_chaine(ids)
    chemin_releve = _sauver_le_releve(dossier, releve, emp_avant, hist_avant)
    print(f"  relevé écrit dans {chemin_releve} — en cas d'arrêt brutal : --remettre-depuis {chemin_releve}")
    maintien_avant = _couper_le_maintien_legal() if MAINTIEN_PREVOYANCE else None
    maintien_coupe = bool(MAINTIEN_PREVOYANCE)
    print(f"\n=== Relevé : {len(releve['schedules'])} plannings, {len(releve['inputs'])} saisies ; "
          f"{sum(1 for g, _ in chaine_avant if g == 'bulletin')} bulletins en ligne, jamais touchés ===")
    resume: dict = {}
    comparaisons: dict = {}
    try:
        _nettoyer_les_doublons_du_cabinet(emps, mois_joues)
        for mois in mois_joues:
            resume[mois] = _jouer_le_mois_a_la_reguliere(emps, mois, evenements)
        print(f"\n{'=' * 70}\n=== Comparaison ligne à ligne avec les bulletins Quadra\n{'=' * 70}")
        eywai = dict(BULLETINS)
        for mois in mois_joues:
            comparaisons[mois] = comparer_le_mois(YEAR, mois, eywai)
            imprimer(mois, comparaisons[mois])
    finally:
        print(f"\n{'=' * 70}\n=== Remise en état\n{'=' * 70}")
        _remettre(ids, releve)
        _restaurer(emp_avant, hist_avant)
        _verifier_la_chaine_intacte(chaine_avant, _empreinte_de_la_chaine(ids))
        if maintien_coupe:
            _remettre_le_maintien_legal(maintien_avant)
        if dossier:
            dossier.mkdir(parents=True, exist_ok=True)
            json.dump(resume, open(dossier / "regulier_resume.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            for mois, res in comparaisons.items():
                json.dump(res, open(dossier / f"regulier_{mois:02d}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"  résultats écrits dans {dossier}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
