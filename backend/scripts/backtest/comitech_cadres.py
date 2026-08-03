#!/usr/bin/env python3
"""Config data-driven des CADRES Comitech (non gérés par comitech_setup, qui ne
traite que la liste HEURES). Rend reproductible la config cadre sur tous les mois.

PERMANENT (specificites_paie) — posé une fois, vaut pour tous les mois :
  - prévoyance cadre TA (brut_plafonne 0.365%/1.825%) + TB (tranche_2 1.14%/1.709%)
  - retraite supplémentaire "Supplémentaire" (brut_plafonne 2.5%/2.5%) = la ligne qui
    débloque les cadres (cf. mémoire backtest-comitech-2026 : décodage des cadres au centime)
  - mutuelle isolée GAN (EMU3), part patronale non réintégrée impôt

MENSUEL (monthly_inputs, marqués CADRE_MARKER -> idempotents) — auto-dérivés du bulletin :
  - "GAN MUTUELLE FAMILLE" -98.12 (net-only) si ligne SMU2 présente
  - "Indemnité de transport" +X (net-only) si ligne STRA présente
  - "Maintien de salaire" +X (taxable) si ligne présente [arrêt : approx, cf. KNOWN_GAP]

NE gère PAS : paternité forfait (réduction base cotis -> chantier moteur).

Usage: .venv/bin/python -m scripts.backtest.comitech_cadres --month 2 [--emp NOM]
"""
from __future__ import annotations

import argparse
import copy
import re
import subprocess
from typing import Dict, List, Optional, Tuple

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import resolve_company_id
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from scripts.donnees_nominatives import charger_ou_vide

COMPANY = "Comitech Composite"
MUT_ISOLE_ID = "d7131a63-7fef-417b-bb5d-f0e6081e457d"
CADRE_MARKER = "BACKTEST_CADRE_COMITECH"

_CFG_CADRES = charger_ou_vide("comitech", "backtest-cadres") or {}

# Cadres avec prévoyance CADRE + retraite supplémentaire (EPR1/EPR2).
# Listes et salaires nominatifs lus hors dépôt Git
# (data/comitech/referentiel/backtest-cadres.json).
CADRE_PREV = list(_CFG_CADRES.get("cadres", []))
CADRE_BASE = {k: tuple(v) for k, v in _CFG_CADRES.get("base_par_periode", {}).items()}


PREV_LIGNES = [
    {"id": "prev_ta", "base": "brut_plafonne", "libelle": "Prévoyance cadre TA (import DSN)",
     "salarial": 0.00365, "patronal": 0.01825},
    {"id": "prev_tb", "base": "tranche_2", "libelle": "Prévoyance cadre TB (import DSN)",
     "salarial": 0.0114, "patronal": 0.01709},
    {"id": "retraite_supp_dsn", "base": "brut_plafonne",
     "libelle": "Retraite supplémentaire (import DSN)", "salarial": 0.025, "patronal": 0.025},
]

# Strict : PAS d'espace intra-nombre -> ne traverse pas les colonnes -layout ni le
# "2025" de "Participation 2025  3502.71" (montants Comitech < 10 000, sans séparateur).
_NUM = re.compile(r"-?\d+\.\d{2}")


def _layout(pdf: str) -> List[str]:
    out = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True)
    return out.stdout.split("\n")


def _segment(lines: List[str], mat: str) -> List[str]:
    """Lignes du bulletin d'un matricule (jusqu'au prochain 'Matricule :')."""
    start = None
    for i, ln in enumerate(lines):
        if re.search(rf"Matricule\s*:\s*{re.escape(mat)}\b", ln):
            start = i
            break
    if start is None:
        return []
    seg = [lines[start]]
    for ln in lines[start + 1:]:
        if re.search(r"Matricule\s*:\s*\w", ln) and mat not in ln:
            break
        seg.append(ln)
    return seg


def _first_amount(seg: List[str], frag: str) -> Optional[float]:
    for ln in seg:
        if frag.lower() in ln.lower():
            nums = _NUM.findall(ln)
            if nums:
                return round(float(nums[0].replace(" ", "")), 2)
    return None


_HDR = re.compile(r"Rubriques.*Montant salarial.*Mt patronal")


