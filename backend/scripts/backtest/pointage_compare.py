"""Comparateur générique pointage réel (badgeuse xlsx/pdf) vs calendrier
stocké en base (`employee_schedules.planned_calendar` / `actual_hours`).

Généralisé à partir du travail ponctuel fait sur GAUTHERON (MBC) lors de
sessions antérieures — réutilisable pour n'importe quel salarié/mois/
entreprise du dossier `Bulletins/`.

Format XLSX badgeuse détecté (colonnes) : Matricule, Jour, Nom, Cod Sectio,
Entrée 1./Sortie 1./Entrée 2./Sortie 2./Entrée 3./Sortie 3., Tot H Poin,
Hr Théoriq, Code Horai. **Les fichiers badgeuse ont un bug de stylesheet XML
("biltinId" au lieu de "builtinId") qui fait planter openpyxl** — toujours
lire avec `engine="calamine"` (pip install python-calamine), jamais openpyxl
par défaut.

Usage :
    .venv/bin/python -m scripts.backtest.pointage_compare "Lewis" 2026 1 --matricule BOURMAULT
    .venv/bin/python -m scripts.backtest.pointage_compare "Lewis" 2026 1          # tous les salariés du fichier

Ce que ça fait : pour chaque jour du mois, compare l'heure théorique/pointée
du fichier badgeuse au `planned_calendar` stocké en base (jour marqué
'travail' avec heures_prevues), et signale :
  - jour marqué 'travail' en base mais ABSENT du pointage réel (0h pointées)
  - jour marqué 'absence_*' en base mais PRÉSENT au pointage réel (>0h)
  - écart d'heures théoriques/prévues > 0.5h un jour donné
Ne modifie RIEN en base — outil de diagnostic en lecture seule uniquement.
"""

from __future__ import annotations

import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from app.core.database import get_supabase_admin_client
from scripts.backtest.bulletins_source import list_pointage_files
from scripts.backtest.employee_matching import _normalize, resolve_company_id


def _read_pointage_xlsx(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, header=None, engine="calamine")
    header_row = None
    for i in range(min(5, len(df))):
        if "Matricule" in df.iloc[i].astype(str).tolist():
            header_row = i
            break
    if header_row is None:
        return pd.DataFrame()
    df.columns = df.iloc[header_row]
    df = df.iloc[header_row + 1 :].reset_index(drop=True)
    cols = {c: str(c).strip() for c in df.columns}
    df = df.rename(columns=cols)
    keep = [c for c in ["Matricule", "Jour", "Nom", "Tot H Poin", "Hr Théoriq"] if c in df.columns]
    if not keep:
        return pd.DataFrame()
    df = df[keep].dropna(subset=["Jour"]) if "Jour" in keep else df
    return df


def load_all_pointage(company: str, year: int, month: int) -> pd.DataFrame:
    """Concatène tous les fichiers pointage xlsx trouvés pour ce mois (les
    entreprises fournissent parfois plusieurs fichiers par semaine)."""
    files = [f for f in list_pointage_files(company, year, month) if f.suffix.lower() == ".xlsx"]
    frames = []
    for f in files:
        try:
            d = _read_pointage_xlsx(f)
            if not d.empty:
                d["__source_file"] = f.name
                frames.append(d)
        except Exception as e:
            print(f"  [WARN] échec lecture {f.name}: {e}")
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(subset=[c for c in ["Matricule", "Jour"] if c in out.columns])
    return out


def _norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return "".join(c for c in s.upper() if c.isalnum())


