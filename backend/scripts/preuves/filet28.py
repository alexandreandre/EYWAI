"""Lot 28 : filet3 du lot 26, dont l'enrichissement rejoue aussi les prêts (en
mémoire) et garde les alertes de saisie plafonnée et de prêt retenu en partie.

Tous les bulletins 2026 des sociétés réelles, recalculés en bac à sable sous piège
à écritures, avec la vue imprimée, puis l'enrichissement d'après enregistrement
(saisies, avances, prêts) rejoué en mémoire (sans identifiant de bulletin : ni
historique ni reste dû écrits).

Le barème de la quotité saisissable est injecté tel que la migration
20261011150000 le pose, pour les deux copies.

Usage (depuis le backend à tester) :
    PYTHONPATH=. <venv>/bin/python scripts/preuves/filet28.py <sortie.json> [Société ...]
"""
from __future__ import annotations

import copy
import json
import sys
import time

from scripts.verification_rgdu import piege

piege.poser_le_piege()

import postgrest._sync.client as _pc  # noqa: E402

_RPC: list[str] = []


def _rpc_interdit(self, fn, *a, **k):
    _RPC.append(fn)
    piege.ECRITURES.append(f"rpc {fn}")
    raise piege.EcritureInterdite(f"rpc interdit : {fn}")


_pc.SyncPostgrestClient.rpc = _rpc_interdit

from app.core.database import get_supabase_admin_client  # noqa: E402
from app.modules.payroll.documents.bulletin_view import construire_vue_bulletin  # noqa: E402
from app.modules.payslips.infrastructure.providers import payslip_generator_provider  # noqa: E402
from app.modules.saisies_avances.application import service as saisies_service  # noqa: E402
from app.modules.employee_loans.application import enrichment as prets  # noqa: E402

# Les prêts suspendus passeraient leur échéance en « skipped » (écriture) : sans
# effet sur le bulletin, la marque n'est pas rejouée.
prets.process_suspended_loan_installments = lambda *a, **k: None

SOCIETES = ("Colorplast", "Comitech Composite", "MAJI", "Zone 404 Mars")
TABLES_TOLEREES = ("employee_cp_seniority_grants", "salary_advances")
CODES_ALERTES = ("quotite_saisissable", "saisie_sur_salaire_plafonnee", "pret_employeur_retenue_partielle")

BAREME_MIGRATION = {
    "par_annee": {
        "2026": {
            "tranches": [
                {"jusqu_a_annuel": 4480, "fraction": "1/20"},
                {"jusqu_a_annuel": 8730, "fraction": "1/10"},
                {"jusqu_a_annuel": 13000, "fraction": "1/5"},
                {"jusqu_a_annuel": 17230, "fraction": "1/4"},
                {"jusqu_a_annuel": 21470, "fraction": "1/3"},
                {"jusqu_a_annuel": 25810, "fraction": "2/3"},
                {"jusqu_a_annuel": None, "fraction": "1"},
            ],
            "majoration_annuelle_par_personne_a_charge": 1740,
        }
    },
    "solde_insaisissable": [
        {"date_debut": "2025-04-01", "montant_mensuel": 646.52},
        {"date_debut": "2026-04-01", "montant_mensuel": 651.69},
    ],
}
if hasattr(saisies_service, "get_bareme_quotite_saisissable"):
    saisies_service.get_bareme_quotite_saisissable = lambda: copy.deepcopy(BAREME_MIGRATION)


def plan(client, societes):
    comps = client.table("companies").select("id, company_name").in_("company_name", list(societes)).execute().data
    noms = {c["id"]: c["company_name"] for c in comps}
    pays = (
        client.table("payslips").select("employee_id, company_id, year, month")
        .in_("company_id", list(noms)).eq("year", 2026).execute().data
    )
    return sorted({(noms[p["company_id"]], p["employee_id"], int(p["month"])) for p in pays})


def _avec_relectures(fn, essais=4):
    for essai in range(essais):
        try:
            return fn()
        except piege.EcritureInterdite:
            raise
        except Exception as exc:  # noqa: BLE001 — réseau
            if essai == essais - 1:
                raise
            print(f"  relecture après {type(exc).__name__}: {str(exc)[:120]}", flush=True)
            time.sleep(5 * (essai + 1))


def cumuls_du_mois_d_avant(client, eid, mois):
    an, m = (2026, mois - 1) if mois > 1 else (2025, 12)
    r = _avec_relectures(lambda: (
        client.table("employee_schedules").select("cumuls")
        .match({"employee_id": eid, "year": an, "month": m}).execute().data
    ))
    return (r[0].get("cumuls") if r else None) or None


