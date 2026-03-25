import { useState, useEffect } from "react";
import {
  LayoutDashboard,
  Users,
  Calculator,
  Calendar,
  TrendingUp,
  UsersRound,
  ClipboardCheck,
  User,
  FileText,
  FolderOpen,
  Plus,
  LogOut,
  ClipboardEdit,
  Notebook,
  Plane,
  Settings,
  Building,
  Building2,
  UserCog,
  UserMinus,
  FlaskConical,
  FileDown,
  FileCheck,
  MessageSquare,
  Scale,
  Wallet,
  Home,
  DollarSign,
  FolderKanban,
  Award,
  Handshake,
  Stethoscope,
  UserPlus,
} from "lucide-react";
import { getMedicalSettings } from "@/api/medicalFollowUp";
import { useAuth } from "@/contexts/AuthContext"; // <-- IMPORTATION
import {
  computeAccessibleGroups,
  useCompanyOptional,
  type CompanyAccess,
} from "@/contexts/CompanyContext"; // <-- IMPORTATION
import { useViewOptional } from "@/contexts/ViewContext"; // NOUVEAU - Gestion de la vue pour collaborateur_rh
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { ChangePasswordModal } from "@/components/ChangePasswordModal";
import { CompanySwitcher } from "@/components/CompanySwitcher";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  SidebarHeader,
  SidebarFooter,
  useSidebar,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";

const menuItems = {
  rh: [
    { title: "Tableau de Bord", url: "/", icon: LayoutDashboard },
    { title: "Collaborateurs", url: "/employees", icon: Users },
    { title: "Titres de séjour", url: "/residence-permits", icon: FileCheck },
    { title: "Entretiens", url: "/annual-reviews", icon: MessageSquare },
    { title: "Promotions", url: "/promotions", icon: Award },
    { title: "CSE & Dialogue Social", url: "/cse", icon: Handshake },
    { title: "Recrutement", url: "/recruitment", icon: UserPlus },
    { title: "Gestion des Utilisateurs", url: "/users", icon: UserCog },
    { title: "Primes", url: "/saisies", icon: ClipboardEdit },
    { title: "Saisies sur salaire", url: "/salary-seizures", icon: Scale },
    { title: "Avances sur salaire", url: "/salary-advances", icon: Wallet },
    { title: "Paie", url: "/payroll", icon: Calculator },
    { title: "Simulation", url: "/simulation", icon: FlaskConical },
    { title: "Calendriers", url: "/schedules", icon: Calendar },
    { title: "Congés & Absences", url: "/leaves", icon: Plane },
    { title: "Notes de frais", url: "/expenses", icon: Notebook },
    { title: "Sortie du collaborateur", url: "/employee-exits", icon: UserMinus },
    { title: "Suivi des Taux", url: "/rates", icon: TrendingUp },
    { title: "Exports", url: "/exports", icon: FileDown },
    { title: "Mon Entreprise", url: "/company", icon: Building },
  ],
  manager: [
    { title: "Mon Équipe", url: "/team", icon: UsersRound },
    { title: "Demandes à valider", url: "/leave-requests", icon: ClipboardCheck },
  ],
  employee: [
    { title: "Tableau de Bord", url: "/", icon: Home },
    { title: "Rémunération", url: "/payslips", icon: DollarSign },
    { title: "Mes Entretiens", url: "/annual-reviews", icon: MessageSquare },
    { title: "Calendrier", url: "/calendar", icon: Calendar },
    { title: "Congés & Absences", url: "/absences", icon: Plane },
    { title: "Notes de Frais", url: "/expenses", icon: Notebook },
    { title: "Avances sur salaire", url: "/salary-advances", icon: Wallet },
    { title: "Mes Documents", url: "/documents", icon: FolderKanban },
    { title: "Profil", url: "/profile", icon: User },
  ]
};

