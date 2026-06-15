import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
} from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { useToast } from '@/components/ui/use-toast';
import * as collectiveAgreementsApi from '@/api/collectiveAgreements';
import { formatCatalogConventionName } from '@/lib/collectiveAgreementDisplay';
import { cn } from '@/lib/utils';
import { Check, ChevronsUpDown, Loader2 } from 'lucide-react';

type CompanyOption = {
  id: string;
  company_name: string;
};

type CollectiveAgreementAssignDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companies: CompanyOption[];
  /** Si fourni, la convention est fixée (depuis le catalogue admin). */
  fixedAgreement?: collectiveAgreementsApi.CollectiveAgreementCatalog | null;
  /** Conventions déjà assignées à l'entreprise cible (pour filtrer le picker). */
  excludedAgreementIds?: string[];
  /** Entreprises qui ont déjà cette convention (catalogue admin). */
  excludedCompanyIds?: string[];
  /** Entreprise cible imposée (fiche entreprise admin / RH). */
  fixedCompanyId?: string;
  fixedCompanyName?: string;
  onAssigned?: () => void;
};

export function CollectiveAgreementAssignDialog({
  open,
  onOpenChange,
  companies,
  fixedAgreement = null,
  excludedAgreementIds = [],
  excludedCompanyIds = [],
  fixedCompanyId,
  fixedCompanyName,
  onAssigned,
}: CollectiveAgreementAssignDialogProps) {
  const { toast } = useToast();
  const [companyId, setCompanyId] = useState('');
  const [agreementId, setAgreementId] = useState('');
  const [catalog, setCatalog] = useState<collectiveAgreementsApi.CollectiveAgreementCatalog[]>([]);
  const [isLoadingCatalog, setIsLoadingCatalog] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [comboboxOpen, setComboboxOpen] = useState(false);

  const targetCompanyId = fixedCompanyId ?? companyId;
  const excluded = useMemo(() => new Set(excludedAgreementIds), [excludedAgreementIds]);
  const excludedCompanies = useMemo(
    () => new Set(excludedCompanyIds),
    [excludedCompanyIds]
  );

  const availableCompanies = useMemo(
    () => companies.filter((c) => !excludedCompanies.has(c.id)),
    [companies, excludedCompanies]
  );

  const availableCatalog = useMemo(
    () => catalog.filter((item) => !excluded.has(item.id)),
    [catalog, excluded]
  );

  useEffect(() => {
    if (!open) return;
    setCompanyId(fixedCompanyId ?? '');
    setAgreementId(fixedAgreement?.id ?? '');
    if (!fixedAgreement) {
      setIsLoadingCatalog(true);
      void collectiveAgreementsApi
        .getCatalog({ active_only: true })
        .then((res) => setCatalog(res.data ?? []))
        .catch(() => setCatalog([]))
        .finally(() => setIsLoadingCatalog(false));
    }
  }, [open, fixedAgreement, fixedCompanyId]);

  const handleSubmit = async () => {
    const selectedAgreementId = fixedAgreement?.id ?? agreementId;
    if (!targetCompanyId || !selectedAgreementId) {
      toast({
        title: 'Champs requis',
        description: 'Sélectionnez une entreprise et une convention.',
        variant: 'destructive',
      });
      return;
    }

    setIsSubmitting(true);
    try {
      await collectiveAgreementsApi.assignAgreement(selectedAgreementId, targetCompanyId);
      toast({
        title: 'Convention assignée',
        description: fixedCompanyName
          ? `Assignée à ${fixedCompanyName}.`
          : 'La convention a été assignée à l\'entreprise.',
      });
      onOpenChange(false);
      onAssigned?.();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string };
      toast({
        title: 'Erreur',
        description:
          error.response?.data?.detail || error.message || 'Assignation impossible.',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px] overflow-hidden">
        <DialogHeader>
          <DialogTitle>Assigner une convention collective</DialogTitle>
          <DialogDescription>
            {fixedAgreement
              ? `Choisissez l'entreprise qui appliquera ${formatCatalogConventionName(fixedAgreement.name)} (IDCC ${fixedAgreement.idcc}).`
              : fixedCompanyName
                ? `Choisissez une convention du catalogue pour ${fixedCompanyName}.`
                : 'Sélectionnez l\'entreprise et la convention à lier.'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {!fixedCompanyId && (
            <div className="space-y-2">
              <Label>Entreprise *</Label>
              <Select value={companyId} onValueChange={setCompanyId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choisir une entreprise du groupe…" />
                </SelectTrigger>
                <SelectContent>
                  {availableCompanies.map((company) => (
                    <SelectItem key={company.id} value={company.id}>
                      {company.company_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {fixedAgreement ? (
            <div className="rounded-md border bg-muted/30 p-3 text-sm">
              <p className="font-medium break-words leading-snug">
                {formatCatalogConventionName(fixedAgreement.name)}
              </p>
              <p className="text-muted-foreground">IDCC {fixedAgreement.idcc}</p>
            </div>
          ) : (
            <div className="space-y-2">
              <Label htmlFor="cc-assign-picker" className="block">
                Convention *
              </Label>
              <Popover open={comboboxOpen} onOpenChange={setComboboxOpen}>
                <PopoverTrigger asChild>
                  <Button
                    id="cc-assign-picker"
                    variant="outline"
                    role="combobox"
                    aria-expanded={comboboxOpen}
                    className="h-auto min-h-10 w-full min-w-0 justify-between gap-2 overflow-hidden whitespace-normal py-2 font-normal"
                    disabled={!targetCompanyId}
                  >
                    <span className="line-clamp-2 min-w-0 flex-1 text-left text-sm leading-snug">
                      {agreementId
                        ? formatCatalogConventionName(
                            availableCatalog.find((c) => c.id === agreementId)?.name
                          )
                        : targetCompanyId
                          ? 'Rechercher une convention…'
                          : 'Choisissez d\'abord une entreprise'}
                    </span>
                    <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[var(--radix-popover-trigger-width)] max-w-[520px] p-0" align="start">
                  <Command>
                    <CommandInput placeholder="Rechercher par nom ou IDCC…" />
                    <CommandEmpty>
                      {isLoadingCatalog ? 'Chargement…' : 'Aucune convention disponible.'}
                    </CommandEmpty>
                    <CommandGroup className="max-h-64 overflow-auto">
                      {availableCatalog.map((agreement) => (
                        <CommandItem
                          key={agreement.id}
                          value={`${agreement.name} ${agreement.idcc}`}
                          onSelect={() => {
                            setAgreementId(agreement.id);
                            setComboboxOpen(false);
                          }}
                        >
                          <Check
                            className={cn(
                              'mr-2 h-4 w-4',
                              agreementId === agreement.id ? 'opacity-100' : 'opacity-0'
                            )}
                          />
                          <div className="min-w-0 flex-1">
                            <p className="font-medium break-words leading-snug">
                              {formatCatalogConventionName(agreement.name)}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              IDCC {agreement.idcc}
                              {agreement.sector ? ` · ${agreement.sector}` : ''}
                            </p>
                          </div>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button
            onClick={() => void handleSubmit()}
            disabled={
              isSubmitting ||
              !targetCompanyId ||
              !(fixedAgreement?.id ?? agreementId)
            }
          >
            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Assigner
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
