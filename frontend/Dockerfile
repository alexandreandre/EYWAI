# Fichier: frontend/Dockerfile

# --- ÉTAPE 1 : BUILD ---
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# On s'assure que VITE_API_URL est utilisé pendant le build
ARG VITE_API_URL=https://sirh-backend-505040845625.europe-west1.run.app
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# --- ÉTAPE 2 : PRODUCTION ---
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.template.conf /etc/nginx/nginx.template.conf

# Variables d'environnement par défaut
ENV PORT=80

CMD sh -c "envsubst '\$PORT' < /etc/nginx/nginx.template.conf > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"
