/** Ce qui est ajouté et pas encore appliqué : en vert, avec la poubelle pour l'enlever. */
import { Trash2, Undo2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { type EtatCorrections, eurosFr, moisAffiche } from '@/features/payroll/utils/correctionsBulletin';

interface Props {
  initial: EtatCorrections;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
}

function Ligne({ texte, detail, onRetirer, disabled }: { texte: string; detail: string; onRetirer: () => void; disabled?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b bg-green-50 px-3 py-2 text-sm dark:bg-green-950/20">
      <div>
        <span className="font-medium">{texte}</span>
        <span className="ml-2 rounded bg-green-100 px-1.5 text-xs font-semibold text-green-800">Nouvelle</span>
        <div className="text-xs text-muted-foreground">{detail}</div>
      </div>
      {disabled ? null : (
        <Button variant="ghost" size="sm" aria-label={`Ne pas ajouter ${texte}`} onClick={onRetirer}>
          <Trash2 className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}

export default function LignesAjoutees({ initial, etat, onChange, disabled }: Props) {
  const heuresChangees = etat.hs25 !== initial.hs25 || etat.hs50 !== initial.hs50;
  const complementairesChangees = etat.hc1 !== initial.hc1 || etat.hc2 !== initial.hc2;
  const rien =
    !heuresChangees &&
    !complementairesChangees &&
    etat.primesAjoutees.length === 0 &&
    etat.heuresRegulariseesAjoutees.length === 0 &&
    etat.regularisationsAjoutees.length === 0;
  if (rien) return null;
  return (
    <div data-testid="lignes-ajoutees">
      {heuresChangees ? (
        <div className="flex items-center justify-between gap-2 border-b bg-green-50 px-3 py-2 text-sm dark:bg-green-950/20">
          <span className="font-medium">
            Heures sup du mois : {String(etat.hs25).replace('.', ',')} h à 25 %, {String(etat.hs50).replace('.', ',')} h à 50 %
          </span>
          {disabled ? null : (
            <Button variant="ghost" size="sm" onClick={() => onChange({ ...etat, hs25: initial.hs25, hs50: initial.hs50 })}>
              <Undo2 className="mr-1 h-4 w-4" /> Remettre
            </Button>
          )}
        </div>
      ) : null}
      {complementairesChangees ? (
        <div className="flex items-center justify-between gap-2 border-b bg-green-50 px-3 py-2 text-sm dark:bg-green-950/20">
          <span className="font-medium">
            Heures complémentaires du mois : {String(etat.hc1).replace('.', ',')} h et {String(etat.hc2).replace('.', ',')} h
          </span>
          {disabled ? null : (
            <Button variant="ghost" size="sm" onClick={() => onChange({ ...etat, hc1: initial.hc1, hc2: initial.hc2 })}>
              <Undo2 className="mr-1 h-4 w-4" /> Remettre
            </Button>
          )}
        </div>
      ) : null}
      {etat.primesAjoutees.map((p, i) => (
        <Ligne
          key={`prime-${i}`}
          texte={p.name}
          detail={eurosFr(p.amount)}
          disabled={disabled}
          onRetirer={() => onChange({ ...etat, primesAjoutees: etat.primesAjoutees.filter((_, j) => j !== i) })}
        />
      ))}
      {etat.heuresRegulariseesAjoutees.map((h, i) => (
        <Ligne
          key={`heures-${i}`}
          texte={`Heures de ${moisAffiche(h.mois_origine)}`}
          detail={`${String(h.quantite).replace('.', ',')} h — ${h.motif}`}
          disabled={disabled}
          onRetirer={() =>
            onChange({ ...etat, heuresRegulariseesAjoutees: etat.heuresRegulariseesAjoutees.filter((_, j) => j !== i) })
          }
        />
      ))}
      {etat.regularisationsAjoutees.map((r, i) => (
        <Ligne
          key={`coti-${i}`}
          texte={r.libelle}
          detail={r.motif}
          disabled={disabled}
          onRetirer={() => onChange({ ...etat, regularisationsAjoutees: etat.regularisationsAjoutees.filter((_, j) => j !== i) })}
        />
      ))}
    </div>
  );
}
