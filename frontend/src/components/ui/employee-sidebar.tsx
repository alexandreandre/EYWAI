// src/components/ui/employee-sidebar.tsx

import { useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { Home, User, Wallet, Calendar, Receipt, FolderKanban, LogOut, Plane, DollarSign, Notebook, Settings, MessageSquare, Scale, Handshake, Stethoscope } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { ChangePasswordModal } from "@/components/ChangePasswordModal";
import { useQuery } from "@tanstack/react-query";
import { getMyElectedStatus } from "@/api/cse";
import { getMedicalSettings } from "@/api/medicalFollowUp";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarHeader,
  SidebarFooter,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";

const baseNavItems = [
  { to: "/", label: "Tableau de Bord", icon: Home },
  { to: "/payslips", label: "Rémunération", icon: DollarSign },
  { to: "/annual-reviews", label: "Mes Entretiens", icon: MessageSquare },
  { to: "/calendar", label: "Calendrier", icon: Calendar },
  { to: "/absences", label: "Congés & Absences", icon: Plane },
  { to: "/expenses", label: "Notes de Frais", icon: Notebook },
  { to: "/salary-advances", label: "Avances sur salaire", icon: Wallet },
  { to: "/documents", label: "Mes Documents", icon: FolderKanban },
  { to: "/profile", label: "Profil", icon: User },
];

export function EmployeeSidebar() {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const location = useLocation();
  const currentPath = location.pathname;
  const [showChangePassword, setShowChangePassword] = useState(false);

  // Vérifier si l'utilisateur est élu CSE
  const { data: electedStatus } = useQuery({
    queryKey: ["cse", "my-elected-status"],
    queryFn: () => getMyElectedStatus(),
    enabled: !!user,
  });

  // Module suivi médical (affiché si activé pour l'entreprise)
  const { data: medicalSettings } = useQuery({
    queryKey: ["medical-follow-up", "settings"],
    queryFn: () => getMedicalSettings(),
    enabled: !!user,
  });

  // Construire la liste des items de navigation avec CSE si élu et Suivi médical si activé
  const navItems = [
    ...baseNavItems,
    ...(medicalSettings?.enabled ? [{ to: "/medical-follow-up", label: "Mon suivi médical", icon: Stethoscope }] : []),
    ...(electedStatus?.is_elected
      ? [{ to: "/cse", label: "CSE/BDES", icon: Handshake }]
      : []),
  ];

  if (!user) {
    return null;
  }

  const isActive = (path: string) => {
    if (path === "/") {
      return currentPath === "/";
    }
    return currentPath.startsWith(path);
  };

  const getNavClassName = (path: string) => {
    const baseClasses = collapsed
      ? "flex items-center justify-center rounded-lg h-8 w-8 p-0 transition-all duration-200 hover:bg-primary/10"
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
            <img
              src="/Colorplast.png"
              alt="Logo Colorplast"
              className="h-10 w-auto"
            />
            <p className="text-xs text-muted-foreground">Espace Collaborateur</p>
          </div>
        )}
      </SidebarHeader>

      <SidebarContent className={collapsed ? "px-2" : "px-4"}>
        <SidebarGroup>
          <SidebarGroupLabel className={collapsed ? "sr-only" : ""}>
            Navigation
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className={collapsed ? "flex flex-col items-center gap-1" : ""}>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.label}>
                  <SidebarMenuButton asChild tooltip={collapsed ? item.label : undefined}>
                    <NavLink to={item.to} className={getNavClassName(item.to)} end={item.to === "/"}>
                      <item.icon className="h-5 w-5 flex-shrink-0" />
                      {!collapsed && <span className="font-medium">{item.label}</span>}
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
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
                    // On ne navigue pas manuellement.
                    // 'ProtectedRoutes' (dans App.tsx) détectera le changement
                    // et s'occupera de la redirection.
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