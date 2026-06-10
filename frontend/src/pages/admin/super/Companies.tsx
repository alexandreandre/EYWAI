// frontend/src/pages/super-admin/Companies.tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  activeStatusToApiParam,
  assignCompanyToGroup,
  deleteAdminCompanyPermanent,
  listAdminCompanies,
  listCompanyGroups,
  patchAdminCompanyStatus,
  reorderGroupCompanies,
} from "@/api/adminCompanies";
import { queryKeys } from "@/lib/queryKeys";
import { AdminPageHeader } from "@/features/admin/components/eywai/AdminPageHeader";
import { AdminStatCard } from "@/features/admin/components/eywai/AdminStatCard";
import { CreateCompanyDialog } from "@/pages/admin/eywai/companies/CreateCompanyDialog";
import { DeleteCompanyAlert } from "@/pages/admin/eywai/companies/DeleteCompanyAlert";
import { CompaniesTable } from "@/pages/admin/eywai/companies/CompaniesTable";
import type {
  ActiveStatusFilter,
  AdminCompany,
  AttachmentFilter,
  CompanySortMode,
} from "@/pages/admin/eywai/companies/types";
import {
  COMPANIES_LIST_LIMIT,
  sortAdminCompanies,
} from "@/pages/admin/eywai/companies/types";
import {
  DEFAULT_PLATFORM_GROUP_NAME,
  findDefaultGroupId,
} from "@/lib/adminGroup";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Building2,
  Plus,
  Users,
  UserX,
  AlertTriangle,
  Link2,
  Loader2,
  GripVertical,
} from "lucide-react";
import { log } from "@/lib/logger";

const SEARCH_DEBOUNCE_MS = 300;

