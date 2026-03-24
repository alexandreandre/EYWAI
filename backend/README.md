# 📚 Documentation Backend API - SIRH Multi-Entreprises

> **Point d’entrée actuel** : `app.main:app` (FastAPI). L’API est un **monolithe modulaire** : le détail des couches et des conventions se trouve dans **[app/README.md](app/README.md)**.

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture](#architecture)
3. [Technologies utilisées](#technologies-utilisées)
4. [Arborescence du projet](#arborescence-du-projet)
5. [Fonctionnalités principales](#fonctionnalités-principales)
6. [Configuration et installation](#configuration-et-installation)
7. [Structure des modules](#structure-des-modules)
8. [Sécurité et authentification](#sécurité-et-authentification)
9. [Base de données](#base-de-données)
10. [API Endpoints](#api-endpoints)
11. [Déploiement](#déploiement)

---

## 🎯 Vue d'ensemble

Le backend du SIRH est une **API RESTful** construite avec **FastAPI** qui gère toutes les fonctionnalités d'un système de gestion des ressources humaines multi-entreprises. Il offre une architecture modulaire, sécurisée et scalable pour gérer les employés, la paie, les absences, les notes de frais, et bien plus encore.

### Caractéristiques principales

- ✅ **Multi-entreprises** : Isolation complète des données par entreprise (Row Level Security)
- ✅ **Multi-rôles** : Super Admin, Admin, RH, Manager, Salarié avec permissions granulaires
- ✅ **Authentification JWT** : Via Supabase Auth
- ✅ **Génération de documents** : Bulletins de paie, contrats, documents de sortie (PDF)
- ✅ **Moteur de calcul de paie** : Intégration avec un moteur Python dédié
- ✅ **Forfait jour** : Support complet du forfait jour avec calculs adaptés
- ✅ **Simulation de paie** : Calcul inverse (Net → Brut) et bulletins simulés
- ✅ **Scraping automatisé** : Mise à jour automatique des barèmes légaux (SMIC, cotisations, etc.)
- ✅ **IA et Copilot** : Assistant intelligent pour requêtes SQL et gestion des conventions collectives
- ✅ **Entretiens annuels** : Gestion complète des entretiens d'évaluation
- ✅ **Titres de séjour** : Suivi et alertes d'expiration
- ✅ **Saisies et avances** : Gestion des saisies mensuelles et avances sur salaire
- ✅ **Primes et participation** : Catalogue de primes et gestion participation/intéressement
- ✅ **Mutuelle entreprise** : Gestion des formules mutuelle
- ✅ **Repos compensateur** : Calcul automatique des COR

---

## 🏗️ Architecture

### Architecture générale

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/REST
                       │ JWT Token
                       │ X-Active-Company Header
┌──────────────────────▼──────────────────────────────────────┐
│                   Backend API (FastAPI)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Routers    │  │   Services   │  │   Schemas   │      │
│  │  (Endpoints) │  │  (Business)  │  │ (Validation)│      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                  │              │
│         └─────────────────┼──────────────────┘              │
│                           │                                 │
│  ┌───────────────────────▼──────────────────────────────┐  │
│  │              Security Layer (JWT Auth)                │  │
│  │         Multi-Company Context Management              │  │
│  └───────────────────────┬──────────────────────────────┘  │
└───────────────────────────┼─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│              Supabase (PostgreSQL + Auth)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Database   │  │     Auth     │  │   Storage   │      │
│  │  (PostgreSQL)│  │   (JWT)      │  │   (Files)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│         Moteur de Calcul de Paie (Python)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Calcul Brut │  │  Cotisations │  │   Simulation│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Flux de requête typique

1. **Client** → Envoie requête avec JWT token et header `X-Active-Company`
2. **Security Layer** → Valide le token, charge l'utilisateur et ses accès multi-entreprises
3. **Context Management** → Définit le contexte PostgreSQL pour l'entreprise active (RLS)
4. **Router** → Traite la requête et appelle le service approprié
5. **Service** → Exécute la logique métier et interagit avec Supabase
6. **Response** → Retourne les données avec en-têtes CORS appropriés

---

## 🛠️ Technologies utilisées

### Framework et runtime

- **FastAPI** : Framework web moderne et performant pour Python
- **Python 3.11+** : Langage de programmation (image Docker `python:3.11-slim`)
- **Uvicorn** : Serveur ASGI pour FastAPI

### Base de données et authentification

- **Supabase** : Backend-as-a-Service
  - PostgreSQL : Base de données relationnelle
  - Supabase Auth : Authentification JWT
  - Supabase Storage : Stockage de fichiers (PDF, logos, etc.)
  - Row Level Security (RLS) : Isolation multi-tenant

### Bibliothèques principales

- **Pydantic** : Validation de données et schémas
- **python-dotenv** : Gestion des variables d'environnement
- **gotrue** : Client Supabase Auth
- **requests** : Requêtes HTTP
- **Jinja2** : Templates pour génération de documents
- **WeasyPrint** : Génération de PDF depuis HTML
- **PyPDF2 / pdfplumber** : Traitement de PDF
- **openai** : Intégration IA pour copilot et parsing de contrats
- **selenium / beautifulsoup4** : Scraping web automatisé
- **dramatiq[redis]** : File de tâches asynchrones (Redis requis si activé)

---

## 📁 Arborescence du projet

```
backend/
├── requirements.txt
├── Dockerfile
├── pytest.ini
├── README.md                 # Ce fichier
│
├── app/                      # Application FastAPI (package Python `app`)
│   ├── README.md             # Architecture modular monolith
│   ├── main.py               # FastAPI, CORS, healthcheck `/health`
│   ├── api/router.py         # Inclusion de tous les routers des modules
│   ├── core/                 # Config, base de données, chemins, logging
│   ├── shared/               # Transverse (kernel, infra PDF, email, etc.)
│   ├── runtime/              # Ressources runtime (ex. templates paie)
│   └── modules/              # Domaines métier (un dossier = un module)
│       ├── auth/
│       ├── employees/
│       ├── payslips/
│       ├── payroll/          # Moteur de paie, documents, solde de tout compte, exports paie
│       ├── absences/
│       ├── expenses/
│       ├── schedules/
│       ├── monthly_inputs/
│       ├── saisies_avances/
│       ├── employee_exits/
│       ├── exports/
│       ├── collective_agreements/
│       ├── copilot/
│       ├── contract_parser/
│       ├── companies/
│       ├── company_groups/
│       ├── users/
│       ├── access_control/
│       ├── dashboard/
│       ├── super_admin/
│       ├── scraping/
│       ├── rates/
│       ├── residence_permits/
│       ├── rib_alerts/
│       ├── annual_reviews/
│       ├── bonus_types/
│       ├── participation/
│       ├── mutuelle_types/
│       ├── repos_compensateur/
│       ├── medical_follow_up/
│       ├── cse/
│       ├── recruitment/
│       ├── promotions/
│       └── uploads/
│
└── tests/                    # Pytest : unit/, integration/, e2e/, migration/
    └── README.md
```

Les **préfixes de route** exacts et les schémas de requête/réponse sont la **source de vérité** : documentation interactive `/docs` et `/redoc` une fois l’API lancée.

---

## 🚀 Fonctionnalités principales

### 1. Gestion des employés

- **CRUD complet** : Création, lecture, mise à jour, suppression
- **Import/Export** : Import CSV, export de données
- **Génération de documents** : Contrats de travail, identifiants de connexion (PDF)
- **Gestion des contrats** : CDI, CDD, stage, etc.
- **Historique** : Suivi des modifications

**Endpoints principaux :**
- `GET /api/employees` - Liste des employés
- `POST /api/employees` - Créer un employé
- `GET /api/employees/{id}` - Détails d'un employé
- `PUT /api/employees/{id}` - Modifier un employé
- `DELETE /api/employees/{id}` - Supprimer un employé
- `POST /api/employees/{id}/contract` - Générer un contrat PDF
- `POST /api/employees/{id}/credentials` - Générer identifiants PDF

### 2. Gestion de la paie

- **Génération de bulletins** : Calcul automatique via moteur Python
- **Édition de bulletins** : Modification manuelle avec historique
- **Simulation de paie** : Calcul inverse (Net → Brut) et bulletins simulés
- **Historique** : Versioning complet des modifications
- **Export PDF** : Génération de bulletins au format PDF

**Endpoints principaux :**
- `POST /api/actions/generate-payslip` - Générer un bulletin
- `GET /api/me/payslips` - Mes bulletins (salarié)
- `GET /api/payslips` - Liste des bulletins (RH)
- `GET /api/payslips/{id}` - Détails d'un bulletin
- `POST /api/payslips/{id}/edit` - Éditer un bulletin
- `POST /api/payslips/{id}/restore` - Restaurer une version
- `GET /api/payslips/{id}/history` - Historique des modifications

### 3. Simulation de paie

- **Calcul inverse** : Déterminer le brut à partir du net souhaité
- **Bulletins simulés** : Créer des simulations sans affecter les données réelles
- **Scénarios prédéfinis** : Augmentation, prime, heures supplémentaires, etc.
- **Comparaison** : Comparer simulation vs réel
- **Historique** : Consulter toutes les simulations d'un employé

**Endpoints principaux :**
- `POST /api/simulation/reverse-calculation` - Calcul inverse
- `POST /api/simulation/create-payslip` - Créer une simulation
- `GET /api/simulation/{id}` - Détails d'une simulation
- `GET /api/simulation/employee/{employee_id}` - Liste des simulations
- `POST /api/simulation/{id}/compare` - Comparer avec réel
- `DELETE /api/simulation/{id}` - Supprimer une simulation
- `GET /api/simulation/predefined-scenarios/{employee_id}` - Scénarios prédéfinis

### 4. Gestion des absences

- **Demandes de congés** : Création, validation, refus
- **Types d'absences** : Congés payés, RTT, maladie, etc.
- **Calendrier** : Visualisation des absences
- **Statistiques** : Taux d'absentéisme, jours restants

**Endpoints principaux :**
- `GET /api/absences` - Liste des absences
- `POST /api/absences` - Créer une demande
- `PUT /api/absences/{id}/approve` - Approuver
- `PUT /api/absences/{id}/reject` - Refuser
- `GET /api/absences/calendar` - Calendrier des absences

### 5. Notes de frais

- **Déclaration** : Création de notes de frais
- **Validation** : Workflow de validation
- **Types** : Frais kilométriques, repas, hébergement, etc.
- **Justificatifs** : Upload de fichiers

**Endpoints principaux :**
- `GET /api/expenses` - Liste des notes de frais
- `POST /api/expenses` - Créer une note de frais
- `PUT /api/expenses/{id}/approve` - Approuver
- `PUT /api/expenses/{id}/reject` - Refuser

### 6. Calendriers et plannings

- **Gestion des horaires** : Création et modification de plannings
- **Calendrier mensuel** : Visualisation des horaires
- **Types de planning** : Standard, variable, équipe

**Endpoints principaux :**
- `GET /api/schedules` - Liste des plannings
- `POST /api/schedules` - Créer un planning
- `GET /api/schedules/me` - Mes plannings (salarié)
- `GET /api/schedules/rh` - Plannings RH (gestion)

### 7. Saisies mensuelles

- **Saisie des données** : Heures, primes, absences du mois
- **Validation** : Workflow de validation avant paie
- **Historique** : Suivi des saisies

**Endpoints principaux :**
- `GET /api/monthly-inputs` - Liste des saisies
- `POST /api/monthly-inputs` - Créer une saisie
- `PUT /api/monthly-inputs/{id}` - Modifier une saisie

### 8. Sorties de salariés

- **Gestion des sorties** : Démission, licenciement, rupture conventionnelle, etc.
- **Génération de documents** : Attestation Pôle Emploi, certificat de travail, solde de tout compte
- **Édition de documents** : Modification manuelle avec historique
- **Calcul automatique** : Calcul du solde selon le type de sortie

**Endpoints principaux :**
- `GET /api/employee-exits` - Liste des sorties
- `POST /api/employee-exits` - Créer une sortie
- `GET /api/employee-exits/{id}` - Détails d'une sortie
- `POST /api/employee-exits/{id}/generate-document` - Générer un document
- `GET /api/employee-exits/{id}/documents/{document_id}` - Détails d'un document
- `POST /api/employee-exits/{id}/documents/{document_id}/edit` - Éditer un document
- `POST /api/employee-exits/{id}/documents/{document_id}/publish` - Publier un document

### 9. Conventions collectives

- **Catalogue** : Liste des conventions collectives disponibles
- **Recherche** : Recherche par IDCC, secteur, etc.
- **Chat IA** : Assistant pour questions sur les conventions
- **Intégration** : Utilisation dans les calculs de paie

**Endpoints principaux :**
- `GET /api/collective-agreements` - Liste des conventions
- `GET /api/collective-agreements/{id}` - Détails d'une convention
- `POST /api/collective-agreements/chat` - Chat IA sur conventions

### 10. Copilot IA

- **Text-to-SQL** : Conversion de questions en langage naturel en requêtes SQL
- **Agent IA** : Assistant intelligent avec planification et recherche
- **Requêtes sécurisées** : Respect des permissions et isolation multi-entreprises

**Endpoints principaux :**
- `POST /api/copilot/query` - Requête Text-to-SQL
- `POST /api/copilot/...` - Agent IA (voir tags **Copilot** dans `/docs`)

### 11. Scraping automatisé (Super Admin)

- **Mise à jour automatique** : SMIC, cotisations, plafonds sécurité sociale
- **Sources multiples** : Validation par consensus (3 sources)
- **Alertes** : Notifications en cas d'erreur
- **Historique** : Suivi des exécutions

**Endpoints principaux :**
- `GET /api/scraping/dashboard` - Tableau de bord scraping
- `GET /api/scraping/sources` - Liste des sources
- `POST /api/scraping/execute` - Exécuter un scraping
- `GET /api/scraping/jobs` - Historique des jobs
- `GET /api/scraping/alerts` - Alertes

### 12. Gestion multi-entreprises

- **Isolation des données** : Row Level Security (RLS)
- **Accès multiples** : Un utilisateur peut accéder à plusieurs entreprises
- **Groupes d'entreprises** : Organisation en groupes
- **Permissions granulaires** : Par entreprise et par rôle

**Endpoints principaux :**
- `GET /api/users/me` - Informations utilisateur avec accès entreprises
- `GET /api/company` - Détails de l'entreprise active
- `GET /api/company-groups` - Liste des groupes
- `GET /api/company-groups/{id}` - Détails d'un groupe

### 13. Super Admin

- **Gestion des entreprises** : Création, modification, suppression
- **Gestion des utilisateurs** : Attribution de rôles et permissions
- **Monitoring** : Statistiques globales
- **Réduction Fillon** : Configuration et suivi

**Endpoints principaux :**
- `GET /api/super-admin/dashboard` - Tableau de bord
- `GET /api/super-admin/companies` - Liste des entreprises
- `POST /api/super-admin/companies` - Créer une entreprise
- `GET /api/super-admin/users` - Liste des utilisateurs
- `GET /api/super-admin/monitoring` - Monitoring

### 14. Exports

- **Export de données** : Export CSV/Excel des données RH et paie
- **Filtres avancés** : Par période, employé, type de données
- **Formats multiples** : CSV, Excel

**Endpoints principaux :**
- `GET /api/exports/employees` - Export des employés
- `GET /api/exports/payslips` - Export des bulletins
- `GET /api/exports/absences` - Export des absences

### 15. Titres de séjour

- **Suivi des titres** : Gestion des titres de séjour des employés
- **Alertes d'expiration** : Notifications automatiques
- **Renouvellements** : Suivi des renouvellements

**Endpoints principaux :**
- `GET /api/residence-permits` - Liste des titres de séjour
- `POST /api/residence-permits` - Créer un titre de séjour
- `PUT /api/residence-permits/{id}` - Modifier un titre
- `GET /api/residence-permits/expiring` - Titres expirant bientôt

### 16. Alertes RIB

- **Détection de modifications** : Alertes lors de changements de RIB
- **Détection de doublons** : Identification des RIB en double
- **Notifications** : Alertes automatiques aux RH

**Endpoints principaux :**
- `GET /api/rib-alerts` - Liste des alertes
- `GET /api/rib-alerts/duplicates` - RIB en double
- `POST /api/rib-alerts/{id}/resolve` - Résoudre une alerte

### 17. Entretiens annuels

- **Création et gestion** : Gestion complète des entretiens d'évaluation
- **Objectifs et compétences** : Suivi des objectifs et évaluation des compétences
- **Historique** : Consultation de l'historique des entretiens
- **Espace salarié** : Consultation par le salarié

**Endpoints principaux :**
- `GET /api/annual-reviews` - Liste des entretiens
- `POST /api/annual-reviews` - Créer un entretien
- `GET /api/annual-reviews/{id}` - Détails d'un entretien
- `PUT /api/annual-reviews/{id}` - Modifier un entretien
- `GET /api/annual-reviews/employee/{employee_id}` - Entretiens d'un employé

### 18. Types de primes

- **Catalogue de primes** : Gestion des types de primes disponibles
- **Intégration paie** : Utilisation dans les bulletins
- **Configuration** : Paramétrage des primes

**Endpoints principaux :**
- `GET /api/bonus-types` - Liste des types de primes
- `POST /api/bonus-types` - Créer un type de prime
- `PUT /api/bonus-types/{id}` - Modifier un type

### 19. Participation et Intéressement

- **Gestion** : Configuration et suivi de la participation et de l'intéressement
- **Calcul automatique** : Intégration dans les bulletins
- **Historique** : Suivi des versements

**Endpoints principaux :**
- `GET /api/participation` - Configuration participation
- `POST /api/participation` - Créer une participation
- `GET /api/participation/employee/{employee_id}` - Participation d'un employé

### 20. Mutuelle entreprise

- **Catalogue de formules** : Gestion des formules mutuelle disponibles
- **Adhésions** : Gestion des adhésions des employés
- **Intégration paie** : Prélèvements dans les bulletins

**Endpoints principaux :**
- `GET /api/mutuelle-types` - Liste des formules mutuelle
- `POST /api/mutuelle-types` - Créer une formule
- `GET /api/mutuelle-types/{id}/employees` - Employés adhérents

### 21. Repos compensateur

- **Calcul automatique** : Calcul des repos compensateurs (COR)
- **Heures supplémentaires** : Suivi des heures sup
- **Repos à prendre** : Gestion des repos à prendre

**Endpoints principaux :**
- `GET /api/repos-compensateur` - Liste des repos compensateurs
- `POST /api/repos-compensateur/calculate` - Calculer les COR
- `GET /api/repos-compensateur/employee/{employee_id}` - COR d'un employé

### 22. Saisies et avances

- **Saisies mensuelles** : Gestion des saisies (heures, primes, absences)
- **Avances sur salaire** : Gestion des avances
- **Workflow de validation** : Validation avant paie

**Endpoints principaux :**
- `GET /api/saisies-avances` - Liste des saisies et avances
- `POST /api/saisies-avances/saisie` - Créer une saisie
- `POST /api/saisies-avances/avance` - Créer une avance
- `PUT /api/saisies-avances/{id}/validate` - Valider

---

## ⚙️ Configuration et installation

### Prérequis

- Python 3.10+
- PostgreSQL (via Supabase)
- Redis (optionnel, pour Dramatiq)

### Installation

1. **Cloner le dépôt**
```bash
git clone <repository-url>
cd backend_api
```

2. **Créer un environnement virtuel**
```bash
python -m venv venv
source venv/bin/activate  # Sur macOS/Linux
# ou
venv\Scripts\activate     # Sur Windows
```

3. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

4. **Configurer les variables d'environnement**

Créer un fichier `.env` à la racine de `backend_api/` :

```env
# Supabase
SUPABASE_URL=https://votre-projet.supabase.co
SUPABASE_KEY=votre-clé-anon

# OpenAI (pour copilot et parsing)
OPENAI_API_KEY=votre-clé-openai

# SMTP (pour emails)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre-email@gmail.com
SMTP_PASSWORD=votre-mot-de-passe
SMTP_FROM=noreply@sirh.com

# Redis (optionnel, pour Dramatiq)
REDIS_URL=redis://localhost:6379/0
```

5. **Lancer l'application**

```bash
# Mode développement
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Mode production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker

```bash
# Construire l'image
docker build -t sirh-backend .

# Lancer le conteneur
docker run -p 8000:8000 --env-file .env sirh-backend
```

---

## 🔐 Sécurité et authentification

### Authentification JWT

L'authentification est gérée par **Supabase Auth** avec des tokens JWT.

**Flux d'authentification :**

1. **Login** : `POST /api/auth/login`
   - Email + mot de passe
   - Retourne un JWT token

2. **Validation** : Chaque requête nécessite le header :
   ```
   Authorization: Bearer <token>
   ```

3. **Multi-entreprises** : Header supplémentaire pour l'entreprise active :
   ```
   X-Active-Company: <company_id>
   ```

### Gestion des permissions

Le système utilise une hiérarchie de rôles :

- **Super Admin** : Accès à toutes les entreprises
- **Admin** : Gestion complète de son entreprise
- **RH** : Gestion RH de son entreprise
- **Manager** : Gestion de son équipe
- **Salarié** : Accès à ses propres données

### Row Level Security (RLS)

Toutes les tables PostgreSQL utilisent RLS pour isoler les données par entreprise :

```sql
-- Exemple de politique RLS
CREATE POLICY "Users can only see their company's employees"
ON employees
FOR SELECT
USING (company_id = current_setting('app.current_company_id')::uuid);
```

Le contexte d'entreprise est défini automatiquement par `security.py` via la fonction PostgreSQL `set_session_company()`.

---

## 🗄️ Base de données

### Schéma principal

```
companies (entreprises)
├── profiles (utilisateurs)
│   └── user_company_accesses (accès multi-entreprises)
├── employees (employés)
│   ├── payslips (bulletins de paie)
│   ├── absence_requests (demandes d'absence)
│   ├── expense_reports (notes de frais)
│   ├── monthly_inputs (saisies mensuelles)
│   ├── schedules (plannings)
│   ├── employee_exits (sorties)
│   └── simulations (simulations de paie)
├── collective_agreements (conventions collectives)
└── company_groups (groupes d'entreprises)
```

### Migrations

Les migrations SQL sont dans le dossier `migrations/`. L'ordre d'exécution est documenté dans `migrations/README_PRINCIPAL.md`.

**Exécuter les migrations :**

```bash
# Via psql
psql -U postgres -d votre_base -f migrations/run_all_migrations.sql

# Ou via Supabase CLI
supabase db push
```

---

## 📡 API Endpoints

### Structure des endpoints

Tous les endpoints suivent cette structure :

```
/api/{module}/{action}
```

**Exemples :**
- `GET /api/employees` - Liste des employés
- `POST /api/employees` - Créer un employé
- `GET /api/employees/{id}` - Détails d'un employé
- `PUT /api/employees/{id}` - Modifier un employé
- `DELETE /api/employees/{id}` - Supprimer un employé

### Documentation interactive

FastAPI génère automatiquement une documentation interactive :

- **Swagger UI** : `http://localhost:8000/docs`
- **ReDoc** : `http://localhost:8000/redoc`

### Gestion des erreurs

Toutes les erreurs suivent ce format :

```json
{
  "detail": "Message d'erreur descriptif"
}
```

**Codes HTTP standards :**
- `200` : Succès
- `201` : Créé
- `400` : Requête invalide
- `401` : Non authentifié
- `403` : Non autorisé
- `404` : Non trouvé
- `422` : Erreur de validation
- `500` : Erreur serveur

---

## 🚀 Déploiement

### Déploiement sur Google Cloud Run

1. **Construire l'image Docker**
```bash
docker build -t gcr.io/votre-projet/sirh-backend .
```

2. **Pousser l'image**
```bash
docker push gcr.io/votre-projet/sirh-backend
```

3. **Déployer sur Cloud Run**
```bash
gcloud run deploy sirh-backend \
  --image gcr.io/votre-projet/sirh-backend \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated
```

### Variables d'environnement Cloud Run

Configurer dans la console Cloud Run ou via CLI :

```bash
gcloud run services update sirh-backend \
  --set-env-vars SUPABASE_URL=...,SUPABASE_KEY=...
```

### Health Check

L'endpoint `/` retourne un statut de santé :

```bash
curl https://votre-api.run.app/
# {"message": "API du SaaS RH fonctionnelle !"}
```

---

## 📝 Notes techniques

### Performance

- **Cache** : Utilisation de Redis pour le cache (optionnel)
- **Pagination** : Tous les endpoints de liste supportent la pagination
- **Lazy loading** : Chargement à la demande des données lourdes

### Logging

Les logs sont écrits dans la console avec différents niveaux :
- `INFO` : Informations générales
- `WARNING` : Avertissements
- `ERROR` : Erreurs
- `DEBUG` : Détails de débogage

### Tests

```bash
# Lancer les tests (à implémenter)
pytest tests/
```

---

## 📚 Ressources supplémentaires

- [Documentation FastAPI](https://fastapi.tiangolo.com/)
- [Documentation Supabase](https://supabase.com/docs)
- [Migrations README](migrations/README_PRINCIPAL.md)
- [Moteur de calcul README](backend_calculs/README.md)

---

## 🤝 Contribution

Pour contribuer au projet :

1. Créer une branche depuis `main`
2. Implémenter les modifications
3. Tester localement
4. Créer une Pull Request

---

## 📄 Licence

[Spécifier la licence du projet]

---

**Dernière mise à jour** : Février 2026

