"""
Modèles OpenRouter par cas d'usage.

Les identifiants sont définis dans le code (pas dans .env) pour pouvoir
varier selon la fonctionnalité. Pour l'instant : gpt-4o-mini partout.
"""

# Référence OpenRouter (préfixe fournisseur obligatoire)
GPT_4O_MINI = "openai/gpt-4o-mini"

# --- Application (modules métier) ---

# Assistant RH (copilot) : un modèle par rôle plutôt qu'un modèle unique.
# Mesures du banc d'essai (backend/scripts/eval_assistant_rh.py, 05/08/2026) :
# le routage est équivalent d'un modèle à l'autre, mais la vitesse et la qualité
# de rédaction ne le sont pas, et la branche convention a besoin d'un grand
# contexte depuis que le texte de base intégral est envoyé.
#
# - planification : sur le chemin critique de CHAQUE question -> le plus rapide ;
# - convention : contexte 1 M requis (le texte de base va jusqu'à 400 000 car.) ;
# - aide logiciel / synthèse : qualité de rédaction, coût négligeable ici
#   (de l'ordre du demi-centime par question).
MODEL_COPILOT_PLANNING = "google/gemini-3.1-flash-lite"
MODEL_COPILOT_AGREEMENT = "google/gemini-3-flash-preview"
MODEL_COPILOT_APP_HELP = "google/gemini-3-flash-preview"
MODEL_COPILOT_SYNTHESIS = "google/gemini-3-flash-preview"

# Conservé pour les appels hors copilot qui s'y réfèrent encore.
MODEL_COPILOT = MODEL_COPILOT_SYNTHESIS
MODEL_COLLECTIVE_AGREEMENT_CHAT = GPT_4O_MINI
MODEL_CONTRACT_EXTRACTION = GPT_4O_MINI
MODEL_RECRUITMENT_SCORING = GPT_4O_MINI
MODEL_COMPETENCIES_MOBILITY = GPT_4O_MINI
MODEL_CSE_RECORDING = GPT_4O_MINI
MODEL_CC_RULES_EXTRACTION = "google/gemini-2.5-flash"
MODEL_CC_TRAINING_EXTRACTION = "google/gemini-2.5-flash"

# Saisie assistée du calendrier (page Calendriers RH)
# - Instruction en langage naturel -> heures par jour (Gemini Flash : rapide + JSON fiable)
MODEL_SCHEDULE_NL_FILL = "google/gemini-2.5-flash"
# - Relevé de pointeuse (PDF/image OCR) -> heures par jour : Gemini pour
#   les tableaux denses multi-employés
MODEL_TIMESHEET_EXTRACTION = "google/gemini-2.5-flash"
# - Extraction hybride par page (vision + texte OCR)
MODEL_TIMESHEET_VISION = "google/gemini-2.5-flash"
MODEL_TIMESHEET_PAGE_TEXT = "google/gemini-2.5-flash"

# --- Scripts de scraping ---

MODEL_SCRAPING_EXTRACTION = GPT_4O_MINI
