import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Plus, UserPlus } from "lucide-react";
import apiClient from "@/api/apiClient";
import {
  getRoleTemplates,
  updateUserPermissions,
  buildPermissionGrantsPayload,
  syncPermissionGrants,
  type PermissionGrantInput,
  type RoleTemplateDetail,
} from "@/api/permissions";
import { PermissionsMatrix } from "@/components/PermissionsMatrix";
import { PermissionScopeEditor } from "@/features/access-control";
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { AdminPageHeader } from "@/features/admin/components/eywai/AdminPageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const RH_ROLES = ["admin", "rh", "collaborateur_rh", "custom"] as const;

const PROFILE_PRESETS: Array<{
  role: (typeof RH_ROLES)[number];
  title: string;
  description: string;
}> = [
  {
    role: "admin",
    title: "Administrateur entreprise",
    description: "Gestion complète de l'entreprise, paramètres et utilisateurs.",
  },
  {
    role: "rh",
    title: "Responsable RH",
    description: "Paie, absences, dossiers salariés et pilotage RH.",
  },
  {
    role: "collaborateur_rh",
    title: "Collaborateur RH",
    description: "Saisie et suivi opérationnel, droits limités selon le profil.",
  },
  {
    role: "custom",
    title: "Profil sur mesure",
    description: "Droits finement ajustés via la matrice de permissions.",
  },
];

const ROLE_LABELS: Record<string, string> = {
  admin: "Administrateur",
  rh: "RH",
  collaborateur_rh: "Collaborateur RH",
  custom: "Personnalisé",
};

type CompanyRow = { id: string; company_name: string };

type PlatformUser = {
  id: string;
  first_name: string;
  last_name: string;
  role: string;
  company_id: string;
  company_name?: string;
  email?: string;
};

