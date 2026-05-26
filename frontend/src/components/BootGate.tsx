import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/contexts/AuthContext';
import { useCompanyOptional } from '@/contexts/CompanyContext';
import { useBoot } from '@/contexts/BootContext';
import { AppBootScreen } from '@/components/AppBootScreen';
import { prefetchForUser } from '@/lib/prefetchByRole';

/** Délai max du splash, même si le prefetch ou les entreprises traînent */
const BOOT_MAX_MS = 3000;

type BootGateProps = {
  children: React.ReactNode;
};

/**
 * Affiche le splash jusqu'à ce que auth (+ entreprises si besoin) soient prêts.
 * Le prefetch tourne en arrière-plan sans bloquer l'ouverture de l'app.
 */
export function BootGate({ children }: BootGateProps) {
  const { user, isLoading: authLoading } = useAuth();
  const companyCtx = useCompanyOptional();
  const { markStep, finishBoot, isBooting } = useBoot();
  const queryClient = useQueryClient();

  const isSuperAdmin =
    user?.is_super_admin === true || user?.role === 'super_admin';
  const companyLoading =
    Boolean(user) && !isSuperAdmin && (companyCtx?.isLoading ?? false);
  const activeCompany = companyCtx?.activeCompany ?? null;
  const activeCompanyId = activeCompany?.company_id;

  // Plafond absolu : ne jamais bloquer plus de BOOT_MAX_MS
  useEffect(() => {
    if (!isBooting) return;
    const safetyTimer = setTimeout(() => {
      finishBoot();
    }, BOOT_MAX_MS);
    return () => clearTimeout(safetyTimer);
  }, [isBooting, finishBoot]);

  useEffect(() => {
    if (authLoading) {
      markStep('Chargement de votre session…', 15);
      return;
    }

    if (!user) {
      finishBoot();
      return;
    }

    if (companyLoading) {
      markStep('Chargement de vos entreprises…', 50);
      return;
    }

    markStep('Ouverture de l\'application…', 85);

    // Prefetch non bloquant : les pages afficheront des skeletons si besoin
    void prefetchForUser(queryClient, user, activeCompany);

    const openTimer = setTimeout(() => {
      markStep('Prêt', 100);
      finishBoot();
    }, 120);

    return () => clearTimeout(openTimer);
  }, [
    authLoading,
    user?.id,
    user?.role,
    companyLoading,
    activeCompanyId,
    markStep,
    finishBoot,
    queryClient,
    user,
    activeCompany,
  ]);

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
