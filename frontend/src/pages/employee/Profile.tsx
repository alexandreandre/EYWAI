// src/pages/employee/Profile.tsx (COMPLET ET CORRIGÉ)

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/contexts/AuthContext';
import { Home, Phone, Mail, ShieldAlert, Banknote, Users, Pencil, Loader2, FileText, Percent, HeartHandshake, Umbrella } from 'lucide-react';
import apiClient from '@/api/apiClient';
import { useToast } from '@/components/ui/use-toast';
import { z } from "zod"; // Importer Zod pour la validation optionnelle
import { useForm } from 'react-hook-form'; // Importer react-hook-form
import { zodResolver } from '@hookform/resolvers/zod'; // Importer le resolver Zod
import { Form, FormControl, FormField, FormItem, FormMessage } from '@/components/ui/form'; // Importer les composants Form

// --- ✅ INTERFACE ALIGNÉE SUR FullEmployee ---
interface EmployeeData {
  id: string;
  employee_folder_name: string; // Ajouté pour correspondre à FullEmployee
  first_name: string;
  last_name: string;
  email?: string | null;
  nir?: string | null; // Ajouté pour correspondre
  date_naissance?: string | null; // Date en string
  lieu_naissance?: string | null; // Ajouté
  nationalite?: string | null; // Ajouté
  phone_number?: string | null; // Champ ajouté explicitement
  adresse?: {
    rue?: string;
    code_postal?: string;
    ville?: string;
  } | null;
  coordonnees_bancaires?: {
    iban?: string;
    // bic?: string; // Si tu l'as dans FullEmployee, ajoute-le
  } | null;
  hire_date?: string | null; // Date en string
  contract_type?: string | null;
  statut?: string | null;
  job_title?: string | null;
  periode_essai?: Record<string, any> | null; // Utiliser Record pour un objet flexible
  is_temps_partiel?: boolean | null;
  duree_hebdomadaire?: number | null;
  salaire_de_base?: Record<string, any> | null;
  classification_conventionnelle?: Record<string, any> | null;
  elements_variables?: Record<string, any> | null;
  avantages_en_nature?: Record<string, any> | null;
  specificites_paie?: {
    is_alsace_moselle?: boolean; // Ajouté pour correspondre
    prelevement_a_la_source?: {
      is_personnalise?: boolean;
      taux?: number | null; // Taux peut être null
    };
    transport?: { // Ajouté
      abonnement_mensuel_total?: number;
    };
    titres_restaurant?: { // Ajouté
        beneficie?: boolean;
        nombre_par_mois?: number;
    };
    mutuelle?: {
      adhesion?: boolean; // Ajouté
      lignes_specifiques?: {
        id: string;
        libelle: string;
        montant_salarial?: number; // Ajouté
        montant_patronal?: number; // Ajouté
        part_patronale_soumise_a_csg?: boolean; // Ajouté
      }[];
    };
    prevoyance?: {
      adhesion?: boolean;
      lignes_specifiques?: {
        id: string;
        libelle: string;
        salarial?: number; // Ajouté
        patronal?: number; // Ajouté
        forfait_social?: number; // Ajouté
      }[];
    };
  } | null;
}

// --- ✅ Schéma Zod pour la validation (basé sur UpdateEmployee) ---
const profileUpdateSchema = z.object({
  // first_name: z.string().min(1, "Prénom requis").optional(), // Généralement non modifiable par l'employé
  // last_name: z.string().min(1, "Nom requis").optional(),   // Généralement non modifiable par l'employé
  email: z.string().email("Email invalide").optional().or(z.literal('')), // Permet vide si optionnel
  phone_number: z.string().optional().or(z.literal('')), // Permet vide si optionnel
  adresse: z.object({
    rue: z.string().optional().or(z.literal('')),
    code_postal: z.string().optional().or(z.literal('')),
    ville: z.string().optional().or(z.literal('')),
  }).optional().nullable(),
});

type ProfileUpdateFormData = z.infer<typeof profileUpdateSchema>;

