import { lazy, Suspense } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useBadgeuseTerminalAuth } from '@/hooks/useBadgeuseTerminalAuth';
import { BadgeuseTerminalSessionLost } from '@/components/badgeuse/rh/BadgeuseTerminalSessionLost';
import { BadgeuseTerminalSkeleton } from '@/components/skeletons/BadgeuseTerminalSkeleton';
import { hasTerminalToken } from '@/lib/badgeuseTerminalAuth';

const BadgeuseRhScanView = lazy(() =>
  import('@/components/badgeuse/rh/BadgeuseRhScanView').then((m) => ({
    default: m.BadgeuseRhScanView,
  }))
);

export function BadgeuseTerminalGate() {
  const { user, isLoading: authLoading } = useAuth();
  const terminalAuth = useBadgeuseTerminalAuth(Boolean(user));

  const waitingForTerminal = terminalAuth.isLoading && !terminalAuth.session;
  const waitingForAuth =
    authLoading && !hasTerminalToken() && !terminalAuth.session;

  if (waitingForAuth || waitingForTerminal) {
    return <BadgeuseTerminalSkeleton />;
  }

  if (terminalAuth.mode === 'none') {
    return <BadgeuseTerminalSessionLost />;
  }

  return (
    <div className="min-h-screen bg-background">
      <main className="mx-auto w-full max-w-6xl p-4 sm:p-6 lg:p-8">
        <Suspense fallback={<BadgeuseTerminalSkeleton />}>
          <BadgeuseRhScanView
            authMode={terminalAuth.mode === 'terminal' ? 'terminal' : 'rh'}
            terminalSession={terminalAuth.session}
          />
        </Suspense>
      </main>
    </div>
  );
}
