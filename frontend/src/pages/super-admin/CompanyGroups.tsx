/**
 * CompanyGroups : Page de gestion des groupes d'entreprises (Super Admin)
 *
 * Permet de :
 * - Voir tous les groupes avec leurs statistiques
 * - Créer un nouveau groupe
 * - Accéder au détail d'un groupe
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '@/api/apiClient';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { LogoUploader } from '@/components/LogoUploader';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Building2, Plus, Users, TrendingUp, Loader2, ChevronRight } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useToast } from '@/hooks/use-toast';

interface CompanyGroup {
  id: string;
  group_name: string;
  description: string | null;
  created_at: string;
  company_count: number;
  total_employees: number;
}

interface AvailableCompany {
  id: string;
  company_name: string;
  siret: string | null;
}

export default function CompanyGroups() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [groups, setGroups] = useState<CompanyGroup[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  // Form state
  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupDescription, setNewGroupDescription] = useState('');
  const [newGroupLogoUrl, setNewGroupLogoUrl] = useState<string | null>(null);
  const [selectedCompanyIds, setSelectedCompanyIds] = useState<string[]>([]);
  const [availableCompanies, setAvailableCompanies] = useState<AvailableCompany[]>([]);

  useEffect(() => {
    loadGroups();
  }, []);

  const loadGroups = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await apiClient.get('/api/company-groups/');
      setGroups(response.data);
    } catch (err: any) {
      console.error('Erreur lors du chargement des groupes:', err);
      setError(err.response?.data?.detail || 'Erreur lors du chargement des groupes');
    } finally {
      setIsLoading(false);
    }
  };

  const loadAvailableCompanies = async () => {
    try {
      // Utiliser un groupe temporaire pour récupérer toutes les entreprises sans groupe
      const response = await apiClient.get('/api/company-groups/temp/available-companies');
      setAvailableCompanies(response.data);
    } catch (err: any) {
      console.error('Erreur lors du chargement des entreprises:', err);
    }
  };

  const toggleCompanySelection = (companyId: string) => {
    setSelectedCompanyIds(prev =>
      prev.includes(companyId)
        ? prev.filter(id => id !== companyId)
        : [...prev, companyId]
    );
  };

  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) {
      toast({
        title: "Erreur",
        description: "Le nom du groupe est requis",
        variant: "destructive",
      });
      return;
    }

    try {
      setIsCreating(true);

      // 1. Créer le groupe
      const createResponse = await apiClient.post('/api/company-groups/', {
        group_name: newGroupName,
        description: newGroupDescription || null,
        logo_url: newGroupLogoUrl || null,
      });

      const newGroup = createResponse.data;

      // 2. Ajouter les entreprises sélectionnées au groupe (si il y en a)
      if (selectedCompanyIds.length > 0) {
        try {
          await apiClient.post(`/api/company-groups/${newGroup.id}/companies/bulk`, {
            company_ids: selectedCompanyIds,
          });

          toast({
            title: "Groupe créé",
            description: `Le groupe "${newGroupName}" a été créé avec ${selectedCompanyIds.length} entreprise(s)`,
          });
        } catch (bulkErr: any) {
          console.error('Erreur lors de l\'ajout des entreprises:', bulkErr);
          toast({
            title: "Groupe créé avec avertissement",
            description: `Le groupe "${newGroupName}" a été créé, mais certaines entreprises n'ont pas pu être ajoutées`,
            variant: "default",
          });
        }
      } else {
        toast({
          title: "Groupe créé",
          description: `Le groupe "${newGroupName}" a été créé avec succès`,
        });
      }

      // Réinitialiser le formulaire
      setNewGroupName('');
      setNewGroupDescription('');
      setNewGroupLogoUrl(null);
      setSelectedCompanyIds([]);
      setIsCreateDialogOpen(false);

      // Recharger la liste
      loadGroups();
    } catch (err: any) {
      console.error('Erreur lors de la création du groupe:', err);
      toast({
        title: "Erreur",
        description: err.response?.data?.detail || 'Erreur lors de la création du groupe',
        variant: "destructive",
      });
    } finally {
      setIsCreating(false);
    }
  };

  // Charger les entreprises disponibles quand le dialog s'ouvre
  useEffect(() => {
    if (isCreateDialogOpen) {
      loadAvailableCompanies();
    }
  }, [isCreateDialogOpen]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Groupes d'Entreprises</h1>
          <p className="text-muted-foreground">
            Gérez les groupes et holdings regroupant plusieurs entreprises
          </p>
        </div>
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Nouveau Groupe
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Créer un nouveau groupe</DialogTitle>
              <DialogDescription>
                Créez un groupe pour regrouper plusieurs entreprises (holding, enseigne, etc.)
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <LogoUploader
                  currentLogoUrl={newGroupLogoUrl}
                  entityType="group"
                  onLogoChange={setNewGroupLogoUrl}
                  size="md"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="group-name">Nom du groupe *</Label>
                <Input
                  id="group-name"
                  placeholder="Ex: Groupe ABC, Holding XYZ..."
                  value={newGroupName}
                  onChange={(e) => setNewGroupName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="group-description">Description</Label>
                <Textarea
                  id="group-description"
                  placeholder="Description du groupe (optionnel)"
                  value={newGroupDescription}
                  onChange={(e) => setNewGroupDescription(e.target.value)}
                  rows={3}
                />
              </div>

              {/* Sélection des entreprises */}
              <div className="space-y-2 border-t pt-4">
                <Label>Entreprises à ajouter (optionnel)</Label>
                <p className="text-sm text-muted-foreground">
                  Sélectionnez les entreprises à inclure dans ce groupe
                </p>
                {availableCompanies.length === 0 ? (
                  <p className="text-sm text-muted-foreground italic py-4">
                    Aucune entreprise disponible (toutes sont déjà assignées à des groupes)
                  </p>
                ) : (
                  <div className="border rounded-lg max-h-60 overflow-y-auto">
                    {availableCompanies.map((company) => (
                      <label
                        key={company.id}
                        className="flex items-center gap-3 p-3 hover:bg-muted/50 cursor-pointer border-b last:border-b-0"
                      >
                        <input
                          type="checkbox"
                          checked={selectedCompanyIds.includes(company.id)}
                          onChange={() => toggleCompanySelection(company.id)}
                          className="w-4 h-4 text-primary border-gray-300 rounded focus:ring-2 focus:ring-primary"
                        />
                        <div className="flex-1">
                          <p className="font-medium">{company.company_name}</p>
                          {company.siret && (
                            <p className="text-xs text-muted-foreground font-mono">
                              {company.siret}
                            </p>
                          )}
                        </div>
                      </label>
                    ))}
                  </div>
                )}
                {selectedCompanyIds.length > 0 && (
                  <p className="text-sm text-primary font-medium">
                    {selectedCompanyIds.length} entreprise(s) sélectionnée(s)
                  </p>
                )}
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                Annuler
              </Button>
              <Button onClick={handleCreateGroup} disabled={isCreating}>
                {isCreating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Création...
                  </>
                ) : (
                  'Créer le groupe'
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Liste des groupes */}
      {groups.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Building2 className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">Aucun groupe créé</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Créez votre premier groupe pour regrouper plusieurs entreprises
            </p>
            <Button onClick={() => setIsCreateDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Créer un groupe
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {groups.map((group) => (
            <Card
              key={group.id}
              className="cursor-pointer hover:shadow-lg transition-shadow"
              onClick={() => navigate(`/super-admin/groups/${group.id}`)}
            >
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <Building2 className="h-5 w-5 text-primary" />
                    <CardTitle className="text-lg">{group.group_name}</CardTitle>
                  </div>
                  <ChevronRight className="h-5 w-5 text-muted-foreground" />
                </div>
                {group.description && (
                  <CardDescription className="line-clamp-2">
                    {group.description}
                  </CardDescription>
                )}
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground flex items-center gap-1">
                      <Building2 className="h-4 w-4" />
                      Entreprises
                    </span>
                    <span className="font-semibold">{group.company_count}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground flex items-center gap-1">
                      <Users className="h-4 w-4" />
                      Employés total
                    </span>
                    <span className="font-semibold">{group.total_employees}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground flex items-center gap-1">
                      <TrendingUp className="h-4 w-4" />
                      Créé le
                    </span>
                    <span className="text-xs">
                      {new Date(group.created_at).toLocaleDateString('fr-FR')}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
