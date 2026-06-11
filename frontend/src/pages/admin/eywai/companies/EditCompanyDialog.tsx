import { useEffect, useState } from "react";
import type { AdminCompanyDetails, AdminCompanyUpdate } from "@/api/adminCompanies";
import { patchAdminCompany } from "@/api/adminCompanies";
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
import { showErrorToast } from "@/lib/errorMessages";
import { Building2, Loader2, MapPin, PenLine } from "lucide-react";

type EditCompanyDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  company: AdminCompanyDetails;
  onSaved: (company: AdminCompanyDetails) => void;
  toast: (opts: {
    title: string;
    description?: string;
    variant?: "default" | "destructive";
  }) => void;
};

function companyToForm(company: AdminCompanyDetails): AdminCompanyUpdate {
  return {
    company_name: company.company_name ?? "",
    raison_sociale: company.raison_sociale ?? "",
    legal_form: company.legal_form ?? "",
    siren: company.siren ?? "",
    siret: company.siret ?? "",
    code_naf: company.code_naf ?? company.naf_ape ?? "",
    urssaf_number: company.urssaf_number ?? "",
    adresse_rue: company.adresse_rue ?? "",
    adresse_code_postal: company.adresse_code_postal ?? "",
    adresse_ville: company.adresse_ville ?? "",
    phone: company.phone ?? "",
    email: company.email ?? "",
    website: company.website ?? "",
    nom_signataire_rh: company.nom_signataire_rh ?? "",
    qualite_signataire_rh: company.qualite_signataire_rh ?? "",
  };
}

function FormSection({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof Building2;
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border/80 bg-muted/20 p-4 sm:p-5">
      <div className="mb-4 flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-4 w-4" aria-hidden />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
          {description ? (
            <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
          ) : null}
        </div>
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  );
}

