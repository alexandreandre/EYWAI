import { log } from '@/lib/logger';
import { useCallback, useEffect, useMemo, useState } from 'react';
import apiClient from '@/api/apiClient';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  Loader2,
  PlusCircle,
  Trash2,
  Edit2,
  HeartHandshake,
  Check,
  ChevronsUpDown,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';
import {
  mutuelleTypesClientForCompany,
  type MutuelleType,
  type MutuelleTypeCreate,
} from '@/api/mutuelleTypes';
import { pscSettingsClientForCompany, type PscSettings } from '@/api/pscSettings';
import {
  PACK_COUVERTURE_LABELS,
  STATUT_CATEGORIEL_LABELS,
  resolveOrganismeLabel,
} from '@/lib/mutuelleUtils';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';

interface SimpleEmployee {
  id: string;
  first_name: string;
  last_name: string;
  job_title: string | null;
}

const EMPTY_FORM: MutuelleTypeCreate = {
  libelle: '',
  montant_salarial: 0,
  montant_patronal: 0,
  part_patronale_soumise_a_csg: true,
  is_active: true,
  pack_couverture: null,
  statut_categoriel: 'tous',
  organisme_label: null,
  employee_ids: [],
};

export type CompanyMutuelleSectionProps = {
  /** Super Admin : société cible. Omis = entreprise active (RH). */
  companyId?: string;
  canEdit?: boolean;
  /** Intégration dans l'onglet paramètres paie (sans carte externe). */
  embedded?: boolean;
  className?: string;
};

