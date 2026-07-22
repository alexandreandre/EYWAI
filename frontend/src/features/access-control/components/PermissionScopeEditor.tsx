import { log } from '@/lib/logger';
import React, { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Info, Plus, Trash2 } from 'lucide-react';
import {
  getPermissionsMatrix,
  syncPermissionGrants,
  type PermissionGrantInput,
  type PermissionScopeMode,
  type PermissionTargetInput,
} from '@/api/permissions';
import { getEmployeesLite, type EmployeeLite } from '@/api/employees';
import { getTeams, type Team } from '@/api/teams';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

const SCOPE_MODE_OPTIONS: Array<{ value: PermissionScopeMode; label: string; description: string }> = [
  {
    value: 'company',
    label: "Toute l'entreprise",
    description: 'Accès à tous les salariés de l’entreprise pour cette permission.',
  },
  {
    value: 'teams',
    label: 'Équipes',
    description: 'Accès limité aux salariés des équipes sélectionnées.',
  },
  {
    value: 'none',
    label: 'Exceptions uniquement',
    description: 'Aucun accès par défaut ; seules les exceptions allow/deny s’appliquent.',
  },
];

interface PermissionScopeEditorProps {
  companyId: string;
  selectedPermissionIds: string[];
  grants: PermissionGrantInput[];
  onGrantsChange: (grants: PermissionGrantInput[]) => void;
  disabled?: boolean;
}

