# scripts/SMIC.py

import json
import re
import requests
from bs4 import BeautifulSoup

FICHIER_ENTREPRISE = 'config/parametres_entreprise.json'
URL_URSSAF = "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/montant-smic.html"

def parse_valeur_numerique(text: str) -> float:
    """
    Nettoie et convertit un texte contenant une valeur monétaire en float.
    Exemple : "11,88 €" -> 11.88
    """
    if not text: return 0.0
    cleaned_text = text.replace(',', '.').replace('\xa0', '').replace('€', '').strip()
    match = re.search(r"([0-9]+\.?[0-9]*)", cleaned_text)
    if match:
        return float(match.group(1))
    return 0.0

def get_smic_horaire_par_cas(soup, section_id: str, nom_cas: str) -> float:
    """
    Fonction générique pour scraper le SMIC horaire d'une section donnée.
    """
    section = soup.find('div', id=section_id)
    if not section:
        raise ValueError(f"Section '{nom_cas}' (ID: {section_id}) introuvable.")
    
    table_rows = section.find_all('tr')
    for row in table_rows:
        header_cell = row.find('th')
        if header_cell and 'Smic horaire brut' in header_cell.get_text(strip=True):
            value_cell = row.find('td')
            if not value_cell:
                raise ValueError(f"Cellule de valeur manquante pour le SMIC horaire dans '{nom_cas}'.")
            
            valeur_smic = parse_valeur_numerique(value_cell.get_text())
            print(f"  - SMIC horaire brut trouvé ({nom_cas}): {valeur_smic} €")
            return valeur_smic
            
    raise ValueError(f"Ligne 'Smic horaire brut' introuvable dans la section '{nom_cas}'.")

def get_tous_les_smic() -> dict | None:
    """
    Scrape le site de l'URSSAF pour trouver tous les montants du SMIC horaire.
    Retourne un dictionnaire avec les 3 cas ou None si erreur.
    """
    try:
        print(f" scraping de l'URL : {URL_URSSAF}...")
        r = requests.get(URL_URSSAF, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        })
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        
        current_year = 2025 # L'année est dans les IDs des sections
        
        smic_valeurs = {
            "cas_general": get_smic_horaire_par_cas(soup, f'Cas-general-{current_year}', 'Cas général'),
            "entre_17_et_18_ans": get_smic_horaire_par_cas(soup, f'salaries-entre-17-18-{current_year}', '17-18 ans'),
            "moins_de_17_ans": get_smic_horaire_par_cas(soup, f'salaries-moins-17-{current_year}', 'Moins de 17 ans')
        }
        
        return smic_valeurs

    except Exception as e:
        print(f"ERREUR : Le scraping a échoué. Raison : {e}")
        return None

if __name__ == "__main__":
    valeurs_smic = get_tous_les_smic()
    
    if valeurs_smic is not None:
        print(json.dumps(valeurs_smic))