def enrichissement(pdata, eid, mois):
    """L'enrichissement d'après enregistrement, en mémoire (payslip_id=None) :
    saisies et avances, puis prêts."""
    if not isinstance(pdata, dict):
        return None
    try:
        enrichi = _avec_relectures(
            lambda: saisies_service.enrich_payslip(copy.deepcopy(pdata), eid, 2026, mois, payslip_id=None)
        )
    except piege.EcritureInterdite:
        raise
    except Exception as exc:  # noqa: BLE001
        return {"erreur": f"{type(exc).__name__}: {str(exc)[:200]}"}
    erreur_prets = None
    try:
        enrichi = _avec_relectures(
            lambda: prets.enrich_payslip_loans(copy.deepcopy(enrichi), eid, 2026, mois, payslip_id=None)
        )
    except piege.EcritureInterdite:
        raise
    except Exception as exc:  # noqa: BLE001
        erreur_prets = f"{type(exc).__name__}: {str(exc)[:200]}"
    return {
        "net_a_payer": enrichi.get("net_a_payer"),
        "retenues_saisies": enrichi.get("retenues_saisies"),
        "remboursements_avances": enrichi.get("remboursements_avances"),
        "remboursements_prets": enrichi.get("remboursements_prets"),
        "erreur_prets": erreur_prets,
        "alertes": [a for a in enrichi.get("alertes_baremes") or [] if a.get("code") in CODES_ALERTES],
    }


def main(sortie: str, societes) -> int:
    client = get_supabase_admin_client()
    taches = plan(client, societes)
    print(f"{len(taches)} bulletins à rejouer", flush=True)
    resultats = {}
    t0 = time.time()
    for i, (soc, eid, mois) in enumerate(taches, 1):
        avant = len(piege.ECRITURES)
        cumuls = cumuls_du_mois_d_avant(client, eid, mois)
        cle = f"{soc}|{eid}|{mois}"
        try:
            res = None
            for essai in range(3):
                try:
                    res = payslip_generator_provider.generate_en_bac_a_sable(eid, 2026, mois, cumuls)
                    break
                except Exception as exc:  # noqa: BLE001
                    texte = f"{type(exc).__name__}: {exc}"
                    reseau = any(m in texte for m in ("Connect", "Timeout", "RemoteProtocol", "ReadError",
                                                      "illisible", "connexion", "Server disconnected"))
                    if not reseau or essai == 2:
                        raise
                    print(f"  nouvel essai après {texte[:120]}", flush=True)
                    time.sleep(5 * (essai + 1))
            pdata = res.get("payslip_data")
            try:
                vue = construire_vue_bulletin(pdata) if isinstance(pdata, dict) else None
            except Exception as exc:  # noqa: BLE001
                vue = {"erreur_vue": f"{type(exc).__name__}: {exc}"}
            resultats[cle] = {
                "statut": "ok",
                "payslip_data": pdata,
                "cumuls": res.get("cumuls"),
                "vue": vue,
                "enrichissement": enrichissement(pdata, eid, mois),
            }
        except Exception as exc:  # noqa: BLE001
            resultats[cle] = {"statut": "erreur", "erreur": f"{type(exc).__name__}: {str(exc)[:300]}"}
        nouvelles = piege.ECRITURES[avant:]
        resultats[cle]["ecritures"] = nouvelles
        interdites = [e for e in nouvelles if not any(e.endswith(f" {t}") for t in TABLES_TOLEREES)]
        print(f"[{i}/{len(taches)}] {soc[:10]} m{mois} {resultats[cle]['statut']}"
              + (f" écritures {nouvelles}" if nouvelles else ""), flush=True)
        if interdites:
            print(f"ARRÊT : écriture tentée hors de {TABLES_TOLEREES} : {interdites}", flush=True)
            with open(sortie, "w", encoding="utf-8") as f:
                json.dump(resultats, f, ensure_ascii=False, default=str, sort_keys=True)
            return 2
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, default=str, sort_keys=True)
    ok = sum(1 for v in resultats.values() if v["statut"] == "ok")
    print(f"terminé : {ok}/{len(resultats)} ok en {time.time() - t0:.0f} s ; ECRITURES {sorted(set(piege.ECRITURES))}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], tuple(sys.argv[2:]) or SOCIETES))
