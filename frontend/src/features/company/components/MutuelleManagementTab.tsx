import { log } from '@/lib/logger';
import { useEffect, useMemo, useState } from "react";
import apiClient from "@/api/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, PlusCircle, Trash2, Edit2, HeartHandshake, Check, ChevronsUpDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { mutuelleTypesApi, MutuelleType, MutuelleTypeCreate } from "@/api/mutuelleTypes";
import {
  PACK_COUVERTURE_LABELS,
  STATUT_CATEGORIEL_LABELS,
} from "@/lib/mutuelleUtils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface SimpleEmployee {
  id: string;
  first_name: string;
  last_name: string;
  job_title: string | null;
}

// Composant pour la gestion des mutuelles
export default function MutuelleManagementTab() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [mutuelles, setMutuelles] = useState<MutuelleType[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingMutuelle, setEditingMutuelle] = useState<MutuelleType | null>(null);
  const [formData, setFormData] = useState<MutuelleTypeCreate>({
    libelle: '',
    montant_salarial: 0,
    montant_patronal: 0,
    part_patronale_soumise_a_csg: true,
    is_active: true,
    pack_couverture: null,
    statut_categoriel: 'tous',
    employee_ids: [],
  });
  const [employees, setEmployees] = useState<SimpleEmployee[]>([]);
  const [loadingEmployees, setLoadingEmployees] = useState(false);
  const [employeePopoverOpen, setEmployeePopoverOpen] = useState(false);

  useEffect(() => {
    loadMutuelles();
    loadEmployees();
  }, []);

  const loadEmployees = async () => {
    try {
      setLoadingEmployees(true);
      const response = await apiClient.get<SimpleEmployee[]>('/api/employees');
      setEmployees(response.data);
    } catch (error: any) {
      log.error("Erreur lors du chargement des employés:", error);
    } finally {
      setLoadingEmployees(false);
    }
  };

  const loadMutuelles = async () => {
    try {
      setLoading(true);
      const data = await mutuelleTypesApi.getMutuelleTypes();
      setMutuelles(data);
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error.response?.data?.detail || "Impossible de charger les mutuelles",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
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
        employee_ids: mutuelle.employee_ids || [],
      });
    } else {
      setEditingMutuelle(null);
      setFormData({
        libelle: '',
        montant_salarial: 0,
        montant_patronal: 0,
        part_patronale_soumise_a_csg: true,
        is_active: true,
        pack_couverture: null,
        statut_categoriel: 'tous',
        employee_ids: [],
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
        title: "Erreur",
        description: "Veuillez remplir tous les champs correctement",
        variant: "destructive",
      });
      return;
    }

    try {
      if (editingMutuelle) {
        // Lors de la modification, ne pas modifier is_active (géré uniquement par le bouton Désactiver/Activer)
        const { is_active, ...updateData } = formData;
        await mutuelleTypesApi.updateMutuelleType(editingMutuelle.id, updateData);
        toast({
          title: "Succès",
          description: "Formule de mutuelle mise à jour",
        });
      } else {
        // Lors de la création, toujours créer avec is_active = true
        const { is_active, ...createData } = formData;
        await mutuelleTypesApi.createMutuelleType({ ...createData, is_active: true });
        toast({
          title: "Succès",
          description: "Formule de mutuelle créée",
        });
      }
      handleCloseDialog();
      loadMutuelles();
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error.response?.data?.detail || "Une erreur est survenue",
        variant: "destructive",
      });
    }
  };

  const handleSelectAllEmployees = () => {
    if (formData.employee_ids?.length === employees.length) {
      setFormData({ ...formData, employee_ids: [] });
    } else {
      setFormData({ ...formData, employee_ids: employees.map(e => e.id) });
    }
  };

  const handleToggleEmployee = (employeeId: string) => {
    const currentIds = formData.employee_ids || [];
    const isSelected = currentIds.includes(employeeId);
    const newIds = isSelected
      ? currentIds.filter(id => id !== employeeId)
      : [...currentIds, employeeId];
    setFormData({ ...formData, employee_ids: newIds });
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Êtes-vous sûr de vouloir supprimer cette formule de mutuelle ?")) {
      return;
    }

    try {
      await mutuelleTypesApi.deleteMutuelleType(id);
      toast({
        title: "Succès",
        description: "Formule de mutuelle supprimée",
      });
      loadMutuelles();
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error.response?.data?.detail || "Impossible de supprimer la formule",
        variant: "destructive",
      });
    }
  };

  const handleToggleActive = async (mutuelle: MutuelleType) => {
    try {
      await mutuelleTypesApi.updateMutuelleType(mutuelle.id, {
        is_active: !mutuelle.is_active,
      });
      toast({
        title: "Succès",
        description: mutuelle.is_active ? "Formule désactivée" : "Formule activée",
      });
      loadMutuelles();
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error.response?.data?.detail || "Une erreur est survenue",
        variant: "destructive",
      });
    }
  };

  const mutuelleStats = useMemo(() => {
    const formulas = mutuelles.length;
    const covered = new Set(
      mutuelles.flatMap((m) => m.employee_ids ?? []),
    ).size;
    return { formulas, covered };
  }, [mutuelles]);

  if (loading) {
    return (
      <div className="flex justify-center items-center py-10">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-center">
          <div>
            <CardTitle className="flex items-center">
              <HeartHandshake className="mr-2 h-5 w-5" />
              Formules de Mutuelle
            </CardTitle>
            <CardDescription>
              Formules et affectation par salarié — utilisées à l&apos;embauche et en paie.
              {" "}
              {mutuelleStats.formulas} formule{mutuelleStats.formulas > 1 ? "s" : ""} ·{" "}
              {mutuelleStats.covered} employé{mutuelleStats.covered > 1 ? "s" : ""} couvert
              {mutuelleStats.covered > 0 ? "" : "s"}
            </CardDescription>
          </div>
          {user?.role && ['admin', 'rh', 'admin'].includes(user.role) && (
            <Button onClick={() => handleOpenDialog()}>
              <PlusCircle className="mr-2 h-4 w-4" />
              Ajouter une formule
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {mutuelles.length === 0 ? (
          <div className="text-center py-10 text-muted-foreground">
            Aucune formule de mutuelle définie
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Libellé</TableHead>
                <TableHead>Pack</TableHead>
                <TableHead>Catégorie</TableHead>
                <TableHead>Montant Salarial (€)</TableHead>
                <TableHead>Montant Patronal (€)</TableHead>
                <TableHead>Part Patronale CSG</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mutuelles.map((mutuelle) => (
                <TableRow key={mutuelle.id}>
                  <TableCell className="font-medium">{mutuelle.libelle}</TableCell>
                  <TableCell>
                    {mutuelle.pack_couverture
                      ? PACK_COUVERTURE_LABELS[mutuelle.pack_couverture] ?? mutuelle.pack_couverture
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
                    {mutuelle.employee_ids && mutuelle.employee_ids.length > 0 && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        ({mutuelle.employee_ids.length} employé{mutuelle.employee_ids.length > 1 ? 's' : ''})
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      {user?.role && ['admin', 'rh', 'admin'].includes(user.role) && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleToggleActive(mutuelle)}
                            title={mutuelle.is_active ? "Désactiver" : "Activer"}
                          >
                            {mutuelle.is_active ? "Désactiver" : "Activer"}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenDialog(mutuelle)}
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(mutuelle.id)}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingMutuelle ? "Modifier la formule" : "Nouvelle formule de mutuelle"}
            </DialogTitle>
            <DialogDescription>
              {editingMutuelle
                ? "Modifiez les informations de la formule de mutuelle"
                : "Remplissez les informations pour créer une nouvelle formule de mutuelle"}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="libelle">Libellé *</Label>
              <Input
                id="libelle"
                value={formData.libelle}
                onChange={(e) => setFormData({ ...formData, libelle: e.target.value })}
                placeholder="Ex: Mutuelle Collaborateur Seul"
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
                      pack_couverture: v === '__none__' ? null : (v as MutuelleTypeCreate['pack_couverture']),
                    })
                  }
                >
                  <SelectTrigger><SelectValue placeholder="Non précisé" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">Non précisé</SelectItem>
                    {Object.entries(PACK_COUVERTURE_LABELS).map(([k, label]) => (
                      <SelectItem key={k} value={k}>{label}</SelectItem>
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
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(STATUT_CATEGORIEL_LABELS).map(([k, label]) => (
                      <SelectItem key={k} value={k}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="montant_salarial">Montant Salarial (€) *</Label>
                <Input
                  id="montant_salarial"
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.montant_salarial}
                  onChange={(e) =>
                    setFormData({ ...formData, montant_salarial: parseFloat(e.target.value) || 0 })
                  }
                />
              </div>
              <div>
                <Label htmlFor="montant_patronal">Montant Patronal (€) *</Label>
                <Input
                  id="montant_patronal"
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.montant_patronal}
                  onChange={(e) =>
                    setFormData({ ...formData, montant_patronal: parseFloat(e.target.value) || 0 })
                  }
                />
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="part_patronale_csg"
                checked={formData.part_patronale_soumise_a_csg}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, part_patronale_soumise_a_csg: checked === true })
                }
              />
              <Label htmlFor="part_patronale_csg" className="cursor-pointer">
                Part patronale soumise à CSG (défiscalisation)
              </Label>
            </div>
            
            {/* Sélection des employés */}
            <div className="space-y-2">
              <Label>Employés souscrivant à cette mutuelle</Label>
              <Popover open={employeePopoverOpen} onOpenChange={setEmployeePopoverOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    className="w-full justify-between font-normal"
                    disabled={loadingEmployees}
                  >
                    {formData.employee_ids && formData.employee_ids.length > 0
                      ? `${formData.employee_ids.length} employé(s) sélectionné(s)`
                      : "Sélectionner des employés..."}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[--radix-popover-trigger-width] p-0 z-[100]" align="start">
                  <Command>
                    <CommandInput placeholder="Rechercher un employé..." />
                    <CommandList className="max-h-[300px] overflow-y-auto">
                      <CommandEmpty>Aucun employé trouvé.</CommandEmpty>
                      <CommandGroup>
                        <CommandItem onSelect={handleSelectAllEmployees} className="cursor-pointer">
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              formData.employee_ids?.length === employees.length ? "opacity-100" : "opacity-0"
                            )}
                          />
                          {formData.employee_ids?.length === employees.length
                            ? "Tout désélectionner"
                            : "Tout sélectionner"}
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
                                "mr-2 h-4 w-4",
                                formData.employee_ids?.includes(employee.id) ? "opacity-100" : "opacity-0"
                              )}
                            />
                            <div>
                              <p>{employee.first_name} {employee.last_name}</p>
                              {employee.job_title && (
                                <p className="text-xs text-muted-foreground">{employee.job_title}</p>
                              )}
                            </div>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
              {formData.employee_ids && formData.employee_ids.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  {formData.employee_ids.length} employé(s) sélectionné(s). Ces employés seront automatiquement associés à cette mutuelle.
                </p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleCloseDialog}>
              Annuler
            </Button>
            <Button onClick={handleSubmit}>
              {editingMutuelle ? "Modifier" : "Créer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}