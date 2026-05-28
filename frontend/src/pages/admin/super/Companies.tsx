// frontend/src/pages/super-admin/Companies.tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/api/apiClient";
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
} from "@/pages/admin/eywai/companies/types";
import { COMPANIES_LIST_LIMIT } from "@/pages/admin/eywai/companies/types";
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
  Building2,
  Plus,
  Users,
  UserX,
  AlertTriangle,
  Link2,
  Loader2,
} from "lucide-react";
import { log } from "@/lib/logger";

interface CompanyGroup {
  id: string;
  group_name: string;
}

export default function Companies() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [apiSearch, setApiSearch] = useState("");
  const [localSearch, setLocalSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<ActiveStatusFilter>("all");
  const [attachmentFilter, setAttachmentFilter] = useState<AttachmentFilter>("all");

  const [groups, setGroups] = useState<CompanyGroup[]>([]);
  const [majiGroupId, setMajiGroupId] = useState<string | null>(null);
  const [assigningToGroup, setAssigningToGroup] = useState(false);
  const [bulkAssigning, setBulkAssigning] = useState(false);

  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [companyToDelete, setCompanyToDelete] = useState<AdminCompany | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [companyToDeactivate, setCompanyToDeactivate] = useState<AdminCompany | null>(null);

  const majiGroupName =
    groups.find((g) => g.id === majiGroupId)?.group_name ?? DEFAULT_PLATFORM_GROUP_NAME;

  const loadGroups = useCallback(async () => {
    try {
      const response = await apiClient.get("/api/company-groups/");
      const list: CompanyGroup[] = response.data ?? [];
      setGroups(list);
      setMajiGroupId(findDefaultGroupId(list));
    } catch (error) {
      log.error("Erreur chargement groupes:", error);
    }
  }, []);

  const companiesQuery = useQuery({
    queryKey: [...queryKeys.adminCompanies(), apiSearch, statusFilter] as const,
    queryFn: async () => {
      const params: Record<string, string | number | boolean> = {
        limit: COMPANIES_LIST_LIMIT,
      };
      if (apiSearch.trim()) params.search = apiSearch.trim();
      if (statusFilter === "active") params.is_active = true;
      if (statusFilter === "inactive") params.is_active = false;
      const response = await apiClient.get("/api/super-admin/companies", { params });
      return (response.data.companies ?? []) as AdminCompany[];
    },
    placeholderData: (previous) => previous,
  });

  const companies = companiesQuery.data ?? [];
  const loading = companiesQuery.isLoading && companies.length === 0;
  const loadError =
    companiesQuery.isError && companies.length === 0
      ? "Impossible de charger les entreprises."
      : null;

  const refreshCompanies = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.adminCompanies() });
  };

  useEffect(() => {
    void loadGroups();
  }, [loadGroups]);

  const groupCompanies = useMemo(
    () => (majiGroupId ? companies.filter((c) => c.group_id === majiGroupId) : []),
    [companies, majiGroupId],
  );

  const orphanCompanies = useMemo(
    () => companies.filter((c) => !c.group_id),
    [companies],
  );

  const displayedCompanies = useMemo(() => {
    let list = companies;
    if (majiGroupId) {
      if (attachmentFilter === "in_group") {
        list = list.filter((c) => c.group_id === majiGroupId);
      } else if (attachmentFilter === "orphan") {
        list = list.filter((c) => !c.group_id);
      }
    }
    const q = localSearch.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (c) =>
          c.company_name.toLowerCase().includes(q) ||
          (c.siret?.toLowerCase().includes(q) ?? false) ||
          (c.email?.toLowerCase().includes(q) ?? false),
      );
    }
    return list;
  }, [companies, majiGroupId, attachmentFilter, localSearch]);

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
      await apiClient.post(`/api/company-groups/${majiGroupId}/companies/${companyId}`);
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
        await apiClient.post(`/api/company-groups/${majiGroupId}/companies/${c.id}`);
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

  const confirmToggleStatus = async (company: AdminCompany) => {
    try {
      await apiClient.patch(`/api/super-admin/companies/${company.id}`, {
        is_active: !company.is_active,
      });
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
      const response = await apiClient.delete(
        `/api/super-admin/companies/${companyToDelete.id}/permanent`,
      );
      toast({
        title: "Entreprise supprimée",
        description: response.data.message ?? "Suppression définitive effectuée.",
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
        <CardContent className="grid gap-4 pt-6 lg:grid-cols-12">
          <div className="space-y-2 lg:col-span-4">
            <Label htmlFor="api-search">Recherche serveur</Label>
            <Input
              id="api-search"
              placeholder="Nom, SIRET, e-mail…"
              value={apiSearch}
              onChange={(e) => setApiSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void companiesQuery.refetch()}
            />
          </div>
          <div className="space-y-2 lg:col-span-3">
            <Label htmlFor="local-search">Filtrer la liste</Label>
            <Input
              id="local-search"
              placeholder="Filtre instantané…"
              value={localSearch}
              onChange={(e) => setLocalSearch(e.target.value)}
            />
          </div>
          <div className="space-y-2 lg:col-span-2">
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
          <div className="space-y-2 lg:col-span-2">
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
          <div className="flex items-end lg:col-span-1">
            <Button className="w-full" onClick={() => void companiesQuery.refetch()}>
              Actualiser
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="border-b px-4 py-3">
            <p className="text-sm font-medium">{majiGroupName}</p>
            <p className="text-xs text-muted-foreground">
              {displayedCompanies.length} ligne(s) affichée(s)
              {companies.length >= COMPANIES_LIST_LIMIT
                ? ` · limite ${COMPANIES_LIST_LIMIT} chargée(s)`
                : ""}
            </p>
          </div>
          <div className="overflow-x-auto">
            <CompaniesTable
              companies={displayedCompanies}
              majiGroupId={majiGroupId}
              assigningToGroup={assigningToGroup}
              onAssignToGroup={(id) => void handleAssignFromTable(id)}
              onToggleStatus={handleToggleStatus}
              onDelete={setCompanyToDelete}
              emptyMessage={
                attachmentFilter === "orphan"
                  ? "Aucune entreprise à rattacher."
                  : `Aucune entreprise dans le groupe ${majiGroupName}.`
              }
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
