import { BadgeuseRhScanView } from '@/components/badgeuse/rh/BadgeuseRhScanView';
import type { BadgeuseTerminalAuthMode } from '@/hooks/useBadgeuseTerminalAuth';
import type { BadgeuseTerminalSession } from '@/lib/badgeuseTerminalAuth';

type Props = {
  authMode?: BadgeuseTerminalAuthMode;
  terminalSession?: BadgeuseTerminalSession | null;
};

export default function BadgeuseRhScanPage(props: Props) {
  return <BadgeuseRhScanView {...props} />;
}
