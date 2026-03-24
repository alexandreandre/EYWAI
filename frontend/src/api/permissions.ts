import apiClient from './apiClient';

// =====================================================
// TYPES
// =====================================================

export interface PermissionCategory {
  id: string;
  code: string;
  label: string;
  description?: string;
  display_order: number;
  is_active: boolean;
}

export interface PermissionAction {
  id: string;
  code: string;
  label: string;
  description?: string;
  is_active: boolean;
}

export interface Permission {
  id: string;
  category_id: string;
  action_id: string;
  code: string;
  label: string;
  description?: string;
  required_role?: 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur';
  is_active: boolean;
}

export interface PermissionWithMetadata extends Permission {
  category_code: string;
  category_label: string;
  action_code: string;
  action_label: string;
  is_granted: boolean;
}

export interface PermissionMatrixAction {
  id: string;
  code: string;
  label: string;
  action_code: string;
  action_label: string;
  is_granted: boolean;
}

export interface PermissionMatrixCategory {
  code: string;
  label: string;
  description?: string;
  actions: PermissionMatrixAction[];
}

export interface PermissionMatrix {
  categories: PermissionMatrixCategory[];
}

export interface UserPermissionsSummary {
  user_id: string;
  company_id: string;
  base_role: 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom';
  role_template_id?: string;
  role_template_name?: string;
  total_permissions: number;
  permissions_by_category: { [key: string]: number };
  all_permissions: PermissionWithMetadata[];
}

