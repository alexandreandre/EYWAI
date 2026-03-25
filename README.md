# 🏢 SIRH - Système d'Information des Ressources Humaines

> **Plateforme SaaS complète de gestion RH multi-entreprises** avec gestion de paie, absences, notes de frais, simulations et bien plus encore.  
> Code source du dépôt **EYWAI**.

[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18.3+-61dafb.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.8+-3178c6.svg)](https://www.typescriptlang.org/)

---

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture globale](#architecture-globale)
3. [Structure du projet](#structure-du-projet)
4. [Fonctionnalités principales](#fonctionnalités-principales)
5. [Prérequis](#prérequis)
6. [Installation et démarrage](#installation-et-démarrage)
7. [Développement](#développement)
8. [Déploiement](#déploiement)
9. [Documentation](#documentation)
10. [Contribution](#contribution)

---

## 🎯 Vue d'ensemble

**SIRH** est une plateforme SaaS complète de gestion des ressources humaines conçue pour les entreprises de toutes tailles. Elle offre une solution intégrée pour gérer les employés, la paie, les absences, les notes de frais, et bien plus encore, avec un système multi-entreprises sécurisé.

### Caractéristiques principales

- ✅ **Multi-entreprises** : Isolation complète des données par entreprise (Row Level Security)
- ✅ **Multi-rôles** : Super Admin, Admin, RH, Manager, Salarié avec permissions granulaires
- ✅ **Gestion complète de la paie** : Génération, édition, simulation avec calcul inverse
- ✅ **Forfait jour** : Gestion des employés en forfait jour avec calendrier adapté
- ✅ **Documents automatisés** : Bulletins de paie, contrats, documents de sortie (PDF)
- ✅ **IA intégrée** : Copilot Text-to-SQL et Agent IA pour assistance
- ✅ **Scraping automatisé** : Mise à jour automatique des barèmes légaux
- ✅ **Interface moderne** : React + TypeScript avec design responsive
- ✅ **API RESTful** : Backend FastAPI performant et documenté
- ✅ **Entretiens annuels** : Gestion complète des entretiens d'évaluation
- ✅ **Titres de séjour** : Suivi des titres de séjour des employés
- ✅ **Saisies et avances** : Gestion des saisies mensuelles et avances sur salaire
- ✅ **Suivi médical** : Parcours visite médicale (RH et espace collaborateur)
- ✅ **CSE** : Espace dédié CSE (RH et représentants)
- ✅ **Recrutement & promotions** : Modules associés côté API et interface RH

### Technologies utilisées

**Backend :**
- FastAPI (Python 3.11+), application modulaire sous `backend/app/`
- Supabase (PostgreSQL + Auth)
- Moteur de calcul de paie intégré au module `payroll`
- Docker (image backend dans `backend/Dockerfile`)

**Frontend :**
- React 18 + TypeScript
- Vite
- Tailwind CSS + Shadcn/ui
- React Query
- Docker

---

## 🏗️ Architecture globale

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React)                         │
│              Port: 8080 (dev) / 80 (prod)                  │
│         Interface utilisateur multi-rôles                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/REST
                       │ JWT Token
                       │ X-Active-Company Header
┌──────────────────────▼──────────────────────────────────────┐
│              Backend API (FastAPI)                          │
│              Port: 8000 (dev) / 8080 (prod)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Routers    │  │   Services   │  │   Schemas     │   │
│  │  (Endpoints) │  │  (Business)  │  │ (Validation) │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
│                           │                                │
│  ┌───────────────────────▼──────────────────────────────┐ │
│  │      Security Layer (JWT Auth + Multi-Company)        │ │
│  └───────────────────────┬──────────────────────────────┘ │
└───────────────────────────┼─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│              Supabase (PostgreSQL + Auth)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Database   │  │     Auth     │  │   Storage    │      │
│  │  (PostgreSQL) │  │   (JWT)     │  │   (Files)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│         Moteur de Calcul de Paie (Python)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Calcul Brut │  │  Cotisations │  │   Simulation│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Flux de communication

1. **Frontend** → Envoie requêtes HTTP avec token JWT et header `X-Active-Company`
2. **Backend** → Valide l'authentification et définit le contexte d'entreprise (RLS)
3. **Backend** → Traite la requête et interagit avec Supabase
4. **Backend** → Appelle le moteur de calcul si nécessaire (paie)
5. **Backend** → Retourne les données au frontend
6. **Frontend** → Met à jour l'interface utilisateur

---

## 📁 Structure du projet

```
EYWAI/   (racine du dépôt)
├── README.md                 # Ce fichier
├── DEPLOIEMENT.md            # Guide de déploiement (ex. Cloud Run)
│
├── backend/                  # API FastAPI — monolithe modulaire
│   ├── README.md             # Vue d’ensemble API, domaines, endpoints
│   ├── app/README.md         # Architecture détaillée (couches, modules)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── pytest.ini
│   ├── app/                  # Code applicatif
│   │   ├── main.py           # Point d’entrée FastAPI (`app.main:app`)
│   │   ├── api/router.py     # Agrégation des routers des modules
│   │   ├── core/             # Config, DB, sécurité
│   │   ├── shared/           # Transverse (PDF, utilitaires, etc.)
│   │   └── modules/          # Un dossier par domaine (auth, employees, payroll, …)
│   └── tests/                # Pytest (unit, integration, e2e) — voir tests/README.md
│
└── frontend/                 # SPA React + Vite + TypeScript
    ├── README.md
    ├── package.json
    ├── vite.config.ts        # Dev server : port 8080
    └── src/
        ├── pages/            # Écrans (RH, collaborateur, super-admin)
        ├── components/       # UI métier + Shadcn
        ├── api/              # Clients HTTP
        ├── contexts/         # Auth, entreprise, vue RH/collaborateur
        └── hooks/
```

### Modules principaux

- **`backend/app/`** : API REST FastAPI organisée par **modules métier** (`app/modules/<domaine>/` avec couches api → application → domain → infrastructure).
- **`frontend/`** : Interface React (Vite), consommation de l’API via `VITE_API_URL`.
- **Schéma SQL / RLS** : géré côté projet Supabase (pas de dossier `migrations/` versionné à la racine de ce dépôt).

---

## 🚀 Fonctionnalités principales

### Gestion des employés
- CRUD complet des employés
- Import/Export CSV
- Génération de contrats et identifiants (PDF)
- Gestion des contrats (CDI, CDD, stage, etc.)

### Gestion de la paie
- Génération automatique de bulletins
- Édition manuelle avec historique complet
- Simulation de paie (calcul inverse Net → Brut)
- Export PDF des bulletins
- Versioning des modifications

### Absences et congés
- Demandes de congés avec workflow de validation
- Calendrier des absences
- Statistiques d'absentéisme
- Types multiples (CP, RTT, maladie, etc.)

### Notes de frais
- Déclaration de notes de frais
- Workflow de validation
- Upload de justificatifs
- Types variés (kilométriques, repas, hébergement)

### Calendriers et plannings
- Gestion des horaires
- Calendrier mensuel interactif
- Types de planning (standard, variable, équipe)
- **Forfait jour** : Interface adaptée avec cases à cocher pour les jours travaillés

### Sorties de salariés
- Gestion des sorties (démission, licenciement, etc.)
- Génération automatique de documents :
  - Certificat de travail
  - Attestation Pôle Emploi
  - Solde de tout compte
- Édition manuelle avec historique

### Simulation de paie
- Calcul inverse (déterminer le brut à partir du net)
- Bulletins simulés sans affecter les données réelles
- Scénarios prédéfinis (augmentation, prime, heures sup)
- Comparaison simulation vs réel

### Conventions collectives
- Catalogue des conventions disponibles
- Recherche par IDCC, secteur
- Chat IA pour questions sur les conventions
- Intégration dans les calculs de paie

### Copilot IA
- **Text-to-SQL** : Conversion de questions en langage naturel en SQL
- **Agent IA** : Assistant intelligent avec planification et recherche
- Requêtes sécurisées avec respect des permissions

### Scraping automatisé (Super Admin)
- Mise à jour automatique des barèmes légaux
- Sources multiples avec validation par consensus
- Alertes en cas d'erreur
- Historique des exécutions

### Multi-entreprises
- Isolation complète des données (RLS)
- Accès multiples pour un même utilisateur
- Groupes d'entreprises
- Permissions granulaires par entreprise

### Super Admin
- Gestion des entreprises
- Gestion des utilisateurs
- Monitoring global
- Configuration du scraping

### Entretiens annuels
- Création et gestion des entretiens d'évaluation
- Suivi des objectifs et compétences
- Historique des entretiens par employé
- Espace salarié pour consultation

### Titres de séjour
- Suivi des titres de séjour des employés
- Alertes d'expiration
- Gestion des renouvellements

### Saisies et avances
- Saisies mensuelles (heures, primes, absences)
- Gestion des avances sur salaire
- Workflow de validation

### Primes et participation
- Catalogue de types de primes
- Gestion de la participation et de l'intéressement
- Calcul automatique dans les bulletins

### Mutuelle entreprise
- Catalogue des formules mutuelle
- Gestion des adhésions
- Intégration dans les bulletins de paie

### Repos compensateur
- Calcul automatique des repos compensateurs (COR)
- Gestion des heures supplémentaires
- Suivi des repos à prendre

---

## 📦 Prérequis

### Pour le développement local

**Backend :**
- Python 3.11 ou supérieur (aligné sur `backend/Dockerfile`)
- PostgreSQL (via Supabase)
- pip (gestionnaire de paquets Python)

**Frontend :**
- Node.js 18 ou supérieur
- npm, yarn ou pnpm

**Optionnel :**
- Docker et Docker Compose (pour déploiement local)
- Google Cloud SDK (pour déploiement Cloud Run)

### Services externes requis

- **Supabase** : Base de données PostgreSQL + Authentification
  - Créer un projet sur [supabase.com](https://supabase.com)
  - Récupérer `SUPABASE_URL` et `SUPABASE_KEY`

- **OpenAI** (optionnel) : Pour le copilot IA
  - Créer une clé API sur [platform.openai.com](https://platform.openai.com)

- **SMTP** (optionnel) : Pour l'envoi d'emails
  - Configuration Gmail ou Brevo (voir `CONFIGURATION_SMTP_*.md`)

---

## 🛠️ Installation et démarrage

### Option 1 : Développement local (recommandé pour le développement)

#### 1. Cloner le dépôt

```bash
git clone <repository-url>
cd EYWAI
```

#### 2. Configuration du backend

```bash
cd backend

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Sur macOS/Linux
# ou
venv\Scripts\activate     # Sur Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
# Créer un fichier `.env` à la racine de `backend/` (voir backend/README.md)
# Ex. : SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY (optionnel), REDIS_URL (optionnel, Dramatiq)
```

#### 3. Configuration du frontend

```bash
cd ../frontend

# Installer les dépendances
npm install
# ou
yarn install
# ou
pnpm install

# Configurer les variables d'environnement
# Créer un fichier .env avec :
# VITE_API_URL=http://localhost:8000
```

#### 4. Configuration de la base de données

Appliquer le schéma SQL, les politiques **RLS** et les données de référence sur votre projet **Supabase** (SQL Editor ou outil interne). Le dépôt ne contient pas de dossier `migrations/` à la racine ; se référer à la documentation d’exploitation du projet.

#### 5. Lancer les services

**Terminal 1 - Backend :**
```bash
cd backend
source venv/bin/activate  # Si pas déjà activé
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend :**
```bash
cd frontend
npm run dev
```

L'application sera accessible sur :
- **Frontend** : http://localhost:8080
- **Backend API** : http://localhost:8000
- **Documentation API** : http://localhost:8000/docs
- **Santé** : http://localhost:8000/health

### Option 2 : Docker (images séparées)

Il n’y a pas de `docker-compose.yml` à la racine de ce dépôt. Vous pouvez construire et lancer chaque service avec les `Dockerfile` du **backend** et du **frontend** (voir [DEPLOIEMENT.md](DEPLOIEMENT.md)).

---

## 💻 Développement

### Structure de développement

- **Backend** : Développement dans `backend/` (package `app.*`)
  - Les modifications sont rechargées automatiquement avec `--reload`
  - Documentation API disponible sur `/docs` (Swagger)

- **Frontend** : Développement dans `frontend/`
  - Hot reload automatique avec Vite
  - Les modifications sont visibles immédiatement

### Workflow recommandé

1. **Créer une branche** pour votre fonctionnalité
2. **Développer** en local avec les services lancés
3. **Tester** les modifications
4. **Commit** et push vers le dépôt
5. **Créer une Pull Request**

### Commandes utiles

**Backend :**
```bash
cd backend
source venv/bin/activate
# Toute la suite (voir backend/tests/README.md pour les marqueurs et l’auth de test)
pytest

# Exemple : exclure les tests e2e
pytest -m "not e2e"
```

**Frontend :**
```bash
cd frontend
# Linter
npm run lint

# Build de production
npm run build

# Prévisualiser le build
npm run preview
```

---

## 🚀 Déploiement

### Déploiement sur Google Cloud Run

Le projet est configuré pour être déployé sur **Google Cloud Run** avec Docker.

#### Prérequis

1. **Google Cloud SDK installé**
   ```bash
   # Voir https://cloud.google.com/sdk/docs/install
   ```

2. **Projet Google Cloud configuré**
   ```bash
   gcloud config set project saas-rh-prod
   ```

3. **Authentification Docker**
   ```bash
   gcloud auth configure-docker
   ```

#### Procédure

Suivre **[DEPLOIEMENT.md](DEPLOIEMENT.md)** pour le build des images, le push (ex. Artifact Registry / GCR) et le déploiement sur **Cloud Run** (variables d’environnement, ports, secrets).

#### Configuration des variables d'environnement

Dans la console Cloud Run, configurer les variables d'environnement pour chaque service :

**Backend :**
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `OPENAI_API_KEY` (optionnel)
- `SMTP_HOST`, `SMTP_PORT`, etc. (optionnel)

**Frontend :**
- `VITE_API_URL` : URL du backend déployé

---

## 📚 Documentation

### Documentation principale

- **[GUIDE_UTILISATION.md](GUIDE_UTILISATION.md)** : Guide pas à pas pour débutants (installation locale, Git, PR, IA).
- **[backend/README.md](backend/README.md)** : Vue d’ensemble du backend, domaines couverts, configuration.
- **[backend/app/README.md](backend/app/README.md)** : Architecture **modular monolith** (couches, conventions, démarrage).
- **[backend/tests/README.md](backend/tests/README.md)** : Organisation des tests Pytest.
- **[frontend/README.md](frontend/README.md)** : Frontend React / Vite, routes, stack UI.

### Documentation supplémentaire

- [DEPLOIEMENT.md](DEPLOIEMENT.md) — Déploiement (ex. Cloud Run, Docker).
- Documentation technique par module sous `backend/app/modules/*/(*.md)` (décisions, migrations de code).

### Documentation API

Une fois le backend lancé, la documentation interactive est disponible :

- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc

---

## 🔒 Sécurité

### Authentification

- **JWT Tokens** : Authentification via Supabase Auth
- **Expiration** : Tokens avec expiration configurable
- **Refresh** : Mécanisme de rafraîchissement des tokens

### Autorisation

- **Rôles** : Super Admin, Admin, RH, Manager, Salarié
- **Permissions granulaires** : Par entreprise et par fonctionnalité
- **Row Level Security (RLS)** : Isolation des données au niveau PostgreSQL

### Multi-entreprises

- **Isolation complète** : Chaque entreprise ne voit que ses données
- **Contexte d'entreprise** : Défini automatiquement via header `X-Active-Company`
- **Validation** : Vérification des accès à chaque requête

### Bonnes pratiques

- Ne jamais commiter les fichiers `.env`
- Utiliser des secrets managés en production (Google Secret Manager)
- Activer HTTPS en production
- Configurer les CORS correctement
- Auditer régulièrement les permissions

---

## 🧪 Tests

### Tests backend

```bash
cd backend
source venv/bin/activate
pytest
```

### Tests frontend

Aucun script `npm run test` n’est défini dans `frontend/package.json` pour l’instant ; le lint est disponible via `npm run lint`.

---

## 🤝 Contribution

**Nouveau sur le dépôt ?** Commence par **[GUIDE_UTILISATION.md](GUIDE_UTILISATION.md)** (installation, Git, messages de commit, hooks).

### Processus de contribution

1. **Fork** le projet (ou clone selon les droits de l’équipe)
2. **Créer une branche** pour votre fonctionnalité (`git checkout -b feature/ma-fonctionnalite`)
3. **Commit** vos changements au format **Conventional Commits**, par ex. `git commit -m "feat(frontend): ajouter l’export CSV"` — détail dans [CONTRIBUTING.md](CONTRIBUTING.md)
4. **Push** vers la branche (`git push -u origin feature/ma-fonctionnalite`)
5. **Créer une Pull Request**

### Standards de code

- **Backend** : Suivre PEP 8 (Python) ; Ruff via pre-commit sur les fichiers modifiés
- **Frontend** : Suivre les conventions ESLint configurées
- **Commits** : Format contrôlé par **commitlint** (voir [CONTRIBUTING.md](CONTRIBUTING.md))
- **Documentation** : Mettre à jour la documentation si nécessaire

---

## 📞 Support

### Problèmes courants

**Backend ne démarre pas :**
- Vérifier que les variables d'environnement sont configurées
- Vérifier que Supabase est accessible
- Consulter les logs pour plus de détails

**Frontend ne se connecte pas au backend :**
- Vérifier que `VITE_API_URL` est correctement configuré
- Vérifier que le backend est lancé et accessible
- Vérifier les CORS dans la configuration backend

**Erreurs de base de données :**
- Vérifier le schéma et les politiques RLS sur Supabase
- Contrôler les variables d’environnement et les logs backend

### Ressources

- **Documentation backend** : [backend/README.md](backend/README.md), [backend/app/README.md](backend/app/README.md)
- **Documentation frontend** : [frontend/README.md](frontend/README.md)
- **Issues GitHub** : Pour signaler des bugs ou demander des fonctionnalités

---

## 📄 Licence

[Spécifier la licence du projet]

---

## 🙏 Remerciements

- **Supabase** : Pour l'infrastructure backend
- **FastAPI** : Pour le framework API
- **React** : Pour le framework frontend
- **Shadcn/ui** : Pour les composants UI
- **Tous les contributeurs** : Pour leur travail sur le projet

---

## 📊 Statut du projet

- ✅ **Backend** : Production ready
- ✅ **Frontend** : Production ready
- ✅ **Multi-entreprises** : Implémenté et testé
- ✅ **Gestion de paie** : Fonctionnel avec édition
- ✅ **Simulation** : Fonctionnelle
- ✅ **Documents de sortie** : Génération et édition fonctionnelles
- ✅ **Tests backend** : Suite Pytest (unit, intégration, e2e / smoke) dans `backend/tests/`
- 🔄 **Tests frontend** : À étendre (pas de runner npm dédié actuellement)
- 🔄 **Documentation** : En amélioration continue

---

**Dernière mise à jour** : mars 2025

**Version** : suivre les tags Git / releases du dépôt (le frontend `package.json` reste en `0.0.0` pour l’outil de build).

