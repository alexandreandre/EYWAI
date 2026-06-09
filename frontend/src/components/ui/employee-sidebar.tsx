// src/components/ui/employee-sidebar.tsx

import { useState, useEffect, useMemo } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Home,
  User,
  Wallet,
  Landmark,
  CalendarDays,
  Plane,
  Notebook,
  Handshake,
  Stethoscope,
  LifeBuoy,
  GraduationCap,
  FileText,
  ScanLine,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { SidebarAccountMenu } from "@/components/ui/sidebar-account-menu";
import { NotificationBell } from "@/components/NotificationBell";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { prefetchEmployeeRoute } from "@/lib/prefetchEmployee";
import { getMyElectedStatus } from "@/api/cse";
import { getMedicalSettings } from "@/api/medicalFollowUp";
import { useEmployeeMedicalObligationsQuery } from "@/hooks/queries/useEmployeeMedicalObligationsQuery";
import { shouldShowEmployeeMedicalNavBadge } from "@/lib/employeeMedicalFollowUp";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuBadge,
  SidebarHeader,
  SidebarFooter,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

type NavItem = {
  to: string;
  label: string;
  icon: LucideIcon;
  badge?: boolean;
};

/** Ordre unique : fréquence quotidienne → administratif → conformité / rôles spécifiques. */
const coreNavItems: NavItem[] = [
  { to: "/", label: "Tableau de bord", icon: Home },
  { to: "/calendar", label: "Calendrier et planning", icon: CalendarDays },
  { to: "/badgeuse", label: "Ma badgeuse", icon: ScanLine },
  { to: "/absences", label: "Congés & absences", icon: Plane },
  { to: "/expenses", label: "Notes de frais", icon: Notebook },
  { to: "/salary-advances", label: "Avances & acomptes", icon: Wallet },
  { to: "/employee-loans", label: "Prêts employeur", icon: Landmark },
  { to: "/employee/documents", label: "Mes documents", icon: FileText },
  { to: "/employee/formation", label: "Ma formation", icon: GraduationCap },
];

const profileItem: NavItem = {
  to: "/profile",
  label: "Mon profil",
  icon: User,
};

function isNavActive(path: string, currentPath: string): boolean {
  if (path === "/") {
    return currentPath === "/";
  }
  if (path === "/employee/formation") {
    return (
      currentPath.startsWith("/employee/formation") ||
      currentPath === "/habilitations" ||
      currentPath === "/objectives" ||
      currentPath === "/catalogue-formations"
    );
  }
  if (path === "/employee/documents") {
    return currentPath.startsWith("/employee/documents");
  }
  if (path === "/calendar") {
    return currentPath === "/calendar" || currentPath.startsWith("/employee/planning");
  }
  if (path === "/badgeuse") {
    return currentPath.startsWith("/badgeuse");
  }
  return currentPath.startsWith(path);
}