export interface RoleTemplate {
  id: string;
  company_id?: string;
  name: string;
  description?: string;
  job_title?: string;
  base_role: 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom';
  is_system: boolean;
  is_active: boolean;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface RoleTemplateDetail extends RoleTemplate {
  company_name?: string;
  created_by_name?: string;
  permissions_count: number;
  permissions: PermissionWithMetadata[];
}

export interface RoleTemplateWithPermissions extends RoleTemplate {
  permissions: Permission[];
  permissions_count: number;
}

export interface RoleTemplateOption {
  id: string;
  name: string;
  job_title?: string;
  base_role: string;
  is_system: boolean;
  permissions_count: number;
}

export interface UserCompanyAccessData {
  company_id: string;
  base_role: 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom';
  is_primary: boolean;
  role_template_id?: string;
  permission_ids: string[];
  contract_type?: string;
  statut?: string;
}

export interface UserCreateWithPermissions {
  email: string;
  username?: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
  job_title?: string;
  company_accesses: UserCompanyAccessData[];
}

export interface UserUpdateWithPermissions {
  first_name?: string;
  last_name?: string;
  job_title?: string;
  company_id: string;
  base_role?: 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom';
  role_template_id?: string;
  permission_ids?: string[];
}

export interface RoleHierarchyCheckResponse {
  is_allowed: boolean;
  creator_role: string;
  target_role: string;
  message: string;
}

export interface PermissionCheckResponse {
  has_permission: boolean;
  permission_code: string;
  user_id: string;
  company_id: string;
}

export interface AccessibleCompany {
  company_id: string;
  company_name: string;
  creator_role: string;
  can_create_roles: string[];
}

// =====================================================
// API CALLS - CATÉGORIES & ACTIONS
// =====================================================

export const getPermissionCategories = async (): Promise<PermissionCategory[]> => {
  const response = await apiClient.get('/api/user-management/permission-categories');
  return response.data;
};

export const getPermissionActions = async (): Promise<PermissionAction[]> => {
  const response = await apiClient.get('/api/user-management/permission-actions');
  return response.data;
};

export const getAllPermissions = async (
  categoryId?: string,
  requiredRole?: string
): Promise<Permission[]> => {
  const params = new URLSearchParams();
  if (categoryId) params.append('category_id', categoryId);
  if (requiredRole) params.append('required_role', requiredRole);

  const response = await apiClient.get(`/api/user-management/permissions?${params.toString()}`);
  return response.data;
};

export const getPermissionsMatrix = async (
  companyId: string,
  userId?: string
): Promise<PermissionMatrix> => {
  const params = new URLSearchParams({ company_id: companyId });
  if (userId) params.append('user_id', userId);

  const response = await apiClient.get(`/api/user-management/permissions/matrix?${params.toString()}`);
  return response.data;
};

// =====================================================
// API CALLS - PERMISSIONS UTILISATEUR
// =====================================================

export const getUserPermissions = async (
  userId: string,
  companyId: string
): Promise<UserPermissionsSummary> => {
  const response = await apiClient.get(
    `/api/user-management/users/${userId}/permissions?company_id=${companyId}`
  );
  return response.data;
};

export const grantUserPermissions = async (
  userId: string,
  companyId: string,
  permissionIds: string[]
): Promise<{ message: string }> => {
  const response = await apiClient.post(`/api/user-management/users/${userId}/permissions`, {
    user_id: userId,
    company_id: companyId,
    permission_ids: permissionIds,
  });
  return response.data;
};

export const updateUserPermissions = async (
  userId: string,
  companyId: string,
  permissionIds: string[]
): Promise<{ message: string }> => {
  const response = await apiClient.put(`/api/user-management/users/${userId}/permissions`, {
    user_id: userId,
    company_id: companyId,
    permission_ids: permissionIds,
  });
  return response.data;
};

export const revokeUserPermission = async (
  userId: string,
  permissionId: string,
  companyId: string
): Promise<{ message: string }> => {
  const response = await apiClient.delete(
    `/api/user-management/users/${userId}/permissions/${permissionId}?company_id=${companyId}`
  );
  return response.data;
};

// =====================================================
// API CALLS - TEMPLATES DE RÔLES
// =====================================================

export const getRoleTemplates = async (
  companyId?: string,
  baseRole?: string,
  includeSystem: boolean = true
): Promise<RoleTemplateDetail[]> => {
  const params = new URLSearchParams();
  if (companyId) params.append('company_id', companyId);
  if (baseRole) params.append('base_role', baseRole);
  params.append('include_system', includeSystem.toString());

  const response = await apiClient.get(`/api/user-management/role-templates?${params.toString()}`);
  return response.data;
};

export const getRoleTemplate = async (templateId: string): Promise<RoleTemplateWithPermissions> => {
  const response = await apiClient.get(`/api/user-management/role-templates/${templateId}`);
  return response.data;
};

export const createRoleTemplate = async (data: {
  company_id?: string;
  name: string;
  description?: string;
  job_title?: string;
  base_role: string;
  permission_ids: string[];
}): Promise<RoleTemplate> => {
  const response = await apiClient.post('/api/user-management/role-templates', data);
  return response.data;
};

export const quickCreateRoleTemplate = async (data: {
  company_id: string;
  name: string;
  job_title: string;
  base_role: 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom';
  description?: string;
  permission_ids: string[];
}): Promise<{ message: string; template_id: string; name: string }> => {
  const response = await apiClient.post('/api/user-management/role-templates/quick-create', data);
  return response.data;
};

export const updateRoleTemplate = async (
  templateId: string,
  data: {
    name?: string;
    description?: string;
    job_title?: string;
    base_role?: string;
    is_active?: boolean;
    permission_ids?: string[];
  }
): Promise<RoleTemplate> => {
  const response = await apiClient.put(`/api/user-management/role-templates/${templateId}`, data);
  return response.data;
};

export const deleteRoleTemplate = async (templateId: string): Promise<{ message: string }> => {
  const response = await apiClient.delete(`/api/user-management/role-templates/${templateId}`);
  return response.data;
};

// =====================================================
// API CALLS - VÉRIFICATIONS
// =====================================================

export const checkRoleHierarchy = async (
  targetRole: string,
  companyId: string
): Promise<RoleHierarchyCheckResponse> => {
  const response = await apiClient.get(
    `/api/user-management/check-hierarchy?target_role=${targetRole}&company_id=${companyId}`
  );
  return response.data;
};

export const checkUserPermission = async (
  userId: string,
  companyId: string,
  permissionCode: string
): Promise<PermissionCheckResponse> => {
  const response = await apiClient.get(
    `/api/user-management/check-permission?user_id=${userId}&company_id=${companyId}&permission_code=${permissionCode}`
  );
  return response.data;
};

// =====================================================
// API CALLS - CRÉATION D'UTILISATEURS
// =====================================================

export const createUserWithPermissions = async (
  data: UserCreateWithPermissions
): Promise<any> => {
  const response = await apiClient.post('/api/users/create-with-permissions', data);
  return response.data;
};

export const getUserDetail = async (
  userId: string,
  companyId: string
): Promise<any> => {
  console.log('[API permissions.ts] getUserDetail called with:', { userId, companyId });
  const url = `/api/users/${userId}?company_id=${companyId}`;
  console.log('[API permissions.ts] Making GET request to:', url);

  try {
    console.log('[API permissions.ts] BEFORE apiClient.get...');
    const response = await apiClient.get(url);
    console.log('[API permissions.ts] ✅ Response received:', response);
    console.log('[API permissions.ts] Response data:', response.data);
    return response.data;
  } catch (error: any) {
    console.error('[API permissions.ts] ❌ Error in getUserDetail:', error);
    console.error('[API permissions.ts] Error details:', {
      message: error.message,
      response: error.response,
      status: error.response?.status,
      data: error.response?.data
    });
    throw error;
  }
};

export const updateUserWithPermissions = async (
  userId: string,
  data: UserUpdateWithPermissions
): Promise<any> => {
  const response = await apiClient.put(`/api/users/${userId}/update`, data);
  return response.data;
};

export const getCompanyUsers = async (
  companyId: string,
  role?: string
): Promise<any[]> => {
  const params = role ? `?role=${role}` : '';
  const response = await apiClient.get(`/api/users/company/${companyId}${params}`);
  return response.data;
};

export const getAccessibleCompaniesForUserCreation = async (): Promise<AccessibleCompany[]> => {
  const response = await apiClient.get('/api/users/accessible-companies');
  return response.data;
};

/**
 * Récupère les accès multi-entreprises d'un utilisateur.
 * Retourne la liste des entreprises auxquelles l'utilisateur a accès avec son rôle dans chacune.
 */
export const getUserCompanyAccesses = async (userId: string): Promise<
  Array<{ company_id: string; company_name: string; role: string; is_primary: boolean; siret?: string; group_id?: string }>
> => {
  const response = await apiClient.get(`/api/users/company-accesses/${userId}`);
  return response.data;
};
