import { log } from '@/lib/logger';
import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useActiveCompanyId } from "@/hooks/queries/useCompanyId";
import { queryKeys } from "@/lib/queryKeys";
import apiClient from '@/api/apiClient';
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, PlusCircle, Loader2, Upload, FileText, Trash2 } from "lucide-react";
import { mutuelleTypesApi, MutuelleType } from "@/api/mutuelleTypes";
import { getPscSettings } from "@/api/pscSettings";
import { MutuelleSelectionField } from "@/components/mutuelle/MutuelleSelectionField";
import { filterMutuellesForEmployee } from "@/lib/mutuelleUtils";
import { PrevoyanceAffiliationFields } from "@/features/employees/components/PrevoyanceAffiliationFields";
import * as collectiveAgreementsApi from "@/api/collectiveAgreements";
import { getTeams } from "@/api/teams";
import {
  createEmployeeFormSchema,
  translateFieldName,
  type CreateEmployeeFormValues,
} from "@/features/employees/components/createEmployeeFormSchema";
import { EmployeeContractConfigFormFields } from "@/features/employees/components/EmployeeContractConfigFields";
import { isAlternanceContract, isStageContract } from "@/constants/contracts";
import {
  resolveDefaultCollectiveAgreementId,
  sortAffiliatedCompanyAgreements,
} from "@/lib/companyCollectiveAgreementUtils";

function defaultTrialSettings(contractType: string) {
  const ct = (contractType || "").toLowerCase();
  const excluded =
    isStageContract(contractType) || isAlternanceContract(contractType);
  if (excluded) {
    return { enabled: false, duree: 2, unite: "mois" as const, renouvellement: true };
  }
  const isCdd = ct.includes("cdd") && !ct.includes("cdi");
  return {
    enabled: true,
    duree: isCdd ? 1 : 2,
    unite: "mois" as const,
    renouvellement: true,
  };
}