export function EditCompanyDialog({
  open,
  onOpenChange,
  company,
  onSaved,
  toast,
}: EditCompanyDialogProps) {
  const [form, setForm] = useState<AdminCompanyUpdate>(() => companyToForm(company));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(companyToForm(company));
    }
  }, [open, company]);

  const updateField = <K extends keyof AdminCompanyUpdate>(
    key: K,
    value: AdminCompanyUpdate[K],
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedName = form.company_name?.trim();
    if (!trimmedName) {
      toast({
        title: "Nom requis",
        description: "Le nom de l'entreprise ne peut pas être vide.",
        variant: "destructive",
      });
      return;
    }

    const payload: AdminCompanyUpdate = {
      ...form,
      company_name: trimmedName,
      raison_sociale: form.raison_sociale?.trim() || null,
      legal_form: form.legal_form?.trim() || null,
      siren: form.siren?.trim() || null,
      siret: form.siret?.trim() || null,
      code_naf: form.code_naf?.trim() || null,
      urssaf_number: form.urssaf_number?.trim() || null,
      adresse_rue: form.adresse_rue?.trim() || null,
      adresse_code_postal: form.adresse_code_postal?.trim() || null,
      adresse_ville: form.adresse_ville?.trim() || null,
      phone: form.phone?.trim() || null,
      email: form.email?.trim() || null,
      website: form.website?.trim() || null,
      nom_signataire_rh: form.nom_signataire_rh?.trim() || null,
      qualite_signataire_rh: form.qualite_signataire_rh?.trim() || null,
    };

    try {
      setSaving(true);
      const updated = await patchAdminCompany(company.id, payload);
      toast({
        title: "Entreprise mise à jour",
        description: "Les informations ont été enregistrées.",
      });
      onSaved({ ...company, ...updated, stats: company.stats });
      onOpenChange(false);
    } catch (error: unknown) {
      showErrorToast(error, {
        title: "Enregistrement impossible",
        fallback: "Les modifications n'ont pas pu être enregistrées.",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl gap-0 overflow-hidden p-0">
        <DialogHeader className="space-y-3 border-b bg-gradient-to-br from-primary/5 via-background to-background px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
              <PenLine className="h-5 w-5" aria-hidden />
            </div>
            <div className="text-left">
              <DialogTitle>Modifier l&apos;entreprise</DialogTitle>
              <DialogDescription>
                Mettez à jour l&apos;identité légale et les coordonnées de{" "}
                <span className="font-medium text-foreground">{company.company_name}</span>.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex max-h-[calc(90vh-8.5rem)] flex-col">
          <div className="space-y-4 overflow-y-auto px-6 py-5">
            <FormSection
              icon={Building2}
              title="Identité légale"
              description="Informations affichées sur la fiche et les documents RH."
            >
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="edit_company_name">Nom affiché *</Label>
                  <Input
                    id="edit_company_name"
                    required
                    disabled={saving}
                    value={form.company_name ?? ""}
                    onChange={(e) => updateField("company_name", e.target.value)}
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="edit_raison_sociale">Raison sociale</Label>
                  <Input
                    id="edit_raison_sociale"
                    disabled={saving}
                    value={form.raison_sociale ?? ""}
                    onChange={(e) => updateField("raison_sociale", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit_legal_form">Forme juridique</Label>
                  <Input
                    id="edit_legal_form"
                    placeholder="SAS, SARL…"
                    disabled={saving}
                    value={form.legal_form ?? ""}
                    onChange={(e) => updateField("legal_form", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit_code_naf">Code NAF/APE</Label>
                  <Input
                    id="edit_code_naf"
                    disabled={saving}
                    value={form.code_naf ?? ""}
                    onChange={(e) => updateField("code_naf", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit_siren">SIREN</Label>
                  <Input
                    id="edit_siren"
                    disabled={saving}
                    value={form.siren ?? ""}
                    onChange={(e) => updateField("siren", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit_siret">SIRET</Label>
                  <Input
                    id="edit_siret"
                    disabled={saving}
                    value={form.siret ?? ""}
                    onChange={(e) => updateField("siret", e.target.value)}
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="edit_urssaf">N° URSSAF</Label>
                  <Input
                    id="edit_urssaf"
                    disabled={saving}
                    value={form.urssaf_number ?? ""}
                    onChange={(e) => updateField("urssaf_number", e.target.value)}
                  />
                </div>
              </div>
            </FormSection>

            <FormSection
              icon={MapPin}
              title="Coordonnées"
              description="Adresse et moyens de contact de l'établissement."
            >
              <div className="space-y-2">
                <Label htmlFor="edit_adresse_rue">Rue</Label>
                <Input
                  id="edit_adresse_rue"
                  disabled={saving}
                  value={form.adresse_rue ?? ""}
                  onChange={(e) => updateField("adresse_rue", e.target.value)}
                />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="edit_adresse_cp">Code postal</Label>
                  <Input
                    id="edit_adresse_cp"
                    disabled={saving}
                    value={form.adresse_code_postal ?? ""}
                    onChange={(e) => updateField("adresse_code_postal", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit_adresse_ville">Ville</Label>
                  <Input
                    id="edit_adresse_ville"
                    disabled={saving}
                    value={form.adresse_ville ?? ""}
                    onChange={(e) => updateField("adresse_ville", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit_phone">Téléphone</Label>
                  <Input
                    id="edit_phone"
                    type="tel"
                    disabled={saving}
                    value={form.phone ?? ""}
                    onChange={(e) => updateField("phone", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit_email">E-mail</Label>
                  <Input
                    id="edit_email"
                    type="email"
                    disabled={saving}
                    value={form.email ?? ""}
                    onChange={(e) => updateField("email", e.target.value)}
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="edit_website">Site web</Label>
                  <Input
                    id="edit_website"
                    type="url"
                    placeholder="https://"
                    disabled={saving}
                    value={form.website ?? ""}
                    onChange={(e) => updateField("website", e.target.value)}
                  />
                </div>
              </div>
            </FormSection>

            <FormSection
              icon={PenLine}
              title="Signataire des documents RH"
              description="Apparaît sur les contrats et attestations générés."
            >
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="edit_nom_signataire">Nom du signataire</Label>
                  <Input
                    id="edit_nom_signataire"
                    placeholder="Ex. Marie Dupont"
                    disabled={saving}
                    value={form.nom_signataire_rh ?? ""}
                    onChange={(e) => updateField("nom_signataire_rh", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit_qualite_signataire">Qualité</Label>
                  <Input
                    id="edit_qualite_signataire"
                    placeholder="Ex. Directeur RH"
                    disabled={saving}
                    value={form.qualite_signataire_rh ?? ""}
                    onChange={(e) => updateField("qualite_signataire_rh", e.target.value)}
                  />
                </div>
              </div>
            </FormSection>
          </div>

          <DialogFooter className="border-t bg-muted/30 px-6 py-4 sm:justify-end">
            <Button
              type="button"
              variant="outline"
              disabled={saving}
              onClick={() => onOpenChange(false)}
            >
              Annuler
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Enregistrement…
                </>
              ) : (
                "Enregistrer les modifications"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
