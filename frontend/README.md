# 📚 Documentation Frontend - SIRH Multi-Entreprises

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture](#architecture)
3. [Technologies utilisées](#technologies-utilisées)
4. [Arborescence du projet](#arborescence-du-projet)
5. [Fonctionnalités principales](#fonctionnalités-principales)
6. [Configuration et installation](#configuration-et-installation)
7. [Structure des composants](#structure-des-composants)
8. [Gestion d'état](#gestion-détat)
9. [Routing](#routing)
10. [API Client](#api-client)
11. [Styles et UI](#styles-et-ui)
12. [Déploiement](#déploiement)

---

## 🎯 Vue d'ensemble

Le frontend du SIRH est une **application web moderne** construite avec **React 18** et **TypeScript** qui offre une interface utilisateur complète pour la gestion des ressources humaines. L'application est conçue pour être **multi-entreprises**, **responsive** et **accessible**.

### Caractéristiques principales

- ✅ **Multi-entreprises** : Sélecteur d'entreprise avec contexte global
- ✅ **Multi-rôles** : Interfaces adaptées selon le rôle (RH, Salarié, Manager, Admin, Super Admin)
- ✅ **Forfait jour** : Interface adaptée avec cases à cocher pour les jours travaillés
- ✅ **Responsive Design** : Compatible mobile, tablette et desktop
- ✅ **Dark Mode** : Support du thème sombre (via next-themes)
- ✅ **Composants réutilisables** : Bibliothèque Shadcn/ui
- ✅ **Gestion d'état moderne** : Context API + React Query
- ✅ **TypeScript** : Typage fort pour une meilleure maintenabilité
- ✅ **Performance** : Code splitting, lazy loading, optimisations

---

## 🏗️ Architecture

### Architecture générale

```
┌─────────────────────────────────────────────────────────────┐
│                    Application React                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Contexts   │  │   Hooks      │  │  Components  │     │
│  │  (Auth, Co.) │  │  (Custom)    │  │  (UI, Pages) │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                  │             │
│         └─────────────────┼──────────────────┘             │
│                           │                                 │
│  ┌───────────────────────▼──────────────────────────────┐  │
│  │              React Router (Routing)                 │  │
│  │         Protected Routes + Role Guards              │  │
│  └───────────────────────┬──────────────────────────────┘  │
│                           │                                 │
│  ┌───────────────────────▼──────────────────────────────┐  │
│  │              API Client (Axios)                      │  │
│  │    Interceptors (Auth, Multi-Company Headers)       │  │
│  └───────────────────────┬──────────────────────────────┘  │
└───────────────────────────┼─────────────────────────────────┘
                            │ HTTP/REST
                            │ JWT Token
                            │ X-Active-Company
┌───────────────────────────▼─────────────────────────────────┐
│              Backend API (FastAPI)                          │
└─────────────────────────────────────────────────────────────┘
```

### Flux de données

1. **Utilisateur** → Action dans l'interface
2. **Composant** → Appel à un hook ou fonction API
3. **API Client** → Ajout automatique des headers (Auth, Company)
4. **Backend** → Traitement et retour des données
5. **React Query** → Mise en cache et mise à jour de l'UI
6. **Composant** → Affichage des données

---

## 🛠️ Technologies utilisées

### Framework et langage

- **React 18.3+** : Bibliothèque UI
- **TypeScript 5.8+** : Typage statique
- **Vite 5.4+** : Build tool et dev server

### Routing

- **React Router DOM 6.30+** : Navigation et routing

### Gestion d'état

- **React Context API** : État global (Auth, Company)
- **TanStack React Query 5.83+** : Cache et synchronisation des données serveur
- **React Hooks** : Hooks personnalisés pour la logique métier

### UI et styles

- **Tailwind CSS 3.4+** : Framework CSS utility-first
- **Shadcn/ui** : Composants UI réutilisables basés sur Radix UI
- **Radix UI** : Primitives UI accessibles
- **Lucide React** : Icônes
- **Framer Motion** : Animations
- **next-themes** : Gestion du thème (dark/light)

### Formulaires et validation

- **React Hook Form 7.63+** : Gestion de formulaires
- **Zod 3.25+** : Validation de schémas
- **@hookform/resolvers** : Intégration Zod avec React Hook Form

### Visualisation de données

- **Recharts 2.15+** : Graphiques et visualisations
- **FullCalendar React** : Calendriers interactifs
- **React Big Calendar** : Calendrier alternatif

### Autres bibliothèques

- **Axios 1.12+** : Client HTTP
- **date-fns 3.6+** : Manipulation de dates
- **react-pdf** : Affichage de PDF
- **Sonner** : Notifications toast
- **cmdk** : Command palette

---

## 📁 Arborescence du projet

```
frontend/
├── index.html                      # Point d'entrée HTML
├── package.json                    # Dépendances npm
├── vite.config.ts                  # Configuration Vite
├── tsconfig.json                   # Configuration TypeScript
├── tailwind.config.ts              # Configuration Tailwind
├── postcss.config.js               # Configuration PostCSS
├── components.json                 # Configuration Shadcn/ui
│
├── public/                         # Assets statiques
│   ├── favicon.ico
│   ├── logo.png
│   └── ...
│
├── src/
│   ├── main.tsx                    # Point d'entrée React
│   ├── App.tsx                     # Composant racine et routing
│   ├── App.css                     # Styles globaux
│   ├── index.css                   # Styles Tailwind
│   │
│   ├── api/                        # Clients API
│   │   ├── apiClient.ts           # Client Axios configuré
│   │   ├── absences.ts            # API absences
│   │   ├── calendar.ts            # API calendrier
│   │   ├── collectiveAgreements.ts # API conventions collectives
│   │   ├── employeeExits.ts       # API sorties salariés
│   │   ├── expenses.ts            # API notes de frais
│   │   ├── payslips.ts            # API bulletins de paie
│   │   ├── permissions.ts         # API permissions
│   │   ├── saisies.ts             # API saisies mensuelles
│   │   ├── scraping.ts            # API scraping (Super Admin)
│   │   └── simulation.ts          # API simulation de paie
│   │
│   ├── components/                 # Composants React
│   │   ├── ui/                    # Composants UI de base (Shadcn)
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── table.tsx
│   │   │   ├── card.tsx
│   │   │   ├── app-sidebar.tsx    # Sidebar principale (RH)
│   │   │   ├── employee-sidebar.tsx # Sidebar salarié
│   │   │   └── ...
│   │   │
│   │   ├── dashboard/             # Composants dashboard
│   │   │   ├── chart-container.tsx
│   │   │   └── kpi-card.tsx
│   │   │
│   │   ├── forms/                 # Formulaires réutilisables
│   │   │   └── NewEmployeeForm.tsx
│   │   │
│   │   ├── payslip-edit/          # Composants édition bulletins
│   │   │   ├── PayslipHeaderSection.tsx
│   │   │   ├── CalculBrutSection.tsx
│   │   │   ├── CotisationsSection.tsx
│   │   │   ├── CongesAbsencesSection.tsx
│   │   │   ├── NotesDeFraisSection.tsx
│   │   │   ├── PrimesNonSoumisesSection.tsx
│   │   │   ├── SyntheseNetSection.tsx
│   │   │   ├── NotesSection.tsx
│   │   │   ├── PreviewPanel.tsx
│   │   │   └── HistoryPanel.tsx
│   │   │
│   │   ├── exit-document-edit/    # Composants édition documents sortie
│   │   │   ├── CertificatTravailSection.tsx
│   │   │   ├── AttestationPoleEmploiSection.tsx
│   │   │   ├── SoldeToutCompteSection.tsx
│   │   │   └── DynamicLineList.tsx
│   │   │
│   │   ├── exits/                 # Composants sorties salariés
│   │   │   ├── CreateExitDialog.tsx
│   │   │   └── ExitDetailsPanel.tsx
│   │   │
│   │   ├── simulation/            # Composants simulation de paie
│   │   │   ├── PayslipSimulationForm.tsx
│   │   │   ├── PayslipSimulationResult.tsx
│   │   │   ├── ReverseCalculationForm.tsx
│   │   │   ├── ReverseCalculationResult.tsx
│   │   │   ├── SimulationHistory.tsx
│   │   │   ├── SimulationPreview.tsx
│   │   │   └── index.ts
│   │   │
│   │   ├── AbsenceRequestModal.tsx
│   │   ├── ChangePasswordModal.tsx
│   │   ├── CollectiveAgreementCard.tsx
│   │   ├── CompanySwitcher.tsx    # Sélecteur d'entreprise
│   │   ├── CopilotModal.tsx       # Modal copilot Text-to-SQL
│   │   ├── CopilotModalAgent.tsx  # Modal copilot Agent IA
│   │   ├── LogoUploader.tsx
│   │   ├── NewExpenseModal.tsx
│   │   ├── PermissionsMatrix.tsx  # Matrice de permissions
│   │   ├── SaisieModal.tsx
│   │   └── ScheduleModal.tsx
│   │
│   ├── contexts/                  # Contextes React
│   │   ├── AuthContext.tsx       # Contexte authentification
│   │   └── CompanyContext.tsx    # Contexte multi-entreprises
│   │
│   ├── hooks/                     # Hooks personnalisés
│   │   ├── use-mobile.tsx        # Détection mobile
│   │   ├── use-toast.ts          # Hook pour notifications
│   │   └── useCalendar.ts        # Hook calendrier
│   │
│   ├── lib/                       # Utilitaires
│   │   └── utils.ts              # Fonctions utilitaires (cn, etc.)
│   │
│   ├── pages/                     # Pages de l'application
│   │   ├── Login.tsx             # Page de connexion
│   │   ├── ForgotPassword.tsx    # Mot de passe oublié
│   │   ├── ResetPassword.tsx     # Réinitialisation mot de passe
│   │   ├── NotFound.tsx          # Page 404
│   │   │
│   │   ├── Dashboard.tsx         # Tableau de bord RH
│   │   ├── Employees.tsx         # Liste des employés
│   │   ├── EmployeeDetail.tsx    # Détails d'un employé
│   │   ├── Payroll.tsx           # Liste des bulletins
│   │   ├── PayrollDetail.tsx     # Détails bulletins d'un employé
│   │   ├── PayslipEdit.tsx      # Édition d'un bulletin
│   │   ├── Saisies.tsx          # Saisies mensuelles
│   │   ├── Rates.tsx            # Suivi des taux
│   │   ├── Absences.tsx          # Gestion des absences (RH)
│   │   ├── Expenses.tsx          # Notes de frais (RH)
│   │   ├── Schedules.tsx        # Calendriers et plannings
│   │   ├── CompanyPage.tsx      # Paramètres entreprise
│   │   ├── EmployeeExits.tsx    # Sorties de salariés
│   │   ├── ExitDocumentEdit.tsx # Édition documents de sortie
│   │   ├── Simulation.tsx       # Simulation de paie
│   │   ├── UserManagement.tsx   # Gestion des utilisateurs
│   │   ├── UserCreation.tsx     # Création d'utilisateur
│   │   ├── UserEdit.tsx        # Édition d'utilisateur
│   │   ├── GroupDashboard.tsx  # Tableau de bord groupe
│   │   ├── Exports.tsx         # Exports (RH/Paie)
│   │   ├── ResidencePermits.tsx # Titres de séjour
│   │   ├── AnnualReviews.tsx   # Entretiens annuels
│   │   ├── AnnualReviewDetail.tsx # Détails entretien
│   │   ├── SalarySeizures.tsx   # Saisies sur salaire
│   │   └── SalaryAdvances.tsx   # Avances sur salaire
│   │   │
│   │   ├── employee/            # Pages espace salarié
│   │   │   ├── Dashboard.tsx   # Tableau de bord salarié
│   │   │   ├── Profile.tsx     # Profil salarié
│   │   │   ├── Payslips.tsx    # Mes bulletins
│   │   │   ├── Absences.tsx    # Mes absences
│   │   │   ├── Calendar.tsx    # Mon calendrier
│   │   │   ├── Expenses.tsx    # Mes notes de frais
│   │   │   ├── Documents.tsx  # Mes documents
│   │   │   └── AnnualReviews.tsx # Mes entretiens annuels
│   │   │
│   │   └── super-admin/         # Pages Super Admin
│   │       ├── SuperAdminLayout.tsx
│   │       ├── SuperAdminDashboard.tsx
│   │       ├── Companies.tsx
│   │       ├── CompanyDetails.tsx
│   │       ├── Users.tsx
│   │       ├── Monitoring.tsx
│   │       ├── ReductionFillon.tsx
│   │       ├── Scraping.tsx
│   │       ├── CollectiveAgreementsCatalog.tsx
│   │       ├── CompanyGroups.tsx
│   │       └── CompanyGroupDetail.tsx
│   │
│   └── integrations/             # Intégrations externes
│       └── supabase/
│           ├── client.ts         # Client Supabase (si utilisé)
│           └── types.ts          # Types TypeScript Supabase
│
├── dist/                         # Build de production (généré)
├── node_modules/                 # Dépendances npm
├── Dockerfile                    # Configuration Docker
├── nginx.conf                    # Configuration Nginx
└── nginx.template.conf           # Template Nginx
```

---

## 🚀 Fonctionnalités principales

### 1. Authentification et autorisation

- **Connexion** : Email + mot de passe avec validation
- **Mot de passe oublié** : Flux de réinitialisation par email
- **Gestion de session** : Persistance du token JWT dans localStorage
- **Protection des routes** : Guards selon le rôle utilisateur
- **Déconnexion** : Nettoyage de la session

**Pages :**
- `/login` - Page de connexion
- `/forgot-password` - Mot de passe oublié
- `/reset-password` - Réinitialisation

### 2. Multi-entreprises

- **Sélecteur d'entreprise** : Changement d'entreprise en temps réel
- **Contexte global** : Entreprise active disponible dans toute l'application
- **Isolation visuelle** : Affichage adapté selon l'entreprise
- **Groupes d'entreprises** : Visualisation et gestion des groupes

**Composants :**
- `CompanySwitcher` - Sélecteur d'entreprise
- `CompanyContext` - Contexte React pour l'entreprise active

### 3. Tableau de bord

- **KPIs** : Indicateurs clés (effectifs, absences, paie, etc.)
- **Graphiques** : Visualisations avec Recharts
- **Statistiques** : Données agrégées par période
- **Alertes** : Notifications importantes

**Pages :**
- `/` - Tableau de bord RH
- `/employee/` - Tableau de bord salarié
- `/super-admin` - Tableau de bord Super Admin

### 4. Gestion des employés

- **Liste des employés** : Tableau avec recherche et filtres
- **Détails employé** : Vue complète avec onglets (contrat, paie, absences, etc.)
- **Création** : Formulaire complet avec validation
- **Modification** : Édition des informations
- **Suppression** : Avec confirmation
- **Génération de documents** : Contrats, identifiants (PDF)

**Pages :**
- `/employees` - Liste des employés
- `/employees/:employeeId` - Détails d'un employé

### 5. Gestion de la paie

- **Liste des bulletins** : Par employé ou globale
- **Génération** : Création de nouveaux bulletins
- **Édition** : Modification manuelle avec sections dédiées
  - En-tête (période, employé)
  - Calcul brut (salaire, heures, primes)
  - Cotisations (salariales et patronales)
  - Congés et absences
  - Notes de frais
  - Primes non soumises
  - Synthèse net
  - Notes
- **Prévisualisation** : Aperçu avant sauvegarde
- **Historique** : Versioning complet des modifications
- **Restaurer** : Retour à une version précédente
- **Export PDF** : Téléchargement des bulletins

**Pages :**
- `/payroll` - Liste des bulletins
- `/payroll/:employeeId` - Bulletins d'un employé
- `/payslips/:payslipId/edit` - Édition d'un bulletin

### 6. Simulation de paie

- **Calcul inverse** : Déterminer le brut à partir du net souhaité
- **Création de simulation** : Bulletins simulés sans affecter les données réelles
- **Scénarios prédéfinis** : Augmentation, prime, heures sup, etc.
- **Comparaison** : Comparer simulation vs réel
- **Historique** : Liste de toutes les simulations
- **Prévisualisation** : Aperçu du bulletin simulé

**Pages :**
- `/simulation` - Module de simulation

**Composants :**
- `ReverseCalculationForm` - Formulaire calcul inverse
- `PayslipSimulationForm` - Formulaire création simulation
- `SimulationHistory` - Historique des simulations
- `SimulationPreview` - Aperçu simulation

### 7. Gestion des absences

- **Demandes de congés** : Création avec calendrier
- **Validation** : Workflow d'approbation (RH/Manager)
- **Calendrier** : Visualisation des absences
- **Statistiques** : Jours restants, taux d'absentéisme
- **Types** : Congés payés, RTT, maladie, etc.

**Pages :**
- `/leaves` - Gestion des absences (RH)
- `/employee/absences` - Mes absences (salarié)

### 8. Notes de frais

- **Déclaration** : Création de notes de frais
- **Types** : Frais kilométriques, repas, hébergement, etc.
- **Justificatifs** : Upload de fichiers
- **Validation** : Workflow d'approbation
- **Historique** : Suivi des notes

**Pages :**
- `/expenses` - Notes de frais (RH)
- `/employee/expenses` - Mes notes de frais (salarié)

### 9. Calendriers et plannings

- **Gestion des horaires** : Création et modification
- **Calendrier mensuel** : Visualisation avec FullCalendar
- **Types de planning** : Standard, variable, équipe
- **Forfait jour** : Interface adaptée avec cases à cocher pour les jours travaillés
- **Vue salarié** : Consultation de son planning

**Pages :**
- `/schedules` - Gestion des plannings (RH)
- `/employee/calendar` - Mon calendrier (salarié)

### 10. Sorties de salariés

- **Gestion des sorties** : Création et suivi
- **Types** : Démission, licenciement, rupture conventionnelle, etc.
- **Génération de documents** :
  - Certificat de travail
  - Attestation Pôle Emploi
  - Solde de tout compte
- **Édition de documents** : Modification manuelle avec historique
- **Publication** : Finalisation et signature

**Pages :**
- `/employee-exits` - Liste des sorties
- `/employee-exits/:exitId/documents/:documentId/edit` - Édition document

### 11. Saisies mensuelles

- **Saisie des données** : Heures, primes, absences du mois
- **Validation** : Workflow avant paie
- **Historique** : Suivi des saisies

**Pages :**
- `/saisies` - Saisies mensuelles

### 12. Conventions collectives

- **Catalogue** : Liste des conventions disponibles
- **Recherche** : Par IDCC, secteur, etc.
- **Chat IA** : Assistant pour questions sur les conventions
- **Détails** : Informations complètes

**Pages :**
- `/super-admin/collective-agreements` - Catalogue (Super Admin)

### 13. Copilot IA

- **Text-to-SQL** : Conversion de questions en SQL
- **Agent IA** : Assistant intelligent avec planification
- **Interface modale** : Chat interactif
- **Historique** : Sauvegarde des conversations

**Composants :**
- `CopilotModal` - Modal Text-to-SQL
- `CopilotModalAgent` - Modal Agent IA

### 14. Super Admin

- **Gestion des entreprises** : Création, modification, suppression
- **Gestion des utilisateurs** : Attribution de rôles
- **Monitoring** : Statistiques globales
- **Scraping** : Interface de gestion du scraping automatisé
- **Réduction Fillon** : Configuration et suivi
- **Groupes d'entreprises** : Gestion des groupes

**Pages :**
- `/super-admin` - Tableau de bord
- `/super-admin/companies` - Liste des entreprises
- `/super-admin/users` - Liste des utilisateurs
- `/super-admin/scraping` - Gestion scraping
- `/super-admin/monitoring` - Monitoring
- `/super-admin/groups` - Groupes d'entreprises

### 15. Gestion des utilisateurs

- **Liste des utilisateurs** : Avec filtres et recherche
- **Création** : Formulaire avec attribution de permissions
- **Modification** : Édition des permissions granulaires
- **Matrice de permissions** : Visualisation des droits
- **Templates** : Modèles de permissions prédéfinis

**Pages :**
- `/users` - Liste des utilisateurs
- `/users/create` - Création
- `/users/:userId/edit` - Édition

### 16. Exports

- **Export de données** : Export CSV/Excel des données RH et paie
- **Filtres avancés** : Par période, employé, type de données
- **Formats multiples** : CSV, Excel

**Pages :**
- `/exports` - Module d'export

### 17. Titres de séjour

- **Suivi des titres** : Gestion des titres de séjour des employés
- **Alertes d'expiration** : Notifications automatiques
- **Renouvellements** : Suivi des renouvellements

**Pages :**
- `/residence-permits` - Liste des titres de séjour

### 18. Entretiens annuels

- **Création et gestion** : Gestion complète des entretiens d'évaluation
- **Objectifs et compétences** : Suivi des objectifs et évaluation des compétences
- **Historique** : Consultation de l'historique des entretiens
- **Espace salarié** : Consultation par le salarié

**Pages :**
- `/annual-reviews` - Liste des entretiens (RH)
- `/annual-reviews/:reviewId` - Détails d'un entretien
- `/employee/annual-reviews` - Mes entretiens (salarié)

### 19. Saisies et avances

- **Saisies mensuelles** : Gestion des saisies (heures, primes, absences)
- **Avances sur salaire** : Gestion des avances
- **Workflow de validation** : Validation avant paie

**Pages :**
- `/salary-seizures` - Saisies sur salaire
- `/salary-advances` - Avances sur salaire

---

## ⚙️ Configuration et installation

### Prérequis

- Node.js 18+
- npm ou yarn ou pnpm

### Installation

1. **Cloner le dépôt**
```bash
git clone <repository-url>
cd frontend
```

2. **Installer les dépendances**
```bash
npm install
# ou
yarn install
# ou
pnpm install
```

3. **Configurer les variables d'environnement**

Créer un fichier `.env` à la racine de `frontend/` :

```env
# URL de l'API backend
VITE_API_URL=http://localhost:8000
# ou en production
VITE_API_URL=https://votre-api.run.app
```

4. **Lancer l'application en développement**

```bash
npm run dev
# ou
yarn dev
# ou
pnpm dev
```

L'application sera accessible sur `http://localhost:8080`

5. **Build de production**

```bash
npm run build
# ou
yarn build
# ou
pnpm build
```

Les fichiers de production seront générés dans le dossier `dist/`

6. **Prévisualiser le build**

```bash
npm run preview
# ou
yarn preview
# ou
pnpm preview
```

### Configuration Vite

Le fichier `vite.config.ts` configure :
- Port : 8080
- Host : `::` (toutes les interfaces)
- Alias `@` : Pointe vers `./src`
- Plugin React SWC : Compilation rapide

### Configuration TypeScript

- `tsconfig.json` : Configuration principale
- `tsconfig.app.json` : Configuration pour l'application
- `tsconfig.node.json` : Configuration pour les scripts Node

---

## 🧩 Structure des composants

### Composants UI (Shadcn)

Les composants UI sont basés sur **Shadcn/ui** et **Radix UI** pour l'accessibilité.

**Exemples :**
- `Button` - Boutons avec variantes
- `Input` - Champs de saisie
- `Dialog` - Modales
- `Table` - Tableaux
- `Card` - Cartes
- `Select` - Sélecteurs
- `Calendar` - Calendriers
- `Toast` - Notifications

**Utilisation :**
```tsx
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader } from '@/components/ui/dialog';

function MyComponent() {
  return (
    <Dialog>
      <DialogContent>
        <DialogHeader>Mon titre</DialogHeader>
        <Button variant="default">Cliquer</Button>
      </DialogContent>
    </Dialog>
  );
}
```

### Composants métier

Les composants métier encapsulent la logique spécifique à l'application.

**Exemples :**
- `CompanySwitcher` - Sélecteur d'entreprise
- `AbsenceRequestModal` - Modal de demande d'absence
- `PayslipEdit` - Éditeur de bulletin
- `SimulationForm` - Formulaire de simulation

### Patterns de composition

- **Composition** : Préférer la composition à l'héritage
- **Props** : Typage strict avec TypeScript
- **Hooks** : Logique réutilisable dans des hooks personnalisés
- **Context** : État global via Context API

---

## 🔄 Gestion d'état

### Context API

**AuthContext** : Gestion de l'authentification
- `user` - Utilisateur connecté
- `login(token)` - Connexion
- `logout()` - Déconnexion
- `isLoading` - État de chargement

**CompanyContext** : Gestion multi-entreprises
- `activeCompany` - Entreprise active
- `accessibleCompanies` - Liste des entreprises accessibles
- `setActiveCompany(id)` - Changer d'entreprise

### React Query

**TanStack React Query** pour la gestion des données serveur :

```tsx
import { useQuery, useMutation } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';

// Query (GET)
const { data, isLoading, error } = useQuery({
  queryKey: ['employees'],
  queryFn: () => apiClient.get('/api/employees').then(res => res.data)
});

// Mutation (POST/PUT/DELETE)
const mutation = useMutation({
  mutationFn: (newEmployee) => 
    apiClient.post('/api/employees', newEmployee),
  onSuccess: () => {
    queryClient.invalidateQueries(['employees']);
  }
});
```

**Avantages :**
- Cache automatique
- Refetch intelligent
- Optimistic updates
- Gestion des erreurs

---

## 🧭 Routing

### Structure des routes

L'application utilise **React Router DOM** avec une structure hiérarchique :

```tsx
<Routes>
  {/* Routes publiques */}
  <Route path="/login" element={<LoginPage />} />
  <Route path="/forgot-password" element={<ForgotPasswordPage />} />
  
  {/* Routes protégées */}
  <Route element={<ProtectedRoutes />}>
    {/* Routes RH */}
    <Route path="/" element={<RhDashboard />} />
    <Route path="/employees" element={<Employees />} />
    {/* ... */}
    
    {/* Routes Salarié */}
    <Route element={<EmployeeLayout />}>
      <Route path="/" element={<EmployeeDashboard />} />
      {/* ... */}
    </Route>
    
    {/* Routes Super Admin */}
    <Route path="/super-admin" element={<SuperAdminLayout />}>
      <Route index element={<SuperAdminDashboard />} />
      {/* ... */}
    </Route>
  </Route>
</Routes>
```

### Protection des routes

Les routes sont protégées par le composant `ProtectedRoutes` qui :
1. Vérifie l'authentification
2. Redirige vers `/login` si non authentifié
3. Affiche l'interface appropriée selon le rôle

### Navigation

```tsx
import { useNavigate } from 'react-router-dom';

function MyComponent() {
  const navigate = useNavigate();
  
  const handleClick = () => {
    navigate('/employees/123');
  };
  
  return <Button onClick={handleClick}>Voir employé</Button>;
}
```

---

## 🌐 API Client

### Configuration

Le client API est configuré dans `src/api/apiClient.ts` avec **Axios**.

**Fonctionnalités :**
- Base URL configurable via `.env`
- Intercepteurs pour :
  - Ajout automatique du token JWT
  - Ajout du header `X-Active-Company`
  - Gestion des erreurs
  - Logging des requêtes

### Utilisation

```tsx
import apiClient from '@/api/apiClient';

// GET
const response = await apiClient.get('/api/employees');
const employees = response.data;

// POST
const newEmployee = await apiClient.post('/api/employees', {
  first_name: 'Jean',
  last_name: 'Dupont'
});

// PUT
await apiClient.put(`/api/employees/${id}`, updatedData);

// DELETE
await apiClient.delete(`/api/employees/${id}`);
```

### Gestion des erreurs

```tsx
try {
  await apiClient.post('/api/employees', data);
} catch (error) {
  if (error.response?.status === 401) {
    // Non authentifié → rediriger vers login
    navigate('/login');
  } else if (error.response?.status === 403) {
    // Non autorisé → afficher message
    toast.error('Vous n\'avez pas les permissions');
  }
}
```

---

## 🎨 Styles et UI

### Tailwind CSS

L'application utilise **Tailwind CSS** pour le styling.

**Configuration** : `tailwind.config.ts`

**Utilisation :**
```tsx
<div className="flex items-center justify-between p-4 bg-white rounded-lg shadow">
  <h1 className="text-2xl font-bold text-gray-900">Titre</h1>
</div>
```

### Thème sombre

Support du dark mode via **next-themes** :

```tsx
import { useTheme } from 'next-themes';

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <Button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
      Toggle theme
    </Button>
  );
}
```

### Responsive Design

Utilisation des breakpoints Tailwind :
- `sm:` - 640px+
- `md:` - 768px+
- `lg:` - 1024px+
- `xl:` - 1280px+

**Exemple :**
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {/* Contenu */}
</div>
```

### Animations

Animations avec **Framer Motion** :

```tsx
import { motion } from 'framer-motion';

<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.3 }}
>
  Contenu animé
</motion.div>
```

---

## 🚀 Déploiement

### Build de production

```bash
npm run build
```

Les fichiers sont générés dans `dist/` et peuvent être servis par n'importe quel serveur web statique.

### Déploiement avec Docker

1. **Construire l'image**
```bash
docker build -t sirh-frontend .
```

2. **Lancer le conteneur**
```bash
docker run -p 80:80 sirh-frontend
```

Le Dockerfile utilise **Nginx** pour servir les fichiers statiques.

### Déploiement sur Google Cloud Run

1. **Build et push de l'image**
```bash
docker build -t gcr.io/votre-projet/sirh-frontend .
docker push gcr.io/votre-projet/sirh-frontend
```

2. **Déployer**
```bash
gcloud run deploy sirh-frontend \
  --image gcr.io/votre-projet/sirh-frontend \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated
```

### Variables d'environnement

En production, configurer `VITE_API_URL` pour pointer vers l'API backend.

---

## 📝 Notes techniques

### Performance

- **Code splitting** : Chargement à la demande des routes
- **Lazy loading** : Composants chargés uniquement quand nécessaires
- **Memoization** : `React.memo`, `useMemo`, `useCallback`
- **Virtual scrolling** : Pour les grandes listes

### Accessibilité

- **ARIA labels** : Attributs ARIA pour les lecteurs d'écran
- **Navigation clavier** : Support complet du clavier
- **Contraste** : Respect des standards WCAG
- **Focus visible** : Indicateurs de focus clairs

### Tests

```bash
# À implémenter
npm run test
```

### Linting

```bash
npm run lint
```

---

## 📚 Ressources supplémentaires

- [Documentation React](https://react.dev/)
- [Documentation React Router](https://reactrouter.com/)
- [Documentation TanStack Query](https://tanstack.com/query/latest)
- [Documentation Tailwind CSS](https://tailwindcss.com/)
- [Documentation Shadcn/ui](https://ui.shadcn.com/)
- [Documentation Vite](https://vitejs.dev/)

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
