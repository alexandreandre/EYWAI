import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Loader2,
  PlusCircle,
  Search,
  Filter,
  Edit,
  Trash2,
  Shield,
  Building,
  Mail,
  Briefcase,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Users as UsersIcon,
  Upload,
  FileText,
  Sparkles,
} from 'lucide-react';
import {
  getCompanyUsers,
  getAccessibleCompaniesForUserCreation,
  getRoleTemplates,
  getRoleTemplate,
  quickCreateRoleTemplate,
  createRoleTemplate,
  createUserWithPermissions,
  updateUserWithPermissions,
  getAllPermissions,
  AccessibleCompany,
  UserCompanyAccessData,
  RoleTemplateDetail,
} from '../api/permissions';
import PermissionsMatrix from '../components/PermissionsMatrix';
import { cn } from '../lib/utils';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from '../components/ui/dialog';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '../components/ui/form';
import { Input } from '../components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Checkbox } from '../components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useFieldArray } from 'react-hook-form';
import apiClient from '../api/apiClient';
import { mutuelleTypesApi, MutuelleType } from '../api/mutuelleTypes';
import * as collectiveAgreementsApi from '../api/collectiveAgreements';
import { CONTRACT_TYPES, EMPLOYEE_STATUSES } from '../constants/contracts';

interface UserDetail {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  job_title?: string;
  company_id: string;
  role: 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom';
  role_template_name?: string;  // Nom du template de rôle pour les rôles custom
  created_at: string;
  can_edit: boolean;
}

// État d'accès entreprise pour l'onglet Accès RH (réplique UserCreation)
interface CompanyAccessState extends UserCompanyAccessData {
  enabled: boolean;
  expanded: boolean;
  templates: RoleTemplateDetail[];
  loadingTemplates: boolean;
  isCreatingNewRole: boolean;
  customRoles: RoleTemplateDetail[];
  loadingCustomRoles: boolean;
  hasAllPermissions: boolean; // Option "Tout" : toutes les permissions RH
  newRoleData: {
    name: string;
    job_title: string;
    description: string;
    base_role: 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom';
  };
}

