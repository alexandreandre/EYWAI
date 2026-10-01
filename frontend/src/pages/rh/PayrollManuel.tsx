import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { RhPageHeader } from '@/components/layout';
import {
  ETAPES_MANUEL,
  PIEGES_MANUEL,
  SECTIONS_MANUEL,
} from '@/features/payroll/utils/manuelOperateur';

export default function PayrollManuel() {
  const etapes = SECTIONS_MANUEL.find((s) => s.id === 'etapes');
  const pieges = SECTIONS_MANUEL.find((s) => s.id === 'pieges');

  return (
    <article className="mx-auto max-w-2xl space-y-8">
      <RhPageHeader
        title="Manuel de la paie du mois"
        description="Les étapes dans l’ordre, les pièges déjà vus, et quoi faire. Relisez chaque écran : une coche verte n’apparaît que si le logiciel peut le prouver."
        back={
          <Link
            to="/payroll"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden />
            Retour à la paie
          </Link>
        }
      />

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">{etapes?.titre}</h2>
        {etapes?.intro ? <p className="text-sm text-muted-foreground">{etapes.intro}</p> : null}
        {ETAPES_MANUEL.map((etape) => (
          <div key={etape.titre} className="space-y-2">
            <h3 className="text-sm font-semibold">{etape.titre}</h3>
            {etape.paragraphes.map((p) => (
              <p key={p} className="text-sm leading-relaxed text-foreground/90">
                {p}
              </p>
            ))}
          </div>
        ))}
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">{pieges?.titre}</h2>
        {pieges?.intro ? <p className="text-sm text-muted-foreground">{pieges.intro}</p> : null}
        <ul className="space-y-3">
          {PIEGES_MANUEL.map((piege) => (
            <li key={piege.titre} className="rounded-lg border border-border bg-muted/20 px-4 py-3">
              <p className="text-sm font-semibold">{piege.titre}</p>
              <p className="mt-1 text-sm leading-relaxed text-foreground/90">{piege.quoiFaire}</p>
            </li>
          ))}
        </ul>
      </section>
    </article>
  );
}