export default function ProfilePage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [isEditing, setIsEditing] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false); // État pour le bouton de sauvegarde
  const [profile, setProfile] = useState<EmployeeData | null>(null);

  // Initialisation de react-hook-form
  const form = useForm<ProfileUpdateFormData>({
    resolver: zodResolver(profileUpdateSchema),
    defaultValues: { // Sera peuplé par useEffect
      email: '',
      phone_number: '',
      adresse: {
        rue: '',
        code_postal: '',
        ville: '',
      }
    },
  });

  // Fonction pour formater les dates (inchangée)
  const formatDate = (dateString: string | undefined | null) => {
    if (!dateString) return 'N/A';
    try {
      // Vérifie si c'est une date valide avant de formater
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return 'Date invalide';
      return date.toLocaleDateString('fr-FR');
    } catch (e) {
      return 'Date invalide';
    }
  };

  // Charger le profil
  useEffect(() => {
    if (user?.id) {
      const fetchProfile = async () => {
        setIsLoading(true);
        try {
          const response = await apiClient.get<EmployeeData>(`/api/employees/${user.id}`);
          console.log("Données brutes reçues:", response.data);
          setProfile(response.data);
          // ✅ Peuple react-hook-form avec les données chargées
          form.reset({
            email: response.data.email || '',
            phone_number: response.data.phone_number || '',
            adresse: response.data.adresse ? {
              rue: response.data.adresse.rue || '',
              code_postal: response.data.adresse.code_postal || '',
              ville: response.data.adresse.ville || '',
            } : null, // Mettre null si l'adresse est nulle
          });
        } catch (error) {
          console.error("Erreur lors du chargement du profil", error);
          toast({ title: "Erreur", description: "Impossible de charger les informations.", variant: "destructive" });
        } finally {
          setIsLoading(false);
        }
      };
      fetchProfile();
    }
  }, [user?.id, toast, form]); // form ajouté aux dépendances

  // ✅ Soumission du formulaire via react-hook-form
  const onSubmit = async (data: ProfileUpdateFormData) => {
    if (!profile) return;
    setIsSaving(true);
    console.log("Données envoyées pour mise à jour:", data); // Debug
    try {
        // Le payload 'data' correspond maintenant au schéma UpdateEmployee
        await apiClient.put(`/api/employees/${profile.id}`, data);
        toast({ title: "Succès", description: "Votre demande de modification a été soumise." });
        setIsEditing(false);
        // Recharger les données pour afficher les nouvelles valeurs (même si validation RH)
        const response = await apiClient.get<EmployeeData>(`/api/employees/${user.id}`);
        setProfile(response.data);
        form.reset(data); // Met à jour les defaultValues du form
    } catch(error: any) {
         console.error("Erreur lors de la sauvegarde du profil", error);
         const errorMsg = error.response?.data?.detail || "Impossible de sauvegarder les modifications.";
         toast({ title: "Erreur", description: errorMsg, variant: "destructive" });
    } finally {
        setIsSaving(false);
    }
  };

  // Helper pour obtenir la première ligne de mutuelle/prévoyance (simplification)
  const getFirstSocialLine = (type: 'mutuelle' | 'prevoyance') => {
    const lines = profile?.specificites_paie?.[type]?.lignes_specifiques;
    return lines && lines.length > 0 ? lines[0] : null;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Mon Profil</h1>
        {!isEditing ? (
          <Button onClick={() => setIsEditing(true)}><Pencil className="mr-2 h-4 w-4" /> Demander une modification</Button>
        ) : (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => { setIsEditing(false); form.reset(); }} disabled={isSaving}>Annuler</Button>
            {/* Le bouton Save est maintenant géré par le Form */}
          </div>
        )}
      </div>

      {isLoading && !profile && (
        <div className="flex justify-center items-center h-64">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      )}

      {/* --- Section Contrat --- */}
      {profile && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center"><FileText className="mr-2 h-5 w-5" /> Mon Contrat</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <Label className="text-xs text-muted-foreground">Poste</Label>
                <p className="font-semibold">{profile.job_title || 'Non renseigné'}</p>
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Type de contrat</Label>
                <p className="font-semibold">{profile.contract_type || 'Non renseigné'}</p>
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Date d'arrivée</Label>
                <p className="font-semibold">{formatDate(profile.hire_date)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* --- Section Informations Personnelles (Utilise react-hook-form) --- */}
      {profile && (
        // ✅ Envelopper dans le composant Form
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <Card>
              <CardHeader>
                <CardTitle>Informations Personnelles</CardTitle>
                <CardDescription>Vos informations de contact. Les modifications sont soumises à validation.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Adresse */}
                <div className="flex items-center gap-4">
                  <Home className="h-5 w-5 text-muted-foreground" />
                  <div className="grid w-full gap-1.5">
                    <Label>Adresse Postale</Label>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      <FormField
                        control={form.control}
                        name="adresse.rue"
                        render={({ field }) => (
                          <FormItem>
                            <FormControl><Input placeholder="Rue" {...field} value={field.value ?? ''} disabled={!isEditing} /></FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="adresse.code_postal"
                        render={({ field }) => (
                          <FormItem>
                            <FormControl><Input placeholder="Code Postal" {...field} value={field.value ?? ''} disabled={!isEditing} /></FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="adresse.ville"
                        render={({ field }) => (
                          <FormItem>
                            <FormControl><Input placeholder="Ville" {...field} value={field.value ?? ''} disabled={!isEditing} /></FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                  </div>
                </div>
                {/* Téléphone */}
                <div className="flex items-center gap-4">
                  <Phone className="h-5 w-5 text-muted-foreground" />
                  <div className="grid w-full gap-1.5">
                    <FormField
                      control={form.control}
                      name="phone_number"
                      render={({ field }) => (
                        <FormItem>
                          <Label htmlFor="phone">Téléphone</Label>
                          <FormControl><Input id="phone" {...field} value={field.value ?? ''} disabled={!isEditing} /></FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </div>
                {/* Email Personnel */}
                <div className="flex items-center gap-4">
                  <Mail className="h-5 w-5 text-muted-foreground" />
                  <div className="grid w-full gap-1.5">
                    <FormField
                      control={form.control}
                      name="email"
                      render={({ field }) => (
                        <FormItem>
                          <Label htmlFor="personalEmail">Email Personnel</Label>
                          <FormControl><Input id="personalEmail" type="email" {...field} value={field.value ?? ''} disabled={!isEditing} /></FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </div>
              </CardContent>
              {/* ✅ Bouton de sauvegarde à l'intérieur du formulaire */}
              {isEditing && (
                <CardContent>
                    <Button type="submit" disabled={isSaving}>
                        {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Soumettre pour validation
                    </Button>
                </CardContent>
              )}
            </Card>
          </form>
        </Form>
      )}

      {/* --- Section Prévoyance, Mutuelle, PAS --- */}
      {profile && (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center"><Percent className="mr-2 h-5 w-5" /> Prélèvement à la Source</CardTitle>
            </CardHeader>
            <CardContent>
              <Label>Taux d'imposition</Label>
              <p className="text-2xl font-bold">
                {profile.specificites_paie?.prelevement_a_la_source?.taux != null
                  ? `${profile.specificites_paie.prelevement_a_la_source.taux}%`
                  : 'Non communiqué'}
              </p>
              <p className="text-xs text-muted-foreground mt-2">Ce taux est transmis par l'administration fiscale.</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center"><HeartHandshake className="mr-2 h-5 w-5" /> Mutuelle</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Label>Organisme</Label>
              <p className="font-semibold">{getFirstSocialLine('mutuelle')?.libelle || 'Non affilié'}</p>
              <Label>N° Adhérent</Label>
              <p className="font-semibold">N/A</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center"><Umbrella className="mr-2 h-5 w-5" /> Prévoyance</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Label>Organisme</Label>
              <p className="font-semibold">
                  {profile.specificites_paie?.prevoyance?.adhesion
                      ? (getFirstSocialLine('prevoyance')?.libelle || 'Affilié (détails N/A)')
                      : 'Non affilié'}
              </p>
              <Label>N° Adhérent</Label>
              <p className="font-semibold">N/A</p>
            </CardContent>
          </Card>
        </div>
      )}

       {/* --- Section Données Bancaires --- */}
      {profile && (
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center"><Banknote className="mr-2 h-5 w-5" /> Données Bancaires</CardTitle>
              </CardHeader>
              <CardContent>
                <Label>IBAN actuel</Label>
                {/* Sécurisation : Affiche seulement les 4 derniers chiffres */}
                <Input value={profile.coordonnees_bancaires?.iban ? `FR** **** **** **** **** ***${profile.coordonnees_bancaires.iban.slice(-4)}` : ''} disabled />
                <p className="text-xs text-muted-foreground mt-2">Pour modifier votre IBAN, veuillez contacter le service RH avec un nouveau RIB.</p>
              </CardContent>
            </Card>
            {/* --- Section Contact Urgence --- */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center"><ShieldAlert className="mr-2 h-5 w-5" /> Contact d'Urgence</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                 <div className="grid w-full gap-1.5">
                  <Label htmlFor="emergencyContact">Personne à contacter (Bientôt disponible)</Label>
                  {/* TODO: Ajouter ces champs au backend (FullEmployee et UpdateEmployee) */}
                  <Input id="emergencyContact" value="Fonctionnalité à venir" disabled />
                </div>
              </CardContent>
            </Card>
          </div>
      )}

      {/* --- Section Famille --- */}
      {profile && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center"><Users className="mr-2 h-5 w-5" /> Famille & Ayants Droit</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">Pour déclarer un nouveau membre (conjoint, enfant), veuillez contacter directement le service RH.</p>
               {/* TODO: Potentiellement ajouter un tableau ici si les données sont disponibles */}
            </CardContent>
          </Card>
      )}
    </div>
  );
}