export function CreateEmployeeForm({ onCreated }: { onCreated?: () => void }) {
  const companyId = useActiveCompanyId();
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

  const teamsActiveQuery = useQuery({
    queryKey: ["teams-active"],
    queryFn: () => getTeams(false),
    enabled: isDialogOpen,
  });
  const activeTeamsSorted = [...(teamsActiveQuery.data?.teams ?? [])].sort((a, b) =>
    a.name.localeCompare(b.name, "fr", { sensitivity: "base" }),
  );

  // Conventions collectives de l'entreprise (pour le sélecteur)
  const [companyAgreements, setCompanyAgreements] = useState<collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails[]>([]);
  // Grille de classification pour la convention sélectionnée
  const [classificationsCc, setClassificationsCc] = useState<collectiveAgreementsApi.ClassificationConventionnelle[]>([]);

  // Formulaire avec toutes les valeurs par défaut (déclaré avant les useEffect qui l'utilisent)
  const form = useForm<CreateEmployeeFormValues>({
    resolver: zodResolver(createEmployeeFormSchema),
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
      date_conclusion_contrat: "",
      date_debut_execution: "",
      contract_end_date: "",
      team_id: "",
      has_periode_essai: true,
      periode_essai: {
        duree_initiale: 2,
        unite: "mois",
        renouvellement_possible: true,
      },
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
        maintien_regime_apprenti: false,
        personnel_rd_eligible_jei: false,
        mandataire_rd: false,
        prelevement_a_la_source: {
          is_personnalise: false,
          taux: 0,
        },
        transport: {
          abonnement_mensuel_total: 0,
          indemnite_mensuelle_nette: 0,
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
        .then((res) => {
          const allAgreements = res.data || [];
          const affiliated = sortAffiliatedCompanyAgreements(allAgreements);
          setCompanyAgreements(affiliated);
          const current = form.getValues("collective_agreement_id");
          const resolved = resolveDefaultCollectiveAgreementId(allAgreements, current);
          if (resolved !== current) {
            form.setValue("collective_agreement_id", resolved);
          }
        })
        .catch(() => setCompanyAgreements([]));
    }
  }, [isDialogOpen, form]);

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

  const watchedContractType = form.watch("contract_type");
  useEffect(() => {
    const settings = defaultTrialSettings(watchedContractType);
    form.setValue("has_periode_essai", settings.enabled);
    if (settings.enabled) {
      form.setValue("periode_essai", {
        duree_initiale: settings.duree,
        unite: settings.unite,
        renouvellement_possible: settings.renouvellement,
      });
    }
  }, [watchedContractType, form]);

  // Charger les mutuelles disponibles
  const [availableMutuelles, setAvailableMutuelles] = useState<MutuelleType[]>([]);
  const [loadingMutuelles, setLoadingMutuelles] = useState(false);
  const [companyOrganismeLabel, setCompanyOrganismeLabel] = useState<string | null>(null);

  useEffect(() => {
    if (!isDialogOpen) return;
    const loadMutuelles = async () => {
      try {
        setLoadingMutuelles(true);
        const [mutuelles, psc] = await Promise.all([
          mutuelleTypesApi.getMutuelleTypes(),
          getPscSettings().catch(() => null),
        ]);
        setAvailableMutuelles(mutuelles.filter((m) => m.is_active));
        setCompanyOrganismeLabel(psc?.mutuelle_organisme_label ?? null);
      } catch (error) {
        log.error("Erreur lors du chargement des mutuelles:", error);
      } finally {
        setLoadingMutuelles(false);
      }
    };
    void loadMutuelles();
  }, [isDialogOpen]);

  const { fields: mutuelleFields, append: appendMutuelle, remove: removeMutuelle } = useFieldArray({
    control: form.control,
    name: "specificites_paie.mutuelle.lignes_specifiques",
  });

  const employeeStatut = form.watch("statut");
  const filteredMutuelles = filterMutuellesForEmployee(availableMutuelles, employeeStatut);

  const queryClient = useQueryClient();

  const fetchEmployees = async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.employees(companyId) });
    onCreated?.();
  };

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
        log.warn("Avertissements lors de l'extraction :", warnings);
        setExtractionError(`Extraction réussie avec des avertissements : ${warnings.join(', ')}`);
      }

    } catch (error: any) {
      log.error("Erreur lors de l'extraction du PDF :", error);
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
        log.warn("Avertissements lors de l'extraction du RIB :", warnings);
        setRibExtractionError(`Extraction réussie avec des avertissements : ${warnings.join(', ')}`);
      }

    } catch (error: any) {
      log.error("Erreur lors de l'extraction du RIB :", error);
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
        log.warn("Avertissements lors de l'extraction du questionnaire :", warnings);
        setQuestionnaireExtractionError(`Extraction réussie avec des avertissements : ${warnings.join(', ')}`);
      }

    } catch (error: any) {
      log.error("Erreur lors de l'extraction du questionnaire :", error);
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

  const onSubmit = async (values: CreateEmployeeFormValues) => {
  // Réinitialiser les erreurs à chaque nouvelle soumission valide
  setValidationErrorSummary(null);
  setServerError(null);
  setServerFieldErrors(null);
  
  // On prépare le payload final pour le backend
  const payload = {
    ...values,
    team_id: values.team_id?.trim() ? values.team_id.trim() : null,
    periode_essai: values.has_periode_essai
      ? {
          ...values.periode_essai!,
          statut: "en_cours",
        }
      : null,
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
        lignes_specifiques: values.specificites_paie.prevoyance.adhesion
          ? values.specificites_paie.prevoyance.lignes_specifiques ?? []
          : [],
      },
    }
  };
  delete (payload as { has_periode_essai?: boolean }).has_periode_essai;

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
      log.warn("Aucun fichier PDF de contrat n'a été joint.");
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
    log.error("Erreur lors de l'envoi au backend :", error.response?.data || error.message);

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
    setValidationErrorSummary(messages);
    setServerError(null); // On s'assure de ne pas afficher une ancienne erreur serveur
  };

  return (
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
          <Plus className="mr-2 h-4 w-4" />
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
                      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        <FormField control={form.control} name="adresse.code_postal" render={({ field }) => (<FormItem><FormLabel>Code Postal</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <FormField control={form.control} name="adresse.ville" render={({ field }) => (<FormItem><FormLabel>Ville</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                      </div>
                      <h3 className="font-semibold pt-4">Coordonnées bancaires</h3>
                      <FormField control={form.control} name="coordonnees_bancaires.iban" render={({ field }) => (<FormItem><FormLabel>IBAN</FormLabel><FormControl><Input placeholder="FR76..." {...field} /></FormControl><FormMessage /></FormItem>)} />
                      <FormField control={form.control} name="coordonnees_bancaires.bic" render={({ field }) => (<FormItem><FormLabel>BIC</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                      <FormField
                        control={form.control}
                        name="team_id"
                        render={({ field }) => (
                          <FormItem className="pt-4">
                            <FormLabel>Équipe</FormLabel>
                            <Select
                              value={field.value && field.value.length > 0 ? field.value : "__none__"}
                              onValueChange={(v) => field.onChange(v === "__none__" ? "" : v)}
                              disabled={teamsActiveQuery.isLoading}
                            >
                              <FormControl>
                                <SelectTrigger className="w-full max-w-md">
                                  <SelectValue placeholder={teamsActiveQuery.isLoading ? "Chargement…" : "Choisir une équipe"} />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                <SelectItem value="__none__">Aucune équipe</SelectItem>
                                {activeTeamsSorted.map((team) => (
                                  <SelectItem key={team.id} value={team.id}>
                                    <span className="flex items-center gap-2">
                                      <span
                                        className="h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-border"
                                        style={{ backgroundColor: team.color }}
                                        aria-hidden
                                      />
                                      {team.name}
                                    </span>
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </TabsContent>
                    <TabsContent value="contrat">
                      <div className="space-y-4">
                        <FormField control={form.control} name="hire_date" render={({ field }) => (<FormItem><FormLabel>Date d'entrée</FormLabel><FormControl><Input type="date" {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <FormField control={form.control} name="job_title" render={({ field }) => (<FormItem><FormLabel>Intitulé du poste</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <EmployeeContractConfigFormFields control={form.control} />
                        <div className="space-y-4 rounded-md border border-dashed p-4">
                          <FormField
                            control={form.control}
                            name="has_periode_essai"
                            render={({ field }) => (
                              <FormItem className="flex flex-row items-center justify-between gap-4">
                                <div className="space-y-1">
                                  <FormLabel>Période d&apos;essai</FormLabel>
                                  <p className="text-xs text-muted-foreground">
                                    Active le suivi des échéances et alimente le contrat PDF.
                                  </p>
                                </div>
                                <FormControl>
                                  <Switch checked={field.value} onCheckedChange={field.onChange} />
                                </FormControl>
                              </FormItem>
                            )}
                          />
                          {form.watch("has_periode_essai") && (
                            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                              <FormField
                                control={form.control}
                                name="periode_essai.duree_initiale"
                                render={({ field }) => (
                                  <FormItem>
                                    <FormLabel>Durée</FormLabel>
                                    <FormControl>
                                      <Input type="number" min={1} {...field} />
                                    </FormControl>
                                    <FormMessage />
                                  </FormItem>
                                )}
                              />
                              <FormField
                                control={form.control}
                                name="periode_essai.unite"
                                render={({ field }) => (
                                  <FormItem>
                                    <FormLabel>Unité</FormLabel>
                                    <Select value={field.value} onValueChange={field.onChange}>
                                      <FormControl>
                                        <SelectTrigger>
                                          <SelectValue />
                                        </SelectTrigger>
                                      </FormControl>
                                      <SelectContent>
                                        <SelectItem value="jours">Jours</SelectItem>
                                        <SelectItem value="semaines">Semaines</SelectItem>
                                        <SelectItem value="mois">Mois</SelectItem>
                                      </SelectContent>
                                    </Select>
                                    <FormMessage />
                                  </FormItem>
                                )}
                              />
                              <FormField
                                control={form.control}
                                name="periode_essai.renouvellement_possible"
                                render={({ field }) => (
                                  <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4 sm:mt-6">
                                    <FormControl>
                                      <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                                    </FormControl>
                                    <div className="space-y-1 leading-none">
                                      <FormLabel>Renouvellement possible</FormLabel>
                                    </div>
                                  </FormItem>
                                )}
                              />
                            </div>
                          )}
                        </div>
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:items-end">
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
                              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
                          <h3 className="font-semibold mb-2">Statut JEI — personnel R&D</h3>
                          <FormField
                            control={form.control}
                            name="specificites_paie.personnel_rd_eligible_jei"
                            render={({ field }) => (
                              <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                                <FormControl>
                                  <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                                </FormControl>
                                <div className="space-y-1 leading-none">
                                  <FormLabel>Personnel R&D éligible à l&apos;exonération JEI</FormLabel>
                                  <p className="text-xs text-muted-foreground">
                                    Chercheurs, ingénieurs, techniciens R&D, gestionnaires de projet R&D,
                                    etc. L&apos;entreprise doit avoir le statut JEI activé dans les paramètres paie.
                                  </p>
                                </div>
                              </FormItem>
                            )}
                          />
                        </div>
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
                                  <p className="text-xs text-muted-foreground">
                                    Remboursement URSSAF : 50 % ajouté au net à payer.
                                  </p>
                                </FormItem>
                              )}
                            />
                            <FormField
                              control={form.control}
                              name="specificites_paie.transport.indemnite_mensuelle_nette"
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Indemnité transport contractuelle (€ net/mois)</FormLabel>
                                  <FormControl><Input type="number" step="0.01" {...field} /></FormControl>
                                  <p className="text-xs text-muted-foreground">
                                    Montant fixe au contrat, versé en net chaque mois.
                                  </p>
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
                              ) : filteredMutuelles.length === 0 ? (
                                <p className="text-sm text-muted-foreground text-center">
                                  Aucune formule compatible avec le statut {employeeStatut ?? 'sélectionné'}.
                                </p>
                              ) : (
                                <FormField
                                  control={form.control}
                                  name="specificites_paie.mutuelle.mutuelle_type_ids"
                                  render={({ field }) => (
                                    <FormItem>
                                      <FormLabel>Sélectionner la formule de mutuelle</FormLabel>
                                      <MutuelleSelectionField
                                        mutuelles={availableMutuelles}
                                        value={field.value?.[0] ?? null}
                                        onChange={(id) => field.onChange([id])}
                                        employeeStatut={employeeStatut}
                                        companyOrganismeLabel={companyOrganismeLabel}
                                        loading={loadingMutuelles}
                                        emptyMessage={
                                          filteredMutuelles.length === 0
                                            ? `Aucune formule compatible avec le statut ${employeeStatut ?? 'sélectionné'}.`
                                            : "Aucune formule de mutuelle disponible. Veuillez en créer dans l'onglet Mutuelle de Mon Entreprise."
                                        }
                                      />
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
                                      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
                            <PrevoyanceAffiliationFields
                              control={form.control}
                              namePrefix="specificites_paie.prevoyance"
                              statut={employeeStatut}
                            />
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
  );
}
