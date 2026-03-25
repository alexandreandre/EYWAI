/**
 * CompanySwitcher : Sélecteur d'entreprise pour utilisateurs multi-entreprises
 *
 * Affiche :
 * - Un simple badge si l'utilisateur n'a accès qu'à une entreprise
 * - Un dropdown si l'utilisateur a accès à plusieurs entreprises
 */

import { useCompany, type CompanyAccess } from '@/contexts/CompanyContext';
import { Building2, ChevronDown, Check } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export function CompanySwitcher() {
  const { accessibleCompanies, activeCompany, setActiveCompany, isLoading, error } = useCompany();

  console.log('%c[CompanySwitcher] 🔨 Rendu du composant CompanySwitcher', 'background: orange; color: white; font-weight: bold');

  // Log localStorage pour debug
  const localStorageCompanyId = localStorage.getItem('activeCompanyId');
  console.log('%c[CompanySwitcher] 📂 localStorage activeCompanyId:', 'background: blue; color: white; font-weight: bold', localStorageCompanyId);

  try {
    // Déterminer si l'utilisateur a accès à plusieurs entreprises d'un même groupe
    const groupedCompanies: Record<string, CompanyAccess[]> = {};
    accessibleCompanies.forEach((company) => {
      if (company.group_id) {
        if (!groupedCompanies[company.group_id]) {
          groupedCompanies[company.group_id] = [];
        }
        groupedCompanies[company.group_id].push(company);
      }
    });

    // Trouver le groupe de l'entreprise active (si elle appartient à un groupe avec >1 entreprise accessible)
    const activeCompanyGroup = activeCompany?.group_id && groupedCompanies[activeCompany.group_id]?.length > 1
      ? groupedCompanies[activeCompany.group_id][0]
      : null;

    console.log('%c[CompanySwitcher] isLoading:', 'color: orange', isLoading);
    console.log('%c[CompanySwitcher] error:', 'color: orange', error);
    console.log('%c[CompanySwitcher] accessibleCompanies:', 'color: orange', accessibleCompanies);
    console.log('');
    console.log('%c[CompanySwitcher] ⭐ ENTREPRISE ACTIVE (activeCompany):', 'background: green; color: white; font-weight: bold; font-size: 14px', activeCompany);
    console.log('');

    // Pendant le chargement
    if (isLoading) {
      console.log('%c[CompanySwitcher] ⏳ Chargement en cours...', 'color: orange');
      return (
        <div className="flex items-center gap-2 px-3 py-2 bg-muted rounded-md animate-pulse">
          <Building2 className="h-4 w-4" />
          <span className="text-sm">Chargement...</span>
        </div>
      );
    }

    // Aucune entreprise
    if (accessibleCompanies.length === 0) {
      console.log('%c[CompanySwitcher] ⚠️ Aucune entreprise accessible', 'color: orange');
      return null;
    }

    // Une seule entreprise : ne rien afficher
    if (accessibleCompanies.length === 1) {
      console.log('%c[CompanySwitcher] ✅ Une seule entreprise - Aucun sélecteur affiché', 'color: green');
      return null;
    }

    // Plusieurs entreprises : dropdown interactif
    console.log('%c[CompanySwitcher] ✅ Plusieurs entreprises - Affichage du dropdown', 'color: green');
    return (
      <div className="flex items-center gap-2">
        {/* Logo du groupe à gauche de la carte, si l'entreprise active appartient à un groupe avec >1 entreprise accessible */}
        {activeCompanyGroup?.group_logo_url && (
          <div className="flex-shrink-0">
            <img
              src={activeCompanyGroup.group_logo_url}
              alt={`Logo ${activeCompanyGroup.group_name || 'groupe'}`}
              className="h-8 w-8 object-contain"
              style={{ transform: `scale(${activeCompanyGroup.group_logo_scale || 1.0})` }}
            />
          </div>
        )}

        <DropdownMenu>
          <DropdownMenuTrigger className="flex items-center gap-2 px-3 py-2 bg-muted/50 rounded-md hover:bg-muted transition-colors outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2">
            <Building2 className="h-4 w-4 text-primary flex-shrink-0" />
            <div className="flex flex-col items-start min-w-0">
              <span className="text-sm font-medium truncate max-w-[200px]">
                {activeCompany?.company_name || 'Sélectionner une entreprise'}
              </span>
              {activeCompany && (
                <span className="text-xs text-muted-foreground capitalize">
                  {activeCompany.role}
                </span>
              )}
            </div>
            <ChevronDown className="h-4 w-4 opacity-50 flex-shrink-0 ml-auto" />
          </DropdownMenuTrigger>

        <DropdownMenuContent align="start" className="w-[280px]">
          <DropdownMenuLabel className="text-xs text-muted-foreground">
            Mes entreprises ({accessibleCompanies.length})
          </DropdownMenuLabel>
          <DropdownMenuSeparator />

          {accessibleCompanies.map((company) => {
            const isActive = activeCompany?.company_id === company.company_id;

            return (
              <DropdownMenuItem
                key={company.company_id}
                onClick={() => setActiveCompany(company.company_id)}
                className={cn(
                  'cursor-pointer',
                  isActive && 'bg-accent'
                )}
              >
                <div className="flex items-center justify-between w-full gap-2">
                  <div className="flex flex-col flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium truncate">{company.company_name}</span>
                      {company.is_primary && (
                        <Badge variant="outline" className="text-[10px] px-1 py-0">
                          Principal
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="capitalize">{company.role}</span>
                      {company.siret && (
                        <>
                          <span>•</span>
                          <span className="font-mono">{company.siret}</span>
                        </>
                      )}
                    </div>
                  </div>
                  {isActive && (
                    <Check className="h-4 w-4 text-primary flex-shrink-0" />
                  )}
                </div>
              </DropdownMenuItem>
            );
          })}
        </DropdownMenuContent>
      </DropdownMenu>
      </div>
    );
  } catch (err) {
    // Erreur inattendue pendant le rendu (logs / dérivations) — ne pas bloquer la sidebar
    console.error('%c[CompanySwitcher] 💥 ERREUR CRITIQUE:', 'background: red; color: white; font-weight: bold', err);
    return null;
  }
}

/**
 * Variante compacte pour la barre de navigation mobile
 */
export function CompanySwitcherCompact() {
  const { accessibleCompanies, activeCompany, setActiveCompany, isLoading } = useCompany();

  if (isLoading || accessibleCompanies.length <= 1) {
    return null;
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex items-center gap-1 px-2 py-1 bg-muted/50 rounded hover:bg-muted transition-colors">
        <Building2 className="h-3 w-3" />
        <span className="text-xs font-medium max-w-[100px] truncate">
          {activeCompany?.company_name}
        </span>
        <ChevronDown className="h-3 w-3 opacity-50" />
      </DropdownMenuTrigger>

      <DropdownMenuContent align="start" className="w-[240px]">
        {accessibleCompanies.map((company) => {
          const isActive = activeCompany?.company_id === company.company_id;

          return (
            <DropdownMenuItem
              key={company.company_id}
              onClick={() => setActiveCompany(company.company_id)}
              className={cn('cursor-pointer', isActive && 'bg-accent')}
            >
              <div className="flex items-center justify-between w-full">
                <span className="text-sm truncate">{company.company_name}</span>
                {isActive && <Check className="h-3 w-3" />}
              </div>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
