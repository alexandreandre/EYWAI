# scripts/AGIRC-ARRCO_LegiSocial.py

import json
import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional

# --- Fichiers et URL cibles ---
FICHIER_TAUX = 'config/taux_cotisations.json'
URL_LEGISOCIAL = "https://www.legisocial.fr/reperes-sociaux/cotisations-agirc-arrco-2025.html"

# --------- Utils ---------
def _txt(el) -> str:
    return el.get_text(" ", strip=True) if el else ""

def _lct(el) -> str:
    return _txt(el).lower()

def _has_pct(s: str) -> bool:
    return bool(re.search(r"\d+\s*(?:,\s*\d+)?\s*%", s))

def parse_taux(text: str) -> Optional[float]:
    """'3,15 %' -> 0.0315."""
    if not text:
        return None
    try:
        cleaned = (text.replace('\u202f', '')
                        .replace('\xa0', '')
                        .replace(' ', '')
                        .replace(',', '.')
                        .replace('%', '')
                        .strip())
        return round(float(cleaned) / 100.0, 5)
    except ValueError:
        return None

# --------- Parsers ciblés (structure LégiSocial) ---------
def _is_tot_statut_table(tbl) -> bool:
    """Table 'Cotisations pour tout statut' contenant Retraite, CEG, CET."""
    t = _lct(tbl)
    return ("libellé cotisations" in t and "bases" in t and "taux" in t) and (
        "retraite tranche 1" in t or "ceg" in t or "cet" in t
    )

def _is_cadres_table(tbl) -> bool:
    """Table 'Cotisations salariés cadres' contenant APEC."""
    t = _lct(tbl)
    return ("libellé cotisations" in t and "apec" in t)

def _extract_row_pcts(tr) -> list[float]:
    """Retourne tous les pourcentages (float taux réels) trouvés dans une ligne."""
    vals = []
    for td in tr.find_all(['td', 'th']):
        txt = _txt(td)
        if _has_pct(txt):
            v = parse_taux(txt)
            if v is not None:
                vals.append(v)
    return vals

def scrape_legisocial() -> Optional[Dict[str, float]]:
    print(f"Scraping : {URL_LEGISOCIAL}")
    r = requests.get(
        URL_LEGISOCIAL,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    taux: Dict[str, float] = {}

    tables = soup.find_all("table")
    print(f"DEBUG: {len(tables)} tables détectées.")

    # 1) Table "Cotisations pour tout statut" -> Retraite T1/T2, CEG T1/T2, CET (une seule fois)
    for i, tbl in enumerate(tables, start=1):
        if not _is_tot_statut_table(tbl):
            continue
        print(f"DEBUG: Table 'tout statut' #{i} identifiée.")
        for tr in tbl.find_all("tr"):
            row = _lct(tr)
            if "retraite tranche 1" in row:
                pcts = _extract_row_pcts(tr)
                # ordre attendu Total, Salarial, Patronal -> on prend salar/patronal
                if len(pcts) >= 3:
                    taux['retraite_comp_t1_salarial'] = pcts[-2]
                    taux['retraite_comp_t1_patronal'] = pcts[-1]
                elif len(pcts) >= 2:
                    taux['retraite_comp_t1_salarial'] = pcts[0]
                    taux['retraite_comp_t1_patronal'] = pcts[1]
                print(f"  Retraite T1: {taux.get('retraite_comp_t1_salarial')} / {taux.get('retraite_comp_t1_patronal')}")
            elif "retraite tranche 2" in row:
                pcts = _extract_row_pcts(tr)
                if len(pcts) >= 3:
                    taux['retraite_comp_t2_salarial'] = pcts[-2]
                    taux['retraite_comp_t2_patronal'] = pcts[-1]
                elif len(pcts) >= 2:
                    taux['retraite_comp_t2_salarial'] = pcts[0]
                    taux['retraite_comp_t2_patronal'] = pcts[1]
                print(f"  Retraite T2: {taux.get('retraite_comp_t2_salarial')} / {taux.get('retraite_comp_t2_patronal')}")
            elif "ceg" in row and "tranche 1" in row:
                pcts = _extract_row_pcts(tr)
                if len(pcts) >= 3:
                    taux['ceg_t1_salarial'] = pcts[-2]
                    taux['ceg_t1_patronal'] = pcts[-1]
                elif len(pcts) >= 2:
                    taux['ceg_t1_salarial'] = pcts[0]
                    taux['ceg_t1_patronal'] = pcts[1]
                print(f"  CEG T1: {taux.get('ceg_t1_salarial')} / {taux.get('ceg_t1_patronal')}")
            elif "ceg" in row and "tranche 2" in row:
                pcts = _extract_row_pcts(tr)
                if len(pcts) >= 3:
                    taux['ceg_t2_salarial'] = pcts[-2]
                    taux['ceg_t2_patronal'] = pcts[-1]
                elif len(pcts) >= 2:
                    taux['ceg_t2_salarial'] = pcts[0]
                    taux['ceg_t2_patronal'] = pcts[1]
                print(f"  CEG T2: {taux.get('ceg_t2_salarial')} / {taux.get('ceg_t2_patronal')}")
            elif "cet" in row:
                # Une seule paire CET pour T1/T2 (identiques)
                pcts = _extract_row_pcts(tr)
                if ('cet_salarial' not in taux) and len(pcts) >= 3:
                    taux['cet_salarial'] = pcts[-2]
                    taux['cet_patronal'] = pcts[-1]
                    print(f"  CET: {taux.get('cet_salarial')} / {taux.get('cet_patronal')}")

    # 2) Table "Cotisations salariés cadres" -> APEC
    for i, tbl in enumerate(tables, start=1):
        if not _is_cadres_table(tbl):
            continue
        print(f"DEBUG: Table 'cadres' #{i} identifiée.")
        for tr in tbl.find_all("tr"):
            row = _lct(tr)
            if row.startswith("apec") or "apec" in row:
                pcts = _extract_row_pcts(tr)
                # ordre attendu Total, Salarial, Patronal -> on prend salar/patronal
                if len(pcts) >= 3:
                    taux['apec_salarial'] = pcts[-2]
                    taux['apec_patronal'] = pcts[-1]
                elif len(pcts) >= 2:
                    taux['apec_salarial'] = pcts[0]
                    taux['apec_patronal'] = pcts[1]
                print(f"  APEC: {taux.get('apec_salarial')} / {taux.get('apec_patronal')}")
                break

    expected_keys = [
        'retraite_comp_t1_salarial', 'retraite_comp_t1_patronal',
        'retraite_comp_t2_salarial', 'retraite_comp_t2_patronal',
        'ceg_t1_salarial', 'ceg_t1_patronal',
        'ceg_t2_salarial', 'ceg_t2_patronal',
        'cet_salarial', 'cet_patronal',
        'apec_salarial', 'apec_patronal'
    ]
    missing = [k for k in expected_keys if k not in taux or taux[k] is None]
    if missing:
        raise ValueError(f"Taux manquants: {missing}. Données partielles: {taux}")

    print("OK: tous les taux extraits.")
    return taux

# --------- Mise à jour config ---------
if __name__ == "__main__":
    try:
        tx = scrape_legisocial()
        if tx:
            print(json.dumps(tx))
    except Exception as e:
        print(f"ERREUR: {e}")
