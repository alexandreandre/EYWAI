# Guide de Déploiement - SIRH sur Google Cloud Run

## Prérequis

1. **Google Cloud SDK installé** : https://cloud.google.com/sdk/docs/install
2. **Projet Google Cloud configuré** : `saas-rh-prod`
3. **Permissions IAM nécessaires** :
   - `roles/cloudbuild.builds.editor` (pour lancer des builds)
   - `roles/iam.serviceAccountUser` (pour utiliser le compte de service Cloud Build)
   - `roles/storage.admin` (pour uploader les sources)

**Note** : Docker n'est plus nécessaire, le build se fait directement dans Google Cloud Build.

## Déploiement Complet (Backend + Frontend)

### Option 1 : Avec le script automatisé (RECOMMANDÉ)

Depuis le dossier `beta_test`, exécutez :

```bash
# Rendre le script exécutable
chmod +x deploy.sh

# Lancer le déploiement
./deploy.sh
```

### Option 2 : Commandes manuelles

Si vous préférez exécuter les commandes une par une :

#### 1. Configuration initiale

```bash
# Configurer le projet
gcloud config set project saas-rh-prod

# Activer l'API Cloud Build (si pas déjà fait)
gcloud services enable cloudbuild.googleapis.com
```

#### 2. Déploiement du Backend

```bash
# Aller dans le dossier backend
cd backend_api

# Build avec Cloud Build et push automatique vers GCR
gcloud builds submit --tag gcr.io/saas-rh-prod/sirh-backend .

# Déploiement sur Cloud Run
gcloud run deploy sirh-backend \
  --image gcr.io/saas-rh-prod/sirh-backend \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080

# Retour au dossier racine
cd ..
```

#### 3. Déploiement du Frontend

```bash
# Aller dans le dossier frontend
cd frontend

# Build avec Cloud Build et push automatique vers GCR
# Le fichier cloudbuild.yaml garantit que VITE_API_URL est en HTTPS
gcloud builds submit --tag gcr.io/saas-rh-prod/sirh-frontend .

# Déploiement sur Cloud Run
gcloud run deploy sirh-frontend-app \
  --image gcr.io/saas-rh-prod/sirh-frontend \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080

# Retour au dossier racine
cd ..
```

**Note** : Le fichier `cloudbuild.yaml` dans le dossier `frontend/` configure automatiquement `VITE_API_URL` en HTTPS lors du build pour éviter les erreurs Mixed Content.

## Déploiement Partiel

### Déployer uniquement le Backend

```bash
cd backend_api && \
gcloud builds submit --tag gcr.io/saas-rh-prod/sirh-backend . && \
gcloud run deploy sirh-backend \
  --image gcr.io/saas-rh-prod/sirh-backend \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080 && \
cd ..
```

### Déployer uniquement le Frontend

```bash
cd frontend && \
# Le fichier cloudbuild.yaml garantit que VITE_API_URL est en HTTPS
gcloud builds submit --tag gcr.io/saas-rh-prod/sirh-frontend . && \
gcloud run deploy sirh-frontend-app \
  --image gcr.io/saas-rh-prod/sirh-frontend \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080 && \
cd ..
```

## Vérification du Déploiement

### Vérifier les services déployés

```bash
gcloud run services list --region europe-west1
```

### Récupérer les URLs des services

```bash
# URL du backend
gcloud run services describe sirh-backend --region europe-west1 --format 'value(status.url)'

# URL du frontend
gcloud run services describe sirh-frontend-app --region europe-west1 --format 'value(status.url)'
```

### Voir les logs en temps réel

```bash
# Logs du backend
gcloud run logs tail sirh-backend --region europe-west1

# Logs du frontend
gcloud run logs tail sirh-frontend-app --region europe-west1
```

## Variables d'Environnement (Backend)

Si vous devez ajouter des variables d'environnement au backend :

```bash
gcloud run services update sirh-backend \
  --region europe-west1 \
  --set-env-vars="SUPABASE_URL=votre_url,SUPABASE_KEY=votre_key"
```

## Avantages de cette méthode

1. **Pas besoin de Docker local** : Le build se fait dans le cloud
2. **Gestion automatique des permissions** : Plus de problèmes de permissions Docker
3. **Build plus rapide** : Utilise les ressources cloud optimisées
4. **Push automatique** : L'image est automatiquement poussée vers GCR après le build

## Résolution des Problèmes

### Erreur de permissions PERMISSION_DENIED

Si vous obtenez une erreur de permissions, un administrateur du projet doit vous accorder les rôles IAM suivants :

```bash
gcloud projects add-iam-policy-binding saas-rh-prod \
  --member="user:VOTRE_EMAIL@gmail.com" \
  --role="roles/cloudbuild.builds.editor"

gcloud projects add-iam-policy-binding saas-rh-prod \
  --member="user:VOTRE_EMAIL@gmail.com" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding saas-rh-prod \
  --member="user:VOTRE_EMAIL@gmail.com" \
  --role="roles/storage.admin"
```

### Erreur CORS
Si vous avez des erreurs CORS, vérifiez que l'URL du frontend est bien dans la liste `allowed_origins` du fichier `backend_api/core/config.py`.

### Erreur 502
- Vérifiez que le backend est bien déployé et accessible
- Vérifiez que le port 8080 est bien configuré dans les Dockerfiles

### Erreur 405
- Vérifiez la configuration nginx dans `frontend/nginx.template.conf`
- Vérifiez que `VITE_API_URL` pointe bien vers le backend

## URLs des Services

- **Frontend** : https://sirh-frontend-app-505040845625.europe-west1.run.app
- **Backend** : https://sirh-backend-505040845625.europe-west1.run.app

## Notes Importantes

1. Les images Docker sont stockées dans Google Container Registry (GCR)
2. Chaque déploiement crée une nouvelle révision du service
3. Le trafic est automatiquement routé vers la dernière révision
4. Les anciens conteneurs sont automatiquement supprimés après un certain temps