export function EmployeeSidebar() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const queryClient = useQueryClient();
  const companyId = activeCompany?.company_id ?? "";
  const handleNavPrefetch = (to: string) => () => {
    if (user?.id) {
      prefetchEmployeeRoute(queryClient, to, user.id, companyId || undefined);
    }
  };
  const [displayedLogo, setDisplayedLogo] = useState<{ url: string; scale: number } | null>(null);

  useEffect(() => {
    if (activeCompany?.logo_url) {
      setDisplayedLogo({
        url: activeCompany.logo_url,
        scale: activeCompany.logo_scale || 1.0,
      });
    }
  }, [activeCompany?.logo_url, activeCompany?.logo_scale]);

  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const location = useLocation();
  const currentPath = location.pathname;

  const { data: electedStatus } = useQuery({
    queryKey: ["cse", "my-elected-status"],
    queryFn: () => getMyElectedStatus(),
    enabled: !!user,
  });

  const { data: medicalSettings } = useQuery({
    queryKey: ["medical-follow-up", "settings"],
    queryFn: () => getMedicalSettings(),
    enabled: !!user,
  });

  const medicalModuleEnabled = medicalSettings?.enabled === true;

  const { data: myMedicalObligations } = useEmployeeMedicalObligationsQuery(
    !!user && medicalModuleEnabled
  );

  const showMedicalNavBadge = shouldShowEmployeeMedicalNavBadge(myMedicalObligations);

  const mainNavItems = useMemo(() => {
    const items = [...coreNavItems];
    if (medicalModuleEnabled) {
      items.push({
        to: "/medical-follow-up",
        label: "Mon suivi médical",
        icon: Stethoscope,
        badge: showMedicalNavBadge,
      });
    }
    if (electedStatus?.is_elected) {
      items.push({ to: "/cse", label: "Mon CSE", icon: Handshake });
    }
    return items;
  }, [medicalModuleEnabled, showMedicalNavBadge, electedStatus?.is_elected]);

  if (!user) {
    return null;
  }

  const getNavClassName = (path: string) => {
    const baseClasses = collapsed
      ? "flex items-center justify-center rounded-lg h-8 w-8 p-0 transition-all duration-200 hover:bg-primary/10"
      : "flex items-center gap-3 rounded-lg px-3 py-2 transition-all duration-200 hover:bg-primary/10";
    return isNavActive(path, currentPath)
      ? `${baseClasses} bg-primary text-primary-foreground shadow-sm`
      : `${baseClasses} text-muted-foreground hover:text-foreground`;
  };

  const renderNavItem = (item: NavItem) => (
    <SidebarMenuItem key={item.to} className="relative">
      <SidebarMenuButton asChild tooltip={collapsed ? item.label : undefined}>
        <NavLink
          to={item.to}
          className={getNavClassName(item.to)}
          end={item.to === "/"}
          onMouseEnter={handleNavPrefetch(item.to)}
          onFocus={handleNavPrefetch(item.to)}
        >
          <item.icon className="h-5 w-5 flex-shrink-0" />
          {!collapsed && <span className="font-medium">{item.label}</span>}
        </NavLink>
      </SidebarMenuButton>
      {item.badge ? (
        <SidebarMenuBadge
          className="!right-2 !top-1/2 !h-2 !w-2 !min-w-0 !-translate-y-1/2 rounded-full border-0 bg-destructive p-0 text-[0] leading-none text-transparent"
          title="Visite médicale à traiter"
          aria-label="Visite médicale en retard ou à échéance proche"
        >
          .
        </SidebarMenuBadge>
      ) : null}
    </SidebarMenuItem>
  );

  return (
    <Sidebar className={collapsed ? "w-16" : "w-64"} collapsible="icon">
      <SidebarHeader className="p-4">
        <div className="flex items-center justify-start mb-2 -ml-2">
          <SidebarTrigger className="h-8 w-8 p-0 hover:bg-primary/10 flex-shrink-0" />
        </div>
        {!collapsed && (
          <div className="flex flex-col items-center gap-2 text-center">
            {displayedLogo ? (
              <div className="h-24 w-full flex items-center justify-center overflow-hidden">
                <img
                  src={displayedLogo.url}
                  alt={`Logo ${activeCompany?.company_name || "entreprise"}`}
                  className="h-full w-full object-contain transition-all duration-300"
                  style={{ transform: `scale(${displayedLogo.scale})` }}
                />
              </div>
            ) : (
              <img src="/Colorplast.png" alt="Logo par défaut" className="h-10 w-auto" />
            )}
            <p className="text-xs text-muted-foreground">Espace Collaborateur</p>
          </div>
        )}
      </SidebarHeader>

      <SidebarContent className={collapsed ? "px-2" : "px-4"}>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu className={collapsed ? "flex flex-col items-center gap-1" : ""}>
              {mainNavItems.map(renderNavItem)}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className={collapsed ? "p-2" : "px-4 pb-3 pt-2"}>
        {!collapsed && <Separator className="mb-2" />}
        <SidebarMenu className={collapsed ? "mb-2 flex flex-col items-center gap-1" : "mb-2"}>
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip={collapsed ? "Support" : undefined}>
              <NavLink
                to="/support"
                className={getNavClassName("/support")}
                onMouseEnter={handleNavPrefetch("/support")}
                onFocus={handleNavPrefetch("/support")}
              >
                <LifeBuoy className="h-5 w-5 flex-shrink-0" />
                {!collapsed && <span className="font-medium">Support</span>}
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
          {renderNavItem(profileItem)}
        </SidebarMenu>
        <div className={`flex items-center ${collapsed ? "flex-col gap-2" : "gap-3"}`}>
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
          <SidebarAccountMenu collapsed={collapsed} />
        </div>
        {companyId ? (
          <div
            className={cn(
              "mt-2 border-t border-sidebar-border pt-2",
              collapsed && "flex justify-center",
            )}
          >
            <NotificationBell companyId={companyId} collapsed={collapsed} />
          </div>
        ) : null}
      </SidebarFooter>
    </Sidebar>
  );
}
