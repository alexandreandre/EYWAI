# scripts/AGS_AI.py

import json
import re
import time
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

load_dotenv()
# --- Fichiers de configuration (identiques à l'original) ---
FICHIER_ENTREPRISE = 'config/parametres_entreprise.json'
FICHIER_TAUX = 'config/taux_cotisations.json'
# URL cible, plus fiable qu'une recherche
URL_LEGISOCIAL = "https://www.legisocial.fr/reperes-sociaux/taux-cotisations-sociales-urssaf-2025.html"

def parse_taux(text: str) -> float | None:
    """
    Nettoie un texte (ex: "0,15 %"), le convertit en float (0.15)
    puis en taux réel (0.0015).
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

def get_taux_ags_via_scraping() -> float | None:
    """
    Scrape le site LegiSocial pour trouver le taux AGS.
    Cette fonction n'a plus besoin du paramètre `is_ett` car le taux est unifié (hors cas très spécifiques non gérés ici).
    """
    print("\n[DEBUG] === Début de la fonction get_taux_ags_via_scraping ===")
    driver = None
    try:
        print("[DEBUG] Initialisation du navigateur Selenium en mode invisible...")
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36")

        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
        
        print(f"[DEBUG] Navigation vers l'URL : {URL_LEGISOCIAL}...")
        driver.get(URL_LEGISOCIAL)
        time.sleep(3) # Attente pour le chargement de contenu dynamique

        print("[DEBUG] Récupération du code HTML final de la page...")
        page_html = driver.page_source
        soup = BeautifulSoup(page_html, "html.parser")
        
        # On cherche le titre de la section "Cotisations chômage"
        chomage_header = soup.find(lambda tag: tag.name == 'h3' and 'Cotisations chômage' in tag.get_text())
        if not chomage_header:
            raise ValueError("Titre de la section 'Cotisations chômage' introuvable.")
        print("[DEBUG] Section 'Cotisations chômage' trouvée.")
        
        table = chomage_header.find_next('table')
        if not table:
            raise ValueError("Table des cotisations chômage introuvable après le titre.")

        # On parcourt les lignes pour trouver celle qui contient "AGS"
        for row in table.find('tbody').find_all('tr'):
            cells = row.find_all('td')
            if len(cells) > 4 and "AGS" in cells[0].get_text():
                print("[DEBUG] Ligne 'AGS' trouvée dans la table.")
                taux_text = cells[4].get_text() # Le taux employeur est dans la 5ème cellule (index 4)
                taux_final = parse_taux(taux_text)
                if taux_final is not None:
                    print(f"\n>>> Taux final calculé : {taux_final} (soit {taux_final*100:.3f}%)")
                    print("[DEBUG] === Fin de la fonction get_taux_ags_via_scraping (Succès) ===")
                    return taux_final
        
        raise ValueError("Impossible d'extraire le taux AGS de la table chômage.")

    except Exception as e:
        print(f"ERREUR : Le processus global a échoué. Raison : {e}")
        return None
    finally:
        if driver:
            print("[DEBUG] Fermeture du navigateur Selenium.")
            driver.quit()

if __name__ == "__main__":
    print("[DEBUG] ================== DÉBUT DU SCRIPT PRINCIPAL ==================")
    try:
        print(f"[DEBUG] Lecture du fichier de configuration entreprise : '{FICHIER_ENTREPRISE}'")
        with open(FICHIER_ENTREPRISE, 'r', encoding='utf-8') as f:
            config_entreprise = json.load(f)
        conditions = config_entreprise['PARAMETRES_ENTREPRISE']['conditions_cotisations']
        est_ett = conditions.get('est_entreprise_travail_temporaire', False)
        print(f"[DEBUG] Le paramètre 'est_entreprise_travail_temporaire' est : {est_ett} (information non utilisée dans la nouvelle méthode).")
        taux = get_taux_ags_via_scraping()
    
        if taux is not None:
            print(json.dumps(taux))

    except Exception as e:
        print(f"ERREUR : Le script principal a échoué : {e}")
    print("[DEBUG] =================== FIN DU SCRIPT PRINCIPAL ===================")