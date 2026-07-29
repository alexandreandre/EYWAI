# Fichier: frontend/Dockerfile

# --- ÉTAPE 1 : BUILD ---
FROM mirror.gcr.io/library/node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# URL HTTPS du backend (Cloud Run, etc.) — obligatoire au build : --build-arg ou deploy.yml (vars.VITE_API_URL)
ARG VITE_API_URL
ARG VITE_APP_BUILD_ID
# "prod" (défaut) ou "test". Figé au build : le bandeau et le bouton de
# resynchro sont éliminés du bundle de production, pas masqués à l'exécution.
ARG VITE_APP_ENV=prod
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_APP_BUILD_ID=${VITE_APP_BUILD_ID}
ENV VITE_APP_ENV=${VITE_APP_ENV}
RUN npm run build

# --- ÉTAPE 2 : PRODUCTION ---
FROM mirror.gcr.io/library/nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.template.conf /etc/nginx/nginx.template.conf

# Variables d'environnement par défaut
ENV PORT=80

CMD sh -c "envsubst '\$PORT' < /etc/nginx/nginx.template.conf > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"
