import { Fragment, useState, useEffect, useMemo } from "react";
import {
  LayoutDashboard,
  Users,
  Calculator,
  Calendar,
  TrendingUp,
  UsersRound,
  ClipboardCheck,
  User,
  ClipboardEdit,
  ClipboardList,
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
  FileText,
  MessageSquare,
  Scale,
  Wallet,
  Landmark,
  Home,
  FolderKanban,
  Handshake,
  Stethoscope,
  UserPlus,
  ChevronRight,
  LifeBuoy,
  GraduationCap,
  BarChart2,
  ScanLine,
  Clock,
  PiggyBank,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext"; // <-- IMPORTATION
import { isPlatformAdmin } from "@/lib/platformAdmin";
import { useRhSidebarTaskBadges } from "@/hooks/useRhSidebarTaskBadges";
import { LaunchPayrollButton } from "@/features/payroll/components/LaunchPayrollButton";
import {
  computeAccessibleGroups,
  useCompanyOptional,
  type CompanyAccess,
} from "@/contexts/CompanyContext"; // <-- IMPORTATION
import { useViewOptional } from "@/contexts/ViewContext"; // NOUVEAU - Gestion de la vue pour collaborateur_rh
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { prefetchRoute } from "@/lib/prefetchByRole";
import { SidebarAccountMenu } from "@/components/ui/sidebar-account-menu";
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
import { NotificationBell } from "@/components/NotificationBell";
import type { LucideIcon } from "lucide-react";

type SidebarLinkItem = {
  title: string;
  url: string;
  icon: LucideIcon;
  disabled?: boolean;
};
type SidebarLinkGroup = {
  label?: string;
  items: SidebarLinkItem[];
  /** Étapes du parcours paie (numérotées, ligne verticale). */
  workflow?: boolean;
};

/** Hiérarchie typo sidebar RH — alignée sur les primitives `sidebar.tsx`. */
const SIDEBAR_NAV = {
  /** L0 — libellé de groupe (ex. EYWAI Home). */
  groupLabel: "text-xs font-medium text-sidebar-foreground/70",
  /** L1 — lien principal ou titre de section repliable. */
  sectionTitle: "text-sm font-medium leading-none",
  /** L1 — icône (même taille que `[&>svg]:size-4` du menu-button). */
  iconPrimary: "h-4 w-4 shrink-0",
  /** L2 — libellé de sous-section (Effectifs, Outils paie…). */
  subGroupLabel:
    "pt-2 pb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground/70",
  /** L2 — libellé de lien enfant (via SubButton `size="sm"` → text-xs). */
  subLinkLabel: "text-xs leading-snug",
  /** L3 — pastilles numérotées, compteurs, micro-badges. */
  micro: "text-[10px] font-semibold tabular-nums leading-none",
} as const;

const RH_HOME: SidebarLinkItem = {
  title: "Tableau de bord",
  url: "/",
  icon: LayoutDashboard,
};

const RH_TEAM_GROUPS_BASE: SidebarLinkGroup[] = [
  {
    items: [{ title: "Analytics Team", url: "/analytics", icon: BarChart2 }],
  },
  {
    label: "Effectifs",
    items: [
      { title: "Collaborateurs", url: "/employees", icon: Users },
      { title: "Recrutement", url: "/recruitment", icon: UserPlus },
      { title: "Onboarding", url: "/onboarding", icon: ClipboardList },
      { title: "Départs", url: "/employee-exits", icon: UserMinus },
      { title: "Équipes", url: "/teams", icon: Users },
    ],
  },
  {
    label: "Suivi documents",
    items: [
      { title: "Documents", url: "/documents", icon: FileText },
      { title: "Titres de séjour", url: "/residence-permits", icon: FileCheck },
    ],
  },
];

const RH_GESTION_SUIVI_RH_ITEMS: SidebarLinkItem[] = [
  { title: "Badgeuse", url: "/badgeuse-rh", icon: ScanLine },
  { title: "Calendriers", url: "/schedules", icon: Calendar },
  { title: "Planning", url: "/planning", icon: ClipboardList },
  { title: "Entretiens", url: "/formation#entretiens", icon: MessageSquare },
  { title: "Formation & talents", url: "/formation", icon: GraduationCap },
  { title: "Augmentations & Promotions", url: "/augmentations-et-promotions", icon: TrendingUp },
  { title: "CSE & Dialogue Social", url: "/cse", icon: Handshake },
];

function withRhMedicalFollowUpInGroups(groups: SidebarLinkGroup[]): SidebarLinkGroup[] {
  return groups.map((group) => {
    const items = [...group.items];
    const entretiensIdx = items.findIndex((m) => m.url === "/formation#entretiens");
    if (entretiensIdx < 0 || items.some((m) => m.url === "/medical-follow-up")) {
      return group;
    }
    items.splice(entretiensIdx + 1, 0, {
      title: "Suivi médical",
      url: "/medical-follow-up",
      icon: Stethoscope,
    });
    return { ...group, items };
  });
}

const RH_TEAM_GROUPS = RH_TEAM_GROUPS_BASE;

const RH_GESTION_GROUPS_BASE: SidebarLinkGroup[] = [
  {
    items: [
      {
        title: "Analytics Gestion",
        url: "/analytics-gestion",
        icon: BarChart2,
      },
      ...RH_GESTION_SUIVI_RH_ITEMS,
      { title: "Gestion des Utilisateurs", url: "/users", icon: UserCog },
    ],
  },
];

const RH_GESTION_GROUPS = withRhMedicalFollowUpInGroups(RH_GESTION_GROUPS_BASE);

const RH_PAIE_GROUPS: SidebarLinkGroup[] = [
  {
    items: [
      {
        title: "Analytics Paie",
        url: "/analytics-paie",
        icon: BarChart2,
      },
    ],
  },
  {
    workflow: true,
    items: [
      {
        title: "Calendrier",
        url: "/schedules",
        icon: Calendar,
      },
      { title: "Congés & Absences", url: "/leaves", icon: Plane },
      { title: "Suivi IJSS / CPAM", url: "/suivi-ijss", icon: FileCheck },
      { title: "Temps de travail & HS", url: "/suivi-temps-travail", icon: Clock },
      { title: "Contingent HS", url: "/suivi-contingent-hs", icon: Clock },
      { title: "Modulation", url: "/suivi-modulation", icon: Clock },
      { title: "Suivi CET", url: "/suivi-cet", icon: PiggyBank },
      { title: "Notes de frais", url: "/expenses", icon: Notebook },
      { title: "Primes", url: "/saisies", icon: ClipboardEdit },
      { title: "Saisies sur salaire", url: "/salary-seizures", icon: Scale },
      { title: "Avances & acomptes", url: "/salary-advances", icon: Wallet },
      { title: "Prêts employeur", url: "/employee-loans", icon: Landmark },
    ],
  },
  {
    label: "Outils paie",
    items: [
      { title: "Simulation Paie", url: "/simulation", icon: FlaskConical },
      { title: "Suivi des taux", url: "/rates", icon: TrendingUp },
      { title: "Exports", url: "/exports", icon: FileDown },
      { title: "Paie", url: "/payroll", icon: Calculator },
    ],
  },
];

function flattenNavGroups(
  groups: SidebarLinkGroup[],
  includeDisabled = false,
): SidebarLinkItem[] {
  return groups.flatMap((g) =>
    g.items.filter((i) => includeDisabled || !i.disabled),
  );
}

function sectionHasTasksFromGroups(
  groups: SidebarLinkGroup[],
  getCount: (url: string) => number,
): boolean {
  return flattenNavGroups(groups, true).some(
    (i) => !i.disabled && getCount(i.url) > 0,
  );
}

function sectionIsActiveFromGroups(
  groups: SidebarLinkGroup[],
  isActive: (path: string) => boolean,
): boolean {
  return flattenNavGroups(groups, true).some((i) => !i.disabled && isActive(i.url));
}

const MON_ENTREPRISE_NAV_URL = "/company";

function monEntrepriseNavTitle(companyName?: string | null): string {
  const trimmed = companyName?.trim();
  return trimmed || "Mon Entreprise";
}

function buildMonEntrepriseNav(companyName?: string | null): SidebarLinkItem {
  return {
    title: monEntrepriseNavTitle(companyName),
    url: MON_ENTREPRISE_NAV_URL,
    icon: Building,
  };
}

const rhTeamNavItems = flattenNavGroups(RH_TEAM_GROUPS);
const rhPaieNavItems = flattenNavGroups(RH_PAIE_GROUPS);

/** Index d’insertion de « Mon Entreprise » dans Vues consolidées (juste au-dessus de MAJI). */
function monEntrepriseInsertIndexInConsolidated(
  groups: { groupId: string; groupCompanies: CompanyAccess[] }[],
): number {
  const majiIdx = groups.findIndex(
    (g) => (g.groupCompanies[0]?.group_name ?? "").trim().toUpperCase() === "MAJI",
  );
  return majiIdx >= 0 ? majiIdx : groups.length;
}

function consolidatedGroupDisplayName(group: {
  groupCompanies: CompanyAccess[];
}): string {
  return (
    group.groupCompanies[0]?.group_name ||
    `Groupe ${group.groupCompanies.length} entreprises`
  );
}

function getConsolidatedGroupNavClassName(
  path: string,
  collapsed: boolean,
  isActive: (path: string) => boolean,
): string {
  const baseClasses = collapsed
    ? "flex items-center justify-center rounded-lg h-8 w-8 p-0 transition-all duration-200 hover:bg-primary/10"
    : "flex min-h-9 items-center gap-2 rounded-lg px-2.5 py-1.5 transition-all duration-200 hover:bg-primary/10";
  return isActive(path)
    ? `${baseClasses} bg-primary text-primary-foreground shadow-sm`
    : `${baseClasses} text-muted-foreground hover:text-foreground`;
}

function ConsolidatedGroupLinkLabel({
  groupName,
  companyCount,
}: {
  groupName: string;
  companyCount: number;
}) {
  return (
    <div className="flex min-w-0 flex-1 flex-col justify-center leading-tight">
      <span className="truncate text-sm font-medium leading-tight">{groupName}</span>
      <span className="truncate text-[11px] leading-tight opacity-70">
        {companyCount > 1 ? `${companyCount} entreprises` : `${companyCount} entreprise`}
      </span>
    </div>
  );
}

const menuItems = {
  rh: [
    RH_HOME,
    ...rhTeamNavItems,
    ...flattenNavGroups(RH_GESTION_GROUPS),
    ...rhPaieNavItems,
  ] satisfies SidebarLinkItem[],
  manager: [
    { title: "Validations", url: "/approvals", icon: ClipboardCheck },
    { title: "Congés à valider", url: "/leave-requests", icon: Plane },
    { title: "CET à valider", url: "/cet-requests", icon: PiggyBank },
  ],
  employee: [
    { title: "Tableau de Bord", url: "/", icon: Home },
    { title: "Calendrier et planning", url: "/calendar", icon: Calendar },
    { title: "Ma badgeuse", url: "/badgeuse", icon: ScanLine },
    { title: "Congés & Absences", url: "/absences", icon: Plane },
    { title: "Mon CET", url: "/mon-cet", icon: PiggyBank },
    { title: "Notes de Frais", url: "/expenses", icon: Notebook },
    { title: "Avances & acomptes", url: "/salary-advances", icon: Wallet },
    { title: "Prêts employeur", url: "/employee-loans", icon: Landmark },
    { title: "Mes Documents", url: "/employee/documents", icon: FolderKanban },
    { title: "Participation", url: "/employee/participation", icon: Handshake },
    { title: "Ma formation", url: "/employee/formation", icon: GraduationCap },
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
      className="!right-7 !top-1/2 !h-2 !w-2 !min-w-0 !-translate-y-1/2 rounded-full border-0 bg-destructive p-0 text-[0] leading-none text-transparent shadow-sm"
      title={`Actions à traiter — ${sectionLabel}`}
      aria-label={`Des tâches sont en attente dans ${sectionLabel}`}
    >
      .
    </SidebarMenuBadge>
  );
}

function SidebarSubLinkContent({
  item,
  count,
  isActive,
  hideCount,
}: {
  item: SidebarLinkItem;
  count: number;
  isActive: boolean;
  hideCount?: boolean;
}) {
  if (item.disabled) {
    return (
      <SidebarMenuSubButton
        size="sm"
        aria-disabled="true"
        className="pointer-events-none cursor-not-allowed opacity-50"
        title="Bientôt disponible"
      >
        <item.icon className={SIDEBAR_NAV.iconPrimary} />
        <span className={SIDEBAR_NAV.subLinkLabel}>{item.title}</span>
        <span
          className={cn(
            "ml-auto rounded bg-muted px-1.5 py-0.5 uppercase tracking-wider text-muted-foreground",
            SIDEBAR_NAV.micro,
          )}
        >
          Bientôt
        </span>
      </SidebarMenuSubButton>
    );
  }

  return (
    <div className="relative">
      <SidebarMenuSubButton
        asChild
        isActive={isActive}
        size="sm"
        className={cn(count > 0 && "pr-9")}
      >
        <NavLink to={item.url} end={item.url === "/"}>
          <item.icon className={SIDEBAR_NAV.iconPrimary} />
          <span className={SIDEBAR_NAV.subLinkLabel}>{item.title}</span>
        </NavLink>
      </SidebarMenuSubButton>
      <SubNavCountBadge count={hideCount ? 0 : count} />
    </div>
  );
}

/** Sous-lien de navigation (actif ou désactivé « Bientôt »). */
function SidebarSubLinkItem({
  item,
  count,
  isActive,
  hideCount,
}: {
  item: SidebarLinkItem;
  count: number;
  isActive: boolean;
  hideCount?: boolean;
}) {
  return (
    <SidebarMenuSubItem>
      <SidebarSubLinkContent
        item={item}
        count={count}
        isActive={isActive}
        hideCount={hideCount}
      />
    </SidebarMenuSubItem>
  );
}

const PAIE_WORKFLOW_STEP_PX = 28;
const PAIE_WORKFLOW_START_Y = 14;
const PAIE_WORKFLOW_GAP_PX = 16;
const PAIE_WORKFLOW_BTN_ROW_PX = 36;
const PAIE_WORKFLOW_BADGE_COL_PX = 18;
/** Position X du rail vertical (centre de la colonne pastilles). */
const PAIE_WORKFLOW_RAIL_X = 9;
/** Largeur approximative du segment horizontal (18px + gap-2 − rail). */
const PAIE_WORKFLOW_BTN_LEAD_PX = 17;

/** Rail vertical du parcours paie (pastilles numérotées). */
function PaieWorkflowVerticalRail({
  stepCount,
  muted = false,
}: {
  stepCount: number;
  muted?: boolean;
}) {
  const lastStepY = stepCount * PAIE_WORKFLOW_STEP_PX;
  const cornerY =
    lastStepY +
    PAIE_WORKFLOW_GAP_PX +
    PAIE_WORKFLOW_BTN_ROW_PX / 2 -
    4;
  const viewH = cornerY + PAIE_WORKFLOW_BTN_ROW_PX / 2 + 4;

  return (
    <svg
      className="pointer-events-none absolute inset-0 z-0 h-full w-full"
      viewBox={`0 0 200 ${viewH}`}
      preserveAspectRatio="none"
      aria-hidden
    >
      <path
        d={`M ${PAIE_WORKFLOW_RAIL_X} ${PAIE_WORKFLOW_START_Y} L ${PAIE_WORKFLOW_RAIL_X} ${cornerY}`}
        fill="none"
        stroke={muted ? "hsl(var(--muted-foreground))" : "hsl(var(--primary))"}
        strokeWidth="2"
        strokeOpacity={muted ? 0.35 : 0.55}
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Branche horizontale jusqu’au bord gauche du bouton « Lancer la paie ». */
function PaieWorkflowButtonLead({ muted = false }: { muted?: boolean }) {
  const viewW = PAIE_WORKFLOW_BTN_LEAD_PX;

  return (
    <div
      className="pointer-events-none absolute top-1/2 z-0 -translate-y-1/2"
      style={{
        left: `calc(-${PAIE_WORKFLOW_BADGE_COL_PX}px - 0.5rem + ${PAIE_WORKFLOW_RAIL_X}px)`,
        width: `calc(${PAIE_WORKFLOW_BADGE_COL_PX}px + 0.5rem - ${PAIE_WORKFLOW_RAIL_X}px)`,
      }}
      aria-hidden
    >
      <svg
        className="h-2 w-full overflow-visible"
        viewBox={`0 0 ${viewW} 8`}
        preserveAspectRatio="none"
      >
        <path
          d={`M 0 4 L ${viewW} 4`}
          fill="none"
          stroke={muted ? "hsl(var(--muted-foreground))" : "hsl(var(--primary))"}
          strokeWidth="2"
          strokeOpacity={muted ? 0.35 : 0.55}
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}

/** Parcours paie : ligne verticale, numéros d’étape et flèche vers « Lancer la paie ». */
function SidebarPaieWorkflow({
  groups,
  getCount,
  isActive,
  pipelineLoading,
}: {
  groups: SidebarLinkGroup[];
  getCount: (url: string) => number;
  isActive: (path: string) => boolean;
  pipelineLoading?: boolean;
}) {
  /** Liens hors parcours numéroté (ex. Analytics Paie), affichés en tête de section. */
  const topItems = groups
    .filter((g) => !g.workflow && !g.label)
    .flatMap((g) => g.items.filter((i) => !i.disabled));
  const disabledItems = groups
    .filter((g) => !g.workflow && !g.label)
    .flatMap((g) => g.items.filter((i) => i.disabled));
  const workflowItems = groups
    .filter((g) => g.workflow)
    .flatMap((g) => g.items.filter((i) => !i.disabled));
  const toolGroups = groups.filter((g) => g.label && !g.workflow);

  return (
    <div role="group" aria-label="Navigation paie">
      {topItems.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-0.5 pb-2 p-0">
          {topItems.map((item) => (
            <SidebarSubLinkItem
              key={item.url}
              item={item}
              count={getCount(item.url)}
              isActive={isActive(item.url)}
            />
          ))}
        </ul>
      )}

      {disabledItems.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-0.5 py-0.5 p-0">
          {disabledItems.map((item) => (
            <SidebarSubLinkItem
              key={item.url}
              item={item}
              count={0}
              isActive={isActive(item.url)}
            />
          ))}
        </ul>
      )}

      <div
        className="relative flex gap-2 py-0.5"
        role="group"
        aria-label="Parcours de préparation à la paie"
      >
        <PaieWorkflowVerticalRail
          stepCount={workflowItems.length}
          muted={pipelineLoading}
        />

        <div className="relative z-[1] flex w-[18px] shrink-0 flex-col">
          {workflowItems.map((item, index) => {
            const itemCount = getCount(item.url);
            return (
              <div
                key={item.url}
                className="flex h-7 shrink-0 items-center justify-center"
                aria-hidden
              >
                <WorkflowStepBadge
                  step={index + 1}
                  count={itemCount}
                  isLoading={pipelineLoading}
                />
              </div>
            );
          })}
        </div>

        <div className="relative z-[1] flex min-w-0 flex-1 flex-col">
          <SidebarMenuSub className="mx-0 gap-0 border-0 p-0">
            {workflowItems.map((item) => {
              const itemCount = getCount(item.url);
              return (
                <SidebarMenuSubItem key={item.url} className="min-w-0">
                  <SidebarSubLinkContent
                    item={item}
                    count={itemCount}
                    isActive={isActive(item.url)}
                    hideCount={pipelineLoading}
                  />
                </SidebarMenuSubItem>
              );
            })}
          </SidebarMenuSub>

          <div className="relative z-[2] mt-4 flex min-h-9 items-center pb-2">
            <PaieWorkflowButtonLead muted={pipelineLoading} />
            <LaunchPayrollButton
              fullWidth
              className="relative z-[1]"
              pipelineLoading={pipelineLoading}
            />
          </div>
        </div>
      </div>

      {toolGroups.length > 0 && (
        <div className="mt-2 border-t border-sidebar-border pt-2">
          <SidebarNavGroups groups={toolGroups} getCount={getCount} isActive={isActive} />
        </div>
      )}
    </div>
  );
}

function SidebarNavGroups({
  groups,
  getCount,
  isActive,
}: {
  groups: SidebarLinkGroup[];
  getCount: (url: string) => number;
  isActive: (path: string) => boolean;
}) {
  return (
    <>
      {groups.map((group, gi) => (
        <Fragment key={group.label ?? `g-${gi}`}>
          {group.label && (
            <div className={SIDEBAR_NAV.subGroupLabel}>{group.label}</div>
          )}
          {group.items.map((item) => (
            <SidebarSubLinkItem
              key={item.url}
              item={item}
              count={getCount(item.url)}
              isActive={isActive(item.url)}
            />
          ))}
        </Fragment>
      ))}
    </>
  );
}

/** Pastille numérotée d’étape du parcours paie (vert = à jour, rouge = actions en attente). */
function WorkflowStepBadge({
  step,
  count,
  isLoading,
}: {
  step: number;
  count: number;
  isLoading?: boolean;
}) {
  const hasPending = count > 0;

  return (
    <span
      className={cn(
        "relative z-[1] flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full border border-background shadow-sm",
        SIDEBAR_NAV.micro,
        isLoading && "bg-muted text-muted-foreground ring-1 ring-border",
        !isLoading &&
          hasPending &&
          "bg-destructive text-destructive-foreground ring-1 ring-destructive/50",
        !isLoading &&
          !hasPending &&
          "bg-success text-success-foreground ring-1 ring-success/40",
      )}
      aria-label={
        isLoading
          ? `Étape ${step}`
          : hasPending
            ? `Étape ${step} : ${count} élément${count > 1 ? "s" : ""} à traiter`
            : `Étape ${step} : à jour`
      }
    >
      {step}
    </span>
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
      className={cn(
        "pointer-events-none absolute right-1.5 top-1/2 z-[1] flex h-5 min-w-5 -translate-y-1/2 items-center justify-center rounded-md bg-destructive px-1 text-destructive-foreground shadow-sm",
        SIDEBAR_NAV.micro,
      )}
      aria-label={`${nLabel} élément${plural ? "s" : ""} à traiter`}
    >
      {shown}
    </span>
  );
}

export function AppSidebar() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { state } = useSidebar();
  const navigate = useNavigate();
  const collapsed = state === "collapsed";
  const location = useLocation();
  const currentPath = location.pathname;
  
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
  const handleNavPrefetch = (url: string) => () => {
    prefetchRoute(queryClient, url, activeCompany?.company_id);
  };
  const accessibleCompanies: CompanyAccess[] = companyContext?.accessibleCompanies ?? [];
  const accessibleGroups =
    companyContext != null
      ? computeAccessibleGroups(companyContext.accessibleCompanies)
      : [];

  // Mettre à jour le logo affiché seulement quand un nouveau logo est disponible
  useEffect(() => {
    if (activeCompany?.logo_url) {
      setDisplayedLogo({
        url: activeCompany.logo_url,
        scale: activeCompany.logo_scale || 1.0
      });
    }
  }, [activeCompany?.logo_url, activeCompany?.logo_scale]);

  const isActive = (path: string) => {
    if (path === "/") {
      return currentPath === "/";
    }
    if (path === "/formation#entretiens") {
      const hash = window.location.hash.replace(/^#/, "").toLowerCase();
      return (
        currentPath.startsWith("/annual-reviews") ||
        (currentPath.startsWith("/formation") && hash === "entretiens")
      );
    }
    if (path === "/formation") {
      const hash = window.location.hash.replace(/^#/, "").toLowerCase();
      return (
        (currentPath.startsWith("/formation") && hash !== "entretiens") ||
        currentPath === "/habilitations" ||
        currentPath === "/objectives" ||
        currentPath === "/catalogue-formations"
      );
    }
    if (path === "/employee/formation") {
      return (
        currentPath.startsWith("/employee/formation") ||
        currentPath === "/habilitations" ||
        currentPath === "/objectives" ||
        currentPath === "/catalogue-formations"
      );
    }
    if (path.startsWith("/manager/")) {
      return currentPath === path || currentPath.startsWith(`${path}/`);
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
    (user.role === "rh" ||
      user.role === "admin" ||
      (isCollaborateurRh && viewMode === "rh"));
  const { getCount, totalRhPending, isPayrollPipelineLoading } =
    useRhSidebarTaskBadges(isRhMenu);

  const hasConsolidatedViews = accessibleGroups.length > 0;
  const monEntrepriseNav = useMemo(
    () => buildMonEntrepriseNav(activeCompany?.company_name),
    [activeCompany?.company_name],
  );
  const majiInsertIndex = useMemo(
    () => monEntrepriseInsertIndexInConsolidated(accessibleGroups),
    [accessibleGroups],
  );
  const rhGestionGroups = useMemo(() => {
    const base = RH_GESTION_GROUPS.map((g) => ({
      ...g,
      items: [...g.items],
    }));
    if (!hasConsolidatedViews && base[0]) {
      const usersIdx = base[0].items.findIndex((i) => i.url === "/users");
      const idx = usersIdx >= 0 ? usersIdx : base[0].items.length;
      base[0].items.splice(idx, 0, monEntrepriseNav);
    }
    return base;
  }, [hasConsolidatedViews, monEntrepriseNav]);

  const rhCollapsedNavItems = useMemo(
    () => [
      RH_HOME,
      ...flattenNavGroups(RH_TEAM_GROUPS),
      ...flattenNavGroups(rhGestionGroups),
      ...flattenNavGroups(RH_PAIE_GROUPS),
    ],
    [rhGestionGroups],
  );

  const teamSectionHasTasks = sectionHasTasksFromGroups(RH_TEAM_GROUPS, getCount);
  const gestionSectionHasTasks = sectionHasTasksFromGroups(rhGestionGroups, getCount);
  const paieSectionHasTasks =
    !isPayrollPipelineLoading && sectionHasTasksFromGroups(RH_PAIE_GROUPS, getCount);

  const [teamOpen, setTeamOpen] = useState(() =>
    sectionIsActiveFromGroups(RH_TEAM_GROUPS, isActive),
  );
  const [gestionOpen, setGestionOpen] = useState(() =>
    sectionIsActiveFromGroups(rhGestionGroups, isActive),
  );
  const [paieOpen, setPaieOpen] = useState(() =>
    sectionIsActiveFromGroups(RH_PAIE_GROUPS, isActive),
  );

  useEffect(() => {
    if (sectionIsActiveFromGroups(RH_TEAM_GROUPS, isActive)) setTeamOpen(true);
    if (sectionIsActiveFromGroups(rhGestionGroups, isActive)) setGestionOpen(true);
    if (sectionIsActiveFromGroups(RH_PAIE_GROUPS, isActive)) setPaieOpen(true);
  }, [currentPath, location.hash, rhGestionGroups]);

  // Si l'utilisateur n'est pas encore chargé, on n'affiche rien ou un loader
  if (!user) {
    return null;
  }

  // Déterminer quel menu afficher selon le rôle et la vue
  let userRole = user.role as keyof typeof menuItems;
  let items: SidebarLinkItem[] = menuItems[userRole] ?? [];

  // Si collaborateur_rh et vue Collaborateur, afficher le menu collaborateur
  if (isCollaborateurRh && viewMode === 'collaborateur') {
    userRole = 'employee';
    items = menuItems.employee || [];
  } else if (isCollaborateurRh && viewMode === 'rh') {
    // Si collaborateur_rh et vue RH, afficher le menu RH
    userRole = 'rh';
    items = menuItems.rh || [];
  } else if (user.role === 'admin') {
    // Admin : même navigation que la RH (inclut les vues « équipe » manager)
    userRole = 'rh';
    items = menuItems.rh || [];
  }

  if (userRole === "rh" && collapsed) {
    items = rhCollapsedNavItems;
  }

  const showRhAccordion = userRole === "rh" && !collapsed;

  return (
    <Sidebar className={collapsed ? "w-16" : "w-64"} collapsible="icon">
      <SidebarHeader className="p-4">
        <div className="flex items-center justify-start mb-2 -ml-2">
          <SidebarTrigger className="h-8 w-8 p-0 hover:bg-primary/10 flex-shrink-0" />
        </div>
        {!collapsed && accessibleCompanies.length > 1 && (
          <div className="mb-3 w-full">
            <CompanySwitcher variant="sidebar" />
          </div>
        )}
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
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <div className="relative w-full">
                      <SidebarMenuButton
                        asChild
                        isActive={isActive(RH_HOME.url)}
                        className={cn("w-full", totalRhPending > 0 && !collapsed && "pr-9")}
                      >
                        <NavLink to={RH_HOME.url} end={RH_HOME.url === "/"}>
                          <RH_HOME.icon className={SIDEBAR_NAV.iconPrimary} />
                          <span className={SIDEBAR_NAV.sectionTitle}>{RH_HOME.title}</span>
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
                <SidebarMenu className="gap-0">
                  <Collapsible open={teamOpen} onOpenChange={setTeamOpen} className="group/collapsible">
                    <SidebarMenuItem>
                      <div className="relative w-full">
                        <CollapsibleTrigger asChild>
                          <SidebarMenuButton size="sm" className="w-full">
                            <Users className={SIDEBAR_NAV.iconPrimary} />
                            <span className={SIDEBAR_NAV.sectionTitle}>EYWAI Team</span>
                            <ChevronRight
                              className={cn(
                                "ml-auto h-4 w-4 shrink-0 transition-transform duration-200",
                                "group-data-[state=open]/collapsible:rotate-90",
                              )}
                            />
                          </SidebarMenuButton>
                        </CollapsibleTrigger>
                        <SectionTaskDot visible={teamSectionHasTasks} sectionLabel="EYWAI Team" />
                      </div>
                      <CollapsibleContent>
                        <SidebarMenuSub>
                          <SidebarNavGroups
                            groups={RH_TEAM_GROUPS}
                            getCount={getCount}
                            isActive={isActive}
                          />
                        </SidebarMenuSub>
                      </CollapsibleContent>
                    </SidebarMenuItem>
                  </Collapsible>

                  <Collapsible open={gestionOpen} onOpenChange={setGestionOpen} className="group/collapsible">
                    <SidebarMenuItem>
                      <div className="relative w-full">
                        <CollapsibleTrigger asChild>
                          <SidebarMenuButton size="sm" className="w-full">
                            <Settings className={SIDEBAR_NAV.iconPrimary} />
                            <span className={SIDEBAR_NAV.sectionTitle}>EYWAI Gestion</span>
                            <ChevronRight
                              className={cn(
                                "ml-auto h-4 w-4 shrink-0 transition-transform duration-200",
                                "group-data-[state=open]/collapsible:rotate-90",
                              )}
                            />
                          </SidebarMenuButton>
                        </CollapsibleTrigger>
                        <SectionTaskDot visible={gestionSectionHasTasks} sectionLabel="EYWAI Gestion" />
                      </div>
                      <CollapsibleContent>
                        <SidebarMenuSub>
                          <SidebarNavGroups
                            groups={rhGestionGroups}
                            getCount={getCount}
                            isActive={isActive}
                          />
                        </SidebarMenuSub>
                      </CollapsibleContent>
                    </SidebarMenuItem>
                  </Collapsible>

                  <Collapsible open={paieOpen} onOpenChange={setPaieOpen} className="group/collapsible">
                    <SidebarMenuItem>
                      <div className="relative w-full">
                        <CollapsibleTrigger asChild>
                          <SidebarMenuButton size="sm" className="w-full">
                            <Calculator className={SIDEBAR_NAV.iconPrimary} />
                            <span className={SIDEBAR_NAV.sectionTitle}>EYWAI Paie</span>
                            <ChevronRight
                              className={cn(
                                "ml-auto h-4 w-4 shrink-0 transition-transform duration-200",
                                "group-data-[state=open]/collapsible:rotate-90",
                              )}
                            />
                          </SidebarMenuButton>
                        </CollapsibleTrigger>
                        <SectionTaskDot visible={paieSectionHasTasks} sectionLabel="EYWAI Paie" />
                      </div>
                      <CollapsibleContent>
                        <SidebarMenuSub className="mx-0 gap-1 border-0 px-0 py-0.5">
                          <SidebarPaieWorkflow
                            groups={RH_PAIE_GROUPS}
                            getCount={getCount}
                            isActive={isActive}
                            pipelineLoading={isPayrollPipelineLoading}
                          />
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
                      <div className="relative w-full">
                        <SidebarMenuButton asChild tooltip={collapsed ? item.title : undefined}>
                          <NavLink
                            to={item.url}
                            className={cn(getNavClassName(item.url), subCount > 0 && !collapsed && "pr-9")}
                            end={item.url === "/"}
                            onMouseEnter={handleNavPrefetch(item.url)}
                          >
                            <item.icon className={SIDEBAR_NAV.iconPrimary} />
                            {!collapsed && (
                              <span className={SIDEBAR_NAV.sectionTitle}>{item.title}</span>
                            )}
                          </NavLink>
                        </SidebarMenuButton>
                        {!collapsed && userRole === "rh" && subCount > 0 && (
                          <SidebarMenuBadge
                            className={cn(
                              "bg-destructive text-destructive-foreground",
                              SIDEBAR_NAV.micro,
                            )}
                          >
                            {formatNavBadgeCount(subCount)}
                          </SidebarMenuBadge>
                        )}
                      </div>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}

        {/* Section Groupes - affichée uniquement si l'utilisateur a accès à plusieurs entreprises d'un même groupe */}
        {hasConsolidatedViews && (
          <SidebarGroup>
            <SidebarGroupLabel className={collapsed ? "sr-only" : ""}>
              Vues Consolidées
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu className={collapsed ? "flex flex-col items-center gap-1" : "gap-0.5"}>
                {accessibleGroups.slice(0, majiInsertIndex).map((group) => {
                  const groupUrl = `/groups/${group.groupId}`;
                  const groupName = consolidatedGroupDisplayName(group);

                  return (
                    <SidebarMenuItem key={group.groupId}>
                      <SidebarMenuButton
                        asChild
                        className={collapsed ? undefined : "!h-auto"}
                        tooltip={collapsed ? groupName : undefined}
                      >
                        <NavLink
                          to={groupUrl}
                          className={getConsolidatedGroupNavClassName(
                            groupUrl,
                            collapsed,
                            isActive,
                          )}
                        >
                          <Building2 className={SIDEBAR_NAV.iconPrimary} />
                          {!collapsed && (
                            <ConsolidatedGroupLinkLabel
                              groupName={groupName}
                              companyCount={group.groupCompanies.length}
                            />
                          )}
                        </NavLink>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
                <SidebarMenuItem>
                  <SidebarMenuButton
                    asChild
                    tooltip={collapsed ? monEntrepriseNav.title : undefined}
                  >
                    <NavLink
                      to={monEntrepriseNav.url}
                      className={getConsolidatedGroupNavClassName(
                        monEntrepriseNav.url,
                        collapsed,
                        isActive,
                      )}
                    >
                      <monEntrepriseNav.icon className={SIDEBAR_NAV.iconPrimary} />
                      {!collapsed && (
                        <span className="truncate text-sm font-medium leading-tight">
                          {monEntrepriseNav.title}
                        </span>
                      )}
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                {accessibleGroups.slice(majiInsertIndex).map((group) => {
                  const groupUrl = `/groups/${group.groupId}`;
                  const groupName = consolidatedGroupDisplayName(group);

                  return (
                    <SidebarMenuItem key={group.groupId}>
                      <SidebarMenuButton
                        asChild
                        className={collapsed ? undefined : "!h-auto"}
                        tooltip={collapsed ? groupName : undefined}
                      >
                        <NavLink
                          to={groupUrl}
                          className={getConsolidatedGroupNavClassName(
                            groupUrl,
                            collapsed,
                            isActive,
                          )}
                        >
                          <Building2 className={SIDEBAR_NAV.iconPrimary} />
                          {!collapsed && (
                            <ConsolidatedGroupLinkLabel
                              groupName={groupName}
                              companyCount={group.groupCompanies.length}
                            />
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

      <SidebarFooter className={collapsed ? "p-2" : "px-4 pb-2 pt-1.5"}>
        {!collapsed && <Separator className="mb-1.5" />}
        {activeCompany?.company_id ? (
          <div
            className={cn(
              "mb-1",
              collapsed && "flex justify-center",
            )}
          >
            <NotificationBell
              companyId={activeCompany.company_id}
              collapsed={collapsed}
              compact
            />
          </div>
        ) : null}
        <SidebarMenu className={collapsed ? "mb-1.5 flex flex-col items-center gap-0.5" : "mb-1.5 gap-0.5"}>
          {isPlatformAdmin(user) ? (
            <SidebarMenuItem>
              <SidebarMenuButton asChild tooltip={collapsed ? "Platforme Admin" : undefined}>
                <NavLink to="/super-admin" className={getNavClassName("/super-admin")}>
                  <Building2 className="h-5 w-5 flex-shrink-0" />
                  {!collapsed && <span className="font-medium">Platforme Admin</span>}
                </NavLink>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ) : null}
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip={collapsed ? "Support" : undefined}>
              <NavLink to="/support" className={getNavClassName("/support")}>
                <LifeBuoy className="h-5 w-5 flex-shrink-0" />
                {!collapsed && <span className="font-medium">Support</span>}
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <div className={`flex items-center ${collapsed ? 'flex-col gap-1.5' : 'gap-2.5'}`}>
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
      </SidebarFooter>
    </Sidebar>
  );
}