import { useEffect, useRef } from 'react';
import { useIsRestoring, useQueryClient } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useCompanyOptional } from '@/contexts/CompanyContext';
import { useBoot } from '@/contexts/BootContext';
import { AppBootScreen } from '@/components/AppBootScreen';
import { prefetchInBackground, runBootPrefetch } from '@/lib/prefetchByRole';
import { isPlatformAdmin } from '@/lib/platformAdmin';
import { isBadgeuseTerminalPath } from '@/lib/sessionKeepAlive';

/** Durée minimale du splash pour éviter un flash trop court */
const BOOT_MIN_MS = 250;
/** Plafond absolu — ne jamais bloquer indéfiniment */
const BOOT_MAX_MS = 12_000;

type BootGateProps = {
  children: React.ReactNode;
};

/**
 * Écran de démarrage : restauration du cache, session, entreprises, puis prefetch
 * des données des écrans principaux avant d’afficher l’application.
 */
export function BootGate({ children }: BootGateProps) {
  const location = useLocation();
  const isTerminalKiosk = isBadgeuseTerminalPath(location.pathname);
  const { user, isLoading: authLoading } = useAuth();
  const companyCtx = useCompanyOptional();
  const { markStep, finishBoot, isBooting } = useBoot();
  const queryClient = useQueryClient();
  const isRestoring = useIsRestoring();

  const bootStartedAt = useRef<number | null>(null);
  const prefetchStarted = useRef(false);

  const platformAdmin = isPlatformAdmin(user);
  const accessibleCompanies = companyCtx?.accessibleCompanies ?? [];
  const companyLoading = Boolean(user) && (companyCtx?.isLoading ?? false);
  const activeCompany = companyCtx?.activeCompany ?? null;
  const activeCompanyId = activeCompany?.company_id;
  /** Entreprises chargées + entreprise active sélectionnée (évite un prefetch sans X-Active-Company). */
  const companiesReady =
    platformAdmin ||
    !user ||
    (!companyLoading &&
      (accessibleCompanies.length === 0 || Boolean(activeCompany)));

  useEffect(() => {
    if (!isBooting) return;
    if (isTerminalKiosk) {
      finishBoot();
      return;
    }
    if (bootStartedAt.current === null) {
      bootStartedAt.current = Date.now();
    }
    const safetyTimer = setTimeout(() => {
      finishBoot();
    }, BOOT_MAX_MS);
    return () => clearTimeout(safetyTimer);
  }, [isBooting, finishBoot, isTerminalKiosk]);

  const completeBoot = () => {
    const started = bootStartedAt.current ?? Date.now();
    const elapsed = Date.now() - started;
    const wait = Math.max(0, BOOT_MIN_MS - elapsed);

    const done = () => {
      markStep('Prêt', 100);
      if (user) {
        prefetchInBackground(queryClient, user, activeCompany);
      }
      finishBoot();
    };

    if (wait > 0) {
      setTimeout(done, wait);
    } else {
      done();
    }
  };

  useEffect(() => {
    if (!isBooting || isTerminalKiosk) return;

    if (isRestoring) {
      markStep('Restauration de vos données en cache…', 12);
      return;
    }

    if (authLoading) {
      markStep('Chargement de votre session…', 20);
      prefetchStarted.current = false;
      return;
    }

    if (!user) {
      finishBoot();
      return;
    }

    if (!companiesReady) {
      markStep('Chargement de vos entreprises…', 40);
      return;
    }

    if (prefetchStarted.current) return;
    prefetchStarted.current = true;

    void runBootPrefetch(queryClient, user, activeCompany, ({ label, progress }) => {
      markStep(label, progress);
    })
      .catch(() => {
        markStep('Ouverture de l’application…', 90);
      })
      .finally(() => {
        completeBoot();
      });
  }, [
    isBooting,
    isRestoring,
    authLoading,
    user?.id,
    user?.role,
    companiesReady,
    activeCompanyId,
    markStep,
    finishBoot,
    queryClient,
    user,
    activeCompany,
    isTerminalKiosk,
  ]);

  if (isTerminalKiosk) {
    return <>{children}</>;
  }

  if (!isBooting) {
    return <>{children}</>;
  }

  return (
    <>
      <AppBootScreen />
      <div className="invisible" aria-hidden>
        {children}
      </div>
    </>
  );
}
