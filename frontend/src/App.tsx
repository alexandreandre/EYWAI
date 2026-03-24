// src/App.tsx (VERSION COMPLÈTE ET CORRIGÉE)

import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';

// --- Fournisseurs de contexte et composants globaux ---
import { AuthProvider, useAuth } from './contexts/AuthContext'; // À CRÉER
import { CompanyProvider, useCompany } from './contexts/CompanyContext'; // NOUVEAU - Multi-entreprises
import { ViewProvider, useView } from './contexts/ViewContext'; // NOUVEAU - Gestion de la vue pour collaborateur_rh
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppSidebar } from '@/components/ui/app-sidebar';
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Loader2, Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CompanySwitcher } from '@/components/CompanySwitcher'; // NOUVEAU

// --- Pages ---
import LoginPage from './pages/Login'; // À CRÉER
import ForgotPasswordPage from './pages/ForgotPassword';
import ResetPasswordPage from './pages/ResetPassword';
// Pages RH
import RhDashboard from "./pages/Dashboard";
import Employees from "./pages/Employees";
import EmployeeDetail from "./pages/EmployeeDetail";
import Rates from "./pages/Rates";
import Payroll from './pages/Payroll';
import PayrollDetail from './pages/PayrollDetail';
import PayslipEdit from './pages/PayslipEdit'; // NOUVEAU - Édition des bulletins
import Saisies from './pages/Saisies';
import SalarySeizures from './pages/SalarySeizures';
import SalaryAdvances from './pages/SalaryAdvances';
import RhAbsencesPage from './pages/Absences'; // À CRÉER (pour les RH)
import RhExpensesPage from './pages/Expenses';
import RhSchedulesPage from './pages/Schedules'; // NOUVEAU - Gestion des calendriers
import CompanyPage from './pages/CompanyPage';
import EmployeeExits from './pages/EmployeeExits';
import ExitDocumentEdit from './pages/ExitDocumentEdit';
import Exports from './pages/Exports';
import ResidencePermits from './pages/ResidencePermits';
import MedicalFollowUp from './pages/MedicalFollowUp';
import { ErrorBoundaryClass } from '@/components/ErrorBoundary';
import AnnualReviews from './pages/AnnualReviews';
import AnnualReviewDetail from './pages/AnnualReviewDetail';
import Promotions from './pages/Promotions';
import PromotionDetail from './pages/PromotionDetail';
import CSE from './pages/CSE';
import Recruitment from './pages/Recruitment';
// --- Pages Collaborateur (NOUVEAU) ---
import { EmployeeSidebar } from '@/components/ui/employee-sidebar'; // NOUVEAU
import EmployeeDashboard from './pages/employee/Dashboard';
import ProfilePage from './pages/employee/Profile';
import PayslipsPage from './pages/employee/Payslips';
import EmployeeAbsencesPage from './pages/employee/Absences'; // Renommé pour plus de clarté
import EmployeeCalendarPage from './pages/employee/Calendar';
import ExpensesPage from './pages/employee/Expenses';
import SalaryAdvancesPage from './pages/employee/SalaryAdvances';
import DocumentsPage from './pages/employee/Documents';
import EmployeeAnnualReviews from './pages/employee/AnnualReviews';
import EmployeeAnnualReviewDetail from './pages/employee/AnnualReviewDetail';
import EmployeeCSE from './pages/employee/CSE';
import EmployeeMedicalFollowUp from './pages/employee/MedicalFollowUp';
// --- Pages Super Admin ---
import SuperAdminLayout from './pages/super-admin/SuperAdminLayout';
import SuperAdminDashboard from './pages/super-admin/SuperAdminDashboard';
import SuperAdminCompanies from './pages/super-admin/Companies';
import SuperAdminCompanyDetails from './pages/super-admin/CompanyDetails';
import SuperAdminUsers from './pages/super-admin/Users';
import SuperAdminMonitoring from './pages/super-admin/Monitoring';
import SuperAdminTests from './pages/super-admin/Tests';
import SuperAdminReductionFillon from './pages/super-admin/ReductionFillon';
import SuperAdminScraping from './pages/super-admin/Scraping';
import CollectiveAgreementsCatalog from './pages/super-admin/CollectiveAgreementsCatalog';
import CompanyGroups from './pages/super-admin/CompanyGroups';
import CompanyGroupDetail from './pages/super-admin/CompanyGroupDetail';
// Pages Multi-Entreprises
import { GroupDashboard } from './pages/GroupDashboard'; // NOUVEAU
// Pages Gestion Utilisateurs avec Permissions Granulaires
import UserManagement from './pages/UserManagement';
import UserProfile from './pages/UserProfile';
import UserCreation from './pages/UserCreation';
import UserEdit from './pages/UserEdit';
// Page Simulation
import Simulation from './pages/Simulation';
// Page par défaut
import NotFound from "./pages/NotFound";

