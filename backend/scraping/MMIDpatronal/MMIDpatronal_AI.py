# scripts/MMIDpatronal/MMIDpatronal_AI.py
import json
import os
import re
from datetime import datetime, timezone

# Les imports de scraping (requests, bs4) ne sont pas nécessaires
from dotenv import load_dotenv
from openai import OpenAI  # Import pour l'IA

load_dotenv()

# Initialisation du client OpenAI
try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if not client.api_key:
        raise ValueError("OPENAI_API_KEY est vide ou non définie.")
except Exception as e:
    print(f"Erreur initialisation OpenAI: {e}")
    client = None

# URL utilisée par la fonction build_payload (copiée de votre script)
URL_LEGISOCIAL = "https://www.legisocial.fr/reperes-sociaux/taux-cotisations-sociales-urssaf-2025.html"


def iso_now() -> str:
    """Génère un timestamp ISO UTC. (identique à LegiSocial.py)"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_taux(text: str) -> float | None:
    """Fonction parse_taux (identique à LegiSocial.py)"""
    if not text:
        return None
    try:
        cleaned_text = text.replace(",", ".").replace("%", "").strip()
        m = re.search(r"([0-9]+\.?[0-9]*)", cleaned_text)
        if not m:
            return None
        # Arrondi à 5 décimales (comme votre script LegiSocial.py)
        return round(float(m.group(1)) / 100.0, 5) 
    except Exception:
        return None


def get_taux_maladie_ai() -> dict | None:
    """
    Interroge l'API OpenAI (gpt-4o-mini) pour trouver les taux.
    Renvoie un dictionnaire {"plein": float, "reduit": float} ou None.
    (C'est l'équivalent AI de votre get_taux_maladie_legisocial())
    """
    if not client:
        print("Client OpenAI non initialisé. Impossible de continuer.")
        return None

    rates = {"plein": None, "reduit": None}
    
    try:
        current_year = datetime.now().year

        # 1. Définition des prompts pour l'IA
        system_prompt = (
            "Tu es un assistant expert en cotisations sociales françaises (URSSAF). "
            "Ta tâche est de trouver les taux de cotisation patronale 'maladie' (MMID) à jour "
            "en te basant sur tes connaissances internes les plus récentes. "
            "Tu DOIS répondre exclusivement avec un objet JSON valide. "
            "N'ajoute aucun texte explicatif avant ou après l'objet JSON."
        )
        
        user_prompt = (
            f"En te basant sur tes données d'entraînement les plus à jour, quels sont les taux de cotisation "
            f"patronale pour l'Assurance Maladie, Maternité, Invalidité, Décès (MMID) "
            f"en France pour l'année {current_year} ? "
            "Je cherche spécifiquement deux valeurs : "
            "1. Le 'taux plein' (ou 'taux de droit commun', souvent 13,00 %). "
            "2. Le 'taux réduit' (applicable sur les bas salaires, souvent 7,00 %). "
            "Réponds avec un objet JSON ayant les clés exactes : `taux_plein_text` et `taux_reduit_text`."
            # Note: On ne demande plus la source_url, car build_payload ne l'utilise pas
        )

        # print(f"Interrogation de gpt-4o-mini pour les taux {current_year}...")
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0
        )
        
        response_content = completion.choices[0].message.content
        if not response_content:
            raise ValueError("Réponse vide de l'API OpenAI")

        # 2. Parser la réponse JSON de l'IA
        data = json.loads(response_content)
        
        taux_plein_text = data.get("taux_plein_text")
        taux_reduit_text = data.get("taux_reduit_text")

        # 3. Utiliser le parseur du script
        rates["plein"] = parse_taux(taux_plein_text)
        rates["reduit"] = parse_taux(taux_reduit_text)
        
        # print(f"Info récupérée par IA : Taux plein: {taux_plein_text}, Taux réduit: {taux_reduit_text}")
        
        # 4. Retourner le dictionnaire (ou None si rien n'est trouvé)
        if rates["plein"] is not None or rates["reduit"] is not None:
            return rates
        return None

    except Exception as e:
        print(f"Erreur lors de l'appel à l'API OpenAI ou du parsing : {e}")
        return None


def build_payload(rate_plein: float | None, rate_reduit: float | None) -> dict:
    """Fonction build_payload (identique à LegiSocial.py)"""
    return {
        "id": "securite_sociale_maladie",
        "type": "cotisation",
        "libelle": "Sécurité sociale - Maladie, Maternité, Invalidité, Décès",
        "base": "brut",
        "valeurs": {
            "salarial": None,
            "patronal_plein": rate_plein,
            "patronal_reduit": rate_reduit,
        },
        "meta": {
            "source": [{"url": URL_LEGISOCIAL, "label": "LégiSocial — Taux cotisations URSSAF 2025", "date_doc": ""}],
            "scraped_at": iso_now(),
            # Le générateur est mis à jour pour refléter le nom de ce script
            "generator": "scripts/MMIDpatronal/MMIDpatronal_AI.py",
            "method": "secondary", # Utilisation de la méthode de votre script valide
        },
    }


def main() -> None:
    """Fonction main (identique à LegiSocial.py, appelant la version AI)"""
    # Appelle la fonction AI au lieu de la fonction de scraping
    rates = get_taux_maladie_ai() or {} 
    
    payload = build_payload(rates.get("plein"), rates.get("reduit"))
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()