def _col_zone(seg: List[str]) -> Optional[tuple]:
    """(début, fin) de la colonne 'Montant salarial' — pour ne PAS capter la barre
    latérale droite (Plafond Sécu, SMIC, Bruts) qui colle ses nombres en fin de ligne."""
    for ln in seg:
        if _HDR.search(ln):
            return ln.index("Montant salarial"), ln.index("Mt patronal")
    return None


def _montant_zone(seg: List[str], label: str) -> Optional[float]:
    """Nombre de la ligne `label` situé dans la colonne 'Montant salarial'."""
    z = _col_zone(seg)
    if z is None:
        return None
    for ln in seg:
        if label in ln:
            cands = [m for m in _NUM.finditer(ln) if z[0] <= m.end() <= z[1] + 4]
            if cands:
                return round(float(cands[-1].group(0).replace(" ", "")), 2)
    return None


def _salaire_de_base(seg: List[str]) -> Optional[float]:
    """Montant 'SALAIRE DE BASE' via la colonne Montant salarial (robuste sidebar +
    heures-cadre taux×151.67h vs forfait valeur directe)."""
    return _montant_zone(seg, "SALAIRE DE BASE")


def _first_pos(seg: List[str], frag: str) -> Optional[float]:
    """Premier nombre POSITIF de la 1re ligne contenant `frag` (montant en tête,
    avant la barre latérale) — pour participation (montant = 1er nombre)."""
    for ln in seg:
        if frag.lower() in ln.lower():
            for m in _NUM.finditer(ln):
                v = round(float(m.group(0).replace(" ", "")), 2)
                if v > 0:
                    return v
    return None


def _ensure_permanent(admin, cid, mat, month, base_val=None) -> str:
    r = (admin.table("employees").select("id,specificites_paie,salaire_de_base")
         .eq("company_id", cid).eq("matricule", mat).execute().data)
    if not r:
        return "absent"
    e = r[0]
    # Base lue du bulletin du mois (champ salaire_de_base PARTAGÉ -> flip mensuel).
    if base_val is not None:
        sdb = copy.deepcopy(e.get("salaire_de_base") or {"type": "mensuel"})
        if abs(float(sdb.get("valeur") or 0) - base_val) > 0.005:
            sdb["type"] = sdb.get("type", "mensuel"); sdb["valeur"] = base_val
            admin.table("employees").update({"salaire_de_base": sdb}).eq("id", e["id"]).execute()
    sp = copy.deepcopy(e.get("specificites_paie") or {})
    prev = sp.get("prevoyance") or {}
    lignes = prev.get("lignes_specifiques") or []
    have = {l.get("id") for l in lignes}
    changed = False
    for pl in PREV_LIGNES:
        # Brut < plafond -> pas de TB (mais inoffensif : tranche_2=0 -> montant 0).
        if pl["id"] not in have:
            lignes.append(copy.deepcopy(pl)); changed = True
    if changed:
        prev["adhesion"] = True
        prev["lignes_specifiques"] = lignes
        sp["prevoyance"] = prev
    # Mutuelle : tous les cadres ont la GAN ISOLÉ (EMU3 29.24) au bulletin, PAS la
    # mutuelle "Cadre" (170.46). un cadre était mal câblé sur ebdb6e04 -> -139.23 fixe.
    # Réintégration part patronale à l'impôt : démarre AVRIL (cf. HEURES) -> month-aware.
    reintegree = month >= 4
    mut = sp.get("mutuelle") or {}
    want = {"adhesion": True, "pack_couverture": "isole",
            "mutuelle_type_ids": [MUT_ISOLE_ID], "lignes_specifiques": [],
            "part_patronale_reintegree_impot": reintegree}
    if mut != want:
        sp["mutuelle"] = want
        changed = True
    if changed:
        admin.table("employees").update({"specificites_paie": sp}).eq("id", e["id"]).execute()
    return "ok" + ("(+cfg)" if changed else "")


# Noms gérés par ce script : purgés avant réinsertion (idempotent), même sans marqueur
# -> absorbe les ajouts manuels/pré-existants d'une session antérieure (pas de doublon).
_MANAGED_NAMES = ["GAN MUTUELLE FAMILLE", "Indemnité de transport", "Maintien de salaire",
                  "Participation 2025", "Avance participation", "Prime exceptionnelle"]


