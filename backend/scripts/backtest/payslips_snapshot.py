"""Sauvegarde / restauration des lignes `payslips` d'une société pour un mois.

Filet de sécurité avant de régénérer un mois clos d'une autre société pour
vérifier la non-régression d'un changement moteur (règle : un mois convergé
ne se régénère pas sans sauvegarde).

Usage:
    payslips_snapshot.py <Company> <year> <month> --save    [--dir D]
    payslips_snapshot.py <Company> <year> <month> --restore [--dir D]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/Users/alex/Desktop/EYWAI/EYWAI/backend")
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import resolve_company_id

company = sys.argv[1]; year = int(sys.argv[2]); month = int(sys.argv[3])
mode = "--restore" if "--restore" in sys.argv else "--save"
out_dir = Path(sys.argv[sys.argv.index("--dir") + 1]) if "--dir" in sys.argv else Path(
    "/private/tmp/claude-501/-Users-alex-Desktop-EYWAI-EYWAI/6fc59a3b-d7ec-44b9-864f-d43099c7a14a/scratchpad"
)
out_dir.mkdir(parents=True, exist_ok=True)
path = out_dir / f"payslips_{company.lower().replace(' ', '_')}_{year}-{month:02d}.json"

admin = get_supabase_admin_client()
cid = resolve_company_id(company)

if mode == "--save":
    rows = (admin.table("payslips").select("*").eq("company_id", cid)
            .eq("year", year).eq("month", month).execute().data)
    json.dump(rows, open(path, "w"), default=str)
    print(f"{len(rows)} bulletins sauvegardés -> {path}")
else:
    rows = json.load(open(path))
    n = 0
    for r in rows:
        payload = {k: r[k] for k in ("payslip_data", "generated_at", "updated_at", "status",
                                     "manually_edited", "edit_count", "edited_at", "edit_history",
                                     "pdf_storage_path", "url", "file_path", "name") if k in r}
        admin.table("payslips").update(payload).eq("id", r["id"]).execute()
        n += 1
    print(f"{n} bulletins restaurés depuis {path}")
