"""Octobre 2026 au bac à sable, sous piège à écritures : chaque salarié actif d'une société.

Usage (depuis un backend copié) : PYTHONPATH=. python octobre.py <sortie.json> "<Société>"
"""
from __future__ import annotations
import json, sys, time
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import filet28 as F  # pose le piège et les remplacements du filet
from app.core.database import get_supabase_admin_client

def main(sortie, societe):
    client = get_supabase_admin_client()
    cid = client.table("companies").select("id").eq("company_name", societe).execute().data[0]["id"]
    emps = client.table("employees").select("id, hire_date, employment_status").eq("company_id", cid).range(0, 999).execute().data
    cibles = [e["id"] for e in emps if e["employment_status"] in ("actif", "en_sortie") and (e.get("hire_date") or "") <= "2026-10-31"]
    res = {}
    for i, eid in enumerate(cibles, 1):
        avant = len(F.piege.ECRITURES)
        try:
            cumuls = F.cumuls_du_mois_d_avant(client, eid, 10)
            r = F.payslip_generator_provider.generate_en_bac_a_sable(eid, 2026, 10, cumuls)
            p = r.get("payslip_data") or {}
            res[eid] = {"statut": "ok", "net": p.get("net_a_payer"), "brut": p.get("salaire_brut"),
                        "cumul_septembre": cumuls is not None,
                        "alertes": [ (a.get("niveau") or a.get("level") or "", a.get("code") or "", str(a.get("message") or "")[:160]) for a in (p.get("alertes_baremes") or []) if isinstance(a, dict)],
                        "enrichissement": F.enrichissement(p, eid, 10)}
        except Exception as exc:  # noqa: BLE001
            res[eid] = {"statut": "erreur", "erreur": f"{type(exc).__name__}: {str(exc)[:300]}"}
        nouvelles = F.piege.ECRITURES[avant:]
        res[eid]["ecritures"] = nouvelles
        interdites = [e for e in nouvelles if not any(e.endswith(f" {t}") for t in F.TABLES_TOLEREES)]
        print(f"[{i}/{len(cibles)}] {res[eid]['statut']}", flush=True)
        if interdites:
            print("ARRÊT écriture", interdites); break
    json.dump(res, open(sortie, "w"), ensure_ascii=False, default=str)

main(sys.argv[1], sys.argv[2])