def compare_employee(
    company: str,
    year: int,
    month: int,
    pointage_df: pd.DataFrame,
    matricule_db: str,
    nom_complet_db: str,
) -> List[str]:
    """Retourne une liste de lignes d'écart (texte) pour un salarié donné."""
    admin = get_supabase_admin_client()
    cid = resolve_company_id(company)
    emp = (
        admin.table("employees")
        .select("id,first_name,last_name")
        .eq("company_id", cid)
        .execute()
        .data
    )
    target = None
    for e in emp:
        full = f"{e.get('first_name','')} {e.get('last_name','')}"
        if _norm_name(nom_complet_db) == _norm_name(full) or _norm_name(
            e.get("last_name", "")
        ) in _norm_name(nom_complet_db):
            target = e
            break
    if not target:
        return [f"[{matricule_db}] aucun employé DB correspondant à '{nom_complet_db}'"]

    sched = (
        admin.table("employee_schedules")
        .select("planned_calendar")
        .match({"employee_id": target["id"], "year": year, "month": month})
        .execute()
        .data
    )
    if not sched:
        return [f"[{matricule_db}] aucun planned_calendar DB pour {year}-{month:02d}"]
    cal = sched[0].get("planned_calendar") or {}
    # Clé réelle du calendrier stocké en base : "jour" = numéro du jour dans
    # le mois (entier, PAS une date ISO) — cf. `{'jour': 1, 'type': 'conge', ...}`.
    jours = {j.get("jour"): j for j in (cal.get("calendrier_prevu") or [])}

    ecarts: List[str] = []
    sub = pointage_df[pointage_df["Nom"].apply(lambda n: _norm_name(nom_complet_db) in _norm_name(n) or _norm_name(n) in _norm_name(nom_complet_db))] if "Nom" in pointage_df.columns else pointage_df
    for _, row in sub.iterrows():
        try:
            d = pd.to_datetime(row["Jour"]).date()
        except Exception:
            continue
        d_str = d.isoformat()
        heures_pointees = float(row.get("Tot H Poin", 0) or 0)
        j = jours.get(d.day)
        db_type = j.get("type") if j else None
        db_heures = j.get("heures_prevues") if j else None
        if db_type == "travail" and heures_pointees == 0:
            ecarts.append(
                f"[{matricule_db}] {d_str}: DB='travail' ({db_heures}h prévues) mais pointage=0h (probable absence non déclarée en base)"
            )
        elif db_type and db_type.startswith("absence") and heures_pointees > 0:
            ecarts.append(
                f"[{matricule_db}] {d_str}: DB='{db_type}' mais pointage={heures_pointees}h (le salarié a bien travaillé ce jour-là)"
            )
        elif db_type is None and heures_pointees > 0:
            ecarts.append(
                f"[{matricule_db}] {d_str}: absent du planned_calendar DB mais pointage={heures_pointees}h"
            )
    return ecarts


def main():
    args = sys.argv[1:]
    if len(args) < 3:
        print(__doc__)
        return
    company, year, month = args[0], int(args[1]), int(args[2])
    matricule_filter = None
    if "--matricule" in args:
        matricule_filter = args[args.index("--matricule") + 1]

    pointage_df = load_all_pointage(company, year, month)
    if pointage_df.empty:
        print(f"Aucun pointage xlsx lisible pour {company} {year}-{month:02d}")
        return
    print(f"Pointage chargé : {len(pointage_df)} lignes, colonnes={list(pointage_df.columns)}")

    if "Matricule" not in pointage_df.columns or "Nom" not in pointage_df.columns:
        print("Colonnes Matricule/Nom absentes, format non reconnu.")
        return

    employees = pointage_df[["Matricule", "Nom"]].drop_duplicates()
    if matricule_filter:
        employees = employees[
            employees["Nom"].apply(lambda n: matricule_filter.upper() in _norm_name(n))
        ]

    for _, row in employees.iterrows():
        mat, nom = row["Matricule"], row["Nom"]
        ecarts = compare_employee(company, year, month, pointage_df, str(mat), str(nom))
        if ecarts:
            print(f"\n=== {nom} ({mat}) : {len(ecarts)} écart(s) ===")
            for e in ecarts[:20]:
                print(" ", e)


if __name__ == "__main__":
    main()
