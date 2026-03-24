# scripts/alloc.py

import json
import re
import requests
from bs4 import BeautifulSoup

# Définir les chemins des fichiers
URL_URSSAF = "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html"

def get_taux_allocations(is_taux_reduit: bool) -> float | None:
    """
    Scrape le site de l'URSSAF pour trouver le taux des allocations familiales
    (réduit ou plein) en fonction du booléen fourni.
    """
    try:
        print(f" scraping de l'URL : {URL_URSSAF}...")
        r = requests.get(URL_URSSAF, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        })
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        
        # Cibler la section "employeur"
        articles = soup.find_all('article')
        employeur_section_text = ""
        for article in articles:
            h2 = article.find('h2', class_='h4-like')
            if h2 and 'taux de cotisations employeur' in h2.get_text(strip=True).lower():
                employeur_section_text = article.get_text(" ", strip=True)
                break

        if not employeur_section_text:
            raise ValueError("Section 'Taux de cotisations employeur' introuvable.")

        # Déterminer quel motif de texte chercher
        if is_taux_reduit:
            motif_recherche = r"Allocations familiales.*?Taux réduit à\s*([0-9,]+)\s*%"
            type_taux_log = "réduit"
        else:
            motif_recherche = r"Allocations familiales.*?Taux plein à\s*([0-9,]+)\s*%"
            type_taux_log = "plein"
            
        print(f"Recherche du taux d'allocations familiales : '{type_taux_log}'")

        # Appliquer le bon regex
        m = re.search(motif_recherche, employeur_section_text, flags=re.IGNORECASE | re.DOTALL)
        
        if not m:
            raise ValueError(f"Motif pour le taux '{type_taux_log}' des allocations familiales introuvable.")
        
        taux_str = m.group(1).replace(",", ".")
        taux = round(float(taux_str) / 100.0, 5)
        
        print(f" Taux trouvé : {taux*100:.2f}%")
        return taux
        
    except Exception as e:
        print(f"ERREUR : Le scraping a échoué. Raison : {e}")
        return None

if __name__ == "__main__":
    try:
        # Lire le paramètre de l'entreprise pour savoir quel taux chercher
        with open(FICHIER_ENTREPRISE, 'r', encoding='utf-8') as f:
            config_entreprise = json.load(f)
        
        # --- LOGIQUE CORRIGÉE ICI ---
        # Le booléen est maintenant lu dans la sous-section "conditions_cotisations"
        appliquer_taux_reduit = config_entreprise['PARAMETRES_ENTREPRISE']['conditions_cotisations'].get('remuneration_annuelle_brute_inferieure_3.5_smic', False)

        taux = get_taux_allocations(is_taux_reduit=appliquer_taux_reduit)
    
        if taux is not None:
            print(json.dumps(taux))

    except FileNotFoundError:
        print(f"ERREUR : Le fichier '{FICHIER_ENTREPRISE}' est introuvable.")
    except KeyError as e:
        print(f"ERREUR : La structure du fichier '{FICHIER_ENTREPRISE}' est incorrecte ou une clé est manquante : {e}")