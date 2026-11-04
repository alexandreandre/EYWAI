import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { rafraichirBadgesAnciens } from '@/lib/invalidateRhSidebarBadges';
import { useRhPendingTasks } from '@/hooks/useRhPendingTasks';
import { sumRhPendingActions } from '@/lib/rhPendingTasks';

/**
 * Compteurs « à traiter » pour la navigation RH (sidebar).
 * Pastilles agrégées côté UI : présence si count > 0 ; affichage du nombre sur les sous-liens.
 */
export function useRhSidebarTaskBadges(enabled: boolean) {
  const queryClient = useQueryClient();
  const location = useLocation();
  const {
    items,
    sidebarCounts,
    isLoading,
    isPayrollPipelineLoading,
    hasError,
    isPayrollPipelineError,
    retryFailed,
    getCount,
  } = useRhPendingTasks(enabled);

  const prevPathRef = useRef<string | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const prev = prevPathRef.current;
    prevPathRef.current = location.pathname;
    if (prev === null || prev === location.pathname) return;
    // Seulement les compteurs anciens : une mutation réussie, elle, relit tout
    // (écouteur global de lib/queryClient.ts).
    void rafraichirBadgesAnciens(queryClient);
  }, [enabled, location.pathname, queryClient]);

  const dashboardOnlyIds = new Set(['onboardingProfiles', 'pendingSignatures']);
  const totalRhPending = sumRhPendingActions(
    items.filter((item) => !dashboardOnlyIds.has(item.id)),
  );

  return {
    getCount,
    counts: sidebarCounts,
    isLoading,
    isPayrollPipelineLoading,
    hasError,
    isPayrollPipelineError,
    retryFailed,
    totalRhPending,
  };
}