/**
 * Layout pour l'espace Salarié, avec sa propre barre de navigation.
 */
function EmployeeLayout() {
    return (
        <SidebarProvider>
            <div className="grid min-h-screen w-full md:grid-cols-[auto_1fr]">
                <EmployeeSidebar />
                <div className="flex flex-col flex-1">
                    {/* Header mobile avec bouton menu */}
                    <header className="sticky top-0 z-10 flex h-14 items-center gap-4 border-b bg-background px-4 md:hidden">
                        <SidebarTrigger>
                            <Button variant="ghost" size="icon" className="md:hidden">
                                <Menu className="h-5 w-5" />
                                <span className="sr-only">Toggle Menu</span>
                            </Button>
                        </SidebarTrigger>
                        <div className="flex-1">
                            <img src="/Colorplast.png" alt="Logo Colorplast" className="h-8 w-auto" />
                        </div>
                    </header>
                    <main className="flex-1 p-6 lg:p-8 overflow-auto"><Outlet /></main>
                </div>
            </div>
        </SidebarProvider>
    );
}
/**
 * Wrapper pour ajouter le ViewProvider autour de ProtectedRoutes
 */
function ProtectedRoutesWithView() {
  const { user } = useAuth();
  return (
    <ViewProvider userRole={user?.role}>
      <ProtectedRoutes />
    </ViewProvider>
  );
}

/**
 * Ce composant gère les routes protégées. Il vérifie si un utilisateur est connecté
 * et quel est son rôle, puis affiche la bonne interface.
 */