export default function Companies() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<ActiveStatusFilter>("all");
  const [attachmentFilter, setAttachmentFilter] = useState<AttachmentFilter>("in_group");
  const [sortMode, setSortMode] = useState<CompanySortMode>("group_order");
  const [reorderMode, setReorderMode] = useState(false);
  const [savingOrder, setSavingOrder] = useState(false);
  const [orderOverrides, setOrderOverrides] = useState<Record<string, number>>({});

  const [majiGroupId, setMajiGroupId] = useState<string | null>(null);
  const [assigningToGroup, setAssigningToGroup] = useState(false);
  const [bulkAssigning, setBulkAssigning] = useState(false);

  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [companyToDelete, setCompanyToDelete] = useState<AdminCompany | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [companyToDeactivate, setCompanyToDeactivate] = useState<AdminCompany | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(searchInput.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const groupsQuery = useQuery({
    queryKey: ["admin", "company-groups"] as const,
    queryFn: listCompanyGroups,
  });

  const groups = groupsQuery.data ?? [];
  const majiGroupName =
    groups.find((g) => g.id === majiGroupId)?.group_name ?? DEFAULT_PLATFORM_GROUP_NAME;

  useEffect(() => {
    if (groups.length > 0) {
      setMajiGroupId(findDefaultGroupId(groups));
    }
  }, [groups]);

  const companiesQuery = useQuery({
    queryKey: [
      ...queryKeys.adminCompanies(),
      debouncedSearch,
      statusFilter,
    ] as const,
    queryFn: () =>
      listAdminCompanies({
        limit: COMPANIES_LIST_LIMIT,
        search: debouncedSearch || undefined,
        is_active: activeStatusToApiParam(statusFilter),
      }),
    placeholderData: (previous) => previous,
  });

  const companies = useMemo(() => {
    const base = companiesQuery.data ?? [];
    if (Object.keys(orderOverrides).length === 0) return base;
    return base.map((company) =>
      orderOverrides[company.id] != null
        ? { ...company, group_display_order: orderOverrides[company.id] }
        : company,
    );
  }, [companiesQuery.data, orderOverrides]);

  const loading = companiesQuery.isLoading && companies.length === 0;
  const loadError =
    companiesQuery.isError && companies.length === 0
      ? "Impossible de charger les entreprises."
      : null;

  const refreshCompanies = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.adminCompanies() });
  };

  const groupCompanies = useMemo(
    () => (majiGroupId ? companies.filter((c) => c.group_id === majiGroupId) : []),
    [companies, majiGroupId],
  );

  const orphanCompanies = useMemo(
    () => companies.filter((c) => !c.group_id),
    [companies],
  );

  const filteredCompanies = useMemo(() => {
    let list = companies;
    if (majiGroupId) {
      if (attachmentFilter === "in_group") {
        list = list.filter((c) => c.group_id === majiGroupId);
      } else if (attachmentFilter === "orphan") {
        list = list.filter((c) => !c.group_id);
      }
    }
    return list;
  }, [companies, majiGroupId, attachmentFilter]);

  const displayedCompanies = useMemo(
    () => sortAdminCompanies(filteredCompanies, sortMode),
    [filteredCompanies, sortMode],
  );

  const canReorder =
    attachmentFilter === "in_group" &&
    statusFilter === "all" &&
    debouncedSearch === "" &&
    Boolean(majiGroupId) &&
    groupCompanies.length > 1;

  useEffect(() => {
    if (!canReorder && reorderMode) {
      setReorderMode(false);
    }
  }, [canReorder, reorderMode]);

  useEffect(() => {
    if (attachmentFilter === "in_group" && sortMode !== "group_order" && !reorderMode) {
      return;
    }
    if (attachmentFilter !== "in_group" && sortMode === "group_order") {
      setSortMode("name");
    }
  }, [attachmentFilter, sortMode, reorderMode]);

  const assignCompanyToMajiGroup = async (companyId: string): Promise<boolean> => {
    if (!majiGroupId) {
      toast({
        title: "Groupe introuvable",
        description: `Le groupe ${DEFAULT_PLATFORM_GROUP_NAME} n'est pas configuré.`,
        variant: "destructive",
      });
      return false;
    }
    try {
      setAssigningToGroup(true);
      await assignCompanyToGroup(majiGroupId, companyId);
      toast({
        title: "Entreprise rattachée",
        description: `Ajoutée au groupe ${majiGroupName}.`,
      });
      return true;
    } catch (error: unknown) {
      const detail = (error as { response?: { data?: { detail?: string } } })?.response
        ?.data?.detail;
      toast({
        title: "Erreur",
        description:
          typeof detail === "string"
            ? detail
            : `Rattachement au groupe ${DEFAULT_PLATFORM_GROUP_NAME} impossible.`,
        variant: "destructive",
      });
      return false;
    } finally {
      setAssigningToGroup(false);
    }
  };

  const handleAssignFromTable = async (companyId: string) => {
    const ok = await assignCompanyToMajiGroup(companyId);
    if (ok) refreshCompanies();
  };

  const handleBulkAssignOrphans = async () => {
    if (!majiGroupId || orphanCompanies.length === 0) return;
    setBulkAssigning(true);
    let success = 0;
    for (const c of orphanCompanies) {
      try {
        await assignCompanyToGroup(majiGroupId, c.id);
        success += 1;
      } catch {
        /* continue */
      }
    }
    setBulkAssigning(false);
    toast({
      title: "Rattachement terminé",
      description: `${success} entreprise(s) rattachée(s) sur ${orphanCompanies.length}.`,
    });
    refreshCompanies();
  };

  const handleReorder = useCallback(
    async (orderedIds: string[]) => {
      if (!majiGroupId || !canReorder) return;

      if (orderedIds.length !== groupCompanies.length) {
        toast({
          title: "Erreur",
          description: "Impossible de mettre à jour l'ordre.",
          variant: "destructive",
        });
        return;
      }

      const previousOverrides = { ...orderOverrides };
      const optimistic: Record<string, number> = {};
      orderedIds.forEach((id, index) => {
        optimistic[id] = index + 1;
      });
      setOrderOverrides(optimistic);
      setSavingOrder(true);

      try {
        await reorderGroupCompanies(majiGroupId, orderedIds);
        toast({ title: "Ordre enregistré" });
        setOrderOverrides({});
        refreshCompanies();
      } catch (error: unknown) {
        setOrderOverrides(previousOverrides);
        const detail = (error as { response?: { data?: { detail?: string } } })?.response
          ?.data?.detail;
        toast({
          title: "Erreur",
          description:
            typeof detail === "string"
              ? detail
              : "Enregistrement de l'ordre impossible.",
          variant: "destructive",
        });
      } finally {
        setSavingOrder(false);
      }
    },
    [canReorder, groupCompanies.length, majiGroupId, orderOverrides, toast],
  );

  const confirmToggleStatus = async (company: AdminCompany) => {
    try {
      await patchAdminCompanyStatus(company.id, !company.is_active);
      toast({
        title: company.is_active ? "Entreprise désactivée" : "Entreprise activée",
      });
      refreshCompanies();
    } catch (error) {
      log.error("Erreur statut:", error);
      toast({
        title: "Erreur",
        description: "Modification du statut impossible.",
        variant: "destructive",
      });
    }
  };

  const handleToggleStatus = (company: AdminCompany) => {
    if (company.is_active) {
      setCompanyToDeactivate(company);
    } else {
      void confirmToggleStatus(company);
    }
  };

  const handleDeleteCompanyPermanent = async () => {
    if (!companyToDelete) return;
    try {
      setDeleting(true);
      const response = await deleteAdminCompanyPermanent(companyToDelete.id);
      toast({
        title: "Entreprise supprimée",
        description: response.message ?? "Suppression définitive effectuée.",
      });
      setCompanyToDelete(null);
      refreshCompanies();
    } catch (error: unknown) {
      const detail = (error as { response?: { data?: { detail?: string } } })?.response
        ?.data?.detail;
      toast({
        title: "Erreur",
        description: typeof detail === "string" ? detail : "Suppression impossible.",
        variant: "destructive",
      });
    } finally {
      setDeleting(false);
    }
  };

  const headerDescription = useMemo(() => {
    const base = `Les nouvelles entreprises sont automatiquement rattachées au groupe ${majiGroupName}.`;
    if (orphanCompanies.length > 0) {
      return `${base} ${orphanCompanies.length} entreprise(s) à rattacher.`;
    }
    return base;
  }, [majiGroupName, orphanCompanies.length]);

  const emptyMessage = useMemo(() => {
    if (attachmentFilter === "orphan") return "Aucune entreprise à rattacher.";
    if (debouncedSearch) return "Aucune entreprise ne correspond à la recherche.";
    if (statusFilter === "active") return "Aucune entreprise active dans ce périmètre.";
    if (statusFilter === "inactive") return "Aucune entreprise inactive dans ce périmètre.";
    return `Aucune entreprise dans le groupe ${majiGroupName}.`;
  }, [attachmentFilter, debouncedSearch, majiGroupName, statusFilter]);

  const showOrderColumn =
    sortMode === "group_order" && attachmentFilter === "in_group";

  if (loading && companies.length === 0) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-72" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (loadError && companies.length === 0) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Erreur</AlertTitle>
        <AlertDescription className="flex flex-col gap-3">
          {loadError}
          <Button variant="outline" size="sm" onClick={() => void companiesQuery.refetch()}>
            Réessayer
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Entreprises du groupe"
        description={headerDescription}
        actions={
          <>
            {majiGroupId ? (
              <Button variant="outline" onClick={() => navigate(`/super-admin/groups/${majiGroupId}`)}>
                <Link2 className="mr-2 h-4 w-4" />
                Fiche groupe
              </Button>
            ) : null}
            <Button onClick={() => setShowCreateDialog(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Nouvelle entreprise
            </Button>
          </>
        }
      />

      {orphanCompanies.length > 0 ? (
        <Alert variant="default" className="border-amber-200 bg-amber-50 dark:bg-amber-950/20">
          <AlertTriangle className="h-4 w-4 text-amber-600" />
          <AlertTitle>Entreprises hors groupe</AlertTitle>
          <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span>
              {orphanCompanies.length} entreprise(s) ne sont pas encore dans le groupe{" "}
              {majiGroupName}.
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={bulkAssigning || !majiGroupId}
              onClick={() => void handleBulkAssignOrphans()}
            >
              {bulkAssigning ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Rattacher toutes au groupe
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <AdminStatCard
          title="Dans le groupe"
          value={groupCompanies.length}
          subtitle={majiGroupName}
          icon={Building2}
        />
        <AdminStatCard
          title="Actives"
          value={groupCompanies.filter((c) => c.is_active).length}
          subtitle="Périmètre groupe"
          icon={Users}
          variant="success"
        />
        <AdminStatCard
          title="Inactives"
          value={groupCompanies.filter((c) => !c.is_active).length}
          subtitle="Périmètre groupe"
          icon={UserX}
        />
        <AdminStatCard
          title="Hors groupe"
          value={orphanCompanies.length}
          subtitle="À rattacher"
          icon={AlertTriangle}
          variant={orphanCompanies.length > 0 ? "warning" : "default"}
          onClick={
            orphanCompanies.length > 0
              ? () => setAttachmentFilter("orphan")
              : undefined
          }
        />
      </div>

      <Card>
        <CardContent className="grid gap-4 pt-6 md:grid-cols-2 xl:grid-cols-12">
          <div className="space-y-2 xl:col-span-4">
            <Label htmlFor="company-search">Rechercher une entreprise</Label>
            <Input
              id="company-search"
              placeholder="Nom, SIRET, e-mail…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
          </div>
          <div className="space-y-2 xl:col-span-3">
            <Label>Trier par</Label>
            <Select
              value={sortMode}
              onValueChange={(v) => setSortMode(v as CompanySortMode)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="group_order">Ordre personnalisé</SelectItem>
                <SelectItem value="name">Nom (A → Z)</SelectItem>
                <SelectItem value="created_at">Plus récentes</SelectItem>
                <SelectItem value="employees">Effectif</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2 xl:col-span-2">
            <Label>Statut</Label>
            <Select
              value={statusFilter}
              onValueChange={(v) => setStatusFilter(v as ActiveStatusFilter)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Toutes</SelectItem>
                <SelectItem value="active">Actives</SelectItem>
                <SelectItem value="inactive">Inactives</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2 xl:col-span-3">
            <Label>Rattachement</Label>
            <Select
              value={attachmentFilter}
              onValueChange={(v) => setAttachmentFilter(v as AttachmentFilter)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Toutes</SelectItem>
                <SelectItem value="in_group">Dans le groupe</SelectItem>
                <SelectItem value="orphan">À rattacher</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="flex flex-col gap-3 border-b px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-medium">{majiGroupName}</p>
              <p className="text-xs text-muted-foreground">
                {displayedCompanies.length} ligne(s) affichée(s)
                {companies.length >= COMPANIES_LIST_LIMIT
                  ? ` · limite ${COMPANIES_LIST_LIMIT} chargée(s)`
                  : ""}
              </p>
            </div>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-flex">
                    <Button
                      variant={reorderMode ? "default" : "outline"}
                      size="sm"
                      disabled={!canReorder}
                      onClick={() => {
                        setReorderMode((v) => {
                          const next = !v;
                          if (next) setSortMode("group_order");
                          return next;
                        });
                      }}
                    >
                      <GripVertical className="mr-2 h-4 w-4" />
                      {reorderMode ? "Terminer" : "Réorganiser"}
                    </Button>
                  </span>
                </TooltipTrigger>
                {!canReorder ? (
                  <TooltipContent>
                    Disponible avec le filtre « Dans le groupe », sans recherche ni filtre de
                    statut.
                  </TooltipContent>
                ) : null}
              </Tooltip>
            </TooltipProvider>
          </div>
          <div className="max-h-[min(70vh,900px)] overflow-x-auto overflow-y-auto">
            <CompaniesTable
              companies={displayedCompanies}
              majiGroupId={majiGroupId}
              assigningToGroup={assigningToGroup}
              onAssignToGroup={(id) => void handleAssignFromTable(id)}
              onToggleStatus={handleToggleStatus}
              onDelete={setCompanyToDelete}
              emptyMessage={emptyMessage}
              reorderMode={reorderMode && canReorder}
              showOrderColumn={showOrderColumn || (reorderMode && canReorder)}
              savingOrder={savingOrder}
              onReorder={(ids) => void handleReorder(ids)}
            />
          </div>
        </CardContent>
      </Card>

      <CreateCompanyDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        majiGroupId={majiGroupId}
        onCreated={refreshCompanies}
        onAssignToGroup={assignCompanyToMajiGroup}
        toast={toast}
      />

      <DeleteCompanyAlert
        company={companyToDelete}
        open={Boolean(companyToDelete)}
        onOpenChange={(open) => !open && setCompanyToDelete(null)}
        deleting={deleting}
        onConfirm={() => void handleDeleteCompanyPermanent()}
      />

      <AlertDialog
        open={Boolean(companyToDeactivate)}
        onOpenChange={(open) => !open && setCompanyToDeactivate(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Désactiver l&apos;entreprise ?</AlertDialogTitle>
            <AlertDialogDescription>
              {companyToDeactivate?.company_name} ne sera plus accessible aux utilisateurs
              tant qu&apos;elle reste inactive.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (companyToDeactivate) {
                  void confirmToggleStatus(companyToDeactivate);
                  setCompanyToDeactivate(null);
                }
              }}
            >
              Désactiver
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
