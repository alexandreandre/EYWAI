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
  ChevronRight,
  Sparkles,
  Rocket,
  Lock,
  LifeBuoy,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext"; // <-- IMPORTATION
import { useRhSidebarTaskBadges } from "@/hooks/useRhSidebarTaskBadges";
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
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarTrigger,
  SidebarHeader,
  SidebarFooter,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import type { LucideIcon } from "lucide-react";

type SidebarLinkItem = { title: string; url: string; icon: LucideIcon };

const RH_HOME: SidebarLinkItem = {
  title: "Tableau de bord",
  url: "/",
  icon: LayoutDashboard,
};

const RH_TEAM_BASE: SidebarLinkItem[] = [
  { title: "Collaborateurs", url: "/employees", icon: Users },
  { title: "Départs & sorties", url: "/employee-exits", icon: UserMinus },
  { title: "Titres & documents", url: "/residence-permits", icon: FileCheck },
  { title: "Calendriers", url: "/schedules", icon: Calendar },
  { title: "Badgeuse", url: "/badgeuse-rh", icon: Calendar },
  { title: "Mon Entreprise", url: "/company", icon: Building },
  { title: "Entretiens", url: "/annual-reviews", icon: MessageSquare },
  { title: "Promotions", url: "/promotions", icon: Award },
  { title: "CSE & Dialogue Social", url: "/cse", icon: Handshake },
  { title: "Recrutement", url: "/recruitment", icon: UserPlus },
  { title: "Gestion des Utilisateurs", url: "/users", icon: UserCog },
];

const RH_PAIE_ITEMS: SidebarLinkItem[] = [
  { title: "Congés & Absences", url: "/leaves", icon: Plane },
  { title: "Notes de frais", url: "/expenses", icon: Notebook },
  { title: "Primes", url: "/saisies", icon: ClipboardEdit },
  { title: "Saisies sur salaire", url: "/salary-seizures", icon: Scale },
  { title: "Avances sur salaire", url: "/salary-advances", icon: Wallet },
  { title: "Simulation", url: "/simulation", icon: FlaskConical },
  { title: "Suivi des Taux", url: "/rates", icon: TrendingUp },
  { title: "Exports", url: "/exports", icon: FileDown },
  { title: "Paie", url: "/payroll", icon: Calculator },
];

function withRhMedicalFollowUp(team: SidebarLinkItem[]): SidebarLinkItem[] {
  const next = [...team];
  const insertIndex = next.findIndex((m) => m.url === "/annual-reviews");
  const idx = insertIndex >= 0 ? insertIndex + 1 : 4;
  next.splice(idx, 0, {
    title: "Suivi médical",
    url: "/medical-follow-up",
    icon: Stethoscope,
  });
  return next;
}

const rhTeamItems = withRhMedicalFollowUp(RH_TEAM_BASE);

const menuItems = {
  rh: [RH_HOME, ...rhTeamItems, ...RH_PAIE_ITEMS] satisfies SidebarLinkItem[],
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
    { title: "Ma badgeuse", url: "/badgeuse", icon: Calendar },
    { title: "Profil", url: "/profile", icon: User },
  ]
};

function formatNavBadgeCount(n: number): string {
  if (n <= 0) return "0";
  return n > 99 ? "99+" : String(n);
}

/**
 * Pastille discrète sur une section (pas de chiffre).
 * Doit rester alignée sur la ligne du titre (CollapsibleTrigger), pas au centre vertical du bloc
 * une fois la section ouverte — sinon la pastille « glisse » vers le milieu des sous-liens
 * (ex. à côté de « Mon Entreprise »).
 */
function SectionTaskDot({ visible, sectionLabel }: { visible: boolean; sectionLabel: string }) {
  if (!visible) return null;
  return (
    <SidebarMenuBadge
      className="!right-7 !top-1.5 !h-2 !w-2 !min-w-0 rounded-full border-0 bg-destructive p-0 text-[0] leading-none text-transparent shadow-sm"
      title={`Actions à traiter — ${sectionLabel}`}
      aria-label={`Des tâches sont en attente dans ${sectionLabel}`}
    >
      .
    </SidebarMenuBadge>
  );
}

