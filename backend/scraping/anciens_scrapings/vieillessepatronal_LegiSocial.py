# scripts/vieillessepatronal_LegiSocial.py

import json
import re
import requests
from bs4 import BeautifulSoup

# --- Fichiers et URL cibles ---
FICHIER_TAUX = 'config/taux_cotisations.json'
URL_LEGISOCIAL = "https://www.legisocial.fr/reperes-sociaux/taux-cotisations-sociales-urssaf-2025.html"

def parse_taux(text: str) -> float | None:
    """
    Nettoie un texte (ex: "8,55 %"), le convertit en float (8.55)
    puis en taux réel (0.0855).
    """
    if not text:
        return None
    try:
        cleaned_text = text.replace(',', '.').replace('%', '').strip()
        numeric_part = re.search(r"([0-9]+\.?[0-9]*)", cleaned_text)
        if not numeric_part:
            return None
        taux = float(numeric_part.group(1)) / 100.0
        return round(taux, 5)
    except (ValueError, AttributeError):
        return None

def get_taux_vieillesse_patronal_legisocial() -> dict | None:
    """
    Scrape le site LegiSocial pour trouver les taux de l'assurance vieillesse patronale.
    """
    try:
        print(f"Scraping de l'URL : {URL_LEGISOCIAL}...")
        response = requests.get(URL_LEGISOCIAL, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        })
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        
        table_title = soup.find(lambda tag: tag.name in ['h2', 'h3'] and 'Quels sont les taux de cotisations en 2025' in tag.get_text())
        if not table_title:
            raise ValueError("Titre de la table principale des cotisations 2025 introuvable.")
            
        table = table_title.find_next('table')
        if not table:
            raise ValueError("Table des cotisations introuvable après le titre.")

        taux_trouves = {}
        for row in table.find('tbody').find_all('tr'):
            cells = row.find_all('td')
            if len(cells) > 4:
                libelle = cells[0].get_text(strip=True).lower()
                
                if "vieillesse déplafonnée" in libelle:
                    taux_text = cells[4].get_text()
                    taux = parse_taux(taux_text)
                    if taux is not None:
                        print(f"Taux Vieillesse Déplafonnée (patronal) trouvé : {taux*100:.2f}%")
                        taux_trouves['deplafond'] = taux

                elif "vieillesse plafonnée" in libelle:
                    taux_text = cells[4].get_text()
                    taux = parse_taux(taux_text)
                    if taux is not None:
                        print(f"Taux Vieillesse Plafonnée (patronal) trouvé : {taux*100:.2f}%")
                        taux_trouves['plafond'] = taux

        if "deplafond" in taux_trouves and "plafond" in taux_trouves:
            return taux_trouves
        else:
            raise ValueError("Impossible de trouver les deux taux de vieillesse (plafonné et déplafonné).")

    except Exception as e:
        print(f"ERREUR : Le scraping a échoué. Raison : {e}")
        return None

if __name__ == "__main__":
    taux = get_taux_vieillesse_patronal_legisocial()
    
    if taux is not None:
        print(json.dumps(taux))