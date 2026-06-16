import { useMemo } from "react";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { useNavigate } from "react-router-dom";
import {
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Loader2, MoreHorizontal, Plus } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { fetchDsnAdminLateSummary } from "@/api/dsnImport";
import {
  dsnStatusLabel,
  dsnStatusVariant,
} from "@/features/dsn-import/components/DsnCoverageTimeline";
import type { AdminCompany } from "@/pages/admin/eywai/companies/types";
import { DEFAULT_PLATFORM_GROUP_NAME } from "@/lib/adminGroup";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

type CompaniesTableProps = {
  companies: AdminCompany[];
  majiGroupId: string | null;
  assigningToGroup: boolean;
  onAssignToGroup: (companyId: string) => void;
  onToggleStatus: (company: AdminCompany) => void;
  onDelete: (company: AdminCompany) => void;
  emptyMessage?: string;
  reorderMode?: boolean;
  showOrderColumn?: boolean;
  savingOrder?: boolean;
  onReorder?: (orderedIds: string[]) => void;
};

function formatDate(iso: string): string {
  try {
    return format(new Date(iso), "dd/MM/yyyy", { locale: fr });
  } catch {
    return iso;
  }
}

function isInMajiGroup(company: AdminCompany, majiGroupId: string | null): boolean {
  return Boolean(majiGroupId && company.group_id === majiGroupId);
}

function companyInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

type CompanyRowProps = {
  company: AdminCompany;
  orderIndex: number;
  majiGroupId: string | null;
  assigningToGroup: boolean;
  onAssignToGroup: (companyId: string) => void;
  onToggleStatus: (company: AdminCompany) => void;
  onDelete: (company: AdminCompany) => void;
  reorderMode?: boolean;
  showOrderColumn?: boolean;
  sortable?: boolean;
  dsnStatus?: string | null;
};

function CompanyRow({
  company,
  orderIndex,
  majiGroupId,
  assigningToGroup,
  onAssignToGroup,
  onToggleStatus,
  onDelete,
  reorderMode = false,
  showOrderColumn = false,
  sortable = false,
  dsnStatus = null,
}: CompanyRowProps) {
  const navigate = useNavigate();
  const inGroup = isInMajiGroup(company, majiGroupId);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: company.id,
    disabled: !sortable,
  });

  const style = sortable
    ? {
        transform: CSS.Transform.toString(transform),
        transition,
      }
    : undefined;

  const goToCompany = () => navigate(`/super-admin/companies/${company.id}`);

  return (
    <TableRow
      ref={sortable ? setNodeRef : undefined}
      style={style}
      className={cn(isDragging && "opacity-60 bg-muted/40")}
    >
      {showOrderColumn ? (
        <TableCell className="w-12 text-center text-xs tabular-nums text-muted-foreground">
          #{orderIndex + 1}
        </TableCell>
      ) : null}
      {reorderMode ? (
        <TableCell className="w-10 px-2">
          {sortable ? (
            <button
              type="button"
              className="rounded-md p-1 text-muted-foreground hover:bg-muted cursor-grab active:cursor-grabbing touch-none"
              aria-label={`Déplacer ${company.company_name}`}
              {...attributes}
              {...listeners}
            >
              <GripVertical className="h-4 w-4" />
            </button>
          ) : null}
        </TableCell>
      ) : null}
      <TableCell className="cursor-pointer" onClick={goToCompany}>
        <div className="flex items-center gap-3">
          <Avatar className="h-8 w-8">
            {company.logo_url ? (
              <AvatarImage src={company.logo_url} alt={company.company_name} />
            ) : null}
            <AvatarFallback className="text-xs">
              {companyInitials(company.company_name)}
            </AvatarFallback>
          </Avatar>
          <div>
            <p className="font-medium">{company.company_name}</p>
            <p className="text-xs text-muted-foreground">{company.email || "—"}</p>
          </div>
        </div>
      </TableCell>
      <TableCell
        className="hidden md:table-cell text-muted-foreground cursor-pointer"
        onClick={goToCompany}
      >
        {company.siret || "—"}
      </TableCell>
      <TableCell>
        {inGroup ? (
          <Badge variant="secondary">Dans le groupe</Badge>
        ) : (
          <div className="flex flex-col gap-1">
            <Badge variant="outline" className="border-amber-500 text-amber-700">
              À rattacher
            </Badge>
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              disabled={assigningToGroup || !majiGroupId}
              onClick={() => onAssignToGroup(company.id)}
            >
              {assigningToGroup ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                `Rattacher à ${DEFAULT_PLATFORM_GROUP_NAME}`
              )}
            </Button>
          </div>
        )}
      </TableCell>
      <TableCell
        className="hidden sm:table-cell tabular-nums cursor-pointer"
        onClick={goToCompany}
      >
        {company.employees_count ?? 0}
      </TableCell>
      <TableCell
        className="hidden sm:table-cell tabular-nums cursor-pointer"
        onClick={goToCompany}
      >
        {company.users_count ?? 0}
      </TableCell>
      <TableCell onClick={goToCompany}>
        <Badge variant={company.is_active ? "default" : "secondary"}>
          {company.is_active ? "Actif" : "Inactif"}
        </Badge>
      </TableCell>
      <TableCell className="hidden md:table-cell cursor-pointer" onClick={goToCompany}>
        {dsnStatus ? (
          <Badge variant={dsnStatusVariant(dsnStatus)}>{dsnStatusLabel(dsnStatus)}</Badge>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell
        className="hidden lg:table-cell text-muted-foreground text-sm cursor-pointer"
        onClick={goToCompany}
      >
        {formatDate(company.created_at)}
      </TableCell>
      <TableCell>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <MoreHorizontal className="h-4 w-4" />
              <span className="sr-only">Actions</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={goToCompany}>Voir la fiche</DropdownMenuItem>
            <DropdownMenuItem
              onClick={() =>
                navigate(
                  `/super-admin/dsn-import?companyId=${company.id}&mode=monthly`,
                )
              }
            >
              <Plus className="mr-2 h-3.5 w-3.5" />
              Importer DSN
            </DropdownMenuItem>
            {!inGroup && majiGroupId ? (
              <DropdownMenuItem onClick={() => onAssignToGroup(company.id)}>
                Rattacher au groupe
              </DropdownMenuItem>
            ) : null}
            <DropdownMenuItem onClick={() => onToggleStatus(company)}>
              {company.is_active ? "Désactiver" : "Activer"}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-destructive focus:text-destructive"
              onClick={() => onDelete(company)}
            >
              Supprimer définitivement
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
  );
}

