import type { ReactNode } from "react";
import type { CompanyDetails, CompanyDetailsUpdate } from "@/api/company";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

function DlRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-1 py-2 sm:grid-cols-3 sm:gap-4 border-b border-border/60 last:border-0">
      <dt className="text-sm font-medium text-muted-foreground">{label}</dt>
      <dd className="text-sm sm:col-span-2">{value ?? "Non renseigné"}</dd>
    </div>
  );
}

type CompanyIdentityTabProps = {
  company: CompanyDetails;
  canEdit: boolean;
  editOpen: boolean;
  onEditOpenChange: (open: boolean) => void;
  draft: CompanyDetailsUpdate;
  onDraftChange: (d: CompanyDetailsUpdate) => void;
  onSave: () => void;
  saving?: boolean;
};

export function CompanyIdentityTab({
  company,
  canEdit,
  editOpen,
  onEditOpenChange,
  draft,
  onDraftChange,
  onSave,
  saving,
}: CompanyIdentityTabProps): JSX.Element {
  const raison = company.raison_sociale || company.company_name;

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Identité de l&apos;entreprise</CardTitle>
          {canEdit ? (
            <Button variant="outline" size="sm" onClick={() => onEditOpenChange(true)}>
              Modifier
            </Button>
          ) : null}
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
            <dl>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                Informations légales
              </p>
              <DlRow label="Raison sociale" value={raison} />
              <DlRow label="Forme juridique" value={company.legal_form} />
              <DlRow label="SIREN" value={company.siren} />
              <DlRow label="SIRET (siège)" value={company.siret} />
              <DlRow
                label="Code NAF/APE"
                value={company.naf_ape || company.code_naf}
              />
              <DlRow label="N° URSSAF" value={company.urssaf_number} />
            </dl>
            <dl>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                Coordonnées
              </p>
              <DlRow
                label="Adresse"
                value={
                  company.adresse_rue ? (
                    <address className="not-italic">
                      {company.adresse_rue}
                      <br />
                      {company.adresse_code_postal} {company.adresse_ville}
                    </address>
                  ) : null
                }
              />
              <DlRow label="Téléphone" value={company.phone} />
              <DlRow label="Email" value={company.email} />
              <DlRow label="Site web" value={company.website} />
            </dl>
          </div>
        </CardContent>
      </Card>

      <Sheet open={editOpen} onOpenChange={onEditOpenChange}>
        <SheetContent className="overflow-y-auto sm:max-w-lg">
          <SheetHeader>
            <SheetTitle>Modifier l&apos;identité</SheetTitle>
            <SheetDescription>
              Informations légales et coordonnées visibles sur la fiche entreprise.
            </SheetDescription>
          </SheetHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="company_name">Nom affiché</Label>
              <Input
                id="company_name"
                value={draft.company_name ?? ""}
                onChange={(e) =>
                  onDraftChange({ ...draft, company_name: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="raison_sociale">Raison sociale</Label>
              <Input
                id="raison_sociale"
                value={draft.raison_sociale ?? ""}
                onChange={(e) =>
                  onDraftChange({ ...draft, raison_sociale: e.target.value })
                }
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="siren">SIREN</Label>
                <Input
                  id="siren"
                  value={draft.siren ?? ""}
                  onChange={(e) => onDraftChange({ ...draft, siren: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="siret">SIRET</Label>
                <Input
                  id="siret"
                  value={draft.siret ?? ""}
                  onChange={(e) => onDraftChange({ ...draft, siret: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="legal_form">Forme juridique</Label>
              <Input
                id="legal_form"
                value={draft.legal_form ?? ""}
                onChange={(e) =>
                  onDraftChange({ ...draft, legal_form: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="adresse_rue">Rue</Label>
              <Input
                id="adresse_rue"
                value={draft.adresse_rue ?? ""}
                onChange={(e) =>
                  onDraftChange({ ...draft, adresse_rue: e.target.value })
                }
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="adresse_cp">Code postal</Label>
                <Input
                  id="adresse_cp"
                  value={draft.adresse_code_postal ?? ""}
                  onChange={(e) =>
                    onDraftChange({ ...draft, adresse_code_postal: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="adresse_ville">Ville</Label>
                <Input
                  id="adresse_ville"
                  value={draft.adresse_ville ?? ""}
                  onChange={(e) =>
                    onDraftChange({ ...draft, adresse_ville: e.target.value })
                  }
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Téléphone</Label>
              <Input
                id="phone"
                value={draft.phone ?? ""}
                onChange={(e) => onDraftChange({ ...draft, phone: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={draft.email ?? ""}
                onChange={(e) => onDraftChange({ ...draft, email: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="website">Site web</Label>
              <Input
                id="website"
                value={draft.website ?? ""}
                onChange={(e) => onDraftChange({ ...draft, website: e.target.value })}
              />
            </div>
          </div>
          <SheetFooter>
            <Button variant="outline" onClick={() => onEditOpenChange(false)}>
              Annuler
            </Button>
            <Button onClick={onSave} disabled={saving}>
              Enregistrer
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </>
  );
}
