import { Link } from 'react-router-dom';
import {
  ClipboardList,
  Loader2,
  MoreHorizontal,
  Pencil,
  Trash2,
  UserPlus,
} from 'lucide-react';
import { isRecentHire } from '@/lib/onboardingUtils';
import {
  formatEmployeeDateFR,
  getCollectiveAgreementLabel,
  getContractTypeBadge,
  getEmploymentStatusBadge,
  getStatutCadreBadge,
} from '@/lib/employeeDisplayUtils';
import { ResidencePermitBadge } from '@/components/ResidencePermitBadge';
import { TrialPeriodBadge } from '@/components/TrialPeriodBadge';
import type { CompanyCollectiveAgreementWithDetails } from '@/api/collectiveAgreements';
import type { Team } from '@/api/teams';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
export interface EmployeeDetailHeaderEmployee {
  id: string;
  first_name: string;
  last_name: string;
  job_title: string | null;
  contract_type: string | null;
  statut: string | null;
  hire_date: string | null;
  email?: string | null;
  username?: string | null;
  employment_status?: string | null;
  team_id?: string | null;
  collective_agreement_id?: string | null;
  is_subject_to_residence_permit?: boolean | null;
  residence_permit_status?: 'valid' | 'to_renew' | 'expired' | 'to_complete' | null;
  residence_permit_expiry_date?: string | null;
  residence_permit_days_remaining?: number | null;
  residence_permit_data_complete?: boolean | null;
  trial_period_applicable?: boolean | null;
  trial_period_status?:
    | 'in_progress'
    | 'ending_soon'
    | 'ended'
    | 'confirmed'
    | 'to_complete'
    | null;
  trial_period_end_date?: string | null;
  trial_period_days_remaining?: number | null;
  trial_period_renewal_possible?: boolean | null;
}

interface EmployeeDetailHeaderCardProps {
  employee: EmployeeDetailHeaderEmployee;
  credentialsPdfUrl: string | null;
  onDelete: () => void | Promise<void>;
  activeTeams: Team[];
  teamsLoading: boolean;
  draftTeamId: string;
  onDraftTeamIdChange: (value: string) => void;
  savedTeamSelectValue: string;
  teamAssignmentDirty: boolean;
  savingTeam: boolean;
  onSaveTeam: () => void | Promise<void>;
  onCancelTeam: () => void;
  companyAgreements: CompanyCollectiveAgreementWithDetails[];
  collectiveAgreementId: string | null;
  onCollectiveAgreementIdChange: (id: string | null) => void;
  isSavingCC: boolean;
  onSaveCollectiveAgreement: () => void | Promise<void>;
  companyHasCollectiveAgreements?: boolean;
  onEditProfile?: () => void;
}

function MetadataField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div className="text-sm font-medium text-foreground">{children}</div>
    </div>
  );
}

function TeamColorDot({ color }: { color: string }) {
  return (
    <span
      className="h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-border"
      style={{ backgroundColor: color }}
      aria-hidden
    />
  );
}

