import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import apiClient from '../api/apiClient';

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Search, PlusCircle, Eye, Loader2, ChevronRight, Upload, FileText, Trash2, UserMinus, Landmark } from "lucide-react";
import * as ribAlertsApi from "@/api/ribAlerts";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea"; // Pour les champs JSON
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useFieldArray } from "react-hook-form";
import { mutuelleTypesApi, MutuelleType } from "@/api/mutuelleTypes";
import * as collectiveAgreementsApi from "@/api/collectiveAgreements";


// Interface pour la liste (simple)
interface EmployeeListItem {
  id: string;
  first_name: string;
  last_name: string;
  job_title: string | null;
  contract_type: string | null;
  hire_date: string | null;
  employment_status?: string | null;
  current_exit_id?: string | null;
}

// Schéma de validation Zod complet
const formSchema = z.object({
  // --- SECTION SALARIÉ (COMPLÉTÉE) ---
  first_name: z.string().min(2, { message: "Prénom requis." }),
  last_name: z.string().min(2, { message: "Nom requis." }),
  email: z.string().email({ message: "Adresse e-mail invalide." }),
  nir: z.string().length(15, { message: "Le NIR doit faire 15 chiffres." }),
  date_naissance: z.string().refine((d) => d, { message: "Date requise." }),
  lieu_naissance: z.string().min(2, { message: "Lieu de naissance requis." }),
  nationalite: z.string().min(2, { message: "Nationalité requise." }),
  adresse: z.object({
    rue: z.string().min(2, { message: "Rue requise." }),
    code_postal: z.string().min(5, { message: "Code postal requis." }),
    ville: z.string().min(2, { message: "Ville requise." }),
  }),
  coordonnees_bancaires: z.object({
    iban: z.string().min(14, { message: "IBAN invalide." }),
    bic: z.string().min(8, { message: "BIC invalide." }),
  }),
  
  // --- SECTION TITRE DE SÉJOUR (OPTIONNEL) ---
  is_subject_to_residence_permit: z.boolean().optional(),
  residence_permit_expiry_date: z.string().optional(),
  residence_permit_type: z.string().optional(),
  residence_permit_number: z.string().optional(),

  // --- SECTION CONTRAT (COMPLÉTÉE) ---
  hire_date: z.string().refine((d) => !isNaN(Date.parse(d)), { message: "Date invalide." }),
  contract_type: z.string().min(2),
  statut: z.string().min(2),
  job_title: z.string().min(2),
  // periode_essai: z.object({
  //   duree_initiale: z.coerce.number().int().positive(),
  //   unite: z.string(),
  //   renouvellement_possible: z.boolean(),
  // }),
  is_temps_partiel: z.boolean(),
  duree_hebdomadaire: z.coerce.number().positive(),
  
  // --- SECTION RÉMUNÉRATION (COMPLÉTÉE) ---
  salaire_de_base: z.object({
    valeur: z.coerce.number().positive({ message: "Le salaire doit être positif." })
  }),
  classification_conventionnelle: z.object({
    groupe_emploi: z.string().min(1, { message: "Groupe requis." }),
    classe_emploi: z.coerce.number().int(),
    coefficient: z.coerce.number().int().positive({ message: "Coeff. requis." }),
  }),
  collective_agreement_id: z.string().nullable().optional(),

  avantages_en_nature: z.object({
    repas: z.object({
      nombre_par_mois: z.coerce.number().int().min(0),
    }),
    logement: z.object({
      beneficie: z.boolean(),
    }),
    vehicule: z.object({
      beneficie: z.boolean(),
    }),
  }),
  
   // --- SECTION SPÉCIFICITÉS (DÉTAILLÉE) ---
  specificites_paie: z.object({
    is_alsace_moselle: z.boolean(),
    prelevement_a_la_source: z.object({
      is_personnalise: z.boolean(),
      taux: z.coerce.number().min(0).max(100).optional(),
    }),
    transport: z.object({ abonnement_mensuel_total: z.coerce.number().min(0) }),
    titres_restaurant: z.object({
      beneficie: z.boolean(),
      nombre_par_mois: z.coerce.number().int().min(0),
    }),
    mutuelle: z.object({
      mutuelle_type_ids: z.array(z.string()).optional(),
      // Rétrocompatibilité : garder lignes_specifiques pour les anciens employés
      lignes_specifiques: z.array(
        z.object({
          id: z.string().min(1),
          libelle: z.string().min(2),
          montant_salarial: z.coerce.number(),
          montant_patronal: z.coerce.number(),
          part_patronale_soumise_a_csg: z.boolean(),
        })
      ).optional(),
    }),
    // Prévoyance : une adhésion simple, et une liste optionnelle pour les cadres
    prevoyance: z.object({
      adhesion: z.boolean(),
      lignes_specifiques: z.array(
        z.object({
          id: z.string(),
          libelle: z.string().min(2, { message: "Libellé requis." }),
          salarial: z.coerce.number(),
          patronal: z.coerce.number(),
          forfait_social: z.coerce.number(),
        })
      ).optional(),
    }),
  }),
}).superRefine((data, ctx) => {
  // Règle de validation personnalisée pour la prévoyance
  if (data.statut?.toLowerCase() === 'cadre' && data.specificites_paie.prevoyance.adhesion) {
    if (!data.specificites_paie.prevoyance.lignes_specifiques || data.specificites_paie.prevoyance.lignes_specifiques.length === 0) {
      // Si aucune ligne n'est ajoutée pour un cadre, on ne met pas d'erreur pour l'instant,
      // mais on pourrait en ajouter une ici si c'était obligatoire.
      return;
    }
    // On vérifie chaque ligne de prévoyance
    data.specificites_paie.prevoyance.lignes_specifiques.forEach((ligne, index) => {
      if (!ligne.libelle) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Le libellé est requis.",
          path: [`specificites_paie`, `prevoyance`, `lignes_specifiques`, index, `libelle`],
        });
      }
    });
  }
});


const getContractBadge = (type: string) => {
  const variants = { CDI: "bg-blue-100 text-blue-800", CDD: "bg-purple-100 text-purple-800" };
  return <Badge variant="default" className={variants[type as keyof typeof variants] || "bg-gray-100 text-gray-800"}>{type}</Badge>;
};

// Fonction pour traduire les noms de champs techniques en français
const translateFieldName = (fieldPath: string): string => {
  const translations: Record<string, string> = {
    'email': 'Email',
    'nir': 'Numéro de sécurité sociale',
    'first_name': 'Prénom',
    'last_name': 'Nom',
    'date_naissance': 'Date de naissance',
    'lieu_naissance': 'Lieu de naissance',
    'nationalite': 'Nationalité',
    'hire_date': 'Date d\'embauche',
    'job_title': 'Intitulé du poste',
    'contract_type': 'Type de contrat',
    'statut': 'Statut',
    'adresse.rue': 'Rue',
    'adresse.code_postal': 'Code postal',
    'adresse.ville': 'Ville',
    'coordonnees_bancaires.iban': 'IBAN',
    'coordonnees_bancaires.bic': 'BIC',
    'salaire_de_base.valeur': 'Salaire de base',
    'duree_hebdomadaire': 'Durée hebdomadaire',
  };
  return translations[fieldPath] || fieldPath;
};

