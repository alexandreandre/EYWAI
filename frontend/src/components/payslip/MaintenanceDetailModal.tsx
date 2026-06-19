/**
 * Modal explicative — détail calcul maintien de salaire (bulletin).
 */

import type { MaintenancePreview } from '@/api/absences';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

function alertBannerClass(text: string): string {
  const t = text.toLowerCase();
  if (t.includes('non calculables')) {
    return 'rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive';
  }
  if (t.includes('ijss versées directement')) {
    return 'rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-950 dark:bg-blue-950/30 dark:text-blue-100';
  }
  if (
    t.includes('insuffisante') ||
    t.includes('plafonné') ||
    t.includes('prévoyance relais') ||
    t.includes('conventionnelle moins favorable')
  ) {
    return 'rounded-md border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-950 dark:bg-orange-950/20 dark:text-orange-100';
  }
  return 'rounded-md border border-muted bg-muted/40 px-3 py-2 text-sm';
}

const eur = (n: number | null | undefined) =>
  new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 2,
  }).format(Number(n ?? 0));

const pct = (t: number | null | undefined) =>
  `${(Number(t ?? 0) * 100).toFixed(1)} %`;

export interface MaintenanceDetailModalProps {
  open: boolean;
  onClose: () => void;
  maintien: MaintenancePreview;
}

export function MaintenanceDetailModal({
  open,
  onClose,
  maintien,
}: MaintenanceDetailModalProps) {
  const carence = maintien.carence;
  const ijss = maintien.ijss;
  const m = maintien.maintien;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Détail du calcul maintien de salaire</DialogTitle>
        </DialogHeader>

        <div className="space-y-5 text-sm">
          <section className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Qualification
            </h3>
            <p>
              <span className="text-muted-foreground">Type d&apos;arrêt : </span>
              <span className="font-medium">{maintien.type_arret}</span>
            </p>
            <p>Carence SS : {carence.carence_ss_jours} jour(s)</p>
            <p>Carence employeur : {carence.carence_employeur_jours} jour(s)</p>
            {carence.est_continuite ? (
              <Badge className="bg-emerald-600 hover:bg-emerald-600">
                Continuité — pas de nouvelle carence
              </Badge>
            ) : null}
          </section>

          <section className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              IJSS
            </h3>
            <p>Salaire journalier de base : {eur(ijss.salaire_journalier_base)}</p>
            <p>Taux IJSS appliqué : {pct(ijss.taux_applique)}</p>
            <p>Nombre de jours indemnisés : {ijss.nb_jours_indemnises}</p>
            <p>IJSS estimées : {eur(ijss.ijss_theorique)}</p>
          </section>

          <section className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Maintien employeur
            </h3>
            {!m.maintien_applicable && m.motif_non_maintien ? (
              <div className="rounded-md border border-orange-200 bg-orange-50 px-3 py-2 text-orange-950 dark:bg-orange-950/20 dark:text-orange-100">
                {m.motif_non_maintien}
              </div>
            ) : (
              <>
                <p>Taux de maintien : {pct(m.taux_maintien)}</p>
                <p>Maintien cible : {eur(m.maintien_cible)}</p>
                {maintien.subrogation_active ? (
                  <p>IJSS déduites : {eur(ijss.ijss_theorique)}</p>
                ) : null}
                <p>Maintien versé : {eur(m.maintien_verse)}</p>
                <p>Complément employeur : {eur(m.complement_employeur ?? 0)}</p>
              </>
            )}
          </section>

          {maintien.prevoyance &&
          (maintien.prevoyance.prevoyance_declenchee ||
            (maintien.prevoyance.montant ?? 0) > 0 ||
            maintien.prevoyance.seuil_jours != null) ? (
            <section className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Prévoyance
              </h3>
              {maintien.prevoyance.seuil_jours != null ? (
                <p>
                  Seuil de déclenchement : {maintien.prevoyance.seuil_jours} jour(s)
                  d&apos;arrêt
                </p>
              ) : null}
              {maintien.prevoyance.franchise_jours != null ? (
                <p>Franchise : {maintien.prevoyance.franchise_jours} jour(s)</p>
              ) : null}
              {maintien.prevoyance.taux_cible != null ? (
                <p>Taux garanti : {pct(maintien.prevoyance.taux_cible)}</p>
              ) : null}
              {(maintien.prevoyance.montant ?? 0) > 0 ? (
                <>
                  <p>Jours pris en charge : {maintien.prevoyance.nb_jours ?? 0}</p>
                  <p>
                    Complément prévoyance estimé :{' '}
                    {eur(maintien.prevoyance.montant)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Versé par l&apos;organisme assureur, hors paie employeur.
                  </p>
                </>
              ) : maintien.prevoyance.prevoyance_declenchee ? (
                <Badge className="bg-orange-500 hover:bg-orange-500">
                  Prévoyance relais à déclencher
                </Badge>
              ) : null}
              {maintien.prevoyance.motif ? (
                <p className="text-xs text-muted-foreground">
                  {maintien.prevoyance.motif}
                </p>
              ) : null}
            </section>
          ) : null}

          <section className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Subrogation
            </h3>
            {maintien.subrogation_active ? (
              <Badge className="bg-emerald-600 hover:bg-emerald-600">
                Subrogation active — CPAM verse l&apos;employeur
              </Badge>
            ) : (
              <Badge variant="secondary">CPAM verse directement le salarié</Badge>
            )}
          </section>

          {maintien.alertes?.length ? (
            <section className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Alertes
              </h3>
              <ul className="space-y-2">
                {maintien.alertes.map((a, i) => (
                  <li key={i} className={alertBannerClass(a)}>
                    {a}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>

        <DialogFooter>
          <Button type="button" onClick={onClose}>
            Fermer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
