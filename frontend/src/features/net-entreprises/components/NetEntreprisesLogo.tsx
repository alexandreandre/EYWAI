import { cn } from '@/lib/utils';

/**
 * Marque visuelle « net-entreprises.fr » (reproduction stylisée, pas l'asset officiel).
 * Sert de repère visuel dans les écrans de configuration / suivi DSN.
 */
export function NetEntreprisesLogo({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex select-none items-center rounded-md bg-white px-2 py-1 text-sm font-bold leading-none shadow-sm ring-1 ring-inset ring-slate-200',
        className,
      )}
      aria-label="net-entreprises.fr"
    >
      <span className="text-[#0b7bbd]">net</span>
      <span className="text-slate-400">-</span>
      <span className="text-[#e2001a]">entreprises</span>
      <span className="ml-0.5 text-slate-400">.fr</span>
    </span>
  );
}

export default NetEntreprisesLogo;