export function AppSidebar() {

  console.log('%c[AppSidebar] 🔨 Rendu du composant AppSidebar', 'background: purple; color: white; font-weight: bold');

  const { user, logout } = useAuth(); // <-- UTILISATION DU HOOK
  const { state } = useSidebar();
  const navigate = useNavigate();
  const collapsed = state === "collapsed";
  const location = useLocation();
  const currentPath = location.pathname;
  const [showChangePassword, setShowChangePassword] = useState(false);
  
  // Récupérer la vue pour collaborateur_rh (hors ViewProvider : undefined)
  const viewContext = useViewOptional();
  const isCollaborateurRh = viewContext?.isCollaborateurRh || false;
  const viewMode = viewContext?.viewMode || 'rh';
  const setViewMode = viewContext?.setViewMode || (() => {});

  // État local pour garder le logo en mémoire pendant les transitions
  const [displayedLogo, setDisplayedLogo] = useState<{ url: string; scale: number } | null>(null);

  // Récupérer l'entreprise active et les groupes multi-entreprises accessibles
  const companyContext = useCompanyOptional();
  const activeCompany: CompanyAccess | null = companyContext?.activeCompany ?? null;
  const accessibleCompanies: CompanyAccess[] = companyContext?.accessibleCompanies ?? [];
  const accessibleGroups =
    companyContext != null
      ? computeAccessibleGroups(companyContext.accessibleCompanies)
      : [];

  if (!companyContext) {
    console.log('%c[AppSidebar] Pas de CompanyContext disponible', 'color: orange');
  }

  // Mettre à jour le logo affiché seulement quand un nouveau logo est disponible
  useEffect(() => {
    if (activeCompany?.logo_url) {
      setDisplayedLogo({
        url: activeCompany.logo_url,
        scale: activeCompany.logo_scale || 1.0
      });
    }
  }, [activeCompany?.logo_url, activeCompany?.logo_scale]);

  console.log('%c[AppSidebar] User:', 'color: purple', user);
  console.log('%c[AppSidebar] Sidebar state:', 'color: purple', state);
  console.log('%c[AppSidebar] Collapsed:', 'color: purple', collapsed);
  console.log('%c[AppSidebar] Accessible Groups:', 'color: purple', accessibleGroups);

  // Si l'utilisateur n'est pas encore chargé, on n'affiche rien ou un loader
  if (!user) {
    console.log('%c[AppSidebar] ❌ Pas d\'utilisateur - Retour null', 'color: red');
    return null;
  }

  console.log('%c[AppSidebar] ✅ Utilisateur chargé, affichage de la sidebar', 'color: green');

  // Déterminer quel menu afficher selon le rôle et la vue
  let userRole = user.role as keyof typeof menuItems;
  let items = menuItems[userRole] || [];
  
  // Si collaborateur_rh et vue Collaborateur, afficher le menu collaborateur
  if (isCollaborateurRh && viewMode === 'collaborateur') {
    userRole = 'employee';
    items = menuItems.employee || [];
  } else if (isCollaborateurRh && viewMode === 'rh') {
    // Si collaborateur_rh et vue RH, afficher le menu RH
    userRole = 'rh';
    items = menuItems.rh || [];
  }

  // Suivi médical : toujours affiché dans le menu RH (modules activés par défaut)
  if (userRole === 'rh' && Array.isArray(items)) {
    items = [...items];
    const insertIndex = items.findIndex((m: { url: string }) => m.url === '/annual-reviews');
    const idx = insertIndex >= 0 ? insertIndex + 1 : 4;
    items.splice(idx, 0, { title: "Suivi médical", url: "/medical-follow-up", icon: Stethoscope });
  }

  console.log('%c[AppSidebar] Role:', 'color: purple', userRole);
  console.log('%c[AppSidebar] Menu items:', 'color: purple', items.length, 'items');

  const isActive = (path: string) => {
    if (path === "/") {
      return currentPath === "/";
    }
    return currentPath.startsWith(path);
  };

  const getNavClassName = (path: string) => {
    const baseClasses = collapsed
      ? "flex items-center justify-center rounded-lg h-8 w-8 p-0 transition-all duration-200 hover:bg-primary/10" // <-- MODIFIÉ ICI
      : "flex items-center gap-3 rounded-lg px-3 py-2 transition-all duration-200 hover:bg-primary/10";
    return isActive(path)
      ? `${baseClasses} bg-primary text-primary-foreground shadow-sm`
      : `${baseClasses} text-muted-foreground hover:text-foreground`;
  };

  return (
    <Sidebar className={collapsed ? "w-16" : "w-64"} collapsible="icon">
      <SidebarHeader className="p-4">
        <div className="flex items-center justify-start mb-2 -ml-2">
          <SidebarTrigger className="h-8 w-8 p-0 hover:bg-primary/10 flex-shrink-0" />
        </div>
        {!collapsed && (
          <div className="flex flex-col items-center gap-2 text-center">
            {/* Logo de l'entreprise sélectionnée */}
            {displayedLogo ? (
              <div className="h-24 w-full flex items-center justify-center overflow-hidden">
                <img
                  src={displayedLogo.url}
                  alt={`Logo ${activeCompany?.company_name || 'entreprise'}`}
                  className="h-full w-full object-contain transition-all duration-300"
                  style={{ transform: `scale(${displayedLogo.scale})` }}
                />
              </div>
            ) : (
              <img
                src="/Colorplast.png"
                alt="Logo par défaut"
                className="h-10 w-auto"
              />
            )}
          </div>
        )}
      </SidebarHeader>

      {/* Switch de vue pour collaborateur_rh */}
      {isCollaborateurRh && (
        <div className={`px-4 py-3 border-b ${collapsed ? 'px-2' : ''}`}>
          {collapsed ? (
            <div className="flex items-center justify-center">
              <Switch
                checked={viewMode === 'rh'}
                onCheckedChange={(checked) => {
                  setViewMode(checked ? 'rh' : 'collaborateur');
                  // Rediriger vers la page d'accueil de la vue sélectionnée
                  navigate('/');
                }}
                aria-label="Basculer entre vue RH et Collaborateur"
              />
            </div>
          ) : (
            <div className="flex items-center justify-between gap-3">
              <div className="flex flex-col">
                <Label htmlFor="view-switch" className="text-xs font-medium text-muted-foreground">
                  Vue actuelle
                </Label>
                <span className="text-sm font-semibold">
                  {viewMode === 'rh' ? 'Vue RH' : 'Vue Collaborateur'}
                </span>
              </div>
              <Switch
                id="view-switch"
                checked={viewMode === 'rh'}
                onCheckedChange={(checked) => {
                  setViewMode(checked ? 'rh' : 'collaborateur');
                  // Rediriger vers la page d'accueil de la vue sélectionnée
                  navigate('/');
                }}
                aria-label="Basculer entre vue RH et Collaborateur"
              />
            </div>
          )}
        </div>
      )}

      <SidebarContent className={collapsed ? "px-2" : "px-4"}>
        <SidebarGroup>
          <SidebarGroupLabel className={collapsed ? "sr-only" : ""}>
            Navigation
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className={collapsed ? "flex flex-col items-center gap-1" : ""}>
              {items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild tooltip={collapsed ? item.title : undefined}>
                    <NavLink to={item.url} className={getNavClassName(item.url)} end={item.url === "/"}>
                      <item.icon className="h-5 w-5 flex-shrink-0" />
                      {!collapsed && <span className="font-medium">{item.title}</span>}
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Section Groupes - affichée uniquement si l'utilisateur a accès à plusieurs entreprises d'un même groupe */}
        {accessibleGroups.length > 0 && (
          <SidebarGroup>
            <SidebarGroupLabel className={collapsed ? "sr-only" : ""}>
              Vues Consolidées
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu className={collapsed ? "flex flex-col items-center gap-1" : ""}>
                {accessibleGroups.map((group) => {
                  const groupUrl = `/groups/${group.groupId}`;
                  const groupName = group.groupCompanies[0]?.group_name || `Groupe ${group.groupCompanies.length} entreprises`;

                  return (
                    <SidebarMenuItem key={group.groupId}>
                      <SidebarMenuButton asChild tooltip={collapsed ? groupName : undefined}>
                        <NavLink to={groupUrl} className={getNavClassName(groupUrl)}>
                          <Building2 className="h-5 w-5 flex-shrink-0" />
                          {!collapsed && (
                            <div className="flex flex-col">
                              <span className="font-medium text-sm">{groupName}</span>
                              <span className="text-xs text-muted-foreground">
                                {group.groupCompanies.length} entreprises
                              </span>
                            </div>
                          )}
                        </NavLink>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter className={collapsed ? "p-2" : "p-4"}>
        {!collapsed && <Separator className="mb-4" />}
        <div className={`flex items-center ${collapsed ? 'flex-col gap-2' : 'gap-3'}`}>
          {!collapsed && (
            <Avatar className="h-8 w-8">
              <AvatarFallback className="text-xs font-medium bg-primary/10">
                {user.first_name?.charAt(0)}
              </AvatarFallback>
            </Avatar>
          )}
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user.first_name}</p>
              <p className="text-xs text-muted-foreground capitalize">{user.role}</p>
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0 text-muted-foreground hover:bg-primary/10 hover:text-primary"
            aria-label="Paramètres"
            onClick={() => setShowChangePassword(true)}
          >
            <Settings className="h-4 w-4" />
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                aria-label="Se déconnecter"
              >
                <LogOut className="h-4 w-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Se déconnecter ?</AlertDialogTitle>
                <AlertDialogDescription>Êtes-vous sûr de vouloir mettre fin à votre session ?</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Annuler</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => {
                    logout();
                    // On ne navigue pas manuellement ici.
                    // Le composant 'ProtectedRoutes' (dans App.tsx) va
                    // détecter le changement d'état (user=null)
                    // et gérer la redirection vers /login.
                  }}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  Se déconnecter
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>

        {/* Modal de changement de mot de passe */}
        <ChangePasswordModal
          open={showChangePassword}
          onOpenChange={setShowChangePassword}
        />
      </SidebarFooter>
    </Sidebar>
  );
}