/** Compteur sur un sous-lien de navigation. */
function SubNavCountBadge({ count }: { count: number }) {
  if (count <= 0) return null;
  const shown = formatNavBadgeCount(count);
  const nLabel = count > 99 ? "Plus de 99" : String(count);
  const plural = count > 99 || count > 1;
  return (
    <span
      className="pointer-events-none absolute right-1.5 top-1/2 z-[1] flex h-5 min-w-5 -translate-y-1/2 items-center justify-center rounded-md bg-destructive px-1 text-[10px] font-semibold tabular-nums text-destructive-foreground shadow-sm"
      aria-label={`${nLabel} élément${plural ? "s" : ""} à traiter`}
    >
      {shown}
    </span>
  );
}

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

  const isRhMenu =
    !!user &&
    (user.role === "rh" || (isCollaborateurRh && viewMode === "rh"));
  const { getCount, totalRhPending } = useRhSidebarTaskBadges(isRhMenu);

  const teamSectionHasTasks = rhTeamItems.some((i) => getCount(i.url) > 0);
  const paieSectionHasTasks = RH_PAIE_ITEMS.some((i) => getCount(i.url) > 0);

  const [teamOpen, setTeamOpen] = useState(() => rhTeamItems.some((i) => isActive(i.url)));
  const [paieOpen, setPaieOpen] = useState(() => RH_PAIE_ITEMS.some((i) => isActive(i.url)));
  const [plusOpen, setPlusOpen] = useState(false);

  useEffect(() => {
    const pathMatches = (path: string) => {
      if (path === "/") return currentPath === "/";
      return currentPath.startsWith(path);
    };
    if (rhTeamItems.some((i) => pathMatches(i.url))) setTeamOpen(true);
    if (RH_PAIE_ITEMS.some((i) => pathMatches(i.url))) setPaieOpen(true);
  }, [currentPath]);

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

  console.log('%c[AppSidebar] Role:', 'color: purple', userRole);
  console.log('%c[AppSidebar] Menu items:', 'color: purple', items.length, 'items');

  const showRhAccordion = userRole === "rh" && !collapsed;

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
        {showRhAccordion ? (
          <>
            <SidebarGroup>
              <SidebarGroupLabel>EYWAI Home</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <div className="relative w-full">
                      <SidebarMenuButton asChild>
                        <NavLink
                          to={RH_HOME.url}
                          className={cn(getNavClassName(RH_HOME.url), totalRhPending > 0 && "pr-9")}
                          end={RH_HOME.url === "/"}
                        >
                          <RH_HOME.icon className="h-5 w-5 flex-shrink-0" />
                          <span className="font-medium">{RH_HOME.title}</span>
                        </NavLink>
                      </SidebarMenuButton>
                      <SubNavCountBadge count={totalRhPending} />
                    </div>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>

            <SidebarSeparator className="mx-0" />

            <SidebarGroup>
              <SidebarGroupContent>
                <SidebarMenu className="gap-0.5">
                  <Collapsible open={teamOpen} onOpenChange={setTeamOpen} className="group/collapsible">
                    <SidebarMenuItem>
                      <CollapsibleTrigger asChild>
                        <SidebarMenuButton className="w-full">
                          <Users className="h-5 w-5 flex-shrink-0" />
                          <span className="font-medium">EYWAI Team</span>
                          <ChevronRight
                            className={cn(
                              "ml-auto h-4 w-4 shrink-0 transition-transform duration-200",
                              "group-data-[state=open]/collapsible:rotate-90",
                            )}
                          />
                        </SidebarMenuButton>
                      </CollapsibleTrigger>
                      <SectionTaskDot visible={teamSectionHasTasks} sectionLabel="EYWAI Team" />
                      <CollapsibleContent>
                        <SidebarMenuSub>
                          {rhTeamItems.map((item) => (
                            <SidebarMenuSubItem key={item.url}>
                              <div className="relative">
                                <SidebarMenuSubButton
                                  asChild
                                  isActive={isActive(item.url)}
                                  size="sm"
                                  className={cn(getCount(item.url) > 0 && "pr-9")}
                                >
                                  <NavLink to={item.url} end={item.url === "/"}>
                                    <item.icon className="h-4 w-4 shrink-0" />
                                    <span>{item.title}</span>
                                  </NavLink>
                                </SidebarMenuSubButton>
                                <SubNavCountBadge count={getCount(item.url)} />
                              </div>
                            </SidebarMenuSubItem>
                          ))}
                        </SidebarMenuSub>
                      </CollapsibleContent>
                    </SidebarMenuItem>
                  </Collapsible>

                  <Collapsible open={paieOpen} onOpenChange={setPaieOpen} className="group/collapsible">
                    <SidebarMenuItem>
                      <CollapsibleTrigger asChild>
                        <SidebarMenuButton className="w-full">
                          <Calculator className="h-5 w-5 flex-shrink-0" />
                          <span className="font-medium">EYWAI Paie</span>
                          <ChevronRight
                            className={cn(
                              "ml-auto h-4 w-4 shrink-0 transition-transform duration-200",
                              "group-data-[state=open]/collapsible:rotate-90",
                            )}
                          />
                        </SidebarMenuButton>
                      </CollapsibleTrigger>
                      <SectionTaskDot visible={paieSectionHasTasks} sectionLabel="EYWAI Paie" />
                      <CollapsibleContent>
                        <SidebarMenuSub>
                          {RH_PAIE_ITEMS.map((item) => (
                            <SidebarMenuSubItem key={item.url}>
                              <div className="relative">
                                <SidebarMenuSubButton
                                  asChild
                                  isActive={isActive(item.url)}
                                  size="sm"
                                  className={cn(getCount(item.url) > 0 && "pr-9")}
                                >
                                  <NavLink to={item.url} end={item.url === "/"}>
                                    <item.icon className="h-4 w-4 shrink-0" />
                                    <span>{item.title}</span>
                                  </NavLink>
                                </SidebarMenuSubButton>
                                <SubNavCountBadge count={getCount(item.url)} />
                              </div>
                            </SidebarMenuSubItem>
                          ))}
                        </SidebarMenuSub>
                        <div className="mx-3.5 border-l border-sidebar-border px-2.5 py-1.5">
                          <Button size="sm" className="w-full gap-2 shadow-sm" asChild>
                            <NavLink to="/payroll">
                              <Rocket className="h-4 w-4 shrink-0" />
                              Lancer la paie
                            </NavLink>
                          </Button>
                        </div>
                      </CollapsibleContent>
                    </SidebarMenuItem>
                  </Collapsible>

                  <Collapsible open={plusOpen} onOpenChange={setPlusOpen} className="group/collapsible">
                    <SidebarMenuItem>
                      <CollapsibleTrigger asChild>
                        <SidebarMenuButton className="w-full">
                          <Sparkles className="h-5 w-5 flex-shrink-0" />
                          <span className="font-medium">EYWAI+</span>
                          <ChevronRight
                            className={cn(
                              "ml-auto h-4 w-4 shrink-0 transition-transform duration-200",
                              "group-data-[state=open]/collapsible:rotate-90",
                            )}
                          />
                        </SidebarMenuButton>
                      </CollapsibleTrigger>
                      <CollapsibleContent>
                        <SidebarMenuSub>
                          <SidebarMenuSubItem>
                            <span className="flex h-7 min-w-0 items-center gap-2 rounded-md px-2 text-xs text-muted-foreground">
                              Modules selon votre offre
                            </span>
                          </SidebarMenuSubItem>
                          <SidebarMenuSubItem>
                            <span className="flex h-7 min-w-0 items-center gap-2 rounded-md px-2 text-xs text-muted-foreground">
                              <Lock className="h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden />
                              À découvrir
                            </span>
                          </SidebarMenuSubItem>
                        </SidebarMenuSub>
                      </CollapsibleContent>
                    </SidebarMenuItem>
                  </Collapsible>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </>
        ) : (
          <SidebarGroup>
            <SidebarGroupLabel className={collapsed ? "sr-only" : ""}>
              Navigation
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu className={collapsed ? "flex flex-col items-center gap-1" : ""}>
                {items.map((item) => {
                  const subCount =
                    userRole === "rh"
                      ? item.url === "/"
                        ? totalRhPending
                        : getCount(item.url)
                      : 0;
                  return (
                    <SidebarMenuItem key={item.title}>
                      <SidebarMenuButton asChild tooltip={collapsed ? item.title : undefined}>
                        <NavLink to={item.url} className={getNavClassName(item.url)} end={item.url === "/"}>
                          <item.icon className="h-5 w-5 flex-shrink-0" />
                          {!collapsed && <span className="font-medium">{item.title}</span>}
                        </NavLink>
                      </SidebarMenuButton>
                      {userRole === "rh" && subCount > 0 && (
                        <SidebarMenuBadge className="bg-destructive text-[10px] font-semibold tabular-nums text-destructive-foreground">
                          {formatNavBadgeCount(subCount)}
                        </SidebarMenuBadge>
                      )}
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}

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
        <SidebarMenu className={collapsed ? "mb-2 flex flex-col items-center gap-1" : "mb-2"}>
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip={collapsed ? "Support" : undefined}>
              <NavLink to="/support" className={getNavClassName("/support")}>
                <LifeBuoy className="h-5 w-5 flex-shrink-0" />
                {!collapsed && <span className="font-medium">Support</span>}
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
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