export const PermissionScopeEditor: React.FC<PermissionScopeEditorProps> = ({
  companyId,
  selectedPermissionIds,
  grants,
  onGrantsChange,
  disabled = false,
}) => {
  const [loading, setLoading] = useState(true);
  const [teams, setTeams] = useState<Team[]>([]);
  const [employees, setEmployees] = useState<EmployeeLite[]>([]);
  const [permissionLabels, setPermissionLabels] = useState<
    Record<string, { label: string; code: string }>
  >({});
  const [expandedPermissions, setExpandedPermissions] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;

    const loadData = async () => {
      try {
        setLoading(true);
        const [matrix, teamsResponse, employeeRows] = await Promise.all([
          getPermissionsMatrix(companyId),
          getTeams(false),
          getEmployeesLite(),
        ]);

        if (cancelled) return;

        const labels: Record<string, { label: string; code: string }> = {};
        for (const category of matrix.categories) {
          for (const action of category.actions) {
            labels[action.id] = {
              label: action.action_label || action.label,
              code: action.code,
            };
          }
        }

        const companyTeams = teamsResponse.teams.filter(
          (team) => team.company_id === companyId && team.status === 'active'
        );

        setPermissionLabels(labels);
        setTeams(companyTeams);
        setEmployees(employeeRows);
      } catch (error) {
        log.error('Erreur lors du chargement du périmètre des permissions:', error);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadData();
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  const effectiveGrants = useMemo(
    () => syncPermissionGrants(selectedPermissionIds, grants),
    [selectedPermissionIds, grants]
  );

  const grantsByPermissionId = useMemo(
    () => new Map(effectiveGrants.map((grant) => [grant.permission_id, grant])),
    [effectiveGrants]
  );

  const updateGrant = (permissionId: string, patch: Partial<PermissionGrantInput>) => {
    const current = grantsByPermissionId.get(permissionId) ?? {
      permission_id: permissionId,
      scope_mode: 'company' as PermissionScopeMode,
      team_ids: [],
      targets: [],
    };

    onGrantsChange(
      syncPermissionGrants(selectedPermissionIds, [
        ...grants.filter((grant) => grant.permission_id !== permissionId),
        { ...current, ...patch, permission_id: permissionId },
      ])
    );
  };

  const toggleTeam = (permissionId: string, teamId: string) => {
    const current = grantsByPermissionId.get(permissionId);
    const teamIds = current?.team_ids ?? [];
    const nextTeamIds = teamIds.includes(teamId)
      ? teamIds.filter((id) => id !== teamId)
      : [...teamIds, teamId];
    updateGrant(permissionId, { team_ids: nextTeamIds, scope_mode: 'teams' });
  };

  const addTarget = (permissionId: string) => {
    const current = grantsByPermissionId.get(permissionId);
    const targets = current?.targets ?? [];
    const firstEmployeeId = employees[0]?.id;
    if (!firstEmployeeId) return;

    updateGrant(permissionId, {
      targets: [...targets, { employee_id: firstEmployeeId, effect: 'allow' }],
    });
  };

  const updateTarget = (
    permissionId: string,
    index: number,
    patch: Partial<PermissionTargetInput>
  ) => {
    const current = grantsByPermissionId.get(permissionId);
    const targets = [...(current?.targets ?? [])];
    targets[index] = { ...targets[index], ...patch };
    updateGrant(permissionId, { targets });
  };

  const removeTarget = (permissionId: string, index: number) => {
    const current = grantsByPermissionId.get(permissionId);
    const targets = (current?.targets ?? []).filter((_, i) => i !== index);
    updateGrant(permissionId, { targets });
  };

  const togglePermissionExpanded = (permissionId: string) => {
    setExpandedPermissions((prev) => {
      const next = new Set(prev);
      if (next.has(permissionId)) {
        next.delete(permissionId);
      } else {
        next.add(permissionId);
      }
      return next;
    });
  };

  if (loading) {
    return <SharkFinLoader label="Chargement des périmètres…" className="p-8" />;
  }

  if (selectedPermissionIds.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-6 text-center text-sm text-gray-500">
        Sélectionnez au moins une permission pour configurer son périmètre.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
        <div className="flex items-start gap-3">
          <Info className="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-600" />
          <div>
            <h4 className="font-medium text-blue-900">Périmètre des permissions</h4>
            <p className="mt-1 text-sm text-blue-700">
              Pour chaque permission, définissez si l’accès couvre toute l’entreprise, des équipes
              précises, ou uniquement des exceptions salarié (allow / deny).
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {selectedPermissionIds.map((permissionId) => {
          const grant = grantsByPermissionId.get(permissionId);
          const scopeMode = grant?.scope_mode ?? 'company';
          const meta = permissionLabels[permissionId];
          const isExpanded = expandedPermissions.has(permissionId);

          return (
            <div
              key={permissionId}
              className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm"
            >
              <button
                type="button"
                onClick={() => togglePermissionExpanded(permissionId)}
                className="flex w-full items-center justify-between gap-3 border-b border-gray-100 bg-gray-50 px-4 py-3 text-left"
              >
                <div className="flex items-center gap-3">
                  {isExpanded ? (
                    <ChevronDown className="h-5 w-5 text-gray-500" />
                  ) : (
                    <ChevronRight className="h-5 w-5 text-gray-500" />
                  )}
                  <div>
                    <div className="font-medium text-gray-900">
                      {meta?.label ?? 'Permission'}
                    </div>
                    {meta?.code && (
                      <div className="text-xs text-gray-500">{meta.code}</div>
                    )}
                  </div>
                </div>
                <span className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-700">
                  {SCOPE_MODE_OPTIONS.find((option) => option.value === scopeMode)?.label ??
                    scopeMode}
                </span>
              </button>

              {isExpanded && (
                <div className="space-y-5 p-4">
                  <div>
                    <Label className="mb-2 block text-sm font-medium text-gray-700">
                      Mode de périmètre
                    </Label>
                    <div className="grid gap-2 md:grid-cols-3">
                      {SCOPE_MODE_OPTIONS.map((option) => (
                        <label
                          key={option.value}
                          className={cn(
                            'cursor-pointer rounded-lg border-2 p-3 transition-all',
                            scopeMode === option.value
                              ? 'border-blue-500 bg-blue-50'
                              : 'border-gray-200 hover:border-blue-200',
                            disabled && 'cursor-not-allowed opacity-50'
                          )}
                        >
                          <div className="flex items-start gap-2">
                            <input
                              type="radio"
                              name={`scope_mode_${permissionId}`}
                              value={option.value}
                              checked={scopeMode === option.value}
                              onChange={() =>
                                updateGrant(permissionId, { scope_mode: option.value })
                              }
                              disabled={disabled}
                              className="mt-1"
                            />
                            <div>
                              <div className="text-sm font-medium text-gray-900">
                                {option.label}
                              </div>
                              <div className="mt-1 text-xs text-gray-500">
                                {option.description}
                              </div>
                            </div>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>

                  {scopeMode === 'teams' && (
                    <div>
                      <Label className="mb-2 block text-sm font-medium text-gray-700">
                        Équipes autorisées
                      </Label>
                      {teams.length === 0 ? (
                        <p className="text-sm text-gray-500">
                          Aucune équipe active pour cette entreprise.
                        </p>
                      ) : (
                        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                          {teams.map((team) => {
                            const checked = (grant?.team_ids ?? []).includes(team.id);
                            return (
                              <label
                                key={team.id}
                                className={cn(
                                  'flex cursor-pointer items-center gap-3 rounded-lg border p-3',
                                  checked
                                    ? 'border-blue-500 bg-blue-50'
                                    : 'border-gray-200',
                                  disabled && 'cursor-not-allowed opacity-50'
                                )}
                              >
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={() => toggleTeam(permissionId, team.id)}
                                  disabled={disabled}
                                  className="h-4 w-4 rounded"
                                />
                                <span
                                  className="h-3 w-3 rounded-full"
                                  style={{ backgroundColor: team.color }}
                                />
                                <span className="text-sm font-medium text-gray-900">
                                  {team.name}
                                </span>
                              </label>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}

                  <div>
                    <div className="mb-2 flex items-center justify-between">
                      <Label className="text-sm font-medium text-gray-700">
                        Exceptions salarié
                      </Label>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => addTarget(permissionId)}
                        disabled={disabled || employees.length === 0}
                      >
                        <Plus className="mr-1 h-4 w-4" />
                        Ajouter
                      </Button>
                    </div>

                    {(grant?.targets ?? []).length === 0 ? (
                      <p className="text-sm text-gray-500">
                        Aucune exception. Utile pour inclure ou exclure des salariés hors périmètre.
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {(grant?.targets ?? []).map((target, index) => (
                          <div
                            key={`${permissionId}-${index}`}
                            className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3 sm:flex-row sm:items-center"
                          >
                            <Select
                              value={target.employee_id}
                              onValueChange={(value) =>
                                updateTarget(permissionId, index, { employee_id: value })
                              }
                              disabled={disabled}
                            >
                              <SelectTrigger className="sm:flex-1">
                                <SelectValue placeholder="Choisir un salarié" />
                              </SelectTrigger>
                              <SelectContent>
                                {employees.map((employee) => (
                                  <SelectItem key={employee.id} value={employee.id}>
                                    {employee.first_name} {employee.last_name}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>

                            <Select
                              value={target.effect}
                              onValueChange={(value: 'allow' | 'deny') =>
                                updateTarget(permissionId, index, { effect: value })
                              }
                              disabled={disabled}
                            >
                              <SelectTrigger className="sm:w-40">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="allow">Autoriser</SelectItem>
                                <SelectItem value="deny">Refuser</SelectItem>
                              </SelectContent>
                            </Select>

                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={() => removeTarget(permissionId, index)}
                              disabled={disabled}
                              aria-label="Supprimer l'exception"
                            >
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PermissionScopeEditor;
