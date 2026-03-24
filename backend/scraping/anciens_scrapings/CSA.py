# scripts/CSA.py

import json
import re
import requests
from bs4 import BeautifulSoup

URL_URSSAF = "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html"

def get_taux_csa() -> float | None:
    """
    Scrape le site de l'URSSAF pour trouver le taux de la Contribution
    Solidarité Autonomie (CSA).
    """
    try:
        print(f" scraping de l'URL : {URL_URSSAF}...")
        r = requests.get(URL_URSSAF, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        })
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        
        # 1. Isoler la section "employeur"
        articles = soup.find_all('article')
        employeur_section = None
        for article in articles:
            h2 = article.find('h2', class_='h4-like')
            if h2 and 'taux de cotisations employeur' in h2.get_text(strip=True).lower():
                employeur_section = article
                break

        if not employeur_section:
            raise ValueError("Section 'Taux de cotisations employeur' introuvable.")

        # 2. Parcourir chaque ligne du tableau
        table_rows = employeur_section.find_all('tr', class_='table_custom__tbody')
        for row in table_rows:
            header_cell = row.find('th')
            # 3. Si l'en-tête est celui de la CSA...
            if header_cell and 'Contribution solidarité autonomie (CSA)' in header_cell.get_text(strip=True):
                value_cell = row.find('td')
                if not value_cell:
                    raise ValueError("Ligne 'CSA' trouvée, mais cellule de valeur manquante.")
                
                # 4. ...extraire le taux de la cellule de valeur
                value_text = value_cell.get_text(strip=True)
                m = re.search(r"([0-9,]+)\s*%", value_text)
                if not m:
                    raise ValueError(f"Taux CSA introuvable dans la cellule : '{value_text}'")

                taux_str = m.group(1).replace(",", ".")
                taux = round(float(taux_str) / 100.0, 5)
                
                print(f" Taux CSA trouvé : {taux*100:.2f}%")
                return taux

        raise ValueError("Ligne 'Contribution solidarité autonomie (CSA)' introuvable.")
        
    except Exception as e:
        print(f"ERREUR : Le scraping a échoué. Raison : {e}")
        return None

if __name__ == "__main__":
    taux = get_taux_csa()
    if taux is not None:
        payload = {
            "id": "csa",
            "type": "cotisation",
            "libelle": "Contribution Solidarité Autonomie (CSA)",
            "base": "brut",
            "valeurs": {"salarial": None, "patronal": taux},
        }
        print(json.dumps(payload))