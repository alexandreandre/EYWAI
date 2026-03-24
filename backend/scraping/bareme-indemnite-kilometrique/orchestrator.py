# scripts/bareme-indemnite-kilometrique/orchestrator.py

import json
import os
import sys
import hashlib
import subprocess
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(REPO_ROOT, ".env"))

CONFIG_KEY_TO_UPDATE = "baremes_km"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

SCRIPTS = [
    os.path.join(os.path.dirname(__file__), "bareme-indemnite-kilometrique.py"),
    os.path.join(os.path.dirname(__file__), "bareme-indemnite-kilometrique_LegiSocial.py"),
    # os.path.join(os.path.dirname(__file__), "bareme-indemnite-kilometrique_AI.py"),  # décommenter pour inclure l’IA
]


def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL et SUPABASE_SERVICE_KEY (ou SUPABASE_KEY) requis.")
    return create_client(url, key)


def fetch_active_config(supabase: Client, config_key: str) -> Optional[Dict[str, Any]]:
    r = supabase.table("payroll_config").select("*").eq("config_key", config_key).eq("is_active", True).limit(1).execute()
    rows = r.data or []
    return rows[0] if rows else None


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_script(path: str) -> Dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, path],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=os.environ.copy(),
    )
    if proc.returncode != 0:
        print(f"\n[ERREUR] {os.path.basename(path)} a échoué (code {proc.returncode})", file=sys.stderr)
        if proc.stdout.strip():
            print("[stdout]", proc.stdout, file=sys.stderr)
        if proc.stderr.strip():
            print("[stderr]", proc.stderr, file=sys.stderr)
        raise SystemExit(2)

    out = proc.stdout.strip()
    try:
        payload = json.loads(out)
        payload.setdefault("meta", {}).setdefault("generator", os.path.basename(path))
        payload["__script"] = os.path.basename(path)
        return payload
    except Exception as e:
        print(
            f"[ERREUR] Sortie non-JSON depuis {os.path.basename(path)}: {e}\n---stdout---\n{out}\n-------------",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _norm_formula(f: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "segment": int(f.get("segment")),
        "a": None if f.get("a") is None else round(float(f.get("a")), 3),
        "b": None if f.get("b") is None else round(float(f.get("b")), 3),
    }


def _norm_tranche(t: Dict[str, Any]) -> Dict[str, Any]:
    cv_min = t.get("cv_min", None)
    cv_max = t.get("cv_max", None)
    forms = [_norm_formula(f) for f in t.get("formules", [])]
    forms.sort(key=lambda x: x["segment"])
    return {
        "cv_min": cv_min if cv_min is None else int(cv_min),
        "cv_max": cv_max if cv_max is None else int(cv_max),
        "formules": forms,
    }


def _norm_block(block: Dict[str, Any]) -> Dict[str, Any]:
    segs = block.get("segments", [])
    tranches = [_norm_tranche(t) for t in block.get("tranches_cv", [])]
    def keyfn(t):
        mn = float("-inf") if t["cv_min"] is None else int(t["cv_min"])
        mx = float("inf") if t["cv_max"] is None else int(t["cv_max"])
        return (mn, mx)
    tranches.sort(key=keyfn)
    return {"base": block.get("base"), "segments": segs, "tranches_cv": tranches}


def core_signature(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("id") != "baremes_km":
        raise SystemExit("id attendu 'baremes_km'")
    veh = payload.get("vehicules", {})
    return {
        "id": "baremes_km",
        "annee": payload.get("annee"),
        "vehicules": {
            "voitures": _norm_block(veh.get("voitures", {})),
            "motocyclettes": _norm_block(veh.get("motocyclettes", {})),
            "cyclomoteurs": _norm_block(veh.get("cyclomoteurs", {})),
        },
    }


def _eq_float(a: Optional[float], b: Optional[float], tol: float = 1e-6) -> bool:
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= tol


def _eq_formulas(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> bool:
    if len(a) != len(b):
        return False
    for fa, fb in zip(a, b):
        if int(fa["segment"]) != int(fb["segment"]):
            return False
        if not (_eq_float(fa["a"], fb["a"]) and _eq_float(fa["b"], fb["b"])):
            return False
    return True


def _eq_tranches(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> bool:
    if len(a) != len(b):
        return False
    for ta, tb in zip(a, b):
        if ta["cv_min"] != tb["cv_min"] or ta["cv_max"] != tb["cv_max"]:
            return False
        if not _eq_formulas(ta["formules"], tb["formules"]):
            return False
    return True


def equal_core(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    if a.get("annee") != b.get("annee"):
        return False
    va, vb = a["vehicules"], b["vehicules"]
    for k in ("voitures", "motocyclettes", "cyclomoteurs"):
        ba, bb = va.get(k, {}), vb.get(k, {})
        if json.dumps(ba.get("segments", []), sort_keys=True) != json.dumps(bb.get("segments", []), sort_keys=True):
            return False
        if not _eq_tranches(ba.get("tranches_cv", []), bb.get("tranches_cv", [])):
            return False
    return True


def compute_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def merge_sources(payloads: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    seen, out = set(), []
    for p in payloads:
        for s in p.get("meta", {}).get("source", []):
            key = (s.get("url", ""), s.get("label", ""))
            if key not in seen:
                seen.add(key)
                out.append({"url": s.get("url", ""), "label": s.get("label", ""), "date_doc": s.get("date_doc", "")})
    return out


def build_config_data(final_core: Dict[str, Any], sources: List[Dict[str, str]]) -> Dict[str, Any]:
    """Construit le payload pour payroll_config (BAREME_KM + meta)."""
    barème_item = {
        "id": "baremes_km",
        "libelle": f"Barème kilométrique {final_core.get('annee')}",
        "annee": final_core.get("annee"),
        "vehicules": final_core.get("vehicules"),
    }
    meta = {
        "last_scraped": iso_now(),
        "generator": "bareme-indemnite-kilometrique/orchestrator.py",
        "source": sources,
        "hash": compute_hash([barème_item]),
    }
    return {"BAREME_KM": [barème_item], "meta": meta}


def update_config_in_supabase(
    supabase: Client,
    current_row: Optional[Dict[str, Any]],
    new_config_data: Dict[str, Any],
    source_links: List[str],
) -> None:
    if current_row is None:
        new_row = {
            "config_key": CONFIG_KEY_TO_UPDATE,
            "config_data": new_config_data,
            "version": 1,
            "is_active": True,
            "comment": "Mise à jour automatique: barème kilométrique",
            "last_checked_at": iso_now(),
            "source_links": source_links,
        }
        supabase.table("payroll_config").insert(new_row).execute()
        logging.info("✅ baremes_km v1 créée dans payroll_config.")
        return
    current_id = current_row["id"]
    current_version = current_row["version"]
    current_config_data = current_row["config_data"]
    if current_config_data == new_config_data:
        supabase.table("payroll_config").update({
            "last_checked_at": iso_now(),
            "source_links": source_links,
        }).eq("id", current_id).execute()
        logging.info("✅ baremes_km inchangé, last_checked_at mis à jour.")
        return
    new_row = {
        "config_key": CONFIG_KEY_TO_UPDATE,
        "config_data": new_config_data,
        "version": current_version + 1,
        "is_active": True,
        "comment": "Mise à jour automatique: barème kilométrique",
        "last_checked_at": iso_now(),
        "source_links": source_links,
    }
    supabase.table("payroll_config").update({"is_active": False}).eq("id", current_id).execute()
    supabase.table("payroll_config").insert(new_row).execute()
    logging.info(f"✅ baremes_km v{current_version + 1} créée dans payroll_config.")


def debug_mismatch(payloads: List[Dict[str, Any]], sigs: List[Dict[str, Any]]) -> None:
    print("MISMATCH barème kilométrique entre sources:", file=sys.stderr)
    for p, s in zip(payloads, sigs):
        script = p.get("__script", "?")
        v = s["vehicules"]
        def head(trs: List[Dict[str, Any]]) -> str:
            if not trs:
                return "∅"
            f1 = trs[0]["formules"][0]
            return f"n={len(trs)} | seg1 a={f1['a']} b={f1['b']}"
        print(f"- {script}: voitures[{head(v['voitures']['tranches_cv'])}] | "
              f"motos[{head(v['motocyclettes']['tranches_cv'])}] | "
              f"cyclos[{head(v['cyclomoteurs']['tranches_cv'])}]", file=sys.stderr)


def debug_success(payloads: List[Dict[str, Any]], sigs: List[Dict[str, Any]]) -> None:
    v = sigs[0]["vehicules"]
    v0 = v["voitures"]["tranches_cv"][0]["formules"][0]
    m0 = v["motocyclettes"]["tranches_cv"][0]["formules"][0]
    c0 = v["cyclomoteurs"]["tranches_cv"][0]["formules"][0]
    print(f"OK concordance barème: V(seg1 a={v0['a']} b={v0['b']}) | M(seg1 a={m0['a']} b={m0['b']}) | C(seg1 a={c0['a']} b={c0['b']})")


def main() -> None:
    payloads = [run_script(p) for p in SCRIPTS]
    sigs = [core_signature(p) for p in payloads]

    ok = True
    for i in range(len(sigs) - 1):
        if not equal_core(sigs[i], sigs[i + 1]):
            ok = False
            break

    if not ok:
        debug_mismatch(payloads, sigs)
        raise SystemExit(2)

    debug_success(payloads, sigs)

    sources = merge_sources(payloads)
    source_links = [s.get("url", "") for s in sources if s.get("url")]
    new_config_data = build_config_data(sigs[0], sources)
    supabase = get_supabase()
    current_row = fetch_active_config(supabase, CONFIG_KEY_TO_UPDATE)
    update_config_in_supabase(supabase, current_row, new_config_data, source_links)
    print("OK: baremes_km mis à jour dans payroll_config.")


if __name__ == "__main__":
    main()