export function EmployeeDetailHeaderCard({
  employee,
  credentialsPdfUrl,
  onDelete,
  activeTeams,
  teamsLoading,
  draftTeamId,
  onDraftTeamIdChange,
  savedTeamSelectValue,
  teamAssignmentDirty,
  savingTeam,
  onSaveTeam,
  onCancelTeam,
  companyAgreements,
  collectiveAgreementId,
  onCollectiveAgreementIdChange,
  isSavingCC,
  onSaveCollectiveAgreement,
  companyHasCollectiveAgreements = false,
  onEditProfile,
}: EmployeeDetailHeaderCardProps) {
  const fullName = `${employee.first_name} ${employee.last_name}`.trim();
  const initials = `${employee.first_name.charAt(0)}${employee.last_name.charAt(0)}`;
  const showOnboarding = isRecentHire(employee.hire_date);
  const employmentBadge = getEmploymentStatusBadge(employee.employment_status);

  const selectedTeam =
    draftTeamId !== '__none__'
      ? activeTeams.find((t) => t.id === draftTeamId)
      : undefined;

  const selectedAgreement = companyAgreements.find(
    (a) => a.collective_agreement_id === collectiveAgreementId,
  );
  const ccFullLabel = selectedAgreement
    ? getCollectiveAgreementLabel(selectedAgreement)
    : 'Aucune';
  const ccDirty =
    collectiveAgreementId !== (employee.collective_agreement_id ?? null);

  const pdfFileName = `Compte_${employee.first_name}_${employee.last_name}.pdf`;

  const menuItems: Array<{ key: string; node: React.ReactNode }> = [];

  if (credentialsPdfUrl && showOnboarding) {
    menuItems.push({
      key: 'pdf',
      node: (
        <DropdownMenuItem asChild>
          <a
            href={credentialsPdfUrl}
            download={pdfFileName}
            className="flex cursor-pointer items-center"
          >
            <UserPlus className="mr-2 h-4 w-4" />
            PDF création de compte
          </a>
        </DropdownMenuItem>
      ),
    });
  }

  menuItems.push({
    key: 'delete',
    node: (
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onSelect={(e) => e.preventDefault()}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Supprimer le collaborateur
          </DropdownMenuItem>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Êtes-vous absolument certain ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action est irréversible. Elle supprimera définitivement le
              collaborateur, son compte utilisateur, et toutes les données
              associées (bulletins, plannings, etc.).
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => void onDelete()}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Confirmer la suppression
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    ),
  });

  const showActionsMenu = menuItems.length > 0;

  return (
    <Card>
      <CardHeader className="space-y-4 border-b pb-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
            <Avatar className="h-16 w-16 shrink-0">
              <AvatarFallback className="text-xl">{initials}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="line-clamp-2 text-2xl">{fullName}</CardTitle>
                {employmentBadge}
              </div>
              {employee.job_title ? (
                <CardDescription className="text-base">
                  {employee.job_title}
                </CardDescription>
              ) : null}
              {employee.email ? (
                <p className="text-sm">
                  <a
                    href={`mailto:${employee.email}`}
                    className="text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                  >
                    {employee.email}
                  </a>
                </p>
              ) : null}
              {employee.username ? (
                <p className="text-xs text-muted-foreground">
                  Identifiant de connexion&nbsp;:{' '}
                  <span className="font-mono">{employee.username}</span>
                </p>
              ) : null}
            </div>
          </div>

          <div className="flex w-full shrink-0 flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
            {onEditProfile ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full sm:w-auto"
                onClick={onEditProfile}
              >
                <Pencil className="mr-2 h-4 w-4" aria-hidden />
                Modifier la fiche
              </Button>
            ) : null}
            {showOnboarding ? (
              <Button variant="outline" size="sm" asChild className="w-full sm:w-auto">
                <Link to={`/onboarding/${employee.id}`}>
                  <ClipboardList className="mr-2 h-4 w-4" />
                  Voir l&apos;onboarding
                </Link>
              </Button>
            ) : null}
            {credentialsPdfUrl && !showOnboarding ? (
              <Button variant="outline" size="sm" asChild className="w-full sm:w-auto">
                <a href={credentialsPdfUrl} download={pdfFileName} title={pdfFileName}>
                  <UserPlus className="mr-2 h-4 w-4" />
                  PDF compte
                </a>
              </Button>
            ) : null}
            {showActionsMenu ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full sm:w-auto"
                    aria-label="Actions sur le collaborateur"
                  >
                    <MoreHorizontal className="mr-2 h-4 w-4" />
                    Actions
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  {menuItems.map((item) => (
                    <span key={item.key}>{item.node}</span>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            ) : null}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6 pt-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <MetadataField label="Type de contrat">
            {getContractTypeBadge(employee.contract_type)}
          </MetadataField>
          <MetadataField label="Statut">{getStatutCadreBadge(employee.statut)}</MetadataField>
          <MetadataField label="Date d'entrée">
            {formatEmployeeDateFR(employee.hire_date)}
          </MetadataField>
        </div>

        <div className="space-y-4 border-t pt-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Affectation
          </p>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Équipe
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Select
                  value={draftTeamId}
                  onValueChange={onDraftTeamIdChange}
                  disabled={teamsLoading || savingTeam}
                >
                  <SelectTrigger
                    className="h-9 max-w-full gap-2 sm:max-w-xs"
                    aria-label="Équipe du collaborateur"
                  >
                    {selectedTeam ? <TeamColorDot color={selectedTeam.color} /> : null}
                    <SelectValue
                      placeholder={
                        employee.team_id && teamsLoading
                          ? 'Chargement…'
                          : 'Aucune équipe'
                      }
                    />
                  </SelectTrigger>
                  <SelectContent position="popper" className="z-[100]">
                    <SelectItem value="__none__">Aucune équipe</SelectItem>
                    {activeTeams.map((t) => (
                      <SelectItem key={t.id} value={t.id}>
                        <span className="flex items-center gap-2">
                          <TeamColorDot color={t.color} />
                          {t.name}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {teamAssignmentDirty ? (
                  <>
                    <Button
                      type="button"
                      size="sm"
                      disabled={savingTeam}
                      onClick={() => void onSaveTeam()}
                    >
                      {savingTeam ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        'Enregistrer'
                      )}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={savingTeam}
                      onClick={onCancelTeam}
                    >
                      Annuler
                    </Button>
                  </>
                ) : null}
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Convention collective
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="min-w-0 max-w-full sm:max-w-xs">
                        <Select
                          value={collectiveAgreementId ?? '__aucune__'}
                          onValueChange={(v) =>
                            onCollectiveAgreementIdChange(
                              v === '__aucune__' ? null : v,
                            )
                          }
                        >
                          <SelectTrigger className="h-9 w-full max-w-xs [&>span]:truncate">
                            <SelectValue placeholder="Aucune" />
                          </SelectTrigger>
                          <SelectContent position="popper" className="z-[100]">
                            <SelectItem value="__aucune__">Aucune</SelectItem>
                            {companyAgreements.map((a) => (
                              <SelectItem
                                key={a.id}
                                value={a.collective_agreement_id}
                              >
                                {getCollectiveAgreementLabel(a)}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="max-w-sm">
                      <p>{ccFullLabel}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                {selectedAgreement?.agreement_details?.idcc ? (
                  <Badge variant="secondary" className="shrink-0 font-mono text-xs">
                    IDCC {selectedAgreement.agreement_details.idcc}
                  </Badge>
                ) : null}
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() => void onSaveCollectiveAgreement()}
                  disabled={isSavingCC || !ccDirty}
                >
                  {isSavingCC ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  Enregistrer
                </Button>
              </div>
              {companyHasCollectiveAgreements && collectiveAgreementId == null ? (
                <p className="text-xs text-amber-800">
                  Convention collective non renseignée sur cette fiche.
                </p>
              ) : null}
            </div>
          </div>
        </div>

        <ResidencePermitBadge
          data={{
            is_subject_to_residence_permit:
              employee.is_subject_to_residence_permit ?? false,
            residence_permit_status: employee.residence_permit_status ?? null,
            residence_permit_expiry_date:
              employee.residence_permit_expiry_date ?? null,
            residence_permit_days_remaining:
              employee.residence_permit_days_remaining ?? null,
            residence_permit_data_complete:
              employee.residence_permit_data_complete ?? null,
          }}
        />
        <TrialPeriodBadge
          data={{
            trial_period_applicable: employee.trial_period_applicable,
            trial_period_status: employee.trial_period_status,
            trial_period_end_date: employee.trial_period_end_date,
            trial_period_days_remaining: employee.trial_period_days_remaining,
            trial_period_renewal_possible: employee.trial_period_renewal_possible,
          }}
        />
      </CardContent>
    </Card>
  );
}
