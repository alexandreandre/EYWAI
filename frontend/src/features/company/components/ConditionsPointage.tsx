// Réglages des primes liées aux pointages (retour d'Elsa du 17/11/2026) :
// heure de début du poste, pause payée en heures, périmètre (hors forfait
// jours, cadres, alternants), heures de nuit, prime d'assiduité au calendrier.
import { useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { ChampDecimal } from '@/components/ui/champ-decimal';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { direPlage, plageAutourDe } from '@/features/company/lib/primesPointage';

export type { PlageDebut } from '@/features/company/lib/primesPointage';
import type { PlageDebut } from '@/features/company/lib/primesPointage';
type Conditions = Record<string, unknown>;
type Props = { conditions: Conditions; onChange: (next: Conditions) => void };

function sansCle(conditions: Conditions, cle: string): Conditions {
  const copie = { ...conditions };
  delete copie[cle];
  return copie;
}

/** « Seulement les postes qui commencent vers 4 h, 12 h » : on tape l'heure du poste,
 * Martine pose la plage d'une heure de chaque côté (examen du 20/11), ajustable. */
export function PlagesDebut({ conditions, onChange }: Props) {
  const plages = (conditions.plages_debut as PlageDebut[] | undefined) ?? [];
  const [heure, setHeure] = useState('');
  const poser = (suivantes: PlageDebut[]) =>
    onChange(suivantes.length ? { ...conditions, plages_debut: suivantes } : sansCle(conditions, 'plages_debut'));
  const plage = plageAutourDe(heure);
  const ajouter = () => {
    if (!plage) return;
    poser([...plages, plage]);
    setHeure('');
  };
  return (
    <div className="space-y-2" data-testid="plages-debut">
      <Label htmlFor="heure-poste">Seulement les postes qui commencent vers (facultatif)</Label>
      <p className="text-xs text-muted-foreground">
        Tapez l&apos;heure du poste (4, 12, 12h30) : Martine compte les arrivées pointées une heure avant ou après
        (poste de 4 h : arrivée entre 3 h et 5 h). Sans heure ici, tous les jours travaillés comptent. Un jour
        travaillé sans heure d&apos;arrivée dans les pointages est signalé à la simulation.
      </p>
      {plages.map((p, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-medium min-w-[7rem]">Poste {direPlage(p)}</span>
          <span className="text-muted-foreground">arrivée de</span>
          <Input
            type="time"
            aria-label={`Début de la plage ${i + 1}`}
            className="w-28"
            value={p.de}
            onChange={(e) => poser(plages.map((x, j) => (j === i ? { ...x, de: e.target.value } : x)))}
          />
          <span className="text-muted-foreground">à</span>
          <Input
            type="time"
            aria-label={`Fin de la plage ${i + 1}`}
            className="w-28"
            value={p.a}
            onChange={(e) => poser(plages.map((x, j) => (j === i ? { ...x, a: e.target.value } : x)))}
          />
          <Button type="button" variant="ghost" size="sm" onClick={() => poser(plages.filter((_, j) => j !== i))}>
            Retirer
          </Button>
        </div>
      ))}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          id="heure-poste"
          aria-label="Heure du poste"
          className="w-28"
          placeholder="ex. 4"
          value={heure}
          onChange={(e) => setHeure(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              ajouter();
            }
          }}
        />
        <Button type="button" variant="outline" size="sm" disabled={!plage} onClick={ajouter}>
          Ajouter ce poste
        </Button>
        {heure.trim() !== '' && !plage && (
          <span className="text-xs text-destructive">Une heure, par exemple 4 ou 12h30.</span>
        )}
      </div>
    </div>
  );
}

/** Pause payée : N heures par jour au taux horaire du salarié, au lieu d'un montant. */
export function HeuresParJour({ conditions, onChange }: Props) {
  const valeur = conditions.heures_par_jour as number | undefined;
  return (
    <div className="space-y-2">
      <Label htmlFor="heures_par_jour">Ou payer des heures par jour au taux horaire (facultatif)</Label>
      <ChampDecimal
        id="heures_par_jour"
        className="max-w-[10rem]"
        placeholder="ex. 0,5"
        value={valeur}
        onValueChange={(v) =>
          onChange(v == null ? sansCle(conditions, 'heures_par_jour') : { ...conditions, heures_par_jour: v })
        }
      />
      <p className="text-xs text-muted-foreground">
        Rempli, le montant de la règle est ignoré : chaque jour retenu paie ces heures au taux horaire de base de la
        fiche (pause indemnisée de 0,5 h, par exemple).
      </p>
    </div>
  );
}

