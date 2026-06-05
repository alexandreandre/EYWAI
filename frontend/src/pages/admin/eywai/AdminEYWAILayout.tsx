import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, Menu } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  SidebarInset,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { SidebarAccountMenu } from "@/components/ui/sidebar-account-menu";
import { ADMIN_NAV_SECTIONS, isAdminNavActive } from "@/pages/admin/eywai/navigation";
import { useAdminSupportBadges } from "@/hooks/useAdminSupportBadges";

export default function AdminEYWAILayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { data: supportBadges } = useAdminSupportBadges();
  const supportCount = (supportBadges?.pending ?? 0) + (supportBadges?.urgent ?? 0);

  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full bg-muted/30">
        <Sidebar className="border-r border-sidebar-border">
          <SidebarHeader className="border-b border-sidebar-border px-4 py-4">
            <div className="flex flex-col gap-0.5">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                EYWAI
              </span>
              <span className="text-base font-semibold text-sidebar-foreground">
                Platforme Admin
              </span>
            </div>
          </SidebarHeader>
          <SidebarContent>
            {ADMIN_NAV_SECTIONS.map((section) => (
              <SidebarGroup key={section.label}>
                <SidebarGroupLabel>{section.label}</SidebarGroupLabel>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {section.items.map((item) => {
                      const active = isAdminNavActive(location.pathname, item.href);
                      const badge =
                        item.badgeKey === "support" && supportCount > 0
                          ? supportCount
                          : null;
                      return (
                        <SidebarMenuItem key={item.href}>
                          <SidebarMenuButton asChild isActive={active}>
                            <Link to={item.href}>
                              <item.icon className="h-4 w-4" />
                              <span>{item.name}</span>
                            </Link>
                          </SidebarMenuButton>
                          {badge != null ? (
                            <SidebarMenuBadge className="bg-primary text-primary-foreground">
                              {badge > 99 ? "99+" : badge}
                            </SidebarMenuBadge>
                          ) : null}
                        </SidebarMenuItem>
                      );
                    })}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            ))}
          </SidebarContent>
          <SidebarFooter className="border-t border-sidebar-border space-y-1 p-2">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 text-muted-foreground"
              onClick={() => navigate("/")}
            >
              <ArrowLeft className="h-4 w-4" />
              Retour à l&apos;application RH
            </Button>
            <SidebarAccountMenu className="w-full justify-start" />
          </SidebarFooter>
        </Sidebar>
        <SidebarInset className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b bg-background px-4">
            <SidebarTrigger>
              <Button variant="ghost" size="icon" className="md:hidden">
                <Menu className="h-5 w-5" />
                <span className="sr-only">Menu</span>
              </Button>
            </SidebarTrigger>
            <Separator orientation="vertical" className="hidden h-6 md:block" />
            <div className="flex flex-1 items-center justify-between gap-2">
              <p className="hidden text-sm text-muted-foreground md:block">
                Pilotage plateforme — groupes et entreprises
              </p>
              <Badge variant="secondary" className="ml-auto shrink-0 font-normal">
                Accès plateforme
              </Badge>
            </div>
          </header>
          <main className="min-w-0 flex-1 overflow-auto p-4 md:p-6 lg:p-8">
            <Outlet />
          </main>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
}
