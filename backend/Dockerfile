# Fichier: backend_api/Dockerfile

FROM python:3.11-slim

# Empêcher la création de fichiers .pyc + logs non bufferisés
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# --- ✅ AJOUT : Installation des dépendances système ---
# WeasyPrint : Pango, Cairo, GObject, Fontconfig
# OCR : Poppler (pdfinfo, pdftoppm), Tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    fontconfig \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgobject-2.0-0 \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-fra \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
# --- FIN DE L'AJOUT ---

# Installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le code de l'application
COPY . .

# --- ✅ Commande de démarrage : proxy headers pour HTTPS en prod (Cloud Run) ---
# Lit le port depuis la variable $PORT fournie par Cloud Run.
# --forwarded-allow-ips='*' : fait respecter X-Forwarded-Proto pour que les redirections
# (ex. slash final) utilisent https:// au lieu de http:// (évite Mixed Content).
CMD sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --forwarded-allow-ips='*'"