export default function Employees() {
  const [employees, setEmployees] = useState<EmployeeListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [employmentStatusFilter, setEmploymentStatusFilter] = useState<string>("actif");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null); // Pour les erreurs du backend
  const [validationErrorSummary, setValidationErrorSummary] = useState<string[] | null>(null); // Pour le résumé des erreurs de validation
  const [serverFieldErrors, setServerFieldErrors] = useState<Record<string, string> | null>(null); // Pour les erreurs de champs du serveur

  // États pour le dépôt de contrat PDF
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState<string | null>(null);
  const [extractionSuccess, setExtractionSuccess] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  // États pour le dépôt de RIB PDF
  const [uploadedRibFile, setUploadedRibFile] = useState<File | null>(null);
  const [isExtractingRib, setIsExtractingRib] = useState(false);
  const [ribExtractionError, setRibExtractionError] = useState<string | null>(null);
  const [ribExtractionSuccess, setRibExtractionSuccess] = useState(false);
  const [isRibDragging, setIsRibDragging] = useState(false);

  // États pour le dépôt de pièce d'identité (carte d'identité, passeport ou titre de séjour)
  const [uploadedIdFile, setUploadedIdFile] = useState<File | null>(null);
  const [isIdDragging, setIsIdDragging] = useState(false);
  // État pour le type de document fourni (pièce d'identité ou titre de séjour)
  const [identityDocumentType, setIdentityDocumentType] = useState<"identity" | "residence_permit">("identity");

  // États pour le dépôt de questionnaire d'embauche PDF
  const [uploadedQuestionnaireFile, setUploadedQuestionnaireFile] = useState<File | null>(null);
  const [isExtractingQuestionnaire, setIsExtractingQuestionnaire] = useState(false);
  const [questionnaireExtractionError, setQuestionnaireExtractionError] = useState<string | null>(null);
  const [questionnaireExtractionSuccess, setQuestionnaireExtractionSuccess] = useState(false);
  const [isQuestionnaireDragging, setIsQuestionnaireDragging] = useState(false);

  // État pour la génération automatique de contrat PDF
  const [generatePdfContract, setGeneratePdfContract] = useState(false);

  const [ribAlerts, setRibAlerts] = useState<ribAlertsApi.RibAlert[]>([]);

  // Conventions collectives de l'entreprise (pour le sélecteur)
  const [companyAgreements, setCompanyAgreements] = useState<collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails[]>([]);
  // Grille de classification pour la convention sélectionnée
  const [classificationsCc, setClassificationsCc] = useState<collectiveAgreementsApi.ClassificationConventionnelle[]>([]);

  const navigate = useNavigate();

  // Formulaire avec toutes les valeurs par défaut (déclaré avant les useEffect qui l'utilisent)
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      first_name: "", last_name: "", email: "", nir: "", date_naissance: "",
      lieu_naissance: "",       nationalite: "Française",
      adresse: { rue: "", code_postal: "", ville: "" },
      coordonnees_bancaires: { iban: "", bic: "" },
      // Titre de séjour (optionnel)
      is_subject_to_residence_permit: false,
      residence_permit_expiry_date: "",
      residence_permit_type: "",
      residence_permit_number: "",
      hire_date: new Date().toISOString().split('T')[0],
      contract_type: "CDI", statut: "Non-Cadre", job_title: "",
      // periode_essai: { duree_initiale: 2, unite: "mois", renouvellement_possible: true },
      is_temps_partiel: false,
      duree_hebdomadaire: 39, 
      salaire_de_base: {
        valeur: 2365.66
      },
      classification_conventionnelle: {
        groupe_emploi: "C",
        classe_emploi: 6,
        coefficient: 240
      },
      collective_agreement_id: null as string | null,
      avantages_en_nature: {
        repas: { nombre_par_mois: 0 },
        logement: { beneficie: false },
        vehicule: { beneficie: false },
      },
      
      specificites_paie: {
        is_alsace_moselle: false,
        prelevement_a_la_source: {
          is_personnalise: false,
          taux: 0,
        },
        transport: {
          abonnement_mensuel_total: 0,
        },
        titres_restaurant: {
          beneficie: true,
          nombre_par_mois: 0,
        },
        mutuelle: {
          mutuelle_type_ids: [],
          lignes_specifiques: [],
        },
        prevoyance: {
          adhesion: true,
          lignes_specifiques: [],
        },
      },
    },
  });

  // Charger les conventions collectives de l'entreprise à l'ouverture du dialog
  useEffect(() => {
    if (isDialogOpen) {
      collectiveAgreementsApi.getMyCompanyAgreements()
        .then((res) => setCompanyAgreements(res.data || []))
        .catch(() => setCompanyAgreements([]));
    }
  }, [isDialogOpen]);

  // Charger les classifications quand une convention collective est sélectionnée
  const selectedCcId = form.watch("collective_agreement_id");
  useEffect(() => {
    if (selectedCcId && selectedCcId !== "__aucune__") {
      collectiveAgreementsApi.getClassifications(selectedCcId)
        .then((res) => {
          const list = res.data || [];
          setClassificationsCc(list);
          // Pré-sélectionner la première classification si la valeur actuelle n'est pas dans la grille
          if (list.length > 0) {
            const current = form.getValues("classification_conventionnelle");
            const currentKey = current ? `${current.groupe_emploi}-${current.classe_emploi}-${current.coefficient}` : "";
            const exists = list.some((c) => `${c.groupe_emploi}-${c.classe_emploi}-${c.coefficient}` === currentKey);
            if (!exists) {
              form.setValue("classification_conventionnelle", { groupe_emploi: list[0].groupe_emploi, classe_emploi: list[0].classe_emploi, coefficient: list[0].coefficient });
            }
          }
        })
        .catch(() => setClassificationsCc([]));
    } else {
      setClassificationsCc([]);
    }
  }, [selectedCcId]);

  // Charger les mutuelles disponibles
  const [availableMutuelles, setAvailableMutuelles] = useState<MutuelleType[]>([]);
  const [loadingMutuelles, setLoadingMutuelles] = useState(false);

  useEffect(() => {
    const loadMutuelles = async () => {
      try {
        setLoadingMutuelles(true);
        const mutuelles = await mutuelleTypesApi.getMutuelleTypes();
        setAvailableMutuelles(mutuelles.filter(m => m.is_active));
      } catch (error) {
        console.error("Erreur lors du chargement des mutuelles:", error);
      } finally {
        setLoadingMutuelles(false);
      }
    };
    loadMutuelles();
  }, []);

  const { fields: mutuelleFields, append: appendMutuelle, remove: removeMutuelle } = useFieldArray({
    control: form.control,
    name: "specificites_paie.mutuelle.lignes_specifiques",
  });

  const { fields: prevoyanceFields, append: appendPrevoyance, remove: removePrevoyance } = useFieldArray({
    control: form.control,
    name: "specificites_paie.prevoyance.lignes_specifiques",
  });

  const isCadre = form.watch("statut")?.toLowerCase() === 'cadre';

  const fetchEmployees = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get<EmployeeListItem[]>('/api/employees');
      setEmployees(response.data);
      setError(null);
    } catch (err) {
      setError("Erreur : Impossible de récupérer la liste des collaborateurs.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchEmployees(); }, []);

  useEffect(() => {
    ribAlertsApi.getRibAlerts({ is_read: false, is_resolved: false, limit: 5 })
      .then((r) => setRibAlerts(r.data.alerts || []))
      .catch(() => setRibAlerts([]));
  }, []);

  // Fonction pour traiter un fichier PDF (utilisée par upload et drag & drop)
  const processPdfFile = async (file: File) => {
    // Vérifier que c'est bien un PDF
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setExtractionError("Veuillez sélectionner un fichier PDF.");
      return;
    }

    setUploadedFile(file);
    setIsExtracting(true);
    setExtractionError(null);
    setExtractionSuccess(false);

    try {
      // Créer un FormData pour envoyer le fichier
      const formData = new FormData();
      formData.append('file', file);

      // Appeler l'API d'extraction
      const response = await apiClient.post('/api/contract-parser/extract-from-pdf', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const extractedData = response.data.extracted_data;
      const warnings = response.data.warnings || [];

      console.log("Données extraites du PDF :", extractedData);

      // Préremplir le formulaire avec les données extraites
      const mergeFormValues = (extracted: any) => {
        const currentValues = form.getValues();

        // Fonction récursive pour fusionner les objets
        const deepMerge = (current: any, extracted: any): any => {
          if (!extracted || typeof extracted !== 'object') return current;

          const result = { ...current };
          for (const key in extracted) {
            if (extracted[key] !== undefined && extracted[key] !== null && extracted[key] !== '') {
              if (typeof extracted[key] === 'object' && !Array.isArray(extracted[key]) && current[key]) {
                result[key] = deepMerge(current[key], extracted[key]);
              } else {
                result[key] = extracted[key];
              }
            }
          }
          return result;
        };

        return deepMerge(currentValues, extracted);
      };

      const mergedValues = mergeFormValues(extractedData);
      if (mergedValues.specificites_paie?.mutuelle?.lignes_specifiques) {
        mergedValues.specificites_paie.mutuelle.lignes_specifiques = 
          mergedValues.specificites_paie.mutuelle.lignes_specifiques.map((ligne: any, index: number) => ({
            ...ligne,
            id: ligne.id || `mutuelle_extracted_${Date.now() + index}` // Garantit un ID
          }));
      }
      
      if (mergedValues.specificites_paie?.prevoyance?.lignes_specifiques) {
         mergedValues.specificites_paie.prevoyance.lignes_specifiques = 
          mergedValues.specificites_paie.prevoyance.lignes_specifiques.map((ligne: any, index: number) => ({
            ...ligne,
            id: ligne.id || `prevoyance_extracted_${Date.now() + index}` // Garantit un ID
          }));
      }

      // Réinitialiser le formulaire avec les nouvelles valeurs
      form.reset(mergedValues);

      setExtractionSuccess(true);

      // Afficher les avertissements s'il y en a
      if (warnings.length > 0) {
        console.warn("Avertissements lors de l'extraction :", warnings);
        setExtractionError(`Extraction réussie avec des avertissements : ${warnings.join(', ')}`);
      }

    } catch (error: any) {
      console.error("Erreur lors de l'extraction du PDF :", error);
      const errorMessage = error.response?.data?.detail || "Erreur lors de l'extraction du PDF. Veuillez réessayer.";
      setExtractionError(errorMessage);
    } finally {
      setIsExtracting(false);
    }
  };

  // Fonction pour extraire les données d'un contrat PDF (upload via clic)
  const handlePdfUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await processPdfFile(file);
  };

  // Gestion du drag & drop
  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const file = files[0];
      await processPdfFile(file);
    }
  };

  // Fonction pour traiter un fichier RIB PDF (utilisée par upload et drag & drop)
  const processRibPdfFile = async (file: File) => {
    // Vérifier que c'est bien un PDF
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setRibExtractionError("Veuillez sélectionner un fichier PDF.");
      return;
    }

    setUploadedRibFile(file);
    setIsExtractingRib(true);
    setRibExtractionError(null);
    setRibExtractionSuccess(false);

    try {
      // Créer un FormData pour envoyer le fichier
      const formData = new FormData();
      formData.append('file', file);

      // Appeler l'API d'extraction du RIB
      const response = await apiClient.post('/api/contract-parser/extract-rib-from-pdf', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const extractedData = response.data.extracted_data;
      const warnings = response.data.warnings || [];

      console.log("Données bancaires extraites du RIB :", extractedData);

      // Préremplir les champs bancaires avec les données extraites
      const currentValues = form.getValues();
      const updatedValues = {
        ...currentValues,
        coordonnees_bancaires: {
          iban: extractedData.iban || currentValues.coordonnees_bancaires?.iban || '',
          bic: extractedData.bic || currentValues.coordonnees_bancaires?.bic || '',
        }
      };

      // Réinitialiser le formulaire avec les nouvelles valeurs
      form.reset(updatedValues);

      setRibExtractionSuccess(true);

      // Afficher les avertissements s'il y en a
      if (warnings.length > 0) {
        console.warn("Avertissements lors de l'extraction du RIB :", warnings);
        setRibExtractionError(`Extraction réussie avec des avertissements : ${warnings.join(', ')}`);
      }

    } catch (error: any) {
      console.error("Erreur lors de l'extraction du RIB :", error);
      const errorMessage = error.response?.data?.detail || "Erreur lors de l'extraction du RIB. Veuillez réessayer.";
      setRibExtractionError(errorMessage);
    } finally {
      setIsExtractingRib(false);
    }
  };

  // Fonction pour extraire les données d'un RIB PDF (upload via clic)
  const handleRibPdfUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await processRibPdfFile(file);
  };

  // Gestion du drag & drop pour le RIB
  const handleRibDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsRibDragging(true);
  };

  const handleRibDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsRibDragging(false);
  };

  const handleRibDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsRibDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const file = files[0];
      await processRibPdfFile(file);
    }
  };

  // Fonction pour traiter un fichier de pièce d'identité (PDF ou image)
  const processIdFile = async (file: File) => {
    // Vérifier que c'est bien un PDF ou une image
    const isPdf = file.name.toLowerCase().endsWith('.pdf');
    const isImage = file.type.startsWith('image/') || 
                    file.name.toLowerCase().match(/\.(jpg|jpeg|png|gif|bmp|webp)$/);
    
    if (!isPdf && !isImage) {
      alert("Veuillez sélectionner un fichier PDF ou une image (JPG, PNG, etc.).");
      return;
    }

    setUploadedIdFile(file);
  };

  // Fonction pour uploader la pièce d'identité (upload via clic)
  const handleIdFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await processIdFile(file);
  };

  // Gestion du drag & drop pour la pièce d'identité
  const handleIdDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsIdDragging(true);
  };

  const handleIdDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsIdDragging(false);
  };

  const handleIdDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsIdDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const file = files[0];
      await processIdFile(file);
    }
  };

  // Fonction pour traiter un fichier questionnaire d'embauche PDF (utilisée par upload et drag & drop)
  const processQuestionnairePdfFile = async (file: File) => {
    // Vérifier que c'est bien un PDF
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setQuestionnaireExtractionError("Veuillez sélectionner un fichier PDF.");
      return;
    }

    setUploadedQuestionnaireFile(file);
    setIsExtractingQuestionnaire(true);
    setQuestionnaireExtractionError(null);
    setQuestionnaireExtractionSuccess(false);

    try {
      // Créer un FormData pour envoyer le fichier
      const formData = new FormData();
      formData.append('file', file);

      // Appeler l'API d'extraction du questionnaire
      const response = await apiClient.post('/api/contract-parser/extract-questionnaire-from-pdf', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const extractedData = response.data.extracted_data;
      const warnings = response.data.warnings || [];

      console.log("Données extraites du questionnaire d'embauche :", extractedData);

      // Préremplir le formulaire avec les données extraites
      const mergeFormValues = (extracted: any) => {
        const currentValues = form.getValues();

        // Fonction récursive pour fusionner les objets
        const deepMerge = (current: any, extracted: any): any => {
          if (!extracted || typeof extracted !== 'object') return current;

          const result = { ...current };
          for (const key in extracted) {
            if (extracted[key] !== undefined && extracted[key] !== null && extracted[key] !== '') {
              if (typeof extracted[key] === 'object' && !Array.isArray(extracted[key]) && current[key]) {
                result[key] = deepMerge(current[key], extracted[key]);
              } else {
                result[key] = extracted[key];
              }
            }
          }
          return result;
        };

        return deepMerge(currentValues, extracted);
      };

      const mergedValues = mergeFormValues(extractedData);
      if (mergedValues.specificites_paie?.mutuelle?.lignes_specifiques) {
        mergedValues.specificites_paie.mutuelle.lignes_specifiques = 
          mergedValues.specificites_paie.mutuelle.lignes_specifiques.map((ligne: any, index: number) => ({
            ...ligne,
            id: ligne.id || `mutuelle_extracted_${Date.now() + index}` // Garantit un ID
          }));
      }
      
      if (mergedValues.specificites_paie?.prevoyance?.lignes_specifiques) {
         mergedValues.specificites_paie.prevoyance.lignes_specifiques = 
          mergedValues.specificites_paie.prevoyance.lignes_specifiques.map((ligne: any, index: number) => ({
            ...ligne,
            id: ligne.id || `prevoyance_extracted_${Date.now() + index}` // Garantit un ID
          }));
      }

      // Réinitialiser le formulaire avec les nouvelles valeurs
      form.reset(mergedValues);

      setQuestionnaireExtractionSuccess(true);

      // Afficher les avertissements s'il y en a
      if (warnings.length > 0) {
        console.warn("Avertissements lors de l'extraction du questionnaire :", warnings);
        setQuestionnaireExtractionError(`Extraction réussie avec des avertissements : ${warnings.join(', ')}`);
      }

    } catch (error: any) {
      console.error("Erreur lors de l'extraction du questionnaire :", error);
      const errorMessage = error.response?.data?.detail || "Erreur lors de l'extraction du questionnaire d'embauche. Veuillez réessayer.";
      setQuestionnaireExtractionError(errorMessage);
    } finally {
      setIsExtractingQuestionnaire(false);
    }
  };

  // Fonction pour extraire les données d'un questionnaire PDF (upload via clic)
  const handleQuestionnairePdfUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await processQuestionnairePdfFile(file);
  };

  // Gestion du drag & drop pour le questionnaire
  const handleQuestionnaireDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsQuestionnaireDragging(true);
  };

  const handleQuestionnaireDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsQuestionnaireDragging(false);
  };

  const handleQuestionnaireDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsQuestionnaireDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const file = files[0];
      await processQuestionnairePdfFile(file);
    }
  };

  const onSubmit = async (values: z.infer<typeof formSchema>) => {
  // Réinitialiser les erreurs à chaque nouvelle soumission valide
  setValidationErrorSummary(null);
  setServerError(null);
  setServerFieldErrors(null);
  
  console.log("Validation réussie, données brutes du formulaire :", values);

  // On prépare le payload final pour le backend
  const payload = {
    ...values,
    specificites_paie: {
      ...values.specificites_paie,
      // On met à jour la section mutuelle pour inclure "adhesion"
      mutuelle: {
        adhesion: (values.specificites_paie.mutuelle.mutuelle_type_ids?.length || 0) > 0 || (values.specificites_paie.mutuelle.lignes_specifiques?.length || 0) > 0,
        mutuelle_type_ids: values.specificites_paie.mutuelle.mutuelle_type_ids || [],
        lignes_specifiques: values.specificites_paie.mutuelle.lignes_specifiques || [],
      },
      // On met à jour la section prévoyance avec la logique conditionnelle
      prevoyance: {
        adhesion: values.specificites_paie.prevoyance.adhesion,
        lignes_specifiques: 
          (values.specificites_paie.prevoyance.adhesion && values.statut?.toLowerCase() === 'cadre') 
          ? values.specificites_paie.prevoyance.lignes_specifiques
          : [], // On envoie une liste vide si non-cadre ou si l'adhésion n'est pas cochée
      },
    }
  };

  console.log("Payload final envoyé au backend :", payload);

  try {
    // 1. Créer un objet FormData
    const formData = new FormData();

    // 2. Ajouter les données du formulaire (le JSON) en tant que champ "data"
    // Le backend devra parser ce string
    formData.append('data', JSON.stringify(payload));

    // 3. Ajouter le flag de génération automatique de PDF
    formData.append('generate_pdf_contract', generatePdfContract.toString());

    // 4. Ajouter le fichier PDF s'il existe (seulement si pas de génération auto)
    if (uploadedFile && !generatePdfContract) {
      // Le nom 'contrat.pdf' est important, mais c'est le 3ème argument
      // Le premier argument 'file' doit correspondre à ce que le backend attend
      formData.append('file', uploadedFile, 'contrat.pdf');
    } else if (!generatePdfContract) {
      // Gérer le cas où aucun fichier n'est joint (si c'est optionnel)
      console.warn("Aucun fichier PDF de contrat n'a été joint.");
      // Si le fichier est OBLIGATOIRE, tu devrais arrêter ici :
      // setServerError("Veuillez déposer un contrat PDF pour continuer.");
      // return;
    }

    // 5. Ajouter le fichier de pièce d'identité s'il existe
    if (uploadedIdFile) {
      formData.append('identity_file', uploadedIdFile);
    }

    // 6. Envoyer la requête en 'multipart/form-data'
    const response = await apiClient.post('/api/employees', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    setIsDialogOpen(false);
    form.reset();
    setGeneratePdfContract(false);
    setIdentityDocumentType("identity"); // Réinitialiser le type de document
    setUploadedIdFile(null); // Réinitialiser le fichier uploadé
    await fetchEmployees();

    // Affiche le mot de passe à l'utilisateur (et avertissements RIB si doublon)
    const newEmployeeData = response.data;
    if (newEmployeeData && newEmployeeData.generated_password) {
      // Message différent si génération auto de PDF
      const pdfMessage = generatePdfContract
        ? '\n\nContrat disponible dans la section "Contrat"'
        : '\n\nUn PDF avec ces informations a été généré et est disponible dans la fiche de l\'employé.\nVeuillez le télécharger et le transmettre à l\'employé.';
      const warningsMessage = (newEmployeeData as { warnings?: string[] }).warnings?.length
        ? '\n\nAttention : ' + (newEmployeeData as { warnings?: string[] }).warnings!.join('\n')
        : '';

      alert(`Employé créé avec succès !\n\nNom d'utilisateur: ${newEmployeeData.username}\nEmail: ${newEmployeeData.email}\nMot de passe temporaire: ${newEmployeeData.generated_password}${pdfMessage}${warningsMessage}`);
    }

  } catch (error: any) { 
    console.error("Erreur lors de l'envoi au backend :", error.response?.data || error.message);

    // Vérifier si on a des erreurs de champs spécifiques
    if (error.response?.data?.field_errors) {
      const fieldErrors = error.response.data.field_errors;

      // Stocker les erreurs de champs
      setServerFieldErrors(fieldErrors);

      // Appliquer les erreurs aux champs du formulaire
      Object.keys(fieldErrors).forEach((fieldPath) => {
        // Convertir le chemin du champ (ex: "adresse.rue") en format pour setError
        form.setError(fieldPath as any, {
          type: 'server',
          message: fieldErrors[fieldPath]
        });
      });

      // Afficher le message général
      const errorMessage = error.response.data.detail || "Erreur de validation des données";
      setServerError(errorMessage);
    } else {
      // Erreur générale sans champs spécifiques
      const errorMessage = error.response?.data?.detail || "Une erreur inattendue est survenue. Veuillez réessayer.";
      setServerError(errorMessage);
      setServerFieldErrors(null);
    }
  }
};

  // Cette fonction est appelée UNIQUEMENT si la validation Zod échoue
  const onValidationErrors = (errors: any) => {
    console.log("%c❌ Validation Échouée !", "color: red; font-weight: bold;");
    console.log("Champs en erreur :", errors);
    console.log("Détails complets :", JSON.stringify(errors, null, 2));

    // Fonction récursive pour extraire tous les messages d'erreur avec les chemins
    const extractErrorMessages = (obj: any, path: string = ""): string[] => {
      if (!obj) return [];
      return Object.keys(obj).reduce<string[]>((acc, key) => {
        const value = obj[key];
        const currentPath = path ? `${path}.${key}` : key;

        if (value && typeof value === 'object') {
          if (value.message) {
            return [...acc, `${currentPath}: ${value.message}`];
          }
          return [...acc, ...extractErrorMessages(value, currentPath)];
        }
        return acc;
      }, []);
    };

    const messages = extractErrorMessages(errors);
    console.log("Messages d'erreur extraits:", messages);
    setValidationErrorSummary(messages);
    setServerError(null); // On s'assure de ne pas afficher une ancienne erreur serveur
  };

  const filteredEmployees = employees.filter(emp => {
    const matchesSearch = `${emp.first_name} ${emp.last_name}`.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = employmentStatusFilter === 'all' || (emp.employment_status || 'actif') === employmentStatusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6">
      {ribAlerts.length > 0 && (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardHeader className="py-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Landmark className="h-4 w-4" />
              Alertes RIB ({ribAlerts.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="py-2">
            <ul className="space-y-1 text-sm">
              {ribAlerts.slice(0, 3).map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-2">
                  <span className="text-muted-foreground truncate">{a.title} — {a.message}</span>
                  {a.employee_id && (
                    <Button variant="ghost" size="sm" className="shrink-0 h-7" onClick={() => navigate(`/employees/${a.employee_id}`)}>
                      Fiche
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
      <div className="flex items-center justify-between">
        <div><h1 className="text-3xl font-bold">Gestion des Collaborateurs</h1><p className="text-muted-foreground mt-2">{loading ? 'Chargement...' : `${employees.length} collaborateurs`}</p></div>
        <Dialog open={isDialogOpen} onOpenChange={(open) => {
          setIsDialogOpen(open);
          if (!open) {
            form.reset();
            setUploadedFile(null);
            setExtractionError(null);
            setExtractionSuccess(false);
            setUploadedRibFile(null);
            setRibExtractionError(null);
            setRibExtractionSuccess(false);
            setUploadedIdFile(null);
            setUploadedQuestionnaireFile(null);
            setQuestionnaireExtractionError(null);
            setQuestionnaireExtractionSuccess(false);
            setGeneratePdfContract(false);
            setIdentityDocumentType("identity");
          }
        }}>
          <DialogTrigger asChild>
            <Button>
              <PlusCircle className="mr-2 h-4 w-4" />
              Nouveau Collaborateur
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-4xl max-h-[90vh] flex flex-col">
            <DialogHeader>
              <DialogTitle>Nouveau Collaborateur</DialogTitle>
              <DialogDescription>
                Créez un nouveau collaborateur avec ses informations personnelles, contrat et rémunération.
              </DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form id="collab-form" onSubmit={form.handleSubmit(onSubmit, onValidationErrors)} className="flex flex-col min-h-0">
                <Tabs defaultValue="collaborateur" className="w-full flex-1 flex flex-col min-h-0">
                  <TabsList className="grid w-full grid-cols-5">
                    <TabsTrigger value="collaborateur">Collaborateur</TabsTrigger>
                    <TabsTrigger value="contrat">Contrat</TabsTrigger>
                    <TabsTrigger value="remuneration">Rémunération</TabsTrigger>
                    <TabsTrigger value="avantages">Avantages</TabsTrigger>
                    <TabsTrigger value="specifiques">Spécificités</TabsTrigger>
                  </TabsList>
                  <div className="py-4 space-y-4 max-h-[50vh] overflow-y-auto pr-2">
                    <TabsContent value="collaborateur">
                      {!generatePdfContract && (
                        <div
                          className={`mb-6 p-4 border-2 border-dashed rounded-lg transition-all ${
                            isDragging
                              ? 'border-blue-500 bg-blue-50'
                              : 'border-gray-300 bg-gray-50'
                          }`}
                          onDragOver={handleDragOver}
                          onDragLeave={handleDragLeave}
                          onDrop={handleDrop}
                        >
                          <div className="flex items-center gap-3 mb-3">
                            <FileText className="h-5 w-5 text-blue-600" />
                            <h3 className="font-semibold text-lg">Déposer un contrat PDF</h3>
                          </div>
                          <p className="text-sm text-muted-foreground mb-3">
                            {isDragging
                              ? "Déposez votre PDF ici..."
                              : "Glissez-déposez un contrat PDF ou cliquez pour sélectionner un fichier. L'IA préremplira automatiquement les champs."
                            }
                          </p>
                          <div className="flex items-center gap-3">
                            <label htmlFor="pdf-upload" className="cursor-pointer">
                              <div className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors">
                                <Upload className="h-4 w-4" />
                                <span>{uploadedFile ? 'Changer le fichier' : 'Choisir un PDF'}</span>
                              </div>
                              <input
                                id="pdf-upload"
                                type="file"
                                accept=".pdf"
                                onChange={handlePdfUpload}
                                className="hidden"
                              />
                            </label>
                            {uploadedFile && (
                              <span className="text-sm text-gray-600 flex items-center gap-2">
                                <FileText className="h-4 w-4" />
                                {uploadedFile.name}
                              </span>
                            )}
                          </div>
                          {isExtracting && (
                            <div className="mt-3 flex items-center gap-2 text-blue-600">
                              <Loader2 className="h-4 w-4 animate-spin" />
                              <span className="text-sm">Extraction des données en cours...</span>
                            </div>
                          )}
                          {extractionSuccess && !extractionError && (
                            <div className="mt-3">
                              <p className="text-sm text-green-600 font-medium">✓ Extraction réussie</p>
                            </div>
                          )}
                          {extractionError && (
                            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
                              <p className="text-sm text-red-700">{extractionError}</p>
                            </div>
                          )}
                        </div>
                      )}
                      <div
                        className={`mb-6 p-4 border-2 border-dashed rounded-lg transition-all ${
                          isQuestionnaireDragging
                            ? 'border-orange-500 bg-orange-50'
                            : 'border-gray-300 bg-gray-50'
                        }`}
                        onDragOver={handleQuestionnaireDragOver}
                        onDragLeave={handleQuestionnaireDragLeave}
                        onDrop={handleQuestionnaireDrop}
                      >
                        <div className="flex items-center gap-3 mb-3">
                          <FileText className="h-5 w-5 text-orange-600" />
                          <h3 className="font-semibold text-lg">Déposer un questionnaire d'embauche PDF</h3>
                        </div>
                        <p className="text-sm text-muted-foreground mb-3">
                          {isQuestionnaireDragging
                            ? "Déposez votre questionnaire PDF ici..."
                            : "Glissez-déposez un questionnaire d'embauche PDF ou cliquez pour sélectionner un fichier. L'IA préremplira automatiquement les champs."
                          }
                        </p>
                        <div className="flex items-center gap-3">
                          <label htmlFor="questionnaire-pdf-upload" className="cursor-pointer">
                            <div className="flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 transition-colors">
                              <Upload className="h-4 w-4" />
                              <span>{uploadedQuestionnaireFile ? 'Changer le fichier' : 'Choisir un PDF'}</span>
                            </div>
                            <input
                              id="questionnaire-pdf-upload"
                              type="file"
                              accept=".pdf"
                              onChange={handleQuestionnairePdfUpload}
                              className="hidden"
                            />
                          </label>
                          {uploadedQuestionnaireFile && (
                            <span className="text-sm text-gray-600 flex items-center gap-2">
                              <FileText className="h-4 w-4" />
                              {uploadedQuestionnaireFile.name}
                            </span>
                          )}
                        </div>
                        {isExtractingQuestionnaire && (
                          <div className="mt-3 flex items-center gap-2 text-orange-600">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span className="text-sm">Extraction des données du questionnaire en cours...</span>
                          </div>
                        )}
                        {questionnaireExtractionSuccess && !questionnaireExtractionError && (
                          <div className="mt-3">
                            <p className="text-sm text-green-600 font-medium">✓ Extraction du questionnaire réussie</p>
                          </div>
                        )}
                        {questionnaireExtractionError && (
                          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
                            <p className="text-sm text-red-700">{questionnaireExtractionError}</p>
                          </div>
                        )}
                      </div>
                      <div
                        className={`mb-6 p-3 border-2 border-dashed rounded-lg transition-all ${
                          isRibDragging
                            ? 'border-green-500 bg-green-50'
                            : 'border-gray-300 bg-gray-50'
                        }`}
                        onDragOver={handleRibDragOver}
                        onDragLeave={handleRibDragLeave}
                        onDrop={handleRibDrop}
                      >
                        <div className="flex items-center gap-3 mb-2">
                          <FileText className="h-4 w-4 text-green-600" />
                          <h3 className="font-semibold text-base">Déposer un RIB</h3>
                        </div>
                        <p className="text-xs text-muted-foreground mb-3">
                          {isRibDragging
                            ? "Déposez votre RIB PDF ici..."
                            : "Glissez-déposez un RIB PDF ou cliquez pour sélectionner un fichier. L'IA remplira automatiquement les coordonnées bancaires."
                          }
                        </p>
                        <div className="flex items-center gap-3">
                          <label htmlFor="rib-pdf-upload" className="cursor-pointer">
                            <div className="flex items-center gap-2 px-3 py-1.5 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors text-sm">
                              <Upload className="h-3 w-3" />
                              <span>{uploadedRibFile ? 'Changer le RIB' : 'Choisir un RIB'}</span>
                            </div>
                            <input
                              id="rib-pdf-upload"
                              type="file"
                              accept=".pdf"
                              onChange={handleRibPdfUpload}
                              className="hidden"
                            />
                          </label>
                          {uploadedRibFile && (
                            <span className="text-xs text-gray-600 flex items-center gap-2">
                              <FileText className="h-3 w-3" />
                              {uploadedRibFile.name}
                            </span>
                          )}
                        </div>
                        {isExtractingRib && (
                          <div className="mt-2 flex items-center gap-2 text-green-600">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            <span className="text-xs">Extraction des données bancaires en cours...</span>
                          </div>
                        )}
                        {ribExtractionSuccess && !ribExtractionError && (
                          <div className="mt-2">
                            <p className="text-xs text-green-600 font-medium">✓ RIB extrait avec succès</p>
                          </div>
                        )}
                        {ribExtractionError && (
                          <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded-md">
                            <p className="text-xs text-red-700">{ribExtractionError}</p>
                          </div>
                        )}
                      </div>
                      <div className="mb-4">
                        <FormLabel className="text-base font-semibold mb-2 block">Type de document fourni</FormLabel>
                        <Select value={identityDocumentType} onValueChange={(value: "identity" | "residence_permit") => {
                          setIdentityDocumentType(value);
                          setUploadedIdFile(null);
                          if (value === "residence_permit") {
                            form.setValue("is_subject_to_residence_permit", true);
                          } else {
                            form.setValue("is_subject_to_residence_permit", false);
                            form.setValue("residence_permit_expiry_date", "");
                            form.setValue("residence_permit_type", "");
                            form.setValue("residence_permit_number", "");
                          }
                        }}>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Choisir le type de document" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="identity">Pièce d'identité (CNI, Passeport)</SelectItem>
                            <SelectItem value="residence_permit">Titre de séjour</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div
                        className={`mb-6 p-3 border-2 border-dashed rounded-lg transition-all ${
                          isIdDragging
                            ? 'border-purple-500 bg-purple-50'
                            : 'border-gray-300 bg-gray-50'
                        }`}
                        onDragOver={handleIdDragOver}
                        onDragLeave={handleIdDragLeave}
                        onDrop={handleIdDrop}
                      >
                        <div className="flex items-center gap-3 mb-2">
                          <FileText className="h-4 w-4 text-purple-600" />
                          <h3 className="font-semibold text-base">
                            {identityDocumentType === "residence_permit" ? "Titre de séjour" : "Pièce d'identité"}
                          </h3>
                        </div>
                        <p className="text-xs text-muted-foreground mb-3">
                          {isIdDragging
                            ? `Déposez votre ${identityDocumentType === "residence_permit" ? "titre de séjour" : "pièce d'identité"} ici...`
                            : `Glissez-déposez ${identityDocumentType === "residence_permit" ? "un titre de séjour" : "une carte d'identité ou un passeport"} (PDF ou image) ou cliquez pour sélectionner un fichier.`
                          }
                        </p>
                        <div className="flex items-center gap-3">
                          <label htmlFor="id-file-upload" className="cursor-pointer">
                            <div className="flex items-center gap-2 px-3 py-1.5 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition-colors text-sm">
                              <Upload className="h-3 w-3" />
                              <span>{uploadedIdFile ? 'Changer le fichier' : 'Choisir un fichier'}</span>
                            </div>
                            <input
                              id="id-file-upload"
                              type="file"
                              accept=".pdf,.jpg,.jpeg,.png,.gif,.bmp,.webp"
                              onChange={handleIdFileUpload}
                              className="hidden"
                            />
                          </label>
                          {uploadedIdFile && (
                            <span className="text-xs text-gray-600 flex items-center gap-2">
                              <FileText className="h-3 w-3" />
                              {uploadedIdFile.name}
                            </span>
                          )}
                        </div>
                      </div>
                      {identityDocumentType === "residence_permit" && (
                        <div className="mb-6 p-4 border border-purple-200 rounded-lg bg-purple-50/50">
                          <h3 className="font-semibold text-base mb-4 text-purple-900">Informations du titre de séjour</h3>
                          <p className="text-sm text-muted-foreground mb-4">
                            L'employé est automatiquement marqué comme soumis à titre de séjour puisque vous fournissez un titre de séjour.
                          </p>
                          <div className="space-y-4">
                            <FormField
                              control={form.control}
                              name="residence_permit_expiry_date"
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Date d'expiration du titre de séjour <span className="text-red-500">*</span></FormLabel>
                                  <FormControl>
                                    <Input type="date" {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                            <FormField
                              control={form.control}
                              name="residence_permit_type"
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Type de titre de séjour</FormLabel>
                                  <FormControl>
                                    <Input placeholder="ex: Visa de travail, Titre temporaire..." {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                            <FormField
                              control={form.control}
                              name="residence_permit_number"
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Numéro de titre de séjour</FormLabel>
                                  <FormControl>
                                    <Input placeholder="ex: 123456789" {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                          </div>
                        </div>
                      )}
                      <FormField control={form.control} name="first_name" render={({ field }) => (<FormItem><FormLabel>Prénom</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                      <FormField control={form.control} name="last_name" render={({ field }) => (<FormItem><FormLabel>Nom</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                      <FormField control={form.control} name="email" render={({ field }) => (<FormItem><FormLabel>Email</FormLabel><FormControl><Input type="email" placeholder="email@exemple.com" {...field} /></FormControl><FormMessage /></FormItem>)} />
                      <FormField control={form.control} name="nir" render={({ field }) => (<FormItem><FormLabel>N° de Sécurité Sociale</FormLabel><FormControl><Input placeholder="ex: 1850701123456" {...field} /></FormControl><FormMessage /></FormItem>)} />
                      <FormField control={form.control} name="date_naissance" render={({ field }) => (<FormItem><FormLabel>Date de naissance</FormLabel><FormControl><Input type="date" {...field} /></FormControl><FormMessage /></FormItem>)} />
                      <FormField control={form.control} name="lieu_naissance" render={({ field }) => (<FormItem><FormLabel>Lieu de naissance</FormLabel><FormControl><Input placeholder="ex: 75001 Paris" {...field} /></FormControl><FormMessage /></FormItem>)} />
                      <FormField control={form.control} name="nationalite" render={({ field }) => (<FormItem><FormLabel>Nationalité</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                      <h3 className="font-semibold pt-4">Adresse</h3>
                      <FormField control={form.control} name="adresse.rue" render={({ field }) => (<FormItem><FormLabel>Rue</FormLabel><FormControl><Input placeholder="1 Rue de la Paix" {...field} /></FormControl><FormMessage /></FormItem>)} />
                      <div className="grid grid-cols-2 gap-4">
                        <FormField control={form.control} name="adresse.code_postal" render={({ field }) => (<FormItem><FormLabel>Code Postal</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <FormField control={form.control} name="adresse.ville" render={({ field }) => (<FormItem><FormLabel>Ville</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                      </div>
                      <h3 className="font-semibold pt-4">Coordonnées bancaires</h3>
                      <FormField control={form.control} name="coordonnees_bancaires.iban" render={({ field }) => (<FormItem><FormLabel>IBAN</FormLabel><FormControl><Input placeholder="FR76..." {...field} /></FormControl><FormMessage /></FormItem>)} />
                      <FormField control={form.control} name="coordonnees_bancaires.bic" render={({ field }) => (<FormItem><FormLabel>BIC</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                    </TabsContent>
                    <TabsContent value="contrat">
                      <div className="space-y-4">
                        <FormField control={form.control} name="hire_date" render={({ field }) => (<FormItem><FormLabel>Date d'entrée</FormLabel><FormControl><Input type="date" {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <FormField control={form.control} name="job_title" render={({ field }) => (<FormItem><FormLabel>Intitulé du poste</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <div className="grid grid-cols-2 gap-4">
                          <FormField control={form.control} name="contract_type" render={({ field }) => (<FormItem><FormLabel>Type de contrat</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                          <FormField control={form.control} name="statut" render={({ field }) => (<FormItem><FormLabel>Statut</FormLabel><FormControl><Input placeholder="Non-Cadre" {...field} /></FormControl><FormMessage /></FormItem>)} />
                        </div>
                        <div className="grid grid-cols-2 gap-4 items-end">
                          <FormField control={form.control} name="duree_hebdomadaire" render={({ field }) => (<FormItem><FormLabel>Durée hebdo. (heures)</FormLabel><FormControl><Input type="number" {...field} /></FormControl><FormMessage /></FormItem>)} />
                          <FormField
                            control={form.control}
                            name="is_temps_partiel"
                            render={({ field }) => (
                              <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                                <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
                                <div className="space-y-1 leading-none">
                                  <FormLabel>Contrat à temps partiel</FormLabel>
                                </div>
                              </FormItem>
                            )}
                          />
                        </div>
                      </div>
                    </TabsContent>
                    <TabsContent value="remuneration">
                      <div className="space-y-4">
                        <FormField 
                          control={form.control}
                          name="salaire_de_base.valeur" 
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Salaire de base mensuel (€)</FormLabel>
                              <FormControl><Input type="number" step="0.01" {...field} /></FormControl>
                              <FormMessage />
                            </FormItem>
                          )} 
                        />
                        <h3 className="font-semibold pt-4">Convention Collective</h3>
                        <FormField
                          control={form.control}
                          name="collective_agreement_id"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Convention collective</FormLabel>
                              <Select
                                value={field.value ?? "__aucune__"}
                                onValueChange={(v) => {
                                  field.onChange(v === "__aucune__" ? null : v);
                                  if (v === "__aucune__") {
                                    form.setValue("classification_conventionnelle", { groupe_emploi: "C", classe_emploi: 6, coefficient: 240 });
                                  }
                                }}
                              >
                                <FormControl>
                                  <SelectTrigger className="w-full max-w-md">
                                    <SelectValue placeholder="Aucune" />
                                  </SelectTrigger>
                                </FormControl>
                                <SelectContent>
                                  <SelectItem value="__aucune__">Aucune</SelectItem>
                                  {companyAgreements.map((a) => (
                                    <SelectItem key={a.id} value={a.collective_agreement_id}>
                                      {a.agreement_details?.name || a.agreement_details?.idcc || "Convention"} (IDCC {a.agreement_details?.idcc})
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        {selectedCcId && selectedCcId !== "__aucune__" && (
                          <>
                            <h3 className="font-semibold pt-4">Classification Conventionnelle</h3>
                            {classificationsCc.length > 0 ? (
                              <FormField
                                control={form.control}
                                name="classification_conventionnelle"
                                render={({ field }) => (
                                  <FormItem>
                                    <FormLabel>Classification</FormLabel>
                                    <Select
                                      value={[field.value?.groupe_emploi, field.value?.classe_emploi, field.value?.coefficient].join("-")}
                                      onValueChange={(val) => {
                                        const c = classificationsCc.find(
                                          (x) => `${x.groupe_emploi}-${x.classe_emploi}-${x.coefficient}` === val
                                        );
                                        if (c) field.onChange({ groupe_emploi: c.groupe_emploi, classe_emploi: c.classe_emploi, coefficient: c.coefficient });
                                      }}
                                    >
                                      <FormControl>
                                        <SelectTrigger className="w-full max-w-md">
                                          <SelectValue placeholder="Choisir une classification" />
                                        </SelectTrigger>
                                      </FormControl>
                                      <SelectContent>
                                        {classificationsCc.map((c) => (
                                          <SelectItem
                                            key={`${c.groupe_emploi}-${c.classe_emploi}-${c.coefficient}`}
                                            value={`${c.groupe_emploi}-${c.classe_emploi}-${c.coefficient}`}
                                          >
                                            Groupe {c.groupe_emploi} - Classe {c.classe_emploi} - Coeff. {c.coefficient}
                                          </SelectItem>
                                        ))}
                                      </SelectContent>
                                    </Select>
                                    <FormMessage />
                                  </FormItem>
                                )}
                              />
                            ) : (
                              <div className="grid grid-cols-3 gap-4">
                                <FormField 
                                  control={form.control}
                                  name="classification_conventionnelle.groupe_emploi" 
                                  render={({ field }) => (
                                    <FormItem>
                                      <FormLabel>Groupe</FormLabel>
                                      <FormControl><Input {...field} /></FormControl>
                                      <FormMessage />
                                    </FormItem>
                                  )} 
                                />
                                <FormField 
                                  control={form.control}
                                  name="classification_conventionnelle.classe_emploi" 
                                  render={({ field }) => (
                                    <FormItem>
                                      <FormLabel>Classe</FormLabel>
                                      <FormControl><Input type="number" {...field} /></FormControl>
                                      <FormMessage />
                                    </FormItem>
                                  )} 
                                />
                                <FormField 
                                  control={form.control}
                                  name="classification_conventionnelle.coefficient" 
                                  render={({ field }) => (
                                    <FormItem>
                                      <FormLabel>Coefficient</FormLabel>
                                      <FormControl><Input type="number" {...field} /></FormControl>
                                      <FormMessage />
                                    </FormItem>
                                  )} 
                                />
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </TabsContent>
                    <TabsContent value="avantages">
                      <div className="space-y-4">
                        <FormField
                          control={form.control}
                          name="avantages_en_nature.repas.nombre_par_mois"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Nombre de repas fournis par mois</FormLabel>
                              <FormControl><Input type="number" {...field} /></FormControl>
                              <FormMessage />
                            </FormItem>
                          )} 
                        />
                        <div className="grid grid-cols-2 gap-4">
                          <FormField
                            control={form.control}
                            name="avantages_en_nature.logement.beneficie"
                            render={({ field }) => (
                              <FormItem className="flex flex-row items-center space-x-3 space-y-0 rounded-md border p-4">
                                <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
                                <FormLabel>Bénéficie d'un logement de fonction</FormLabel>
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name="avantages_en_nature.vehicule.beneficie"
                            render={({ field }) => (
                              <FormItem className="flex flex-row items-center space-x-3 space-y-0 rounded-md border p-4">
                                <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
                                <FormLabel>Bénéficie d'un véhicule de fonction</FormLabel>
                              </FormItem>
                            )}
                          />
                        </div>
                      </div>
                    </TabsContent>
                    <TabsContent value="specifiques">
                      <div className="space-y-6">
                        <div>
                          <h3 className="font-semibold mb-2">Prélèvement à la Source (PAS)</h3>
                          <FormField
                            control={form.control}
                            name="specificites_paie.prelevement_a_la_source.is_personnalise"
                            render={({ field }) => (
                              <FormItem className="flex flex-row items-center space-x-3 space-y-0">
                                <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
                                <FormLabel>Appliquer un taux personnalisé</FormLabel>
                              </FormItem>
                            )}
                          />
                          {form.watch("specificites_paie.prelevement_a_la_source.is_personnalise") && (
                            <FormField
                              control={form.control}
                              name="specificites_paie.prelevement_a_la_source.taux"
                              render={({ field }) => (
                                <FormItem className="mt-2 ml-7">
                                  <FormLabel>Taux personnalisé (%)</FormLabel>
                                  <FormControl><Input type="number" step="0.1" {...field} /></FormControl>
                                </FormItem>
                              )}
                            />
                          )}
                        </div>
                        <div>
                          <h3 className="font-semibold mb-2">Indemnités & Avantages</h3>
                          <div className="space-y-4">
                            <FormField
                              control={form.control}
                              name="specificites_paie.transport.abonnement_mensuel_total"
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Abonnement transport mensuel total (€)</FormLabel>
                                  <FormControl><Input type="number" step="0.01" {...field} /></FormControl>
                                </FormItem>
                              )}
                            />
                            <FormField
                              control={form.control}
                              name="specificites_paie.titres_restaurant.nombre_par_mois"
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Nombre de titres-restaurant par mois</FormLabel>
                                  <FormControl><Input type="number" {...field} /></FormControl>
                                </FormItem>
                              )}
                            />
                          </div>
                        </div>
                        <div className="space-y-6">
                          <div>
                            <h3 className="font-semibold mb-2">Mutuelle</h3>
                            <div className="space-y-4 rounded-md border p-4">
                              {loadingMutuelles ? (
                                <div className="flex justify-center py-4">
                                  <Loader2 className="h-5 w-5 animate-spin" />
                                </div>
                              ) : availableMutuelles.length === 0 ? (
                                <p className="text-sm text-muted-foreground text-center">
                                  Aucune formule de mutuelle disponible. Veuillez en créer dans l'onglet "Mutuelle" de la page "Mon Entreprise".
                                </p>
                              ) : (
                                <FormField
                                  control={form.control}
                                  name="specificites_paie.mutuelle.mutuelle_type_ids"
                                  render={({ field }) => (
                                    <FormItem>
                                      <FormLabel>Sélectionner les formules de mutuelle</FormLabel>
                                      <div className="space-y-2 mt-2">
                                        {availableMutuelles.map((mutuelle) => (
                                          <div key={mutuelle.id} className="flex items-center space-x-2 p-2 border rounded-md hover:bg-muted/50">
                                            <Checkbox
                                              checked={field.value?.includes(mutuelle.id) || false}
                                              onCheckedChange={(checked) => {
                                                const currentIds = field.value || [];
                                                if (checked) {
                                                  field.onChange([...currentIds, mutuelle.id]);
                                                } else {
                                                  field.onChange(currentIds.filter((id: string) => id !== mutuelle.id));
                                                }
                                              }}
                                            />
                                            <div className="flex-1">
                                              <div className="font-medium">{mutuelle.libelle}</div>
                                              <div className="text-sm text-muted-foreground">
                                                Salarial: {mutuelle.montant_salarial.toFixed(2)} € | 
                                                Patronal: {mutuelle.montant_patronal.toFixed(2)} €
                                                {mutuelle.part_patronale_soumise_a_csg && (
                                                  <span className="ml-2 text-xs">(Part patronale soumise à CSG)</span>
                                                )}
                                              </div>
                                            </div>
                                          </div>
                                        ))}
                                      </div>
                                      <FormMessage />
                                    </FormItem>
                                  )}
                                />
                              )}
                              {mutuelleFields.length > 0 && (
                                <div className="mt-4 pt-4 border-t">
                                  <p className="text-sm font-medium mb-2">Anciennes lignes de mutuelle (rétrocompatibilité)</p>
                                  {mutuelleFields.map((field, index) => (
                                    <div key={field.id} className="space-y-3 border-b pb-4 last:border-b-0">
                                      <div className="flex justify-between items-end gap-2">
                                        <FormField
                                          control={form.control}
                                          name={`specificites_paie.mutuelle.lignes_specifiques.${index}.libelle`}
                                          render={({ field }) => (
                                            <FormItem className="flex-grow">
                                              <FormLabel>Libellé</FormLabel>
                                              <FormControl><Input {...field} /></FormControl>
                                            </FormItem>
                                          )}
                                        />
                                        <Button
                                          type="button"
                                          variant="ghost"
                                          size="icon"
                                          className="text-destructive hover:text-destructive flex-shrink-0"
                                          onClick={() => removeMutuelle(index)}
                                          title="Supprimer la ligne"
                                        >
                                          <Trash2 className="h-4 w-4" />
                                        </Button>
                                      </div>
                                      <div className="grid grid-cols-2 gap-4">
                                        <FormField control={form.control} name={`specificites_paie.mutuelle.lignes_specifiques.${index}.montant_salarial`} render={({ field }) => (<FormItem><FormLabel>Montant Salarial (€)</FormLabel><FormControl><Input type="number" {...field} /></FormControl></FormItem>)} />
                                        <FormField control={form.control} name={`specificites_paie.mutuelle.lignes_specifiques.${index}.montant_patronal`} render={({ field }) => (<FormItem><FormLabel>Montant Patronal (€)</FormLabel><FormControl><Input type="number" {...field} /></FormControl></FormItem>)} />
                                      </div>
                                      <FormField control={form.control} name={`specificites_paie.mutuelle.lignes_specifiques.${index}.part_patronale_soumise_a_csg`} render={({ field }) => (<FormItem className="flex flex-row items-center space-x-3 pt-2"><FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl><FormLabel>Part patronale soumise à CSG</FormLabel></FormItem>)} />
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                          <div>
                            <h3 className="font-semibold mb-2">Prévoyance</h3>
                            <div className="space-y-4 rounded-md border p-4">
                              <FormField control={form.control} name="specificites_paie.prevoyance.adhesion" render={({ field }) => (<FormItem className="flex flex-row items-center space-x-3"><FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl><FormLabel>Adhésion Prévoyance</FormLabel></FormItem>)} />
                              {form.watch("specificites_paie.prevoyance.adhesion") && isCadre && (
                                <div className="pl-6 border-l-2 ml-2 space-y-4">
                                  <div className="flex justify-between items-center">
                                    <h4 className="text-sm font-medium">Lignes de Prévoyance (Cadre)</h4>
                                    <Button type="button" variant="outline" size="sm" onClick={() => appendPrevoyance({ id: `prevoyance_${prevoyanceFields.length + 1}`, libelle: '', salarial: 0, patronal: 0, forfait_social: 0 })}>
                                      <PlusCircle className="mr-2 h-4 w-4" /> Ajouter
                                    </Button>
                                  </div>
                                  {prevoyanceFields.map((field, index) => (
                                    <div key={field.id} className="space-y-2 border-b pb-4 last:border-b-0">
                                      <FormField control={form.control} name={`specificites_paie.prevoyance.lignes_specifiques.${index}.libelle`} render={({ field }) => (<FormItem><FormLabel>Libellé</FormLabel><FormControl><Input {...field} /></FormControl></FormItem>)} />
                                      <div className="grid grid-cols-3 gap-4">
                                        <FormField control={form.control} name={`specificites_paie.prevoyance.lignes_specifiques.${index}.salarial`} render={({ field }) => (<FormItem><FormLabel>Taux Salarial (%)</FormLabel><FormControl><Input type="number" step="0.0001" {...field} /></FormControl><FormMessage /></FormItem>)} />
                                        <FormField control={form.control} name={`specificites_paie.prevoyance.lignes_specifiques.${index}.patronal`} render={({ field }) => (<FormItem><FormLabel>Taux Patronal (%)</FormLabel><FormControl><Input type="number" step="0.0001" {...field} /></FormControl><FormMessage /></FormItem>)} />
                                        <FormField control={form.control} name={`specificites_paie.prevoyance.lignes_specifiques.${index}.forfait_social`} render={({ field }) => (<FormItem><FormLabel>Forfait Social (%)</FormLabel><FormControl><Input type="number" step="0.01" {...field} /></FormControl><FormMessage /></FormItem>)} />
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    </TabsContent>
                  </div>
                </Tabs>
              </form>
            </Form>
            <DialogFooter className="mt-6 pt-4 border-t border-gray-200">
              <div className="w-full space-y-2">
                {validationErrorSummary && validationErrorSummary.length > 0 && (
                  <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">
                    <p className="font-semibold mb-2">Veuillez corriger les erreurs suivantes :</p>
                    <ul className="list-disc list-inside space-y-1">
                      {validationErrorSummary.map((msg, index) => (
                        <li key={index}>{msg}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {serverError && (
                  <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">
                    <p className="font-semibold mb-2">Erreur :</p>
                    <p className="mb-2">{serverError}</p>
                    {serverFieldErrors && Object.keys(serverFieldErrors).length > 0 && (
                      <div className="mt-2">
                        <p className="font-medium text-xs mb-1">Champs concernés :</p>
                        <ul className="list-disc list-inside space-y-1 text-xs">
                          {Object.entries(serverFieldErrors).map(([field, message]) => (
                            <li key={field}>
                              <span className="font-medium">{translateFieldName(field)}</span> : {message}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
                <div className="flex items-center space-x-2 p-3 bg-blue-50 border border-blue-200 rounded-md">
                  <Checkbox
                    id="generate-pdf-contract"
                    checked={generatePdfContract}
                    onCheckedChange={(checked) => setGeneratePdfContract(checked as boolean)}
                  />
                  <label htmlFor="generate-pdf-contract" className="text-sm font-medium leading-none cursor-pointer">
                    Création de contrat pdf
                  </label>
                </div>
                <Button form="collab-form" type="submit" disabled={form.formState.isSubmitting} className="w-full">
                  {form.formState.isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Enregistrer le collaborateur
                </Button>
              </div>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4 items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" />
              <Input
                placeholder="Rechercher..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="w-[200px]">
              <Select value={employmentStatusFilter} onValueChange={setEmploymentStatusFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="Statut" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tous</SelectItem>
                  <SelectItem value="actif">Actifs</SelectItem>
                  <SelectItem value="en_sortie">En sortie</SelectItem>
                  <SelectItem value="parti">Partis</SelectItem>
                  <SelectItem value="archive">Archivés</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Liste des Collaborateurs</CardTitle></CardHeader>
        <CardContent>
          <Table className="table-fixed">
            <TableHeader><TableRow><TableHead className="w-[40%]">Collaborateur</TableHead><TableHead className="w-[30%]">Poste</TableHead><TableHead className="w-[25%]">Contrat</TableHead><TableHead className="w-[5%]"></TableHead></TableRow></TableHeader>
            <TableBody>
              {loading && <TableRow><TableCell colSpan={4} className="h-24 text-center"><Loader2 className="h-6 w-6 animate-spin mx-auto" /></TableCell></TableRow>}
              {error && <TableRow><TableCell colSpan={4} className="h-24 text-center text-destructive">{error}</TableCell></TableRow>}
              {!loading && !error && filteredEmployees.map((employee) => (
                <TableRow key={employee.id} onClick={() => navigate(`/employees/${employee.id}`)} className="cursor-pointer hover:bg-muted/50">
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <Avatar className="h-8 w-8"><AvatarFallback>{employee.first_name.charAt(0)}{employee.last_name.charAt(0)}</AvatarFallback></Avatar>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <p className="font-medium">{employee.first_name} {employee.last_name}</p>
                          {employee.employment_status === 'en_sortie' && (
                            <Badge variant="outline" className="text-xs flex items-center gap-1">
                              <UserMinus className="h-3 w-3" />
                              En sortie
                            </Badge>
                          )}
                          {employee.employment_status === 'parti' && (
                            <Badge variant="secondary" className="text-xs">
                              Parti
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">Entrée: {employee.hire_date ? new Date(employee.hire_date).toLocaleDateString('fr-FR') : 'N/A'}</p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>{employee.job_title || 'N/A'}</TableCell>
                  <TableCell>{employee.contract_type ? getContractBadge(employee.contract_type) : 'N/A'}</TableCell>
                  <TableCell className="text-right">
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
