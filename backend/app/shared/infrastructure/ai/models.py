"""
Modèles OpenRouter par cas d'usage.

Les identifiants sont définis dans le code (pas dans .env) pour pouvoir
varier selon la fonctionnalité. Pour l'instant : gpt-4o-mini partout.
"""

# Référence OpenRouter (préfixe fournisseur obligatoire)
GPT_4O_MINI = "openai/gpt-4o-mini"

# --- Application (modules métier) ---

MODEL_COPILOT = GPT_4O_MINI
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

# --- Scripts de scraping ---

MODEL_SCRAPING_EXTRACTION = GPT_4O_MINI
