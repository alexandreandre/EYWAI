import React, { useState, useEffect } from 'react';
import { Loader2, Info, ChevronDown, ChevronRight, CheckSquare, Square } from 'lucide-react';
import { getPermissionsMatrix, PermissionMatrix, PermissionMatrixCategory } from '../api/permissions';
import { cn } from '../lib/utils';

interface PermissionsMatrixProps {
  companyId: string;
  userId?: string;
  selectedPermissions: string[];
  onPermissionsChange: (permissions: string[]) => void;
  disabled?: boolean;
  restrictToAvailable?: boolean; // Si true, seules les permissions is_granted peuvent être sélectionnées
}

export const PermissionsMatrix: React.FC<PermissionsMatrixProps> = ({
  companyId,
  userId,
  selectedPermissions,
  onPermissionsChange,
  disabled = false,
  restrictToAvailable = false,
}) => {
  const [matrix, setMatrix] = useState<PermissionMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadMatrix();
  }, [companyId, userId]);

  const loadMatrix = async () => {
    try {
      setLoading(true);
      const data = await getPermissionsMatrix(companyId, userId);
      setMatrix(data);
      // Expand all categories by default
      setExpandedCategories(new Set(data.categories.map((cat) => cat.code)));
    } catch (error) {
      console.error('Erreur lors du chargement de la matrice:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleCategory = (categoryCode: string) => {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(categoryCode)) {
      newExpanded.delete(categoryCode);
    } else {
      newExpanded.add(categoryCode);
    }
    setExpandedCategories(newExpanded);
  };

  const togglePermission = (permissionId: string, isGranted: boolean = true) => {
    if (disabled) return;
    if (restrictToAvailable && !isGranted) return; // Ne pas permettre de sélectionner des permissions non disponibles

    const isSelected = selectedPermissions.includes(permissionId);
    if (isSelected) {
      onPermissionsChange(selectedPermissions.filter((id) => id !== permissionId));
    } else {
      onPermissionsChange([...selectedPermissions, permissionId]);
    }
  };

  const toggleAllInCategory = (category: PermissionMatrixCategory) => {
    if (disabled) return;

    // Si restrictToAvailable, ne considérer que les permissions disponibles
    const availableActions = restrictToAvailable
      ? category.actions.filter((action) => action.is_granted)
      : category.actions;

    const categoryPermissionIds = availableActions.map((action) => action.id);
    const allSelected = categoryPermissionIds.every((id) =>
      selectedPermissions.includes(id)
    );

    if (allSelected) {
      // Désélectionner tous
      onPermissionsChange(
        selectedPermissions.filter((id) => !categoryPermissionIds.includes(id))
      );
    } else {
      // Sélectionner tous (uniquement les disponibles si restrictToAvailable)
      const newSelected = [...selectedPermissions];
      categoryPermissionIds.forEach((id) => {
        if (!newSelected.includes(id)) {
          newSelected.push(id);
        }
      });
      onPermissionsChange(newSelected);
    }
  };

  const getCategoryStatus = (category: PermissionMatrixCategory) => {
    // Si restrictToAvailable, ne considérer que les permissions disponibles
    const availableActions = restrictToAvailable
      ? category.actions.filter((action) => action.is_granted)
      : category.actions;

    const categoryPermissionIds = availableActions.map((action) => action.id);
    const selectedCount = categoryPermissionIds.filter((id) =>
      selectedPermissions.includes(id)
    ).length;

    if (selectedCount === 0) return 'none';
    if (selectedCount === categoryPermissionIds.length) return 'all';
    return 'partial';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!matrix || matrix.categories.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <Info className="h-12 w-12 mx-auto mb-4 text-gray-400" />
        <p>Aucune permission disponible</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
        <div className="flex items-start gap-3">
          <Info className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
          <div>
            <h4 className="font-medium text-blue-900">Configuration des permissions</h4>
            <p className="text-sm text-blue-700 mt-1">
              {restrictToAvailable ? (
                <>
                  Sélectionnez les permissions que vous souhaitez accorder à cet utilisateur.
                  Les permissions grisées ne peuvent pas être accordées car vous ne les possédez pas vous-même.
                </>
              ) : (
                <>
                  Sélectionnez les permissions que vous souhaitez accorder à cet utilisateur.
                  Les permissions sont organisées par catégorie pour faciliter la gestion.
                </>
              )}
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {matrix.categories.map((category) => {
          const isExpanded = expandedCategories.has(category.code);
          const categoryStatus = getCategoryStatus(category);
          const selectedCount = category.actions.filter((action) =>
            selectedPermissions.includes(action.id)
          ).length;

          // Calculer le nombre de permissions disponibles pour l'utilisateur
          const availableActions = restrictToAvailable
            ? category.actions.filter((action) => action.is_granted)
            : category.actions;
          const totalToShow = restrictToAvailable ? availableActions.length : category.actions.length;

          return (
            <div
              key={category.code}
              className="border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm"
            >
              {/* En-tête de catégorie */}
              <div className="bg-gray-50 border-b border-gray-200">
                <div className="flex items-center justify-between p-4">
                  <button
                    type="button"
                    onClick={() => toggleCategory(category.code)}
                    className="flex items-center gap-3 flex-1 text-left"
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-5 w-5 text-gray-500" />
                    ) : (
                      <ChevronRight className="h-5 w-5 text-gray-500" />
                    )}
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-900">
                        {category.label}
                      </h3>
                      {category.description && (
                        <p className="text-sm text-gray-600 mt-0.5">
                          {category.description}
                        </p>
                      )}
                    </div>
                  </button>

                  <div className="flex items-center gap-4">
                    <span className="text-sm text-gray-600">
                      {selectedCount} / {totalToShow}{restrictToAvailable && totalToShow < category.actions.length ? ` (${category.actions.length} au total)` : ''}
                    </span>
                    <button
                      type="button"
                      onClick={() => toggleAllInCategory(category)}
                      disabled={disabled || (restrictToAvailable && availableActions.length === 0)}
                      className={cn(
                        'flex items-center gap-2 px-3 py-1.5 rounded text-sm font-medium transition-colors',
                        disabled || (restrictToAvailable && availableActions.length === 0)
                          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                          : categoryStatus === 'all'
                          ? 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      )}
                    >
                      {categoryStatus === 'all' ? (
                        <>
                          <CheckSquare className="h-4 w-4" />
                          Tout désélectionner
                        </>
                      ) : (
                        <>
                          <Square className="h-4 w-4" />
                          Tout sélectionner
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* Permissions de la catégorie */}
              {isExpanded && (
                <div className="p-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {category.actions.map((action) => {
                      const isSelected = selectedPermissions.includes(action.id);
                      const isUnavailable = restrictToAvailable && !action.is_granted;
                      const isDisabled = disabled || isUnavailable;

                      return (
                        <label
                          key={action.id}
                          className={cn(
                            'flex items-center gap-3 p-3 rounded-lg border-2 transition-all',
                            isDisabled
                              ? 'cursor-not-allowed opacity-50 bg-gray-100'
                              : 'cursor-pointer hover:border-blue-300 hover:bg-blue-50',
                            isSelected && !isUnavailable
                              ? 'border-blue-500 bg-blue-50'
                              : 'border-gray-200',
                            !isSelected && !isDisabled && 'bg-white'
                          )}
                          title={isUnavailable ? "Vous n'avez pas cette permission et ne pouvez donc pas l'accorder" : undefined}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => togglePermission(action.id, action.is_granted)}
                            disabled={isDisabled}
                            className="h-5 w-5 text-blue-600 rounded focus:ring-blue-500 disabled:cursor-not-allowed"
                          />
                          <div className="flex-1 min-w-0">
                            <div className={cn(
                              "font-medium text-sm",
                              isUnavailable ? "text-gray-400" : "text-gray-900"
                            )}>
                              {action.action_label}
                            </div>
                            <div className={cn(
                              "text-xs mt-0.5",
                              isUnavailable ? "text-gray-400" : "text-gray-500"
                            )}>
                              {action.code}
                            </div>
                          </div>
                        </label>
                      );
                    })}
                  </div>

                  {category.actions.length === 0 && (
                    <div className="text-center text-gray-500 text-sm py-8">
                      Aucune action disponible dans cette catégorie
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Résumé des permissions sélectionnées */}
      <div className="mt-6 p-4 bg-gray-50 border border-gray-200 rounded-lg">
        <div className="flex items-center justify-between">
          <span className="font-medium text-gray-700">Total des permissions sélectionnées:</span>
          <span className="text-xl font-bold text-blue-600">{selectedPermissions.length}</span>
        </div>
      </div>
    </div>
  );
};

export default PermissionsMatrix;
