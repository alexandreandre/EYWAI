import { useState } from 'react';
import { ChevronDown, ChevronRight, NotebookPen } from 'lucide-react';

import {
  lireAnnotationsReleve,
  estAnnotationReleve,
  phraseAnnotations,
  type AnnotationsSalarie,
  type JourAnnote,
} from './annotationsReleve';

/**
 * « Relevé à relire » lisible en entier (Elsa, 26/11) : chaque jour annoté sur
 * sa ligne, regroupé par salarié. La phrase du serveur, coupée, était illisible.
 */

const RAPPEL = 'Martine a retenu les heures du badge, pas les annotations.';

function ListeJours({ jours }: { jours: JourAnnote[] }) {
  return (
    <ul className="space-y-0.5">
      {jours.map((j) => (
        <li key={`${j.jour}|${j.annotation}`} className="flex gap-2 break-words">
          {j.jour ? <span className="w-16 shrink-0 font-medium tabular-nums">{j.jour}</span> : null}
          <span className="min-w-0 whitespace-normal">{j.annotation}</span>
        </li>
      ))}
    </ul>
  );
}

/** Le bandeau de la revue : tous les salariés dont le relevé porte des annotations. */
export function AnnotationsReleveBandeau({ groupes }: { groupes: AnnotationsSalarie[] }) {
  const [ouvert, setOuvert] = useState(false);
  if (groupes.length === 0) return null;
  const jours = groupes.reduce((n, g) => n + g.jours.length, 0);
  return (
    <div
      className="shrink-0 rounded-md border border-amber-300/80 bg-amber-50/70 px-2 py-1.5 text-[11px] text-amber-900"
      data-testid="annotations-releve"
    >
      <button
        type="button"
        className="flex w-full items-start gap-1 text-left"
        aria-expanded={ouvert}
        onClick={() => setOuvert((v) => !v)}
      >
        {ouvert ? (
          <ChevronDown className="mt-px h-3.5 w-3.5 shrink-0" />
        ) : (
          <ChevronRight className="mt-px h-3.5 w-3.5 shrink-0" />
        )}
        <span>
          <span className="font-medium">Relevé à relire : {phraseAnnotations(jours, groupes.length)}.</span>{' '}
          {RAPPEL} {ouvert ? 'Replier' : 'Voir chaque jour'}
        </span>
      </button>
      {ouvert ? (
        <div className="mt-1.5 max-h-56 space-y-2 overflow-y-auto pl-5 pr-1">
          {groupes.map((g) => (
            <div key={g.cle}>
              <p className="font-semibold">{g.nom}</p>
              <ListeJours jours={g.jours} />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

const JOURS_VISIBLES = 3;

/** Sous la ligne d'un salarié : ses jours annotés, un par ligne. */
export function AnnotationsReleveLigne({ warnings }: { warnings: readonly string[] }) {
  const [tout, setTout] = useState(false);
  const jours: JourAnnote[] = [];
  const vus = new Set<string>();
  for (const w of warnings) {
    if (!estAnnotationReleve(w)) continue;
    for (const j of lireAnnotationsReleve(w)) {
      const cle = `${j.jour}|${j.annotation}`;
      if (!vus.has(cle)) {
        vus.add(cle);
        jours.push(j);
      }
    }
  }
  if (jours.length === 0) return null;
  const visibles = tout ? jours : jours.slice(0, JOURS_VISIBLES);
  const reste = jours.length - visibles.length;
  return (
    <div className="mt-0.5 pl-6 text-[11px] text-amber-800" data-testid="annotations-releve-ligne">
      <p className="flex items-center gap-1 font-medium">
        <NotebookPen className="h-3 w-3" aria-hidden />
        Relevé à relire : {phraseAnnotations(jours.length, 1)}. {RAPPEL}
      </p>
      <div className="pl-4">
        <ListeJours jours={visibles} />
        {jours.length > JOURS_VISIBLES ? (
          <button
            type="button"
            className="mt-0.5 font-medium text-primary hover:underline"
            onClick={() => setTout((v) => !v)}
          >
            {tout ? 'Montrer moins' : `Voir les ${reste} autre${reste > 1 ? 's' : ''} jour${reste > 1 ? 's' : ''}`}
          </button>
        ) : null}
      </div>
    </div>
  );
}