export default function AccessRH() {
  const { toast } = useToast();
  const [selectedCompanyId, setSelectedCompanyId] = useState("");
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState(0);
  const [form, setForm] = useState({
    email: "",
    password: "",
    first_name: "",
    last_name: "",
    company_id: "",
    role: "rh" as (typeof RH_ROLES)[number],
  });
  const [customPermissions, setCustomPermissions] = useState<string[]>([]);
  const [customGrants, setCustomGrants] = useState<PermissionGrantInput[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const { data: companies = [], isLoading: companiesLoading } = useQuery({
    queryKey: ["admin", "companies-list"],
    queryFn: async () => {
      const res = await apiClient.get<{ companies: CompanyRow[] }>("/api/super-admin/companies", {
        params: { limit: 200 },
      });
      return res.data.companies ?? [];
    },
  });

  const { data: users = [], isLoading: usersLoading, refetch: refetchUsers } = useQuery({
    queryKey: ["admin", "rh-users"],
    queryFn: async () => {
      const res = await apiClient.get<{ users: PlatformUser[] }>("/api/super-admin/users", {
        params: { limit: 200 },
      });
      return (res.data.users ?? []).filter((u) => RH_ROLES.includes(u.role as (typeof RH_ROLES)[number]));
    },
  });

  const { data: templates = [], isLoading: templatesLoading } = useQuery({
    queryKey: ["admin", "role-templates", selectedCompanyId],
    queryFn: () => getRoleTemplates(selectedCompanyId || undefined, undefined, true),
    enabled: Boolean(selectedCompanyId),
  });

  useEffect(() => {
    if (companies.length && !selectedCompanyId) {
      setSelectedCompanyId(companies[0].id);
    }
  }, [companies, selectedCompanyId]);

  const resetWizard = () => {
    setWizardStep(0);
    setForm({
      email: "",
      password: "",
      first_name: "",
      last_name: "",
      company_id: selectedCompanyId || companies[0]?.id || "",
      role: "rh",
    });
    setCustomPermissions([]);
    setCustomGrants([]);
  };

  const openWizard = () => {
    resetWizard();
    setWizardOpen(true);
  };

  const submitCreateUser = async () => {
    const companyId = form.company_id || selectedCompanyId;
    if (!companyId) {
      toast({ title: "Sélectionnez une entreprise", variant: "destructive" });
      return;
    }
    setSubmitting(true);
    try {
      const { data: createRes } = await apiClient.post<{
        user?: { id?: string };
      }>(`/api/super-admin/companies/${companyId}/users`, {
        email: form.email,
        password: form.password,
        first_name: form.first_name,
        last_name: form.last_name,
        role: form.role,
      });
      const createdId = createRes?.user?.id;
      if (form.role === "custom" && customPermissions.length > 0) {
        if (!createdId) {
          toast({
            title: "Permissions non enregistrées",
            description:
              "L'utilisateur a été créé mais son identifiant est manquant pour appliquer les droits.",
            variant: "destructive",
          });
        } else {
          const grantsPayload = buildPermissionGrantsPayload(customPermissions, customGrants);
          await updateUserPermissions(createdId, companyId, customPermissions, grantsPayload);
        }
      }
      toast({ title: "Utilisateur RH créé" });
      setWizardOpen(false);
      void refetchUsers();
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast({
        title: "Erreur",
        description: typeof detail === "string" ? detail : "Création impossible",
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Profils & droits RH"
        description="Créez des accès RH compréhensibles et gérez les modèles de rôles par entreprise."
        actions={
          <Button onClick={openWizard}>
            <UserPlus className="mr-2 h-4 w-4" />
            Inviter un utilisateur RH
          </Button>
        }
      />

      <Tabs defaultValue="users">
        <TabsList>
          <TabsTrigger value="users">Utilisateurs RH</TabsTrigger>
          <TabsTrigger value="templates">Modèles de rôles</TabsTrigger>
          <TabsTrigger value="matrix">Matrice (lecture)</TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Utilisateurs avec accès RH</CardTitle>
              <CardDescription>
                Administrateurs, RH et collaborateurs RH sur l&apos;ensemble de la plateforme.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {usersLoading ? (
                <SharkFinLoader label="Chargement des utilisateurs…" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Nom</TableHead>
                      <TableHead>E-mail</TableHead>
                      <TableHead>Profil</TableHead>
                      <TableHead>Entreprise</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((u) => (
                      <TableRow key={u.id}>
                        <TableCell>
                          {[u.first_name, u.last_name].filter(Boolean).join(" ") || "—"}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {u.email ?? "—"}
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary">{ROLE_LABELS[u.role] ?? u.role}</Badge>
                        </TableCell>
                        <TableCell>{u.company_name ?? u.company_id.slice(0, 8)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="templates" className="mt-4 space-y-4">
          <div className="flex max-w-md items-end gap-3">
            <div className="flex-1 space-y-2">
              <Label>Entreprise</Label>
              <Select value={selectedCompanyId} onValueChange={setSelectedCompanyId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choisir…" />
                </SelectTrigger>
                <SelectContent>
                  {companies.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.company_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <Card>
            <CardContent className="pt-6">
              {templatesLoading || companiesLoading || !selectedCompanyId ? (
                <SharkFinLoader label="Chargement des modèles…" />
              ) : templates.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Aucun modèle pour cette entreprise. Créez-en depuis l&apos;application RH ou via un
                  profil personnalisé.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Nom</TableHead>
                      <TableHead>Rôle de base</TableHead>
                      <TableHead>Permissions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {templates.map((t: RoleTemplateDetail) => (
                      <TableRow key={t.id}>
                        <TableCell className="font-medium">{t.name}</TableCell>
                        <TableCell>{ROLE_LABELS[t.base_role] ?? t.base_role}</TableCell>
                        <TableCell>{t.permissions_count ?? 0}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="matrix" className="mt-4 space-y-4">
          <div className="max-w-md space-y-2">
            <Label>Entreprise pour la matrice</Label>
            <Select value={selectedCompanyId} onValueChange={setSelectedCompanyId}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {companies.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.company_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {selectedCompanyId ? (
            <Card>
              <CardContent className="pt-6">
                <PermissionsMatrix
                  companyId={selectedCompanyId}
                  selectedPermissions={[]}
                  onPermissionsChange={() => {}}
                  disabled
                />
              </CardContent>
            </Card>
          ) : null}
        </TabsContent>
      </Tabs>

      <Dialog open={wizardOpen} onOpenChange={setWizardOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Nouvel utilisateur RH — étape {wizardStep + 1}/3</DialogTitle>
            <DialogDescription>
              {wizardStep === 0 && "Identité et rattachement entreprise"}
              {wizardStep === 1 && "Choisissez un profil métier"}
              {wizardStep === 2 && "Ajustement des droits (profil personnalisé)"}
            </DialogDescription>
          </DialogHeader>

          {wizardStep === 0 && (
            <div className="grid gap-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label>Prénom</Label>
                  <Input
                    value={form.first_name}
                    onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Nom</Label>
                  <Input
                    value={form.last_name}
                    onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>E-mail</Label>
                <Input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Mot de passe temporaire</Label>
                <Input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Entreprise</Label>
                <Select
                  value={form.company_id || selectedCompanyId}
                  onValueChange={(v) => setForm({ ...form, company_id: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {companies.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.company_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {wizardStep === 1 && (
            <div className="grid gap-2">
              {PROFILE_PRESETS.map((p) => (
                <button
                  key={p.role}
                  type="button"
                  className={cn(
                    "rounded-lg border p-3 text-left transition-colors hover:bg-muted/50",
                    form.role === p.role && "border-primary ring-1 ring-primary",
                  )}
                  onClick={() => setForm({ ...form, role: p.role })}
                >
                  <p className="font-medium">{p.title}</p>
                  <p className="text-xs text-muted-foreground">{p.description}</p>
                </button>
              ))}
            </div>
          )}

          {wizardStep === 2 && form.role === "custom" && form.company_id && (
            <div className="space-y-4">
              <PermissionsMatrix
                companyId={form.company_id || selectedCompanyId}
                selectedPermissions={customPermissions}
                onPermissionsChange={(permissions) => {
                  setCustomPermissions(permissions);
                  setCustomGrants((current) => syncPermissionGrants(permissions, current));
                }}
              />
              <PermissionScopeEditor
                companyId={form.company_id || selectedCompanyId}
                selectedPermissionIds={customPermissions}
                grants={customGrants}
                onGrantsChange={setCustomGrants}
              />
            </div>
          )}
          {wizardStep === 2 && form.role !== "custom" && (
            <p className="text-sm text-muted-foreground">
              Le profil « {ROLE_LABELS[form.role]} » utilise les droits standards. Validez pour créer le
              compte.
            </p>
          )}

          <DialogFooter className="gap-2">
            {wizardStep > 0 ? (
              <Button variant="outline" onClick={() => setWizardStep((s) => s - 1)}>
                Retour
              </Button>
            ) : null}
            {wizardStep < 2 ? (
              <Button onClick={() => setWizardStep((s) => s + 1)}>
                Suivant
              </Button>
            ) : (
              <Button onClick={() => void submitCreateUser()} disabled={submitting}>
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                <span className="ml-2">Créer</span>
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
