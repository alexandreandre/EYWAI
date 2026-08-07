import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Building2,
  Users,
  LifeBuoy,
  ScrollText,
  Shield,
  FileText,
  Radar,
  UsersRound,
  Percent,
  Send,
  Mail,
  Plug,
  FileUp,
  Activity,
  FlaskConical,
  Calculator,
} from "lucide-react";

export type AdminNavItem = {
  name: string;
  href: string;
  icon: LucideIcon;
  badgeKey?: "support";
};

export type AdminNavSection = {
  label: string;
  items: AdminNavItem[];
};

export const ADMIN_NAV_SECTIONS: AdminNavSection[] = [
  {
    label: "Accueil",
    items: [{ name: "Tableau de bord", href: "/super-admin", icon: LayoutDashboard }],
  },
  {
    label: "Organisation",
    items: [
      { name: "Groupe", href: "/super-admin/groups", icon: UsersRound },
      { name: "Entreprises du groupe", href: "/super-admin/companies", icon: Building2 },
      { name: "Import & configuration", href: "/super-admin/dsn-import", icon: FileUp },
      { name: "Utilisateurs", href: "/super-admin/users", icon: Users },
    ],
  },
  {
    label: "Gouvernance",
    items: [
      {
        name: "Centre support",
        href: "/super-admin/support",
        icon: LifeBuoy,
        badgeKey: "support",
      },
      { name: "Journal d'activité", href: "/super-admin/activity", icon: ScrollText },
      { name: "Profils & droits RH", href: "/super-admin/access", icon: Shield },
    ],
  },
  {
    label: "Référentiels",
    items: [
      {
        name: "Suivi des taux",
        href: "/super-admin/rates",
        icon: Percent,
      },
      {
        name: "Paramètres paie",
        href: "/super-admin/payroll-settings",
        icon: Percent,
      },
      {
        name: "Conventions collectives",
        href: "/super-admin/collective-agreements",
        icon: FileText,
      },
      {
        name: "Veille réglementaire",
        href: "/super-admin/scraping",
        icon: Radar,
      },
      {
        name: "Télétransmissions DSN",
        href: "/super-admin/dsn-transmissions",
        icon: Send,
      },
      {
        name: "Intégrations comptables",
        href: "/super-admin/accounting-integrations",
        icon: Plug,
      },
      {
        name: "Réduction Fillon",
        href: "/super-admin/reduction-fillon",
        icon: Calculator,
      },
    ],
  },
  {
    label: "Équipe EYWAI",
    items: [
      { name: "Accès plateforme", href: "/super-admin/admins", icon: Shield },
      { name: "Mails automatiques", href: "/super-admin/email-settings", icon: Mail },
      { name: "Monitoring", href: "/super-admin/monitoring", icon: Activity },
      { name: "Tests", href: "/super-admin/tests", icon: FlaskConical },
    ],
  },
];

export function isAdminNavActive(pathname: string, href: string): boolean {
  if (href === "/super-admin") {
    return pathname === href;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}