def _clear_cadre_inputs(admin, eid, year, month):
    existing = (admin.table("monthly_inputs").select("id,name,description")
                .match({"employee_id": eid, "year": year, "month": month}).execute().data or [])
    ids = [r["id"] for r in existing
           if (CADRE_MARKER in (r.get("description") or ""))
           or any(n.lower() in (r.get("name") or "").lower() for n in _MANAGED_NAMES)]
    for i in ids:
        admin.table("monthly_inputs").delete().eq("id", i).execute()


def _add(admin, eid, cid, year, month, name, amount, taxed, taxable):
    admin.table("monthly_inputs").insert({
        "employee_id": eid, "company_id": cid, "year": year, "month": month,
        "name": name, "description": f"Cadre Comitech {month:02d}/{year} {CADRE_MARKER}",
        "amount": amount, "is_socially_taxed": taxed, "is_taxable": taxable,
    }).execute()


def apply_month(year: int, month: int, only: Optional[List[str]] = None):
    admin = get_supabase_admin_client()
    cid = resolve_company_id(COMPANY)
    pdf = resolve_bulletin_pdf(COMPANY, year, month)
    lines = _layout(pdf)
    targets = only or CADRE_PREV
    for mat in targets:
        seg = _segment(lines, mat)
        base_val = _salaire_de_base(seg) if seg else None
        st = _ensure_permanent(admin, cid, mat, month, base_val=base_val)
        if st == "absent":
            print(f"[{mat}] absent en DB"); continue
        r = admin.table("employees").select("id").eq("company_id", cid).eq("matricule", mat).execute().data
        eid = r[0]["id"]
        if not seg:
            print(f"[{mat}] {st} — pas au bulletin {month:02d} (parti ?)"); continue
        _clear_cadre_inputs(admin, eid, year, month)
        added = [f"base={base_val}"]
        fam = _first_amount(seg, "GAN MUTUELLE FAMILLE")
        if fam is not None and fam < 0:
            _add(admin, eid, cid, year, month, "GAN MUTUELLE FAMILLE", fam, False, False)
            added.append(f"fam={fam}")
        tra = _first_amount(seg, "Indemnité de transport")
        if tra is not None and 0 < tra < 500:
            _add(admin, eid, cid, year, month, "Indemnité de transport", tra, False, False)
            added.append(f"transport={tra}")
        mnt = _first_amount(seg, "Maintien de salaire")
        if mnt is not None and mnt > 0:
            _add(admin, eid, cid, year, month, "Maintien de salaire", mnt, True, True)
            added.append(f"maintien={mnt}")
        # Prime exceptionnelle (BPA) : taxable.
        pex = _first_amount(seg, "Prime exceptionnelle")
        if pex is not None and pex > 0:
            _add(admin, eid, cid, year, month, "Prime exceptionnelle", pex, True, True)
            added.append(f"prime_exc={pex}")
        # Participation 2025 numéraire : non soumise cotis, IMPOSABLE (+ MNS), comme MBC.
        # Montant = 1er nombre positif de la ligne (avant la barre latérale). Exclure SINT.
        par = None
        for ln in seg:
            low = ln.lower()
            if "participation" in low and "acompte" not in low and "sint" not in low and "avance" not in low:
                for m in _NUM.finditer(ln):
                    v = round(float(m.group(0).replace(" ", "")), 2)
                    if v > 0:
                        par = v; break
                if par is not None:
                    break
        if par is not None:
            _add(admin, eid, cid, year, month, "Participation 2025 — numéraire", par, False, True)
            added.append(f"participation={par}")
        # SINT Acompte/avance sur participation déjà versée : net-only négatif (1er nombre).
        aco = None
        for ln in seg:
            low = ln.lower()
            if ("acompte sur participation" in low) or ("avance" in low and "participation" in low):
                for m in _NUM.finditer(ln):
                    v = round(float(m.group(0).replace(" ", "")), 2)
                    if v < 0:
                        aco = v; break
                if aco is not None:
                    break
        if aco is not None:
            _add(admin, eid, cid, year, month, "Avance participation 2025 (déjà versée)", aco, False, False)
            added.append(f"acompte={aco}")
        print(f"[{mat}] {st} inputs={added}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--month", type=int, required=True)
    ap.add_argument("--emp", nargs="*", default=None)
    a = ap.parse_args()
    apply_month(a.year, a.month, only=a.emp)


if __name__ == "__main__":
    main()
