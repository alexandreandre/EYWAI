# scripts/FNAL/FNAL_LegiSocial.py
import json
import os
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL_LEGISOCIAL = "https://www.legisocial.fr/reperes-sociaux/taux-cotisations-sociales-urssaf-2025.html"

def iso_now() -> str:
    """Retourne la date et l'heure actuelles au format ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _parse_percent_to_rate(text: str) -> float | None:
    """Extrait un pourcentage d'une chaîne et le convertit en taux décimal."""
    if not text:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", text)
    if not m:
        return None
    return round(float(m.group(1).replace(",", ".")) / 100.0, 6)

def _fetch_page(url: str) -> BeautifulSoup:
    """Récupère et parse le contenu HTML d'une URL."""
    r = requests.get(
        url,
        timeout=25,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        },
    )
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def scrape_fnal_rates_legisocial() -> dict[str, float | None]:
    """
    Scrape et retourne les deux taux FNAL depuis LegiSocial.
    """
    print(f"[DEBUG] Scraping de l'URL : {URL_LEGISOCIAL}...", file=sys.stderr)
    try:
        soup = _fetch_page(URL_LEGISOCIAL)
        print(f"[DEBUG] Page récupérée avec succès (taille: {len(soup.get_text())} caractères)", file=sys.stderr)
        
        taux_moins_50, taux_50_et_plus = None, None

        # Expressions régulières pour trouver les bonnes lignes
        pat_row = re.compile(r"fnal", re.IGNORECASE)
        # Patterns pour identifier par texte (si présent)
        pat_moins_50 = re.compile(r"moins\s+de\s+50", re.IGNORECASE)
        pat_50_et_plus = re.compile(r"(50\s+salari[ée]s\s+et\s+plus|au\s+moins\s+50)", re.IGNORECASE)
        
        # Valeurs de taux FNAL standard (en décimal)
        # 0,10% = 0.001 pour moins de 50 salariés
        # 0,50% = 0.005 pour 50 salariés et plus
        FNAL_MOINS_50_RATE = 0.001  # 0.10%
        FNAL_50_ET_PLUS_RATE = 0.005  # 0.50%

        # DEBUG: Afficher tous les titres H1, H2, H3 trouvés
        print("[DEBUG] === Recherche des titres dans la page ===", file=sys.stderr)
        all_titles = soup.find_all(['h1', 'h2', 'h3', 'h4'])
        print(f"[DEBUG] Nombre total de titres trouvés: {len(all_titles)}", file=sys.stderr)
        for i, title in enumerate(all_titles[:10]):  # Limiter à 10 pour éviter trop de logs
            title_text = title.get_text(" ", strip=True)
            print(f"[DEBUG]   Titre {i+1} ({title.name}): {title_text[:100]}", file=sys.stderr)
        
        # La structure de la table peut varier, on cherche la bonne
        searched_text = "Quels sont les taux de cotisations en 2025"
        print(f"[DEBUG] === Recherche du titre exact: '{searched_text}' ===", file=sys.stderr)
        
        table_title = soup.find(lambda tag: tag.name in ['h2', 'h3'] and searched_text in tag.get_text())
        
        if not table_title:
            # Essayer des variantes
            print(f"[DEBUG] Titre exact '{searched_text}' non trouvé. Recherche de variantes...", file=sys.stderr)
            variants = [
                "Quels sont les taux de cotisations en 2025",
                "taux de cotisations en 2025",
                "taux de cotisations",
                "cotisations en 2025",
                "cotisations sociales",
            ]
            for variant in variants:
                print(f"[DEBUG]   Essai avec: '{variant}'", file=sys.stderr)
                table_title = soup.find(lambda tag: tag.name in ['h1', 'h2', 'h3', 'h4'] and variant.lower() in tag.get_text().lower())
                if table_title:
                    print(f"[DEBUG]   ✓ Variante trouvée: '{variant}'", file=sys.stderr)
                    break
        
        if not table_title:
            print("[DEBUG] ❌ AUCUN titre de table trouvé avec les critères de recherche", file=sys.stderr)
            raise ValueError(f"Titre de la table des cotisations introuvable. Texte recherché: '{searched_text}'. "
                           f"Aucun titre H1/H2/H3/H4 ne contient ce texte.")
        
        print(f"[DEBUG] ✓ Titre trouvé: '{table_title.get_text(' ', strip=True)[:100]}'", file=sys.stderr)
        
        # Chercher la table après le titre
        print("[DEBUG] === Recherche de la table après le titre ===", file=sys.stderr)
        table = table_title.find_next('table')
        
        if not table:
            # Fallback: chercher toutes les tables dans la page
            print("[DEBUG] Aucune table trouvée après le titre. Recherche dans toutes les tables...", file=sys.stderr)
            all_tables = soup.find_all('table')
            print(f"[DEBUG] Nombre total de tables trouvées dans la page: {len(all_tables)}", file=sys.stderr)
            
            for i, t in enumerate(all_tables):
                table_text = t.get_text(" ", strip=True).lower()
                if pat_row.search(table_text):
                    print(f"[DEBUG]   ✓ Table {i+1} contient 'FNAL'", file=sys.stderr)
                    table = t
                    break
                else:
                    print(f"[DEBUG]   ✗ Table {i+1} ne contient pas 'FNAL'", file=sys.stderr)
        
        if not table:
            print("[DEBUG] ❌ AUCUNE table contenant 'FNAL' trouvée dans la page", file=sys.stderr)
            raise ValueError("Table des cotisations introuvable après le titre. Aucune table dans la page ne contient 'FNAL'.")
        
        print(f"[DEBUG] ✓ Table trouvée ({len(table.find_all('tr'))} lignes)", file=sys.stderr)

        print("[DEBUG] === Parsing des lignes de la table ===", file=sys.stderr)
        rows_processed = 0
        rows_with_fnal = 0
        
        for row_idx, tr in enumerate(table.find_all("tr")):
            cells = tr.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            
            rows_processed += 1
            label = cells[0].get_text(" ", strip=True)
            
            if not pat_row.search(label):
                continue
            
            rows_with_fnal += 1
            print(f"[DEBUG]   Ligne {row_idx+1} contient 'FNAL': '{label[:100]}'", file=sys.stderr)
            
            # Le taux patronal est généralement dans la dernière cellule
            last_cell_text = cells[-1].get_text(" ", strip=True)
            print(f"[DEBUG]     → Dernière cellule: '{last_cell_text[:100]}'", file=sys.stderr)
            
            rate = _parse_percent_to_rate(last_cell_text)
            if rate is None:
                print(f"[DEBUG]     → ✗ Aucun pourcentage trouvé dans la dernière cellule", file=sys.stderr)
                continue

            print(f"[DEBUG]     → ✓ Taux extrait: {rate} ({rate*100}%)", file=sys.stderr)

            # Méthode 1: Identifier par le texte du label (si mentionné)
            if pat_moins_50.search(label):
                taux_moins_50 = rate
                print(f"[DEBUG]     → → Assigné à 'moins_50' (détection par texte)", file=sys.stderr)
            elif pat_50_et_plus.search(label):
                taux_50_et_plus = rate
                print(f"[DEBUG]     → → Assigné à '50_et_plus' (détection par texte)", file=sys.stderr)
            # Méthode 2: Identifier par la valeur du taux (fallback)
            elif abs(rate - FNAL_MOINS_50_RATE) < 0.0001:  # Tolérance pour arrondis
                taux_moins_50 = rate
                print(f"[DEBUG]     → → Assigné à 'moins_50' (détection par valeur: {rate*100}% ≈ {FNAL_MOINS_50_RATE*100}%)", file=sys.stderr)
            elif abs(rate - FNAL_50_ET_PLUS_RATE) < 0.0001:  # Tolérance pour arrondis
                taux_50_et_plus = rate
                print(f"[DEBUG]     → → Assigné à '50_et_plus' (détection par valeur: {rate*100}% ≈ {FNAL_50_ET_PLUS_RATE*100}%)", file=sys.stderr)
            else:
                print(f"[DEBUG]     → → ⚠ Taux trouvé ({rate*100}%) mais ne correspond à aucun pattern (moins_50/50_et_plus)", file=sys.stderr)
        
        print(f"[DEBUG] === Résumé du parsing ===", file=sys.stderr)
        print(f"[DEBUG]   Lignes traitées: {rows_processed}", file=sys.stderr)
        print(f"[DEBUG]   Lignes avec 'FNAL': {rows_with_fnal}", file=sys.stderr)
        print(f"[DEBUG]   Taux FNAL (< 50 salariés) trouvé : {taux_moins_50}", file=sys.stderr)
        print(f"[DEBUG]   Taux FNAL (50+ salariés) trouvé : {taux_50_et_plus}", file=sys.stderr)

        if taux_moins_50 is None or taux_50_et_plus is None:
            missing = []
            if taux_moins_50 is None:
                missing.append("moins_50")
            if taux_50_et_plus is None:
                missing.append("50_et_plus")
            print(f"[DEBUG] ❌ ERREUR: Taux manquants après parsing: {', '.join(missing)}", file=sys.stderr)
        
        return {"patronal_moins_50": taux_moins_50, "patronal_50_et_plus": taux_50_et_plus}
    except requests.RequestException as e:
        print(f"[ERROR] ERREUR HTTP lors du scraping : {type(e).__name__}: {e}", file=sys.stderr)
        print(f"[ERROR] URL tentée: {URL_LEGISOCIAL}", file=sys.stderr)
        return {"patronal_moins_50": None, "patronal_50_et_plus": None}
    except ValueError as e:
        print(f"[ERROR] ERREUR de parsing : {e}", file=sys.stderr)
        print(f"[ERROR] URL: {URL_LEGISOCIAL}", file=sys.stderr)
        return {"patronal_moins_50": None, "patronal_50_et_plus": None}
    except Exception as e:
        import traceback
        print(f"[ERROR] ERREUR INATTENDUE lors du scraping : {type(e).__name__}: {e}", file=sys.stderr)
        print(f"[ERROR] URL: {URL_LEGISOCIAL}", file=sys.stderr)
        print(f"[ERROR] Traceback complet:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return {"patronal_moins_50": None, "patronal_50_et_plus": None}

def main() -> None:
    """
    Orchestre le scraping et génère la sortie JSON pour l'orchestrateur.
    """
    rates = scrape_fnal_rates_legisocial()

    missing_rates = []
    if rates.get("patronal_moins_50") is None:
        missing_rates.append("patronal_moins_50")
    if rates.get("patronal_50_et_plus") is None:
        missing_rates.append("patronal_50_et_plus")

    if missing_rates:
        print(f"[ERROR] ERREUR CRITIQUE: Taux FNAL manquants: {', '.join(missing_rates)}", file=sys.stderr)
        print(f"[ERROR] Taux récupérés: {rates}", file=sys.stderr)
        print(f"[ERROR] URL source: {URL_LEGISOCIAL}", file=sys.stderr)
        print("[ERROR] Le scraping n'a pas pu extraire tous les taux requis depuis LegiSocial.", file=sys.stderr)
        sys.exit(1)

    payload = {
        "id": "fnal",
        "type": "cotisation",
        "libelle": "Fonds National d’Aide au Logement (FNAL)",
        "sections": {
            "salarial": None,
            "patronal_moins_50": rates["patronal_moins_50"],
            "patronal_50_et_plus": rates["patronal_50_et_plus"]
        },
        "meta": {
            "source": [{"url": URL_LEGISOCIAL, "label": "LégiSocial — Taux cotisations URSSAF", "date_doc": ""}],
            "scraped_at": iso_now(),
            "generator": "scripts/FNAL/FNAL_LegiSocial.py",
            "method": "secondary",
        },
    }
    
    # Sortie JSON stricte pour l'orchestrateur
    print(json.dumps(payload, ensure_ascii=False))

if __name__ == "__main__":
    main()