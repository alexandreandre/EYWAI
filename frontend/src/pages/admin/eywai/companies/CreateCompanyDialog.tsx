import { useState } from "react";
import apiClient from "@/api/apiClient";
import { LogoUploader } from "@/components/LogoUploader";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2 } from "lucide-react";
import { DEFAULT_PLATFORM_GROUP_NAME } from "@/lib/adminGroup";
import { log } from "@/lib/logger";

type CreateCompanyDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  majiGroupId: string | null;
  onCreated: () => void;
  onAssignToGroup: (companyId: string) => Promise<boolean>;
  toast: (opts: {
    title: string;
    description?: string;
    variant?: "default" | "destructive";
  }) => void;
};

const initialForm = {
  company_name: "",
  siret: "",
  email: "",
  phone: "",
  logo_url: null as string | null,
  logo_scale: 1.0,
  admin_email: "",
  admin_password: "",
  admin_first_name: "",
  admin_last_name: "",
};

export function CreateCompanyDialog({
  open,
  onOpenChange,
  majiGroupId,
  onCreated,
  onAssignToGroup,
  toast,
}: CreateCompanyDialogProps) {
  const [creating, setCreating] = useState(false);
  const [createWithAdmin, setCreateWithAdmin] = useState(false);
  const [formData, setFormData] = useState(initialForm);
  const [logoFile, setLogoFile] = useState<File | null>(null);

  const reset = () => {
    setFormData(initialForm);
    setLogoFile(null);
    setCreateWithAdmin(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setCreating(true);
      const dataToSend = createWithAdmin
        ? {
            company_name: formData.company_name,
            siret: formData.siret || undefined,
            email: formData.email || undefined,
            phone: formData.phone || undefined,
            logo_scale: formData.logo_scale,
            admin_email: formData.admin_email,
            admin_password: formData.admin_password,
            admin_first_name: formData.admin_first_name,
            admin_last_name: formData.admin_last_name,
          }
        : {
            company_name: formData.company_name,
            siret: formData.siret || undefined,
            email: formData.email || undefined,
            phone: formData.phone || undefined,
            logo_scale: formData.logo_scale,
          };

      const response = await apiClient.post("/api/super-admin/companies", dataToSend);
      const createdCompany = response.data.company;

      if (createdCompany?.id && !createdCompany.group_id && majiGroupId) {
        await onAssignToGroup(createdCompany.id);
      }

      if (logoFile && createdCompany?.id) {
        try {
          const formDataUpload = new FormData();
          formDataUpload.append("file", logoFile);
          formDataUpload.append("entity_type", "company");
          formDataUpload.append("entity_id", createdCompany.id);
          await apiClient.post("/api/uploads/logo", formDataUpload, {
            headers: { "Content-Type": "multipart/form-data" },
          });
        } catch (uploadError) {
          log.error("Upload logo:", uploadError);
          toast({
            title: "Entreprise créée",
            description: "Le logo n'a pas pu être envoyé.",
            variant: "default",
          });
        }
      }

      toast({
        title: "Entreprise créée",
        description: `Rattachée au groupe ${DEFAULT_PLATFORM_GROUP_NAME}.`,
      });
      reset();
      onOpenChange(false);
      onCreated();
    } catch (error: unknown) {
      const detail = (error as { response?: { data?: { detail?: string } } })?.response
        ?.data?.detail;
      toast({
        title: "Erreur",
        description:
          typeof detail === "string" ? detail : "Création impossible.",
        variant: "destructive",
      });
    } finally {
      setCreating(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) reset();
        onOpenChange(o);
      }}
    >
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nouvelle entreprise</DialogTitle>
          <DialogDescription>
            Cette entreprise sera rattachée au groupe {DEFAULT_PLATFORM_GROUP_NAME}.
          </DialogDescription>
        </DialogHeader>

        <Alert>
          <AlertDescription>
            Le rattachement au groupe est automatique à la création.
          </AlertDescription>
        </Alert>

        <form onSubmit={handleSubmit} className="space-y-6">
          <LogoUploader
            currentLogoUrl={formData.logo_url}
            currentLogoScale={formData.logo_scale}
            entityType="company"
            onLogoChange={(logoUrl) => setFormData({ ...formData, logo_url: logoUrl })}
            onFileChange={(file) => setLogoFile(file)}
            onScaleChange={(scale) => setFormData({ ...formData, logo_scale: scale })}
            size="lg"
          />

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="company_name">Nom de l&apos;entreprise *</Label>
              <Input
                id="company_name"
                required
                disabled={creating}
                value={formData.company_name}
                onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="siret">SIRET</Label>
              <Input
                id="siret"
                disabled={creating}
                value={formData.siret}
                onChange={(e) => setFormData({ ...formData, siret: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">E-mail entreprise</Label>
              <Input
                id="email"
                type="email"
                disabled={creating}
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="phone">Téléphone</Label>
              <Input
                id="phone"
                type="tel"
                disabled={creating}
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              />
            </div>
          </div>

          <div className="space-y-4 border-t pt-4">
            <div className="flex items-center justify-between">
              <Label className="text-base font-semibold">Administrateur</Label>
              <div className="flex items-center gap-2">
                <Checkbox
                  id="create_with_admin"
                  checked={createWithAdmin}
                  disabled={creating}
                  onCheckedChange={(v) => setCreateWithAdmin(v === true)}
                />
                <Label htmlFor="create_with_admin" className="font-normal">
                  Créer maintenant
                </Label>
              </div>
            </div>
            {createWithAdmin ? (
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Prénom *</Label>
                  <Input
                    required={createWithAdmin}
                    disabled={creating}
                    value={formData.admin_first_name}
                    onChange={(e) =>
                      setFormData({ ...formData, admin_first_name: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Nom *</Label>
                  <Input
                    required={createWithAdmin}
                    disabled={creating}
                    value={formData.admin_last_name}
                    onChange={(e) =>
                      setFormData({ ...formData, admin_last_name: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>E-mail *</Label>
                  <Input
                    type="email"
                    required={createWithAdmin}
                    disabled={creating}
                    value={formData.admin_email}
                    onChange={(e) =>
                      setFormData({ ...formData, admin_email: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Mot de passe *</Label>
                  <Input
                    type="password"
                    required={createWithAdmin}
                    minLength={6}
                    disabled={creating}
                    value={formData.admin_password}
                    onChange={(e) =>
                      setFormData({ ...formData, admin_password: e.target.value })
                    }
                  />
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground italic">
                L&apos;administrateur pourra être ajouté ultérieurement.
              </p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={creating}
              onClick={() => onOpenChange(false)}
            >
              Annuler
            </Button>
            <Button type="submit" disabled={creating}>
              {creating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Création…
                </>
              ) : (
                "Créer l'entreprise"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