export function CompanyMutuelleSection({
  companyId,
  canEdit = true,
  embedded = false,
  className,
}: CompanyMutuelleSectionProps) {
  const { toast } = useToast();
  const mutuelleClient = useMemo(
    () => mutuelleTypesClientForCompany(companyId),
    [companyId],
  );
  const pscClient = useMemo(() => pscSettingsClientForCompany(companyId), [companyId]);
  const employeeHeaders = useMemo(
    () => (companyId ? { 'X-Active-Company': companyId } : undefined),
    [companyId],
  );

  const [mutuelles, setMutuelles] = useState<MutuelleType[]>([]);
  const [pscSettings, setPscSettings] = useState<PscSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingPsc, setSavingPsc] = useState(false);
  const [showDialog, setShowDialog] = useState(false);
  const [editingMutuelle, setEditingMutuelle] = useState<MutuelleType | null>(null);
  const [formData, setFormData] = useState<MutuelleTypeCreate>(EMPTY_FORM);
  const [employees, setEmployees] = useState<SimpleEmployee[]>([]);
  const [loadingEmployees, setLoadingEmployees] = useState(false);
  const [employeePopoverOpen, setEmployeePopoverOpen] = useState(false);

  const companyOrganismeLabel = pscSettings?.mutuelle_organisme_label ?? null;

  const loadEmployees = useCallback(async () => {
    try {
      setLoadingEmployees(true);
      const response = await apiClient.get<SimpleEmployee[]>('/api/employees', {
        headers: employeeHeaders,
      });
      setEmployees(response.data);
    } catch (error: unknown) {
      log.error('Erreur lors du chargement des employés:', error);
    } finally {
      setLoadingEmployees(false);
    }
  }, [employeeHeaders]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [mutuelleData, pscData] = await Promise.all([
        mutuelleClient.getMutuelleTypes(),
        pscClient.get(),
      ]);
      setMutuelles(mutuelleData);
      setPscSettings(pscData);
    } catch (error: unknown) {
      const detail =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Impossible de charger les mutuelles';
      toast({
        title: 'Erreur',
        description: detail,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [mutuelleClient, pscClient]);

  useEffect(() => {
    void loadData();
    void loadEmployees();
  }, [loadData, loadEmployees]);

  const handleSavePsc = async () => {
    if (!pscSettings) return;
    try {
      setSavingPsc(true);
      const updated = await pscClient.update({
        mutuelle_organisme_label: pscSettings.mutuelle_organisme_label?.trim() || null,
        mutuelle_employee_self_service: pscSettings.mutuelle_employee_self_service,
      });
      setPscSettings(updated);
      toast({ title: 'Paramètres mutuelle enregistrés' });
    } catch (error: unknown) {
      const detail =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Enregistrement impossible';
      toast({ title: 'Erreur', description: detail, variant: 'destructive' });
    } finally {
      setSavingPsc(false);
    }
  };

  const handleOpenDialog = (mutuelle?: MutuelleType) => {
    if (mutuelle) {
      setEditingMutuelle(mutuelle);
      setFormData({
        libelle: mutuelle.libelle,
        montant_salarial: mutuelle.montant_salarial,
        montant_patronal: mutuelle.montant_patronal,
        part_patronale_soumise_a_csg: mutuelle.part_patronale_soumise_a_csg,
        is_active: true,
        pack_couverture: mutuelle.pack_couverture ?? null,
        statut_categoriel: mutuelle.statut_categoriel ?? 'tous',
        organisme_label: mutuelle.organisme_label ?? null,
        employee_ids: mutuelle.employee_ids || [],
      });
    } else {
      setEditingMutuelle(null);
      setFormData({
        ...EMPTY_FORM,
        organisme_label: companyOrganismeLabel,
      });
    }
    setShowDialog(true);
  };

  const handleCloseDialog = () => {
    setShowDialog(false);
    setEditingMutuelle(null);
  };

  const handleSubmit = async () => {
    if (!formData.libelle || formData.montant_salarial < 0 || formData.montant_patronal < 0) {
      toast({
        title: 'Erreur',
        description: 'Veuillez remplir tous les champs correctement',
        variant: 'destructive',
      });
      return;
    }

    try {
      if (editingMutuelle) {
        const { is_active, ...updateData } = formData;
        await mutuelleClient.updateMutuelleType(editingMutuelle.id, updateData);
        toast({ title: 'Succès', description: 'Formule de mutuelle mise à jour' });
      } else {
        const { is_active, ...createData } = formData;
        await mutuelleClient.createMutuelleType({ ...createData, is_active: true });
        toast({ title: 'Succès', description: 'Formule de mutuelle créée' });
      }
      handleCloseDialog();
      void loadData();
    } catch (error: unknown) {
      toast({
        title: 'Erreur',
        description:
          (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          'Une erreur est survenue',
        variant: 'destructive',
      });
    }
  };

  const handleSelectAllEmployees = () => {
    if (formData.employee_ids?.length === employees.length) {
      setFormData({ ...formData, employee_ids: [] });
    } else {
      setFormData({ ...formData, employee_ids: employees.map((e) => e.id) });
    }
  };

  const handleToggleEmployee = (employeeId: string) => {
    const currentIds = formData.employee_ids || [];
    const isSelected = currentIds.includes(employeeId);
    const newIds = isSelected
      ? currentIds.filter((id) => id !== employeeId)
      : [...currentIds, employeeId];
    setFormData({ ...formData, employee_ids: newIds });
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Êtes-vous sûr de vouloir supprimer cette formule de mutuelle ?')) {
      return;
    }
    try {
      await mutuelleClient.deleteMutuelleType(id);
      toast({ title: 'Succès', description: 'Formule de mutuelle supprimée' });
      void loadData();
    } catch (error: unknown) {
      toast({
        title: 'Erreur',
        description:
          (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          'Impossible de supprimer la formule',
        variant: 'destructive',
      });
    }
  };

  const handleToggleActive = async (mutuelle: MutuelleType) => {
    try {
      await mutuelleClient.updateMutuelleType(mutuelle.id, {
        is_active: !mutuelle.is_active,
      });
      toast({
        title: 'Succès',
        description: mutuelle.is_active ? 'Formule désactivée' : 'Formule activée',
      });
      void loadData();
    } catch (error: unknown) {
      toast({
        title: 'Erreur',
        description:
          (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          'Une erreur est survenue',
        variant: 'destructive',
      });
    }
  };

  const mutuelleStats = useMemo(() => {
    const formulas = mutuelles.length;
    const active = mutuelles.filter((m) => m.is_active).length;
    const covered = new Set(mutuelles.flatMap((m) => m.employee_ids ?? [])).size;
    return { formulas, active, covered };
  }, [mutuelles]);

  if (loading) {
    return (
      <div className={cn('flex items-center justify-center py-10', className)}>
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const pscBlock = pscSettings ? (
    <div className="space-y-4 rounded-lg border bg-muted/20 p-4">
      <div>
        <p className="text-sm font-medium">Organisme mutuelle (entreprise)</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Affiché sur les formules et lors de l&apos;affectation en fiche collaborateur (ex. APICIL).
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="mutuelle-organisme">Nom de l&apos;organisme</Label>
          <Input
            id="mutuelle-organisme"
            value={pscSettings.mutuelle_organisme_label ?? ''}
            onChange={(e) =>
              setPscSettings((prev) =>
                prev ? { ...prev, mutuelle_organisme_label: e.target.value } : prev,
              )
            }
            placeholder="Ex. APICIL Prévoyance"
            disabled={!canEdit}
          />
        </div>
        <div className="space-y-2 sm:col-span-2">
          <div className="flex items-start gap-3 rounded-md border bg-background p-3">
            <Switch
              id="mutuelle-self-service"
              checked={pscSettings.mutuelle_employee_self_service}
              onCheckedChange={(checked) =>
                setPscSettings((prev) =>
                  prev ? { ...prev, mutuelle_employee_self_service: checked } : prev,
                )
              }
              disabled={!canEdit}
            />
            <div className="space-y-1">
              <Label htmlFor="mutuelle-self-service" className="cursor-pointer text-sm font-medium">
                Choix de la formule par le salarié
              </Label>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Désactivé par défaut : la RH affecte la mutuelle depuis la fiche collaborateur ou
                l&apos;onboarding. Activer uniquement si le salarié doit choisir seul dans son espace.
              </p>
            </div>
          </div>
        </div>
      </div>
      {canEdit ? (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => void handleSavePsc()} disabled={savingPsc}>
            {savingPsc ? 'Enregistrement…' : 'Enregistrer les paramètres'}
          </Button>
        </div>
      ) : null}
    </div>
  ) : null;

  const tableBlock = (
    <>
      {mutuelles.length === 0 ? (
        <div className="py-8 text-center text-muted-foreground">
          Aucune formule de mutuelle définie pour cette entreprise.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Libellé</TableHead>
                <TableHead>Organisme</TableHead>
                <TableHead>Pack</TableHead>
                <TableHead>Catégorie</TableHead>
                <TableHead>Sal. (€)</TableHead>
                <TableHead>Pat. (€)</TableHead>
                <TableHead>CSG</TableHead>
                <TableHead>Statut</TableHead>
                {canEdit ? <TableHead className="text-right">Actions</TableHead> : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {mutuelles.map((mutuelle) => (
                <TableRow key={mutuelle.id}>
                  <TableCell className="font-medium">{mutuelle.libelle}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {resolveOrganismeLabel(mutuelle, companyOrganismeLabel) ?? '—'}
                  </TableCell>
                  <TableCell>
                    {mutuelle.pack_couverture
                      ? (PACK_COUVERTURE_LABELS[mutuelle.pack_couverture] ?? mutuelle.pack_couverture)
                      : '—'}
                  </TableCell>
                  <TableCell>
                    {STATUT_CATEGORIEL_LABELS[mutuelle.statut_categoriel ?? 'tous']}
                  </TableCell>
                  <TableCell>{mutuelle.montant_salarial.toFixed(2)}</TableCell>
                  <TableCell>{mutuelle.montant_patronal.toFixed(2)}</TableCell>
                  <TableCell>
                    {mutuelle.part_patronale_soumise_a_csg ? (
                      <Badge variant="default">Oui</Badge>
                    ) : (
                      <Badge variant="secondary">Non</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {mutuelle.is_active ? (
                      <Badge variant="default">Active</Badge>
                    ) : (
                      <Badge variant="secondary">Inactive</Badge>
                    )}
                    {mutuelle.employee_ids && mutuelle.employee_ids.length > 0 ? (
                      <span className="ml-2 text-xs text-muted-foreground">
                        ({mutuelle.employee_ids.length} sal.)
                      </span>
                    ) : null}
                  </TableCell>
                  {canEdit ? (
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void handleToggleActive(mutuelle)}
                          title={mutuelle.is_active ? 'Désactiver' : 'Activer'}
                        >
                          {mutuelle.is_active ? 'Désactiver' : 'Activer'}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleOpenDialog(mutuelle)}>
                          <Edit2 className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void handleDelete(mutuelle.id)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  ) : null}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );

  const dialogBlock = (
    <Dialog open={showDialog} onOpenChange={setShowDialog}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {editingMutuelle ? 'Modifier la formule' : 'Nouvelle formule de mutuelle'}
          </DialogTitle>
          <DialogDescription>
            Formule utilisée à l&apos;embauche, en paie et dans la DSN.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div>
            <Label htmlFor="libelle">Libellé *</Label>
            <Input
              id="libelle"
              value={formData.libelle}
              onChange={(e) => setFormData({ ...formData, libelle: e.target.value })}
              placeholder="Ex. Mutuelle Collaborateur Seul"
            />
          </div>
          <div>
            <Label htmlFor="organisme-formule">Organisme (optionnel)</Label>
            <Input
              id="organisme-formule"
              value={formData.organisme_label ?? ''}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  organisme_label: e.target.value.trim() || null,
                })
              }
              placeholder={
                companyOrganismeLabel
                  ? `Par défaut : ${companyOrganismeLabel}`
                  : 'Ex. APICIL'
              }
            />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label>Pack de couverture</Label>
              <Select
                value={formData.pack_couverture ?? '__none__'}
                onValueChange={(v) =>
                  setFormData({
                    ...formData,
                    pack_couverture:
                      v === '__none__' ? null : (v as MutuelleTypeCreate['pack_couverture']),
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Non précisé" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Non précisé</SelectItem>
                  {Object.entries(PACK_COUVERTURE_LABELS).map(([k, label]) => (
                    <SelectItem key={k} value={k}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Catégorie salariale</Label>
              <Select
                value={formData.statut_categoriel ?? 'tous'}
                onValueChange={(v) =>
                  setFormData({
                    ...formData,
                    statut_categoriel: v as MutuelleTypeCreate['statut_categoriel'],
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(STATUT_CATEGORIEL_LABELS).map(([k, label]) => (
                    <SelectItem key={k} value={k}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="montant_salarial">Montant salarial (€) *</Label>
              <Input
                id="montant_salarial"
                type="number"
                step="0.01"
                min="0"
                value={formData.montant_salarial}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    montant_salarial: parseFloat(e.target.value) || 0,
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="montant_patronal">Montant patronal (€) *</Label>
              <Input
                id="montant_patronal"
                type="number"
                step="0.01"
                min="0"
                value={formData.montant_patronal}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    montant_patronal: parseFloat(e.target.value) || 0,
                  })
                }
              />
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox
              id="part_patronale_csg"
              checked={formData.part_patronale_soumise_a_csg}
              onCheckedChange={(checked) =>
                setFormData({
                  ...formData,
                  part_patronale_soumise_a_csg: checked === true,
                })
              }
            />
            <Label htmlFor="part_patronale_csg" className="cursor-pointer">
              Part patronale soumise à CSG (défiscalisation)
            </Label>
          </div>
          <div className="space-y-2">
            <Label>Salariés souscrivant à cette formule</Label>
            <Popover open={employeePopoverOpen} onOpenChange={setEmployeePopoverOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  role="combobox"
                  className="w-full justify-between font-normal"
                  disabled={loadingEmployees}
                >
                  {formData.employee_ids && formData.employee_ids.length > 0
                    ? `${formData.employee_ids.length} salarié(s) sélectionné(s)`
                    : 'Sélectionner des salariés…'}
                  <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="z-[100] w-[--radix-popover-trigger-width] p-0" align="start">
                <Command>
                  <CommandInput placeholder="Rechercher un salarié…" />
                  <CommandList className="max-h-[300px] overflow-y-auto">
                    <CommandEmpty>Aucun salarié trouvé.</CommandEmpty>
                    <CommandGroup>
                      <CommandItem
                        onSelect={handleSelectAllEmployees}
                        className="cursor-pointer"
                      >
                        <Check
                          className={cn(
                            'mr-2 h-4 w-4',
                            formData.employee_ids?.length === employees.length
                              ? 'opacity-100'
                              : 'opacity-0',
                          )}
                        />
                        {formData.employee_ids?.length === employees.length
                          ? 'Tout désélectionner'
                          : 'Tout sélectionner'}
                      </CommandItem>
                      {employees.map((employee) => (
                        <CommandItem
                          key={employee.id}
                          value={`${employee.first_name} ${employee.last_name}`}
                          onSelect={() => handleToggleEmployee(employee.id)}
                          className="cursor-pointer"
                        >
                          <Check
                            className={cn(
                              'mr-2 h-4 w-4',
                              formData.employee_ids?.includes(employee.id)
                                ? 'opacity-100'
                                : 'opacity-0',
                            )}
                          />
                          <div>
                            <p>
                              {employee.first_name} {employee.last_name}
                            </p>
                            {employee.job_title ? (
                              <p className="text-xs text-muted-foreground">{employee.job_title}</p>
                            ) : null}
                          </div>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleCloseDialog}>
            Annuler
          </Button>
          <Button onClick={() => void handleSubmit()}>
            {editingMutuelle ? 'Modifier' : 'Créer'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  const statsLine = (
    <span className="text-muted-foreground">
      {mutuelleStats.formulas} formule{mutuelleStats.formulas > 1 ? 's' : ''}
      {' · '}
      {mutuelleStats.active} active{mutuelleStats.active > 1 ? 's' : ''}
      {' · '}
      {mutuelleStats.covered} salarié{mutuelleStats.covered > 1 ? 's' : ''} couvert
      {mutuelleStats.covered > 1 ? 's' : ''}
    </span>
  );

  if (embedded) {
    return (
      <div className={cn('space-y-4', className)}>
        {pscBlock}
        <Separator />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm">{statsLine}</p>
          {canEdit ? (
            <Button size="sm" onClick={() => handleOpenDialog()}>
              <PlusCircle className="mr-2 h-4 w-4" />
              Ajouter une formule
            </Button>
          ) : null}
        </div>
        {tableBlock}
        {canEdit ? dialogBlock : null}
      </div>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="flex items-center">
              <HeartHandshake className="mr-2 h-5 w-5" />
              Mutuelle &amp; complémentaire santé
            </CardTitle>
            <CardDescription className="mt-1.5">
              Organisme, catalogue de formules et affectation salariés — {statsLine}
            </CardDescription>
          </div>
          {canEdit ? (
            <Button onClick={() => handleOpenDialog()}>
              <PlusCircle className="mr-2 h-4 w-4" />
              Ajouter une formule
            </Button>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {pscBlock}
        <Separator />
        {tableBlock}
      </CardContent>
      {canEdit ? dialogBlock : null}
    </Card>
  );
}