function ProtectedRoutes() {
  const { user, isLoading } = useAuth();
  const { accessibleCompanies } = useCompany();
  const { viewMode, isCollaborateurRh } = useView();

  console.log('%c[ProtectedRoutes] 🔍 Rendu du composant', 'background: #222; color: #bada55; font-weight: bold');
  console.log('%c[ProtectedRoutes] isLoading:', 'color: cyan', isLoading);
  console.log('%c[ProtectedRoutes] user:', 'color: cyan', user);
  console.log('%c[ProtectedRoutes] accessibleCompanies:', 'color: cyan', accessibleCompanies);

  // 1. Afficher un indicateur de chargement pendant la vérification de l'authentification
  if (isLoading) {
    console.log('%c[ProtectedRoutes] ⏳ Affichage du loader...', 'color: orange');
    return (
      <div className="flex h-screen w-full items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
      </div>
    );
  }

  // 2. Si pas d'utilisateur, rediriger vers la page de connexion
  if (!user) {
    console.log('%c[ProtectedRoutes] ❌ Pas d\'utilisateur - Redirection vers /login', 'color: red');
    return <Navigate to="/login" replace />;
  }

  console.log('%c[ProtectedRoutes] ✅ Utilisateur connecté:', 'color: green', {
    id: user.id,
    email: user.email,
    role: user.role,
    first_name: user.first_name
  });

  // 3. Si l'utilisateur est un Collaborateur (sans accès RH), afficher l'interface Collaborateur uniquement
  if (user.role === 'collaborateur') {
    console.log('%c[ProtectedRoutes] 👤 Rôle COLLABORATEUR détecté - Affichage EmployeeLayout', 'background: blue; color: white; font-weight: bold');
    return (
      <Routes>
        <Route element={<EmployeeLayout />}>
          <Route path="/" element={<EmployeeDashboard />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/payslips" element={<PayslipsPage />} />
          <Route path="/annual-reviews" element={<EmployeeAnnualReviews />} />
          <Route path="/annual-reviews/:reviewId" element={<EmployeeAnnualReviewDetail />} />
          <Route path="/absences" element={<EmployeeAbsencesPage />} />
          <Route path="/calendar" element={<EmployeeCalendarPage />} />
          <Route path="/expenses" element={<ExpensesPage />} />
          <Route path="/salary-advances" element={<SalaryAdvancesPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/medical-follow-up" element={<EmployeeMedicalFollowUp />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    );
  }

  // 4. Si c'est un RH, collaborateur_rh, admin ou custom avec permissions RH, afficher le layout complet
  // Note: collaborateur_rh peut accéder aux deux interfaces selon la vue sélectionnée
  console.log('%c[ProtectedRoutes] 👔 Rôle RH/ADMIN/COLLABORATEUR_RH détecté - Affichage du layout avec sidebar', 'background: green; color: white; font-weight: bold');
  console.log('%c[ProtectedRoutes] 🎨 Rendu du SidebarProvider...', 'color: magenta');
  console.log('%c[ProtectedRoutes] 🔨 Rendu de AppSidebar...', 'color: yellow');
  console.log('%c[ProtectedRoutes] 🔨 Rendu de CompanySwitcher...', 'color: yellow');
  console.log('%c[ProtectedRoutes] 🔨 Rendu du main content...', 'color: yellow');

  // Vérifier si l'utilisateur a accès à plusieurs entreprises
  const showCompanySwitcher = accessibleCompanies && accessibleCompanies.length > 1;

  // Si collaborateur_rh en vue Collaborateur, afficher les routes collaborateur dans le layout RH (avec switch)
  const isCollaborateurRhView = isCollaborateurRh && viewMode === 'collaborateur';

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-muted/40">
        <AppSidebar />
        <div className="flex-1 flex flex-col">
          {/* Header mobile avec bouton menu et sélecteur d'entreprise - Affiché seulement si plusieurs entreprises */}
          {showCompanySwitcher && (
            <header className="sticky top-0 z-10 flex h-14 items-center gap-4 border-b bg-background px-4 md:hidden">
              <SidebarTrigger>
                <Button variant="ghost" size="icon" className="md:hidden">
                  <Menu className="h-5 w-5" />
                  <span className="sr-only">Toggle Menu</span>
                </Button>
              </SidebarTrigger>
              <div className="flex-1">
                <img src="/Colorplast.png" alt="Logo Colorplast" className="h-8 w-auto" />
              </div>
              {/* Sélecteur d'entreprise - Mobile */}
              <CompanySwitcher />
            </header>
          )}
          {/* Header desktop avec sélecteur d'entreprise - Affiché seulement si plusieurs entreprises */}
          {showCompanySwitcher && (
            <div className="hidden md:flex items-center gap-4 border-b bg-background px-6 py-3">
              <div className="flex-1" />
              <CompanySwitcher />
            </div>
          )}
          <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
            <Routes>
              {isCollaborateurRhView ? (
                // Routes Collaborateur pour collaborateur_rh en vue Collaborateur
                <>
                  <Route path="/" element={<EmployeeDashboard />} />
                  <Route path="/profile" element={<ProfilePage />} />
                  <Route path="/payslips" element={<PayslipsPage />} />
                  <Route path="/annual-reviews" element={<EmployeeAnnualReviews />} />
                  <Route path="/annual-reviews/:reviewId" element={<EmployeeAnnualReviewDetail />} />
                  <Route path="/absences" element={<EmployeeAbsencesPage />} />
                  <Route path="/calendar" element={<EmployeeCalendarPage />} />
                  <Route path="/expenses" element={<ExpensesPage />} />
                  <Route path="/salary-advances" element={<SalaryAdvancesPage />} />
                  <Route path="/documents" element={<DocumentsPage />} />
                  <Route path="/medical-follow-up" element={<EmployeeMedicalFollowUp />} />
                  <Route path="/cse" element={<EmployeeCSE />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </>
              ) : (
                // Routes RH pour rh, admin, collaborateur_rh en vue RH, custom avec permissions RH
                <>
                  <Route path="/" element={<RhDashboard />} />
                  <Route path="/employees" element={<Employees />} />
                  <Route path="/employees/:employeeId" element={<EmployeeDetail />} />
                  <Route path="/saisies" element={<Saisies />} />
                  <Route path="/salary-seizures" element={<SalarySeizures />} />
                  <Route path="/salary-advances" element={<SalaryAdvances />} />
                  <Route path="/rates" element={<Rates />} />
                  <Route path="/payroll" element={<Payroll />} />
                  <Route path="/payroll/:employeeId" element={<PayrollDetail />} />
                  <Route path="/payslips/:payslipId/edit" element={<PayslipEdit />} />
                  <Route path="/leaves" element={<RhAbsencesPage />} />
                  <Route path="/expenses" element={<RhExpensesPage />} />
                  <Route path="/schedules" element={<RhSchedulesPage />} />
                  <Route path="/employee-exits" element={<EmployeeExits />} />
                  <Route path="/employee-exits/:exitId/documents/:documentId/edit" element={<ExitDocumentEdit />} />
                  <Route path="/residence-permits" element={<ResidencePermits />} />
                  <Route path="/medical-follow-up" element={<ErrorBoundaryClass><MedicalFollowUp /></ErrorBoundaryClass>} />
                  <Route path="/annual-reviews" element={<AnnualReviews />} />
                  <Route path="/annual-reviews/:reviewId" element={<AnnualReviewDetail />} />
                  <Route path="/promotions" element={<Promotions />} />
                  <Route path="/promotions/:promotionId" element={<PromotionDetail />} />
                  <Route path="/cse" element={<CSE />} />
                  <Route path="/recruitment" element={<Recruitment />} />
                  <Route path="/simulation" element={<Simulation />} />
                  <Route path="/exports" element={<Exports />} />
                  <Route path="/company" element={<CompanyPage />} />
                  {/* Routes Multi-Entreprises */}
                  <Route path="/groups/:groupId" element={<GroupDashboard />} />
                  {/* Routes Gestion Utilisateurs avec Permissions Granulaires */}
                  <Route path="/users" element={<UserManagement />} />
                  <Route path="/users/create" element={<UserCreation />} />
                  <Route path="/users/:userId" element={<UserProfile />} />
                  <Route path="/users/:userId/edit" element={<UserEdit />} />
                  <Route path="*" element={<NotFound />} />
                </>
              )}
            </Routes>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}


/**
 * Le composant racine de l'application.
 * Il met en place les fournisseurs de contexte et le routeur principal.
 */
export default function App() {
  return (
    <TooltipProvider>
      <Toaster />
      <AuthProvider>
        <CompanyProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              {/* Routes Super Admin */}
              <Route path="/super-admin" element={<SuperAdminLayout />}>
                <Route index element={<SuperAdminDashboard />} />
                <Route path="companies" element={<SuperAdminCompanies />} />
                <Route path="companies/:companyId" element={<SuperAdminCompanyDetails />} />
                <Route path="groups" element={<CompanyGroups />} />
                <Route path="groups/:groupId" element={<CompanyGroupDetail />} />
                <Route path="users" element={<SuperAdminUsers />} />
                <Route path="collective-agreements" element={<CollectiveAgreementsCatalog />} />
                <Route path="reduction-fillon" element={<SuperAdminReductionFillon />} />
                <Route path="scraping" element={<SuperAdminScraping />} />
                <Route path="monitoring" element={<SuperAdminMonitoring />} />
                <Route path="tests" element={<SuperAdminTests />} />
              </Route>
              <Route path="/*" element={<ProtectedRoutesWithView />} />
            </Routes>
          </BrowserRouter>
        </CompanyProvider>
      </AuthProvider>
    </TooltipProvider>
  );
}