// Schéma de validation Zod pour le formulaire de création de collaborateur
const collaboratorFormSchema = z.object({
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
  is_subject_to_residence_permit: z.boolean().optional(),
  residence_permit_expiry_date: z.string().optional(),
  residence_permit_type: z.string().optional(),
  residence_permit_number: z.string().optional(),
  hire_date: z.string().refine((d) => !isNaN(Date.parse(d)), { message: "Date invalide." }),
  contract_type: z.string().min(2),
  statut: z.string().min(2),
  job_title: z.string().min(2),
  is_temps_partiel: z.boolean(),
  duree_hebdomadaire: z.coerce.number().positive(),
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
  if (data.statut?.toLowerCase() === 'cadre' && data.specificites_paie.prevoyance.adhesion) {
    if (!data.specificites_paie.prevoyance.lignes_specifiques || data.specificites_paie.prevoyance.lignes_specifiques.length === 0) {
      return;
    }
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

const UserManagement: React.FC = () => {
  const navigate = useNavigate();

  const [accessibleCompanies, setAccessibleCompanies] = useState<AccessibleCompany[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>('');
  const [users, setUsers] = useState<UserDetail[]>([]);
  const [filteredUsers, setFilteredUsers] = useState<UserDetail[]>([]);
  const [customRoles, setCustomRoles] = useState<Array<{ id: string; name: string }>>([]);

  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('');
  const [loading, setLoading] = useState(true);

  // États pour le modal de création de collaborateur
  const [isCollaboratorDialogOpen, setIsCollaboratorDialogOpen] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [validationErrorSummary, setValidationErrorSummary] = useState<string[] | null>(null);
  const [serverFieldErrors, setServerFieldErrors] = useState<Record<string, string> | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState<string | null>(null);
  const [extractionSuccess, setExtractionSuccess] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadedRibFile, setUploadedRibFile] = useState<File | null>(null);
  const [isExtractingRib, setIsExtractingRib] = useState(false);
  const [ribExtractionError, setRibExtractionError] = useState<string | null>(null);
  const [ribExtractionSuccess, setRibExtractionSuccess] = useState(false);
  const [isRibDragging, setIsRibDragging] = useState(false);
  const [uploadedIdFile, setUploadedIdFile] = useState<File | null>(null);
  const [isIdDragging, setIsIdDragging] = useState(false);
  const [identityDocumentType, setIdentityDocumentType] = useState<"identity" | "residence_permit">("identity");
  const [uploadedQuestionnaireFile, setUploadedQuestionnaireFile] = useState<File | null>(null);
  const [isExtractingQuestionnaire, setIsExtractingQuestionnaire] = useState(false);
  const [questionnaireExtractionError, setQuestionnaireExtractionError] = useState<string | null>(null);
  const [questionnaireExtractionSuccess, setQuestionnaireExtractionSuccess] = useState(false);
  const [isQuestionnaireDragging, setIsQuestionnaireDragging] = useState(false);
  const [generatePdfContract, setGeneratePdfContract] = useState(false);
  const [companyAgreements, setCompanyAgreements] = useState<collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails[]>([]);
  const [classificationsCc, setClassificationsCc] = useState<collectiveAgreementsApi.ClassificationConventionnelle[]>([]);
  const [availableMutuelles, setAvailableMutuelles] = useState<MutuelleType[]>([]);
  const [loadingMutuelles, setLoadingMutuelles] = useState(false);

  // Onglets Nouveau Collaborateur : Accès Collaborateur / Accès RH
  const [hasCollaboratorAccess, setHasCollaboratorAccess] = useState(true);
  const [hasRHAccess, setHasRHAccess] = useState(false);
  // Accès RH pur : identité pour créer un utilisateur sans fiche employé
  const [rhOnlyIdentity, setRhOnlyIdentity] = useState({ first_name: '', last_name: '', email: '' });
  const [rhOnlySubmitting, setRhOnlySubmitting] = useState(false);
  const [newCollaboratorMainTab, setNewCollaboratorMainTab] = useState<'collab' | 'rh'>('collab');
  // Accès RH : entreprises et rôles (réplique UserCreation)
  const [rhAccessibleCompanies, setRhAccessibleCompanies] = useState<AccessibleCompany[]>([]);
  const [rhCompanyAccesses, setRhCompanyAccesses] = useState<{ [companyId: string]: CompanyAccessState }>({});
  const [rhLoadingCompanies, setRhLoadingCompanies] = useState(false);
  const [rhCreatingTemplate, setRhCreatingTemplate] = useState(false);
  const [rhError, setRhError] = useState<string | null>(null);

  useEffect(() => {
    loadAccessibleCompanies();
  }, []);

  useEffect(() => {
    if (selectedCompanyId) {
      loadUsers();
    }
  }, [selectedCompanyId]);

  useEffect(() => {
    applyFilters();
  }, [users, searchQuery, roleFilter]);

  // Formulaire pour la création de collaborateur (déclaré avant les useEffect qui l'utilisent)
  const collaboratorForm = useForm<z.infer<typeof collaboratorFormSchema>>({
    resolver: zodResolver(collaboratorFormSchema),
    defaultValues: {
      first_name: "", last_name: "", email: "", nir: "", date_naissance: "",
      lieu_naissance: "", nationalite: "Française",
      adresse: { rue: "", code_postal: "", ville: "" },
      coordonnees_bancaires: { iban: "", bic: "" },
      is_subject_to_residence_permit: false,
      residence_permit_expiry_date: "",
      residence_permit_type: "",
      residence_permit_number: "",
      hire_date: new Date().toISOString().split('T')[0],
      contract_type: "CDI", statut: "Non-Cadre", job_title: "",
      is_temps_partiel: false,
      duree_hebdomadaire: 39,
      salaire_de_base: { valeur: 2365.66 },
      classification_conventionnelle: { groupe_emploi: "C", classe_emploi: 6, coefficient: 240 },
      collective_agreement_id: null as string | null,
      avantages_en_nature: {
        repas: { nombre_par_mois: 0 },
        logement: { beneficie: false },
        vehicule: { beneficie: false },
      },
      specificites_paie: {
        is_alsace_moselle: false,
        prelevement_a_la_source: { is_personnalise: false, taux: 0 },
        transport: { abonnement_mensuel_total: 0 },
        titres_restaurant: { beneficie: true, nombre_par_mois: 0 },
        mutuelle: { mutuelle_type_ids: [], lignes_specifiques: [] },
        prevoyance: { adhesion: true, lignes_specifiques: [] },
      },
    },
  });

  // Déclarer ces variables avant les useEffect qui les utilisent
  const isCadre = collaboratorForm.watch("statut")?.toLowerCase() === 'cadre';
  const selectedCcId = collaboratorForm.watch("collective_agreement_id");

  // Charger les conventions collectives quand le modal s'ouvre
  useEffect(() => {
    if (isCollaboratorDialogOpen) {
      collectiveAgreementsApi.getMyCompanyAgreements()
        .then((res) => setCompanyAgreements(res.data || []))
        .catch(() => setCompanyAgreements([]));
    }
  }, [isCollaboratorDialogOpen]);

  // Charger les entreprises accessibles pour l'onglet Accès RH
  useEffect(() => {
    if (isCollaboratorDialogOpen && hasRHAccess) {
      setRhLoadingCompanies(true);
      getAccessibleCompaniesForUserCreation()
        .then((companies) => {
          setRhAccessibleCompanies(companies);
          const initial: { [companyId: string]: CompanyAccessState } = {};
          companies.forEach((c) => {
            initial[c.company_id] = {
              company_id: c.company_id,
              base_role: '' as any,
              is_primary: false,
              role_template_id: undefined,
              permission_ids: [],
              enabled: false,
              expanded: false,
              templates: [],
              loadingTemplates: false,
              isCreatingNewRole: false,
              customRoles: [],
              loadingCustomRoles: false,
              hasAllPermissions: false,
              newRoleData: {
                name: '',
                job_title: '',
                description: '',
                base_role: 'custom',
              },
            };
          });
          setRhCompanyAccesses(initial);
          if (companies.length === 1) {
            setRhCompanyAccesses((prev) => ({
              ...prev,
              [companies[0].company_id]: {
                ...prev[companies[0].company_id],
                enabled: true,
                expanded: true,
                is_primary: true,
              },
            }));
            loadCustomRolesForCompany(companies[0].company_id);
          }
        })
        .catch(() => setRhAccessibleCompanies([]))
        .finally(() => setRhLoadingCompanies(false));
    }
  }, [isCollaboratorDialogOpen, hasRHAccess]);

  const loadRoleTemplatesForCompany = async (companyId: string, baseRole: string) => {
    try {
      setRhCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: { ...prev[companyId], loadingTemplates: true },
      }));
      const templates = await getRoleTemplates(companyId, baseRole, true);
      setRhCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: { ...prev[companyId], templates, loadingTemplates: false },
      }));
    } catch {
      setRhCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: { ...prev[companyId], loadingTemplates: false },
      }));
    }
  };

  const loadTemplatePermissions = async (companyId: string, templateId: string) => {
    try {
      const template = await getRoleTemplate(templateId);
      const permissionIds = template.permissions.map((p) => p.id);
      setRhCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: { ...prev[companyId], permission_ids: permissionIds },
      }));
    } catch (err) {
      console.error('Erreur chargement permissions template:', err);
    }
  };

  const loadCustomRolesForCompany = async (companyId: string) => {
    try {
      setRhCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: { ...prev[companyId], loadingCustomRoles: true },
      }));
      const customRoles = await getRoleTemplates(companyId, 'custom', false);
      setRhCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: { ...prev[companyId], customRoles, loadingCustomRoles: false },
      }));
    } catch {
      setRhCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: { ...prev[companyId], loadingCustomRoles: false },
      }));
    }
  };

  const handleRhToggleCompany = (companyId: string, enabled: boolean) => {
    setRhCompanyAccesses((prev) => {
      const next = { ...prev, [companyId]: { ...prev[companyId], enabled, expanded: enabled } };
      if (enabled) {
        if (hasCollaboratorAccess && hasRHAccess) {
          // Accès Collaborateur + RH : rôle forcé à collaborateur_rh
          next[companyId] = { ...next[companyId], base_role: 'collaborateur_rh' as const };
        } else if (hasRHAccess && !hasCollaboratorAccess) {
          // Accès RH seul : rôle par défaut 'rh'
          next[companyId] = { ...next[companyId], base_role: 'rh' as const };
        }
      }
      return next;
    });
    if (enabled) loadCustomRolesForCompany(companyId);
  };

  const handleRhToggleExpand = (companyId: string) => {
    setRhCompanyAccesses((prev) => ({
      ...prev,
      [companyId]: { ...prev[companyId], expanded: !prev[companyId].expanded },
    }));
  };

  const handleRhSetPrimary = (companyId: string) => {
    setRhCompanyAccesses((prev) => {
      const updated = { ...prev };
      Object.keys(updated).forEach((id) => {
        updated[id] = { ...updated[id], is_primary: false };
      });
      updated[companyId] = { ...updated[companyId], is_primary: true };
      return updated;
    });
  };

  const handleRhSelectNewRole = (companyId: string) => {
    setRhCompanyAccesses((prev) => ({
      ...prev,
      [companyId]: {
        ...prev[companyId],
        base_role: '' as any,
        isCreatingNewRole: true,
        role_template_id: undefined,
        permission_ids: [],
        newRoleData: {
          name: '',
          job_title: '',
          description: '',
          base_role: 'custom',
        },
      },
    }));
  };

  const handleRhRoleChange = (companyId: string, role: 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur') => {
    setRhCompanyAccesses((prev) => ({
      ...prev,
      [companyId]: {
        ...prev[companyId],
        base_role: role,
        isCreatingNewRole: false,
        role_template_id: undefined,
        permission_ids: [],
      },
    }));
    loadRoleTemplatesForCompany(companyId, role);
  };

  const handleRhSelectExistingCustomRole = async (companyId: string, roleTemplateId: string) => {
    try {
      const template = await getRoleTemplate(roleTemplateId);
      const permissionIds = template.permissions.map((p) => p.id);
      setRhCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: {
          ...prev[companyId],
          base_role: 'custom',
          isCreatingNewRole: false,
          role_template_id: roleTemplateId,
          permission_ids: permissionIds,
        },
      }));
    } catch (err) {
      console.error('Erreur chargement rôle custom:', err);
      setRhError('Erreur lors du chargement du rôle');
    }
  };

  const handleRhTemplateChange = (companyId: string, templateId: string) => {
    setRhCompanyAccesses((prev) => ({
      ...prev,
      [companyId]: { ...prev[companyId], role_template_id: templateId || undefined },
    }));
    if (templateId) loadTemplatePermissions(companyId, templateId);
    else {
      setRhCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: { ...prev[companyId], permission_ids: [] },
      }));
    }
  };

  const handleRhPermissionsChange = (companyId: string, permissions: string[]) => {
    setRhCompanyAccesses((prev) => ({
      ...prev,
      [companyId]: { ...prev[companyId], permission_ids: permissions },
    }));
  };

  const handleRhCreateNewRoleTemplate = async (companyId: string) => {
    const access = rhCompanyAccesses[companyId];
    if (!access) return;
    if (!access.newRoleData.name || !access.newRoleData.job_title) {
      setRhError('Veuillez remplir le nom et le titre du poste pour le nouveau rôle');
      return;
    }
    if (access.permission_ids.length === 0) {
      setRhError('Veuillez sélectionner au moins une permission');
      return;
    }
    try {
      setRhCreatingTemplate(true);
      setRhError(null);
      const baseRole = access.newRoleData.base_role;
      const payload = {
        company_id: companyId,
        name: access.newRoleData.name,
        job_title: access.newRoleData.job_title,
        description: access.newRoleData.description,
        permission_ids: access.permission_ids,
      };
      const useCreateApi = baseRole === 'custom' || baseRole === 'collaborateur_rh';
      if (useCreateApi) {
        const created = await createRoleTemplate({
          ...payload,
          base_role: baseRole,
        });
        setRhCompanyAccesses((prev) => ({
          ...prev,
          [companyId]: {
            ...prev[companyId],
            base_role: baseRole as any,
            role_template_id: created.id,
            isCreatingNewRole: false,
          },
        }));
      } else {
        const result = await quickCreateRoleTemplate({
          ...payload,
          base_role: baseRole as 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur',
        });
        setRhCompanyAccesses((prev) => ({
          ...prev,
          [companyId]: {
            ...prev[companyId],
            base_role: baseRole as any,
            role_template_id: result.template_id,
            isCreatingNewRole: false,
          },
        }));
      }
      await loadCustomRolesForCompany(companyId);
    } catch (err: any) {
      setRhError(err.response?.data?.detail || 'Erreur lors de la création du template');
    } finally {
      setRhCreatingTemplate(false);
    }
  };

  // Charger les classifications quand une convention collective est sélectionnée
  useEffect(() => {
    if (selectedCcId && selectedCcId !== "__aucune__") {
      collectiveAgreementsApi.getClassifications(selectedCcId)
        .then((res) => {
          const list = res.data || [];
          setClassificationsCc(list);
          if (list.length > 0) {
            const current = collaboratorForm.getValues("classification_conventionnelle");
            const currentKey = current ? `${current.groupe_emploi}-${current.classe_emploi}-${current.coefficient}` : "";
            const exists = list.some((c) => `${c.groupe_emploi}-${c.classe_emploi}-${c.coefficient}` === currentKey);
            if (!exists) {
              collaboratorForm.setValue("classification_conventionnelle", { groupe_emploi: list[0].groupe_emploi, classe_emploi: list[0].classe_emploi, coefficient: list[0].coefficient });
            }
          }
        })
        .catch(() => setClassificationsCc([]));
    } else {
      setClassificationsCc([]);
    }
  }, [selectedCcId, collaboratorForm]);

  // Charger les mutuelles disponibles
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

  const loadAccessibleCompanies = async () => {
    try {
      const companies = await getAccessibleCompaniesForUserCreation();
      setAccessibleCompanies(companies);

      // Présélectionner la première entreprise
      if (companies.length > 0) {
        setSelectedCompanyId(companies[0].company_id);
      }
    } catch (error) {
      console.error('Erreur lors du chargement des entreprises:', error);
    }
  };

  const loadUsers = async () => {
    if (!selectedCompanyId) return;

    try {
      setLoading(true);
      const data = await getCompanyUsers(selectedCompanyId);
      setUsers(data);

      // Extraire les rôles custom uniques
      const customRolesList = data
        .filter((user) => user.role === 'custom' && user.role_template_name)
        .reduce((acc: Array<{ id: string; name: string }>, user) => {
          // Utiliser un Map pour éviter les doublons basés sur le nom
          const existing = acc.find((r: { id: string; name: string }) => r.name === user.role_template_name);
          if (!existing) {
            acc.push({ id: user.role_template_name!, name: user.role_template_name! });
          }
          return acc;
        }, [] as Array<{ id: string; name: string }>);

      setCustomRoles(customRolesList);
    } catch (error) {
      console.error('Erreur lors du chargement des utilisateurs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleViewProfile = (userId: string) => {
    navigate(`/users/${userId}`);
  };

  const applyFilters = () => {
    let filtered = [...users];

    // Filtre de recherche
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (user) =>
          user.first_name.toLowerCase().includes(query) ||
          user.last_name.toLowerCase().includes(query) ||
          user.email.toLowerCase().includes(query) ||
          (user.job_title && user.job_title.toLowerCase().includes(query))
      );
    }

    // Filtre de rôle
    if (roleFilter) {
      // Si c'est un rôle de base (admin, rh, collaborateur_rh, collaborateur), filtrer normalement
      if (['admin', 'rh', 'collaborateur_rh', 'collaborateur'].includes(roleFilter)) {
        filtered = filtered.filter((user) => user.role === roleFilter);
      } else {
        // Sinon c'est un rôle custom, filtrer par le nom du template
        filtered = filtered.filter((user) => user.role === 'custom' && user.role_template_name === roleFilter);
      }
    }

    setFilteredUsers(filtered);
  };

  const { fields: mutuelleFields, append: appendMutuelle, remove: removeMutuelle } = useFieldArray({
    control: collaboratorForm.control,
    name: "specificites_paie.mutuelle.lignes_specifiques",
  });

  const { fields: prevoyanceFields, append: appendPrevoyance, remove: removePrevoyance } = useFieldArray({
    control: collaboratorForm.control,
    name: "specificites_paie.prevoyance.lignes_specifiques",
  });

  const handleCreateUser = () => {
    navigate('/users/create');
  };

  const handleCreateCollaborator = () => {
    setIsCollaboratorDialogOpen(true);
  };

  const handleEditUser = (userId: string) => {
    console.log('[UserManagement] handleEditUser called with userId:', userId);
    console.log('[UserManagement] Navigating to:', `/users/${userId}/edit`);
    navigate(`/users/${userId}/edit`);
    console.log('[UserManagement] navigate() called');
  };

  const roleLabels: { [key: string]: string } = {
    admin: 'Administrateur',
    rh: 'Ressources Humaines',
    collaborateur_rh: 'Collaborateur RH',
    collaborateur: 'Collaborateur',
    custom: 'Personnalisé',
  };

  const roleColors: { [key: string]: string } = {
    admin: 'bg-purple-100 text-purple-800 border-purple-200',
    rh: 'bg-blue-100 text-blue-800 border-blue-200',
    collaborateur_rh: 'bg-green-100 text-green-800 border-green-200',
    collaborateur: 'bg-gray-100 text-gray-800 border-gray-200',
    custom: 'bg-orange-100 text-orange-800 border-orange-200',
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

  // Fonction pour traiter un fichier PDF (contrat)
  const processPdfFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setExtractionError("Veuillez sélectionner un fichier PDF.");
      return;
    }
    setUploadedFile(file);
    setIsExtracting(true);
    setExtractionError(null);
    setExtractionSuccess(false);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await apiClient.post('/api/contract-parser/extract-from-pdf', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const extractedData = response.data.extracted_data;
      const warnings = response.data.warnings || [];
      const mergeFormValues = (extracted: any) => {
        const currentValues = collaboratorForm.getValues();
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
            id: ligne.id || `mutuelle_extracted_${Date.now() + index}`
          }));
      }
      if (mergedValues.specificites_paie?.prevoyance?.lignes_specifiques) {
         mergedValues.specificites_paie.prevoyance.lignes_specifiques = 
          mergedValues.specificites_paie.prevoyance.lignes_specifiques.map((ligne: any, index: number) => ({
            ...ligne,
            id: ligne.id || `prevoyance_extracted_${Date.now() + index}`
          }));
      }
      collaboratorForm.reset(mergedValues);
      setExtractionSuccess(true);
      if (warnings.length > 0) {
        setExtractionError(`Extraction réussie avec des avertissements : ${warnings.join(', ')}`);
      }
    } catch (error: any) {
      console.error("Erreur lors de l'extraction du PDF :", error);
      setExtractionError(error.response?.data?.detail || "Erreur lors de l'extraction du PDF. Veuillez réessayer.");
    } finally {
      setIsExtracting(false);
    }
  };

  const handlePdfUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await processPdfFile(file);
  };

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
      await processPdfFile(files[0]);
    }
  };

  // Fonction pour traiter un fichier RIB PDF
  const processRibPdfFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setRibExtractionError("Veuillez sélectionner un fichier PDF.");
      return;
    }
    setUploadedRibFile(file);
    setIsExtractingRib(true);
    setRibExtractionError(null);
    setRibExtractionSuccess(false);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await apiClient.post('/api/contract-parser/extract-rib-from-pdf', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const extractedData = response.data.extracted_data;
      const currentValues = collaboratorForm.getValues();
      const updatedValues = {
        ...currentValues,
        coordonnees_bancaires: {
          iban: extractedData.iban || currentValues.coordonnees_bancaires?.iban || '',
          bic: extractedData.bic || currentValues.coordonnees_bancaires?.bic || '',
        }
      };
      collaboratorForm.reset(updatedValues);
      setRibExtractionSuccess(true);
    } catch (error: any) {
      console.error("Erreur lors de l'extraction du RIB :", error);
      setRibExtractionError(error.response?.data?.detail || "Erreur lors de l'extraction du RIB. Veuillez réessayer.");
    } finally {
      setIsExtractingRib(false);
    }
  };

  const handleRibPdfUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await processRibPdfFile(file);
  };

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
      await processRibPdfFile(files[0]);
    }
  };

  // Fonction pour traiter un fichier de pièce d'identité
  const processIdFile = async (file: File) => {
    const isPdf = file.name.toLowerCase().endsWith('.pdf');
    const isImage = file.type.startsWith('image/') || 
                    file.name.toLowerCase().match(/\.(jpg|jpeg|png|gif|bmp|webp)$/);
    if (!isPdf && !isImage) {
      alert("Veuillez sélectionner un fichier PDF ou une image (JPG, PNG, etc.).");
      return;
    }
    setUploadedIdFile(file);
  };

  const handleIdFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await processIdFile(file);
  };

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
      await processIdFile(files[0]);
    }
  };

  // Fonction pour traiter un fichier questionnaire d'embauche PDF
  const processQuestionnairePdfFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setQuestionnaireExtractionError("Veuillez sélectionner un fichier PDF.");
      return;
    }
    setUploadedQuestionnaireFile(file);
    setIsExtractingQuestionnaire(true);
    setQuestionnaireExtractionError(null);
    setQuestionnaireExtractionSuccess(false);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await apiClient.post('/api/contract-parser/extract-questionnaire-from-pdf', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const extractedData = response.data.extracted_data;
      const mergeFormValues = (extracted: any) => {
        const currentValues = collaboratorForm.getValues();
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
            id: ligne.id || `mutuelle_extracted_${Date.now() + index}`
          }));
      }
      if (mergedValues.specificites_paie?.prevoyance?.lignes_specifiques) {
         mergedValues.specificites_paie.prevoyance.lignes_specifiques = 
          mergedValues.specificites_paie.prevoyance.lignes_specifiques.map((ligne: any, index: number) => ({
            ...ligne,
            id: ligne.id || `prevoyance_extracted_${Date.now() + index}`
          }));
      }
      collaboratorForm.reset(mergedValues);
      setQuestionnaireExtractionSuccess(true);
    } catch (error: any) {
      console.error("Erreur lors de l'extraction du questionnaire :", error);
      setQuestionnaireExtractionError(error.response?.data?.detail || "Erreur lors de l'extraction du questionnaire d'embauche. Veuillez réessayer.");
    } finally {
      setIsExtractingQuestionnaire(false);
    }
  };

  const handleQuestionnairePdfUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await processQuestionnairePdfFile(file);
  };

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
      await processQuestionnairePdfFile(files[0]);
    }
  };

  // Générer un mot de passe temporaire
  const generateTempPassword = () => {
    const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%*?';
    return Array.from({ length: 12 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
  };

  // Soumission pour accès RH pur (sans fiche employé)
  const handleRhOnlySubmit = async () => {
    setServerError(null);
    const { first_name, last_name, email } = rhOnlyIdentity;
    if (!first_name?.trim() || first_name.trim().length < 2) {
      setServerError('Prénom requis (min. 2 caractères)');
      return;
    }
    if (!last_name?.trim() || last_name.trim().length < 2) {
      setServerError('Nom requis (min. 2 caractères)');
      return;
    }
    if (!email?.trim()) {
      setServerError('Email requis');
      return;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.trim())) {
      setServerError('Adresse e-mail invalide');
      return;
    }
    const enabledAccesses = Object.values(rhCompanyAccesses).filter((a) => a.enabled);
    if (enabledAccesses.length === 0) {
      setServerError("Veuillez activer au moins une entreprise pour l'accès RH");
      return;
    }
    for (const access of enabledAccesses) {
      if (!access.base_role && !access.role_template_id) {
        setServerError("Veuillez sélectionner un rôle pour toutes les entreprises activées");
        return;
      }
    }
    setRhOnlySubmitting(true);
    try {
      const password = generateTempPassword();
      const isSingleCompany = enabledAccesses.length === 1;
      const company_accesses = await Promise.all(
        enabledAccesses.map(async (access) => {
          let permissionIds: string[] = [];
          if (access.hasAllPermissions) {
            const allPerms = await getAllPermissions();
            const rhPerms = allPerms.filter(
              (p) => !p.required_role || ['rh', 'collaborateur_rh', 'admin'].includes(p.required_role)
            );
            permissionIds = rhPerms.map((p) => p.id);
          } else if (access.role_template_id || (access.permission_ids?.length ?? 0) > 0) {
            permissionIds = access.permission_ids || [];
          }
          const baseRole = access.base_role || 'rh';
          return {
            company_id: access.company_id,
            base_role: baseRole,
            is_primary: isSingleCompany ? true : access.is_primary,
            role_template_id: access.role_template_id || undefined,
            permission_ids: permissionIds,
          };
        })
      );
      await createUserWithPermissions({
        email: email.trim(),
        password,
        first_name: first_name.trim(),
        last_name: last_name.trim(),
        company_accesses,
      });
      setIsCollaboratorDialogOpen(false);
      setRhOnlyIdentity({ first_name: '', last_name: '', email: '' });
      setHasRHAccess(false);
      setRhCompanyAccesses({});
      setRhError(null);
      await loadUsers();
      alert(`Utilisateur RH créé avec succès.\n\nIdentifiants :\nEmail : ${email.trim()}\nMot de passe : ${password}\n\nTransmettez ces identifiants à l'utilisateur en toute sécurité.`);
    } catch (err: any) {
      setServerError(err.response?.data?.detail || "Erreur lors de la création de l'utilisateur RH");
    } finally {
      setRhOnlySubmitting(false);
    }
  };

  // Fonction de soumission du formulaire
  const onCollaboratorSubmit = async (values: z.infer<typeof collaboratorFormSchema>) => {
    setValidationErrorSummary(null);
    setServerError(null);
    setServerFieldErrors(null);
    
    // Vérifier si l'accès RH est activé et si des entreprises sont configurées
    const hasRHAccessEnabled = hasRHAccess && Object.values(rhCompanyAccesses).some((access) => access.enabled);
    
    // Si accès RH activé, valider qu'au moins une entreprise est configurée avec un rôle
    if (hasRHAccessEnabled) {
      const enabledAccesses = Object.values(rhCompanyAccesses).filter((access) => access.enabled);
      if (enabledAccesses.length === 0) {
        setServerError("Veuillez activer au moins une entreprise pour l'accès RH");
        return;
      }
      // Si plusieurs entreprises : exiger qu'une soit marquée comme primaire
      if (enabledAccesses.length > 1) {
        const primaryAccess = enabledAccesses.find((access) => access.is_primary);
        if (!primaryAccess) {
          setServerError("Veuillez marquer une entreprise comme primaire pour l'accès RH");
          return;
        }
      }
      const isCollaboratorWithRH = hasCollaboratorAccess && hasRHAccess;
      for (const access of enabledAccesses) {
        if (!isCollaboratorWithRH && !access.base_role && !access.role_template_id) {
          setServerError("Veuillez sélectionner un rôle pour toutes les entreprises activées");
          return;
        }
      }
    }
    
    const payload = {
      ...values,
      specificites_paie: {
        ...values.specificites_paie,
        mutuelle: {
          adhesion: (values.specificites_paie.mutuelle.mutuelle_type_ids?.length || 0) > 0 || (values.specificites_paie.mutuelle.lignes_specifiques?.length || 0) > 0,
          mutuelle_type_ids: values.specificites_paie.mutuelle.mutuelle_type_ids || [],
          lignes_specifiques: values.specificites_paie.mutuelle.lignes_specifiques || [],
        },
        prevoyance: {
          adhesion: values.specificites_paie.prevoyance.adhesion,
          lignes_specifiques: 
            (values.specificites_paie.prevoyance.adhesion && values.statut?.toLowerCase() === 'cadre') 
            ? values.specificites_paie.prevoyance.lignes_specifiques
            : [],
        },
      }
    };
    try {
      // 1. Créer l'employé (collaborateur)
      const formData = new FormData();
      formData.append('data', JSON.stringify(payload));
      formData.append('generate_pdf_contract', generatePdfContract.toString());
      if (uploadedFile && !generatePdfContract) {
        formData.append('file', uploadedFile, 'contrat.pdf');
      }
      if (uploadedIdFile) {
        formData.append('identity_file', uploadedIdFile);
      }
      const response = await apiClient.post('/api/employees', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      
      const newEmployeeData = response.data;
      const generatedPassword = newEmployeeData?.generated_password;
      const employeeEmail = newEmployeeData?.email || values.email;
      const userId = newEmployeeData?.id; // ID de l'utilisateur créé
      
      // 2. Si accès RH activé, créer les accès RH pour l'utilisateur existant
      if (hasRHAccessEnabled && userId) {
        try {
          const enabledAccesses = Object.values(rhCompanyAccesses).filter((access) => access.enabled);
          const isCollaboratorWithRH = hasCollaboratorAccess && hasRHAccess;
          // Quand l'utilisateur a coché Accès Collaborateur ET Accès RH (avec au moins 1 entreprise),
          // le rôle doit toujours être collaborateur_rh, quel que soit le rôle RH choisi (admin, rh, etc.).
          const effectiveRole = (access: typeof enabledAccesses[0]): 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom' => {
            if (isCollaboratorWithRH) return 'collaborateur_rh';
            if (hasRHAccess && !hasCollaboratorAccess) return (access.base_role as 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom') || 'rh';
            return (access.base_role as 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom') || 'collaborateur';
          };
          
          // Créer les accès pour chaque entreprise configurée
          // Si une seule entreprise, elle est automatiquement primaire
          const isSingleCompany = enabledAccesses.length === 1;
          for (const access of enabledAccesses) {
            try {
              const roleToUse = effectiveRole(access);
              const isPrimary = isSingleCompany ? true : access.is_primary;
              // Créer l'accès dans user_company_accesses via l'API (par user_id car l'email n'est pas dans profiles après création employé)
              await apiClient.post('/api/users/grant-access-by-user-id', {
                user_id: userId,
                company_id: access.company_id,
                role: roleToUse,
                is_primary: isPrimary,
              });
              
              // Gérer les permissions : soit "Tout", soit template/rôles spécifiques
              let permissionIdsToUse: string[] = [];
              
              if (access.hasAllPermissions) {
                // Option "Tout" : récupérer toutes les permissions RH disponibles
                try {
                  const allPermissions = await getAllPermissions();
                  // Filtrer les permissions RH (required_role est null, 'rh', 'collaborateur_rh', ou 'admin')
                  const rhPermissions = allPermissions.filter(
                    (p) => !p.required_role || ['rh', 'collaborateur_rh', 'admin'].includes(p.required_role)
                  );
                  permissionIdsToUse = rhPermissions.map((p) => p.id);
                } catch (permError) {
                  console.error("Erreur lors de la récupération de toutes les permissions:", permError);
                  // Continuer avec les permissions vides si erreur
                }
              } else if (access.role_template_id || access.permission_ids?.length > 0) {
                permissionIdsToUse = access.permission_ids || [];
              }
              
              // Mettre à jour les permissions si nécessaire
              if (access.hasAllPermissions || access.role_template_id || permissionIdsToUse.length > 0) {
                await updateUserWithPermissions(userId, {
                  company_id: access.company_id,
                  base_role: roleToUse,
                  role_template_id: access.role_template_id || undefined,
                  permission_ids: permissionIdsToUse,
                });
              }
            } catch (accessError: any) {
              console.error(`Erreur lors de la création de l'accès pour l'entreprise ${access.company_id}:`, accessError);
              const errorDetail = accessError.response?.data?.detail || accessError.message || "Erreur inconnue";
              console.error(`Détails de l'erreur:`, errorDetail);
              // Continuer avec les autres entreprises même si une échoue, mais collecter les erreurs
              const errorMessages = [];
              errorMessages.push(`Entreprise ${access.company_id}: ${errorDetail}`);
              // Afficher l'erreur immédiatement pour cette entreprise
              alert(`Erreur lors de la création de l'accès RH pour l'entreprise ${access.company_id}: ${errorDetail}`);
            }
          }
        } catch (rhError: any) {
          console.error("Erreur lors de la création des accès RH :", rhError);
          // Ne pas bloquer si l'employé a été créé, mais afficher un avertissement
          const rhErrorMessage = rhError.response?.data?.detail || "Erreur lors de la création des accès RH";
          alert(`Employé créé avec succès, mais erreur lors de la création des accès RH : ${rhErrorMessage}`);
        }
      }
      
      setIsCollaboratorDialogOpen(false);
      collaboratorForm.reset();
      setGeneratePdfContract(false);
      setIdentityDocumentType("identity");
      setUploadedIdFile(null);
      setHasCollaboratorAccess(true);
      setHasRHAccess(false);
      setNewCollaboratorMainTab('collab');
      setRhCompanyAccesses({});
      setRhError(null);
      await loadUsers();
      
      if (newEmployeeData && generatedPassword) {
        const pdfMessage = generatePdfContract
          ? '\n\nContrat disponible dans la section "Contrat"'
          : '\n\nUn PDF avec ces informations a été généré et est disponible dans la fiche de l\'employé.\nVeuillez le télécharger et le transmettre à l\'employé.';
        const warningsMessage = (newEmployeeData as { warnings?: string[] }).warnings?.length
          ? '\n\nAttention : ' + (newEmployeeData as { warnings?: string[] }).warnings!.join('\n')
          : '';
        const rhAccessMessage = hasRHAccessEnabled
          ? '\n\n✅ Accès RH créé avec succès'
          : '';
        const importantNote = hasRHAccessEnabled
          ? '\n\n⚠️ IMPORTANT: Utilisez le mot de passe ci-dessus pour vous connecter avec le nom d\'utilisateur ou l\'email.'
          : '';
        alert(`Employé créé avec succès !\n\nNom d'utilisateur: ${newEmployeeData.username}\nEmail: ${newEmployeeData.email}\nMot de passe temporaire: ${generatedPassword}${pdfMessage}${warningsMessage}${rhAccessMessage}${importantNote}`);
      }
    } catch (error: any) {
      console.error("Erreur lors de l'envoi au backend :", error.response?.data || error.message);
      if (error.response?.data?.field_errors) {
        const fieldErrors = error.response.data.field_errors;
        setServerFieldErrors(fieldErrors);
        Object.keys(fieldErrors).forEach((fieldPath) => {
          collaboratorForm.setError(fieldPath as any, {
            type: 'server',
            message: fieldErrors[fieldPath]
          });
        });
        setServerError(error.response.data.detail || "Erreur de validation des données");
      } else {
        setServerError(error.response?.data?.detail || "Une erreur inattendue est survenue. Veuillez réessayer.");
        setServerFieldErrors(null);
      }
    }
  };

  const onValidationErrors = (errors: any) => {
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
    setServerError(null);
  };

  if (loading && users.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  const selectedCompany = accessibleCompanies.find((c) => c.company_id === selectedCompanyId);

  return (
    <div className="space-y-6">
      {/* En-tête */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Gestion des utilisateurs</h1>
          <p className="text-gray-600">Gérez les accès et permissions de vos utilisateurs</p>
        </div>
        <div className="flex gap-2">
          <Dialog open={isCollaboratorDialogOpen} onOpenChange={(open) => {
            setIsCollaboratorDialogOpen(open);
            if (!open) {
              collaboratorForm.reset();
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
              setHasCollaboratorAccess(true);
              setHasRHAccess(false);
              setNewCollaboratorMainTab('collab');
              setRhCompanyAccesses({});
              setRhError(null);
              setRhOnlyIdentity({ first_name: '', last_name: '', email: '' });
            }
          }}>
            <DialogTrigger asChild>
              <Button onClick={handleCreateCollaborator}>
                <PlusCircle className="mr-2 h-4 w-4" />
                Nouvel utilisateur
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-4xl max-h-[90vh] flex flex-col">
              <DialogHeader>
                <DialogTitle>Nouveau Collaborateur</DialogTitle>
                <DialogDescription>
                  Accès collaborateur (fiche + contrat) et/ou accès RH (utilisateur applicatif).
                </DialogDescription>
              </DialogHeader>

              <Tabs value={newCollaboratorMainTab} onValueChange={(v) => setNewCollaboratorMainTab(v as 'collab' | 'rh')} className="w-full flex-1 flex flex-col min-h-0">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="collab">Accès Collaborateur</TabsTrigger>
                  <TabsTrigger value="rh">Accès RH</TabsTrigger>
                </TabsList>

                {/* Onglet 1 : Accès Collaborateur */}
                <TabsContent value="collab" className="flex-1 mt-4 min-h-0 flex flex-col">
                  <div className="flex items-center space-x-2 mb-4">
                    <Checkbox
                      id="access-collab"
                      checked={hasCollaboratorAccess}
                      onCheckedChange={(c) => setHasCollaboratorAccess(!!c)}
                    />
                    <Label htmlFor="access-collab" className="text-sm font-medium cursor-pointer">
                      Accès Collaborateur (fiche salarié, contrat, rémunération, avantages)
                    </Label>
                  </div>
                  <div className={cn(!hasCollaboratorAccess && 'pointer-events-none opacity-50')}>
                    <Form {...collaboratorForm}>
                      <form id="collab-form" onSubmit={collaboratorForm.handleSubmit(onCollaboratorSubmit, onValidationErrors)} className="flex flex-col min-h-0">
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
                              <label htmlFor="pdf-upload-collab" className="cursor-pointer">
                                <div className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors">
                                  <Upload className="h-4 w-4" />
                                  <span>{uploadedFile ? 'Changer le fichier' : 'Choisir un PDF'}</span>
                                </div>
                                <input
                                  id="pdf-upload-collab"
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
                            <label htmlFor="questionnaire-pdf-upload-collab" className="cursor-pointer">
                              <div className="flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 transition-colors">
                                <Upload className="h-4 w-4" />
                                <span>{uploadedQuestionnaireFile ? 'Changer le fichier' : 'Choisir un PDF'}</span>
                              </div>
                              <input
                                id="questionnaire-pdf-upload-collab"
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
                            <label htmlFor="rib-pdf-upload-collab" className="cursor-pointer">
                              <div className="flex items-center gap-2 px-3 py-1.5 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors text-sm">
                                <Upload className="h-3 w-3" />
                                <span>{uploadedRibFile ? 'Changer le RIB' : 'Choisir un RIB'}</span>
                              </div>
                              <input
                                id="rib-pdf-upload-collab"
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
                              collaboratorForm.setValue("is_subject_to_residence_permit", true);
                            } else {
                              collaboratorForm.setValue("is_subject_to_residence_permit", false);
                              collaboratorForm.setValue("residence_permit_expiry_date", "");
                              collaboratorForm.setValue("residence_permit_type", "");
                              collaboratorForm.setValue("residence_permit_number", "");
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
                            <label htmlFor="id-file-upload-collab" className="cursor-pointer">
                              <div className="flex items-center gap-2 px-3 py-1.5 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition-colors text-sm">
                                <Upload className="h-3 w-3" />
                                <span>{uploadedIdFile ? 'Changer le fichier' : 'Choisir un fichier'}</span>
                              </div>
                              <input
                                id="id-file-upload-collab"
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
                                control={collaboratorForm.control}
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
                                control={collaboratorForm.control}
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
                                control={collaboratorForm.control}
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
                        <FormField control={collaboratorForm.control} name="first_name" render={({ field }) => (<FormItem><FormLabel>Prénom</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <FormField control={collaboratorForm.control} name="last_name" render={({ field }) => (<FormItem><FormLabel>Nom</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <FormField control={collaboratorForm.control} name="email" render={({ field }) => (<FormItem><FormLabel>Email</FormLabel><FormControl><Input type="email" placeholder="email@exemple.com" {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <FormField control={collaboratorForm.control} name="nir" render={({ field }) => (<FormItem><FormLabel>N° de Sécurité Sociale</FormLabel><FormControl><Input placeholder="ex: 1850701123456" {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <FormField control={collaboratorForm.control} name="date_naissance" render={({ field }) => (<FormItem><FormLabel>Date de naissance</FormLabel><FormControl><Input type="date" {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <FormField control={collaboratorForm.control} name="lieu_naissance" render={({ field }) => (<FormItem><FormLabel>Lieu de naissance</FormLabel><FormControl><Input placeholder="ex: 75001 Paris" {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <FormField control={collaboratorForm.control} name="nationalite" render={({ field }) => (<FormItem><FormLabel>Nationalité</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <h3 className="font-semibold pt-4">Adresse</h3>
                        <FormField control={collaboratorForm.control} name="adresse.rue" render={({ field }) => (<FormItem><FormLabel>Rue</FormLabel><FormControl><Input placeholder="1 Rue de la Paix" {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <div className="grid grid-cols-2 gap-4">
                          <FormField control={collaboratorForm.control} name="adresse.code_postal" render={({ field }) => (<FormItem><FormLabel>Code Postal</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                          <FormField control={collaboratorForm.control} name="adresse.ville" render={({ field }) => (<FormItem><FormLabel>Ville</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                        </div>
                        <h3 className="font-semibold pt-4">Coordonnées bancaires</h3>
                        <FormField control={collaboratorForm.control} name="coordonnees_bancaires.iban" render={({ field }) => (<FormItem><FormLabel>IBAN</FormLabel><FormControl><Input placeholder="FR76..." {...field} /></FormControl><FormMessage /></FormItem>)} />
                        <FormField control={collaboratorForm.control} name="coordonnees_bancaires.bic" render={({ field }) => (<FormItem><FormLabel>BIC</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                      </TabsContent>
                      <TabsContent value="contrat">
                        <div className="space-y-4">
                          <FormField control={collaboratorForm.control} name="hire_date" render={({ field }) => (<FormItem><FormLabel>Date d'entrée</FormLabel><FormControl><Input type="date" {...field} /></FormControl><FormMessage /></FormItem>)} />
                          <FormField control={collaboratorForm.control} name="job_title" render={({ field }) => (<FormItem><FormLabel>Intitulé du poste</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>)} />
                          <div className="grid grid-cols-2 gap-4">
                            <FormField
                              control={collaboratorForm.control}
                              name="contract_type"
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Type de contrat</FormLabel>
                                  <Select onValueChange={field.onChange} value={field.value}>
                                    <FormControl>
                                      <SelectTrigger>
                                        <SelectValue placeholder="Choisir..." />
                                      </SelectTrigger>
                                    </FormControl>
                                    <SelectContent>
                                      {CONTRACT_TYPES.map((type) => (
                                        <SelectItem key={type} value={type}>{type}</SelectItem>
                                      ))}
                                    </SelectContent>
                                  </Select>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                            <FormField
                              control={collaboratorForm.control}
                              name="statut"
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Statut</FormLabel>
                                  <Select onValueChange={field.onChange} value={field.value}>
                                    <FormControl>
                                      <SelectTrigger>
                                        <SelectValue placeholder="Choisir..." />
                                      </SelectTrigger>
                                    </FormControl>
                                    <SelectContent>
                                      {EMPLOYEE_STATUSES.map((status) => (
                                        <SelectItem key={status} value={status}>{status}</SelectItem>
                                      ))}
                                    </SelectContent>
                                  </Select>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                          </div>
                          <div className="grid grid-cols-2 gap-4 items-end">
                            <FormField control={collaboratorForm.control} name="duree_hebdomadaire" render={({ field }) => (<FormItem><FormLabel>Durée hebdo. (heures)</FormLabel><FormControl><Input type="number" {...field} /></FormControl><FormMessage /></FormItem>)} />
                            <FormField
                              control={collaboratorForm.control}
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
                            control={collaboratorForm.control}
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
                            control={collaboratorForm.control}
                            name="collective_agreement_id"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>Convention collective</FormLabel>
                                <Select
                                  value={field.value ?? "__aucune__"}
                                  onValueChange={(v) => {
                                    field.onChange(v === "__aucune__" ? null : v);
                                    if (v === "__aucune__") {
                                      collaboratorForm.setValue("classification_conventionnelle", { groupe_emploi: "C", classe_emploi: 6, coefficient: 240 });
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
                                  control={collaboratorForm.control}
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
                                    control={collaboratorForm.control}
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
                                    control={collaboratorForm.control}
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
                                    control={collaboratorForm.control}
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
                            control={collaboratorForm.control}
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
                              control={collaboratorForm.control}
                              name="avantages_en_nature.logement.beneficie"
                              render={({ field }) => (
                                <FormItem className="flex flex-row items-center space-x-3 space-y-0 rounded-md border p-4">
                                  <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
                                  <FormLabel>Bénéficie d'un logement de fonction</FormLabel>
                                </FormItem>
                              )}
                            />
                            <FormField
                              control={collaboratorForm.control}
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
                              control={collaboratorForm.control}
                              name="specificites_paie.prelevement_a_la_source.is_personnalise"
                              render={({ field }) => (
                                <FormItem className="flex flex-row items-center space-x-3 space-y-0">
                                  <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
                                  <FormLabel>Appliquer un taux personnalisé</FormLabel>
                                </FormItem>
                              )}
                            />
                            {collaboratorForm.watch("specificites_paie.prelevement_a_la_source.is_personnalise") && (
                              <FormField
                                control={collaboratorForm.control}
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
                                control={collaboratorForm.control}
                                name="specificites_paie.transport.abonnement_mensuel_total"
                                render={({ field }) => (
                                  <FormItem>
                                    <FormLabel>Abonnement transport mensuel total (€)</FormLabel>
                                    <FormControl><Input type="number" step="0.01" {...field} /></FormControl>
                                  </FormItem>
                                )}
                              />
                              <FormField
                                control={collaboratorForm.control}
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
                                    control={collaboratorForm.control}
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
                                            control={collaboratorForm.control}
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
                                          <FormField control={collaboratorForm.control} name={`specificites_paie.mutuelle.lignes_specifiques.${index}.montant_salarial`} render={({ field }) => (<FormItem><FormLabel>Montant Salarial (€)</FormLabel><FormControl><Input type="number" {...field} /></FormControl></FormItem>)} />
                                          <FormField control={collaboratorForm.control} name={`specificites_paie.mutuelle.lignes_specifiques.${index}.montant_patronal`} render={({ field }) => (<FormItem><FormLabel>Montant Patronal (€)</FormLabel><FormControl><Input type="number" {...field} /></FormControl></FormItem>)} />
                                        </div>
                                        <FormField control={collaboratorForm.control} name={`specificites_paie.mutuelle.lignes_specifiques.${index}.part_patronale_soumise_a_csg`} render={({ field }) => (<FormItem className="flex flex-row items-center space-x-3 pt-2"><FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl><FormLabel>Part patronale soumise à CSG</FormLabel></FormItem>)} />
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                            <div>
                              <h3 className="font-semibold mb-2">Prévoyance</h3>
                              <div className="space-y-4 rounded-md border p-4">
                                <FormField control={collaboratorForm.control} name="specificites_paie.prevoyance.adhesion" render={({ field }) => (<FormItem className="flex flex-row items-center space-x-3"><FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl><FormLabel>Adhésion Prévoyance</FormLabel></FormItem>)} />
                                {collaboratorForm.watch("specificites_paie.prevoyance.adhesion") && isCadre && (
                                  <div className="pl-6 border-l-2 ml-2 space-y-4">
                                    <div className="flex justify-between items-center">
                                      <h4 className="text-sm font-medium">Lignes de Prévoyance (Cadre)</h4>
                                      <Button type="button" variant="outline" size="sm" onClick={() => appendPrevoyance({ id: `prevoyance_${prevoyanceFields.length + 1}`, libelle: '', salarial: 0, patronal: 0, forfait_social: 0 })}>
                                        <PlusCircle className="mr-2 h-4 w-4" /> Ajouter
                                      </Button>
                                    </div>
                                    {prevoyanceFields.map((field, index) => (
                                      <div key={field.id} className="space-y-2 border-b pb-4 last:border-b-0">
                                        <FormField control={collaboratorForm.control} name={`specificites_paie.prevoyance.lignes_specifiques.${index}.libelle`} render={({ field }) => (<FormItem><FormLabel>Libellé</FormLabel><FormControl><Input {...field} /></FormControl></FormItem>)} />
                                        <div className="grid grid-cols-3 gap-4">
                                          <FormField control={collaboratorForm.control} name={`specificites_paie.prevoyance.lignes_specifiques.${index}.salarial`} render={({ field }) => (<FormItem><FormLabel>Taux Salarial (%)</FormLabel><FormControl><Input type="number" step="0.0001" {...field} /></FormControl><FormMessage /></FormItem>)} />
                                          <FormField control={collaboratorForm.control} name={`specificites_paie.prevoyance.lignes_specifiques.${index}.patronal`} render={({ field }) => (<FormItem><FormLabel>Taux Patronal (%)</FormLabel><FormControl><Input type="number" step="0.0001" {...field} /></FormControl><FormMessage /></FormItem>)} />
                                          <FormField control={collaboratorForm.control} name={`specificites_paie.prevoyance.lignes_specifiques.${index}.forfait_social`} render={({ field }) => (<FormItem><FormLabel>Forfait Social (%)</FormLabel><FormControl><Input type="number" step="0.01" {...field} /></FormControl><FormMessage /></FormItem>)} />
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
                    </div>
                </TabsContent>

                {/* Onglet 2 : Accès RH */}
                <TabsContent value="rh" className="mt-4 min-h-0 flex flex-col">
                  <div className="flex items-center space-x-2 mb-4">
                    <Checkbox
                      id="access-rh"
                      checked={hasRHAccess}
                      onCheckedChange={(c) => setHasRHAccess(!!c)}
                    />
                    <Label htmlFor="access-rh" className="text-sm font-medium cursor-pointer">
                      Accès RH (utilisateur applicatif, entreprises et rôles)
                    </Label>
                  </div>
                  <div className={cn(!hasRHAccess && 'pointer-events-none opacity-50')}>
                    {hasRHAccess && !hasCollaboratorAccess && (
                      <div className="mb-4 p-4 bg-muted/50 rounded-lg space-y-3">
                        <p className="text-sm font-medium">Identité de l&apos;utilisateur</p>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          <div>
                            <Label htmlFor="rh-only-first" className="text-xs">Prénom *</Label>
                            <Input
                              id="rh-only-first"
                              value={rhOnlyIdentity.first_name}
                              onChange={(e) => setRhOnlyIdentity((p) => ({ ...p, first_name: e.target.value }))}
                              placeholder="Prénom"
                              className="mt-1"
                            />
                          </div>
                          <div>
                            <Label htmlFor="rh-only-last" className="text-xs">Nom *</Label>
                            <Input
                              id="rh-only-last"
                              value={rhOnlyIdentity.last_name}
                              onChange={(e) => setRhOnlyIdentity((p) => ({ ...p, last_name: e.target.value }))}
                              placeholder="Nom"
                              className="mt-1"
                            />
                          </div>
                          <div>
                            <Label htmlFor="rh-only-email" className="text-xs">Email *</Label>
                            <Input
                              id="rh-only-email"
                              type="email"
                              value={rhOnlyIdentity.email}
                              onChange={(e) => setRhOnlyIdentity((p) => ({ ...p, email: e.target.value }))}
                              placeholder="email@exemple.com"
                              className="mt-1"
                            />
                          </div>
                        </div>
                      </div>
                    )}
                    {rhLoadingCompanies ? (
                      <div className="flex justify-center py-8">
                        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                      </div>
                    ) : rhAccessibleCompanies.length === 0 && hasRHAccess ? (
                      <p className="text-sm text-muted-foreground py-4">Aucune entreprise accessible pour l&apos;accès RH.</p>
                    ) : (
                      <div className="space-y-4 max-h-[55vh] overflow-y-auto pr-2">
                        {rhError && (
                          <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">{rhError}</div>
                        )}
                        {rhAccessibleCompanies.map((company) => {
                          const access = rhCompanyAccesses[company.company_id];
                          if (!access) return null;
                          const roleLabelsRh: { [key: string]: string } = {
                            admin: 'Administrateur',
                            rh: 'Ressources Humaines',
                            collaborateur_rh: 'Collaborateur RH',
                            collaborateur: 'Collaborateur',
                            custom: 'Personnalisé',
                          };
                          // Quand Accès collaborateur ET Accès RH sont cochés, le rôle est toujours collaborateur_rh : on n'affiche pas "collaborateur" ni "collaborateur_rh" dans les choix
                          // Quand seul Accès RH est coché, on n'affiche pas non plus "collaborateur" ni "collaborateur_rh" (ces rôles nécessitent l'accès collaborateur)
                          const isCollaboratorWithRH = hasCollaboratorAccess && hasRHAccess;
                          const isRHOnly = hasRHAccess && !hasCollaboratorAccess;
                          // Toujours exclure collaborateur et collaborateur_rh des rôles sélectionnables dans l'accès RH
                          const selectableRoles = company.can_create_roles.filter((r) => r !== 'custom' && r !== 'collaborateur' && r !== 'collaborateur_rh');
                          return (
                            <div
                              key={company.company_id}
                              className={cn(
                                'border-2 rounded-lg p-4 transition-all',
                                access.enabled ? 'border-blue-500 bg-blue-50/50' : 'border-gray-200 bg-white'
                              )}
                            >
                              <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-3 flex-1">
                                  <Checkbox
                                    checked={access.enabled}
                                    onCheckedChange={(c) => handleRhToggleCompany(company.company_id, !!c)}
                                  />
                                  <div>
                                    <div className="font-semibold text-gray-900">{company.company_name}</div>
                                  </div>
                                </div>
                                {access.enabled && (
                                  <>
                                    {Object.values(rhCompanyAccesses).filter((a) => a.enabled).length > 1 && (
                                      <label className="flex items-center gap-2 text-sm">
                                        <input
                                          type="radio"
                                          name="rh_primary_company"
                                          checked={access.is_primary}
                                          onChange={() => handleRhSetPrimary(company.company_id)}
                                          className="w-4 h-4"
                                        />
                                        <span>Primaire</span>
                                      </label>
                                    )}
                                    <Button type="button" variant="ghost" size="icon" onClick={() => handleRhToggleExpand(company.company_id)}>
                                      {access.expanded ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
                                    </Button>
                                  </>
                                )}
                              </div>
                              {access.enabled && access.expanded && (
                                <div className="mt-4 space-y-4 pl-6 border-l-2 border-blue-200">
                                  <div>
                                    {isCollaboratorWithRH ? (
                                      <p className="text-sm text-muted-foreground mb-2">Sélectionnez un template RH pré-enregistré ou l'option "Tout" pour toutes les permissions RH.</p>
                                    ) : (
                                      <p className="text-sm text-muted-foreground mb-2">Sélectionnez un template RH pré-enregistré ou l'option "Tout" pour toutes les permissions RH.</p>
                                    )}
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                      {/* Option "Tout" : toutes les permissions RH */}
                                      <Button
                                        type="button"
                                        variant={access.hasAllPermissions && !access.isCreatingNewRole ? 'default' : 'outline'}
                                        size="sm"
                                        onClick={() => {
                                          setRhCompanyAccesses((prev) => ({
                                            ...prev,
                                            [company.company_id]: {
                                              ...prev[company.company_id],
                                              hasAllPermissions: true,
                                              base_role: isCollaboratorWithRH ? 'collaborateur_rh' : 'rh',
                                              role_template_id: undefined,
                                              permission_ids: [],
                                              isCreatingNewRole: false,
                                            },
                                          }));
                                        }}
                                      >
                                        <Shield className="h-4 w-4 mr-1" />
                                        Tout
                                      </Button>
                                      {selectableRoles.map((role) => (
                                        <Button
                                          key={role}
                                          type="button"
                                          variant={access.base_role === role && !access.hasAllPermissions && !access.isCreatingNewRole ? 'default' : 'outline'}
                                          size="sm"
                                          onClick={() => {
                                            handleRhRoleChange(company.company_id, role as 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur');
                                            setRhCompanyAccesses((prev) => ({
                                              ...prev,
                                              [company.company_id]: {
                                                ...prev[company.company_id],
                                                hasAllPermissions: false,
                                              },
                                            }));
                                          }}
                                        >
                                          <Shield className="h-4 w-4 mr-1" />
                                          {roleLabelsRh[role] || role}
                                        </Button>
                                      ))}
                                      {access.loadingCustomRoles ? (
                                        <div className="flex items-center justify-center p-2 border rounded-md"><Loader2 className="h-4 w-4 animate-spin" /></div>
                                      ) : (
                                        access.customRoles.map((customRole) => (
                                          <Button
                                            key={customRole.id}
                                            type="button"
                                            variant={access.role_template_id === customRole.id && !access.hasAllPermissions && !access.isCreatingNewRole ? 'default' : 'outline'}
                                            size="sm"
                                            onClick={() => {
                                              handleRhSelectExistingCustomRole(company.company_id, customRole.id);
                                              setRhCompanyAccesses((prev) => ({
                                                ...prev,
                                                [company.company_id]: {
                                                  ...prev[company.company_id],
                                                  hasAllPermissions: false,
                                                },
                                              }));
                                            }}
                                          >
                                            {customRole.name}
                                          </Button>
                                        ))
                                      )}
                                      <Button
                                        type="button"
                                        variant={access.isCreatingNewRole ? 'default' : 'outline'}
                                        size="sm"
                                        onClick={() => {
                                          handleRhSelectNewRole(company.company_id);
                                          setRhCompanyAccesses((prev) => ({
                                            ...prev,
                                            [company.company_id]: {
                                              ...prev[company.company_id],
                                              hasAllPermissions: false,
                                            },
                                          }));
                                        }}
                                      >
                                        <Sparkles className="h-4 w-4 mr-1" />
                                        Nouveau rôle
                                      </Button>
                                    </div>
                                  </div>
                                  {access.isCreatingNewRole && (
                                    <>
                                      <div className="bg-muted/50 rounded-lg p-4 space-y-3">
                                        <h4 className="font-medium">Créer un rôle</h4>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                          <div>
                                            <Label>Nom du rôle *</Label>
                                            <Input
                                              value={access.newRoleData.name}
                                              onChange={(e) => setRhCompanyAccesses((prev) => ({
                                                ...prev,
                                                [company.company_id]: {
                                                  ...prev[company.company_id],
                                                  newRoleData: { ...prev[company.company_id].newRoleData, name: e.target.value },
                                                },
                                              }))}
                                              placeholder="Ex: Directeur de Site"
                                            />
                                          </div>
                                          <div>
                                            <Label>Titre du poste *</Label>
                                            <Input
                                              value={access.newRoleData.job_title}
                                              onChange={(e) => setRhCompanyAccesses((prev) => ({
                                                ...prev,
                                                [company.company_id]: {
                                                  ...prev[company.company_id],
                                                  newRoleData: { ...prev[company.company_id].newRoleData, job_title: e.target.value },
                                                },
                                              }))}
                                              placeholder="Ex: Directeur de Site"
                                            />
                                          </div>
                                        </div>
                                        <div>
                                          <Label>Type de rôle (base_role)</Label>
                                          <Select
                                            value={(isCollaboratorWithRH && (access.newRoleData.base_role === 'collaborateur' || access.newRoleData.base_role === 'collaborateur_rh')) ? 'rh' : (access.newRoleData.base_role === 'collaborateur' || access.newRoleData.base_role === 'collaborateur_rh') ? 'rh' : access.newRoleData.base_role}
                                            onValueChange={(v: 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom') => setRhCompanyAccesses((prev) => ({
                                              ...prev,
                                              [company.company_id]: {
                                                ...prev[company.company_id],
                                                newRoleData: { ...prev[company.company_id].newRoleData, base_role: v },
                                              },
                                            }))}
                                          >
                                            <SelectTrigger><SelectValue /></SelectTrigger>
                                            <SelectContent>
                                              <SelectItem value="rh">Ressources Humaines</SelectItem>
                                              <SelectItem value="admin">Administrateur</SelectItem>
                                              <SelectItem value="custom">Personnalisé</SelectItem>
                                              {/* Ne jamais afficher collaborateur et collaborateur_rh dans le Select Nouveau rôle */}
                                            </SelectContent>
                                          </Select>
                                        </div>
                                        <div>
                                          <Label>Description</Label>
                                          <Textarea
                                            value={access.newRoleData.description}
                                            onChange={(e) => setRhCompanyAccesses((prev) => ({
                                              ...prev,
                                              [company.company_id]: {
                                                ...prev[company.company_id],
                                                newRoleData: { ...prev[company.company_id].newRoleData, description: e.target.value },
                                              },
                                            }))}
                                            placeholder="Description optionnelle"
                                            rows={2}
                                          />
                                        </div>
                                        <Button
                                          type="button"
                                          onClick={() => handleRhCreateNewRoleTemplate(company.company_id)}
                                          disabled={rhCreatingTemplate}
                                        >
                                          {rhCreatingTemplate ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Sparkles className="h-4 w-4 mr-2" />}
                                          Créer le rôle
                                        </Button>
                                      </div>
                                      <div>
                                        <Label className="mb-2 block">Permissions ({access.permission_ids.length})</Label>
                                        <div className="border rounded-lg p-3 bg-muted/30">
                                          <PermissionsMatrix
                                            companyId={company.company_id}
                                            selectedPermissions={access.permission_ids}
                                            onPermissionsChange={(perms) => handleRhPermissionsChange(company.company_id, perms)}
                                            restrictToAvailable={true}
                                          />
                                        </div>
                                      </div>
                                    </>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </TabsContent>
              </Tabs>

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
                  {newCollaboratorMainTab === 'collab' && hasCollaboratorAccess && (
                    <>
                      <div className="flex items-center space-x-2 p-3 bg-blue-50 border border-blue-200 rounded-md">
                        <Checkbox
                          id="generate-pdf-contract-collab"
                          checked={generatePdfContract}
                          onCheckedChange={(checked) => setGeneratePdfContract(checked as boolean)}
                        />
                        <label htmlFor="generate-pdf-contract-collab" className="text-sm font-medium leading-none cursor-pointer">
                          Création de contrat pdf
                        </label>
                      </div>
                      <Button form="collab-form" type="submit" disabled={collaboratorForm.formState.isSubmitting} className="w-full">
                        {collaboratorForm.formState.isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Enregistrer le collaborateur
                      </Button>
                    </>
                  )}
                  {newCollaboratorMainTab === 'rh' && hasRHAccess && !hasCollaboratorAccess && (
                    <Button
                      type="button"
                      onClick={handleRhOnlySubmit}
                      disabled={rhOnlySubmitting}
                      className="w-full"
                    >
                      {rhOnlySubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      Créer l&apos;utilisateur RH
                    </Button>
                  )}
                </div>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Sélection d'entreprise */}
      {accessibleCompanies.length > 1 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            <Building className="inline h-5 w-5 mr-2" />
            Entreprise
          </label>
          <select
            value={selectedCompanyId}
            onChange={(e) => setSelectedCompanyId(e.target.value)}
            className="w-full max-w-md px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            {accessibleCompanies.map((company) => (
              <option key={company.company_id} value={company.company_id}>
                {company.company_name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Filtres et recherche */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Recherche */}
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                type="text"
                placeholder="Rechercher par nom, email ou poste..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          {/* Filtre par rôle */}
          <div className="w-full md:w-64">
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Tous les rôles</option>
              <option value="admin">Administrateur</option>
              <option value="rh">Ressources Humaines</option>
              <option value="collaborateur">Collaborateur</option>
              {customRoles.map((customRole) => (
                <option key={customRole.id} value={customRole.name}>
                  {customRole.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Statistiques */}
        <div className="mt-4 flex items-center gap-6 text-sm text-gray-600">
          <div className="flex items-center gap-2">
            <UsersIcon className="h-4 w-4" />
            <span>
              {filteredUsers.length} utilisateur{filteredUsers.length > 1 ? 's' : ''}
            </span>
          </div>
          {searchQuery && (
            <span className="text-blue-600">Filtré par: "{searchQuery}"</span>
          )}
        </div>
      </div>

      {/* Liste des utilisateurs */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        {filteredUsers.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <UsersIcon className="h-16 w-16 mx-auto mb-4 text-gray-300" />
            <p className="text-lg font-medium mb-2">Aucun utilisateur trouvé</p>
            <p className="text-sm">
              {searchQuery
                ? 'Essayez de modifier vos critères de recherche'
                : 'Commencez par créer un utilisateur'}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {filteredUsers.map((user) => {
              console.log('[UserManagement] Rendering user:', {
                id: user.id,
                name: `${user.first_name} ${user.last_name}`,
                can_edit: user.can_edit,
                role: user.role
              });

              return (
                <div
                  key={user.id}
                  className="hover:bg-gray-50 transition-colors cursor-pointer"
                  onClick={() => handleViewProfile(user.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && handleViewProfile(user.id)}
                >
                  {/* Ligne principale */}
                  <div className="p-6">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-4 mb-2">
                          <h3 className="text-lg font-semibold text-gray-900 hover:text-blue-600 transition-colors">
                            {user.first_name} {user.last_name}
                          </h3>
                          <span
                            className={cn(
                              'px-3 py-1 text-xs font-medium rounded-full border',
                              roleColors[user.role]
                            )}
                          >
                            {user.role === 'custom' && user.role_template_name
                              ? user.role_template_name
                              : roleLabels[user.role]}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
                          <div className="flex items-center gap-2">
                            <Mail className="h-4 w-4" />
                            {user.email}
                          </div>
                          {user.job_title && (
                            <div className="flex items-center gap-2">
                              <Briefcase className="h-4 w-4" />
                              {user.job_title}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 ml-4" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => handleViewProfile(user.id)}
                          className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-2"
                        >
                          <ChevronRight className="h-4 w-4" />
                          Voir la fiche
                        </button>
                        {user.can_edit && (
                          <button
                            onClick={() => handleEditUser(user.id)}
                            className="px-4 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors flex items-center gap-2"
                          >
                            <Edit className="h-4 w-4" />
                            Modifier
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default UserManagement;