function StaticCompanyRow(props: Omit<CompanyRowProps, "sortable">) {
  return <CompanyRow {...props} sortable={false} />;
}

function SortableCompanyRow(props: Omit<CompanyRowProps, "sortable">) {
  return <CompanyRow {...props} sortable />;
}

export function CompaniesTable({
  companies,
  majiGroupId,
  assigningToGroup,
  onAssignToGroup,
  onToggleStatus,
  onDelete,
  emptyMessage = "Aucune entreprise.",
  reorderMode = false,
  showOrderColumn = false,
  savingOrder = false,
  onReorder,
}: CompaniesTableProps) {
  const { data: dsnSummary } = useQuery({
    queryKey: ['dsn-admin-late-summary'],
    queryFn: fetchDsnAdminLateSummary,
    staleTime: 60_000,
  });

  const dsnStatusByCompany = useMemo(() => {
    const map = new Map<string, string>();
    const rows = dsnSummary?.all_companies ?? dsnSummary?.companies ?? [];
    rows.forEach((c) => {
      map.set(c.company_id, c.status);
    });
    return map;
  }, [dsnSummary]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  const extraCols =
    (showOrderColumn ? 1 : 0) + (reorderMode ? 1 : 0);
  const colSpan = 9 + extraCols;

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id || !onReorder) return;
    const oldIndex = companies.findIndex((c) => c.id === active.id);
    const newIndex = companies.findIndex((c) => c.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = arrayMove(companies, oldIndex, newIndex);
    onReorder(reordered.map((c) => c.id));
  };

  const header = (
    <TableHeader className="sticky top-0 z-10 bg-background">
      <TableRow>
        {showOrderColumn ? <TableHead className="w-12 text-center">#</TableHead> : null}
        {reorderMode ? <TableHead className="w-10" aria-label="Déplacer" /> : null}
        <TableHead>Entreprise</TableHead>
        <TableHead className="hidden md:table-cell">SIRET</TableHead>
        <TableHead>Rattachement</TableHead>
        <TableHead className="hidden sm:table-cell">Employés</TableHead>
        <TableHead className="hidden sm:table-cell">Utilisateurs</TableHead>
        <TableHead>Statut</TableHead>
        <TableHead className="hidden md:table-cell">DSN</TableHead>
        <TableHead className="hidden lg:table-cell">Créée le</TableHead>
        <TableHead className="w-[50px]" />
      </TableRow>
    </TableHeader>
  );

  if (companies.length === 0) {
    return (
      <Table>
        {header}
        <TableBody>
          <TableRow>
            <TableCell colSpan={colSpan} className="py-10 text-center text-muted-foreground">
              {emptyMessage}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
  }

  if (reorderMode && onReorder) {
    return (
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <Table>
          {header}
          <TableBody>
            {savingOrder ? (
              <TableRow>
                <TableCell colSpan={colSpan} className="py-2 text-center text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Enregistrement de l&apos;ordre…
                  </span>
                </TableCell>
              </TableRow>
            ) : null}
            <SortableContext
              items={companies.map((c) => c.id)}
              strategy={verticalListSortingStrategy}
            >
              {companies.map((company, index) => (
                <SortableCompanyRow
                  key={company.id}
                  company={company}
                  orderIndex={index}
                  majiGroupId={majiGroupId}
                  assigningToGroup={assigningToGroup}
                  onAssignToGroup={onAssignToGroup}
                  onToggleStatus={onToggleStatus}
                  onDelete={onDelete}
                  reorderMode={reorderMode}
                  showOrderColumn={showOrderColumn}
                  dsnStatus={dsnStatusByCompany.get(company.id) ?? null}
                />
              ))}
            </SortableContext>
          </TableBody>
        </Table>
      </DndContext>
    );
  }

  return (
    <Table>
      {header}
      <TableBody>
        {companies.map((company, index) => (
          <StaticCompanyRow
            key={company.id}
            company={company}
            orderIndex={index}
            majiGroupId={majiGroupId}
            assigningToGroup={assigningToGroup}
            onAssignToGroup={onAssignToGroup}
            onToggleStatus={onToggleStatus}
            onDelete={onDelete}
            reorderMode={reorderMode}
            showOrderColumn={showOrderColumn}
            dsnStatus={dsnStatusByCompany.get(company.id) ?? null}
          />
        ))}
      </TableBody>
    </Table>
  );
}