const EXCLUSIONS: { cle: string; libelle: string }[] = [
  { cle: 'exclure_forfait_jours', libelle: 'Hors forfait jours' },
  { cle: 'exclure_cadres', libelle: 'Hors cadres' },
  { cle: 'exclure_alternants', libelle: 'Hors alternants (apprentissage, professionnalisation)' },
];

/** Périmètre des primes de pointage : la population qui pointe. */
export function PerimetrePointage({ conditions, onChange }: Props) {
  return (
    <div className="space-y-2" data-testid="perimetre-pointage">
      <Label>Exclure</Label>
      <div className="flex flex-wrap gap-4">
        {EXCLUSIONS.map(({ cle, libelle }) => (
          <label key={cle} className="flex items-center gap-2 text-sm cursor-pointer">
            <Checkbox
              checked={Boolean(conditions[cle])}
              onCheckedChange={(v) => onChange(v ? { ...conditions, [cle]: true } : sansCle(conditions, cle))}
            />
            {libelle}
          </label>
        ))}
      </div>
    </div>
  );
}

/** Heures de nuit lues sur les pointages, majorées d'un % du taux horaire. */
export function ReglageNuit({ conditions, onChange }: Props) {
  const depuisPointages = Boolean(conditions.depuis_les_pointages);
  return (
    <div className="space-y-2" data-testid="reglage-nuit">
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <Checkbox
          checked={depuisPointages}
          onCheckedChange={(v) =>
            onChange(v ? { ...conditions, depuis_les_pointages: true } : sansCle(conditions, 'depuis_les_pointages'))
          }
        />
        Lire les heures de nuit sur les pointages (sans planning d&apos;équipe)
      </label>
      {depuisPointages && (
        <>
          <p className="text-sm text-muted-foreground">
            Martine compte les heures de chaque poste pointé (première entrée, dernière sortie) tombées dans la plage
            de nuit. Un poste de 5 h donne 1 h de nuit (5 h - 6 h).
          </p>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            Nuit de
            <Input
              type="time"
              aria-label="Début de la nuit"
              className="w-28"
              value={(conditions.nuit_de as string | undefined) ?? '22:00'}
              onChange={(e) => onChange({ ...conditions, nuit_de: e.target.value })}
            />
            à
            <Input
              type="time"
              aria-label="Fin de la nuit"
              className="w-28"
              value={(conditions.nuit_a as string | undefined) ?? '06:00'}
              onChange={(e) => onChange({ ...conditions, nuit_a: e.target.value })}
            />
          </div>
        </>
      )}
      <Label htmlFor="majoration_pct">Majoration en % du taux horaire</Label>
      <ChampDecimal
        id="majoration_pct"
        className="max-w-[10rem]"
        placeholder="ex. 50"
        value={conditions.majoration_pct as number | undefined}
        onValueChange={(v) =>
          onChange(v == null ? sansCle(conditions, 'majoration_pct') : { ...conditions, majoration_pct: v })
        }
      />
    </div>
  );
}

/** Prime d'assiduité lue au calendrier : par semaine ou par mois. */
export function ReglageAssiduite({ conditions, onChange }: Props) {
  const periode = (conditions.periode_assiduite as string | undefined) ?? 'semaine';
  return (
    <div className="space-y-2" data-testid="reglage-assiduite">
      <Label htmlFor="periode_assiduite">Versée</Label>
      <select
        id="periode_assiduite"
        className="block h-10 w-full max-w-xs rounded-md border bg-background px-3 text-sm"
        value={periode}
        onChange={(e) => onChange({ ...conditions, periode_assiduite: e.target.value })}
      >
        <option value="semaine">par semaine sans absence</option>
        <option value="mois">par mois sans absence</option>
      </select>
      <p className="text-xs text-muted-foreground">
        Martine lit le calendrier : un arrêt, une absence non rémunérée, un jour « absent, type à donner » ou une
        journée prévue avec un réel à 0 font perdre la prime. Congés payés, RTT, récupération, repos, fériés,
        activité partielle et congé maternité ou paternité ne font rien perdre. Une semaine se paie dans le mois
        de son dimanche.
      </p>
      {periode === 'mois' && (
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <Checkbox
            checked={conditions.proratiser_temps_partiel !== false}
            onCheckedChange={(v) => onChange({ ...conditions, proratiser_temps_partiel: Boolean(v) })}
          />
          À temps partiel, au prorata de la durée du contrat (mi-temps : la moitié)
        </label>
      )}
    </div>
  );
}
