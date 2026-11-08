// Libellés des signalements DSN : arrêt (04), reprise anticipée (05), fin de contrat (07).
import type { SignalementFait, SignalementLigne, SignalementsResponse } from '@/api/exports';

const MOTIFS: Record<string, string> = {
  '01': 'maladie',
  '02': 'maternité',
  '03': 'paternité',
  '04': 'accident de trajet',
  '05': 'maladie professionnelle',
  '06': 'accident du travail',
  '09': 'adoption',
};

const jour = (iso: string) => iso.split('-').reverse().join('/');

export function libelleSignalement(l: SignalementLigne): string {
  if (l.nature === '07') return `Fin de contrat le ${jour(l.debut)}`;
  const arret = `arrêt ${MOTIFS[l.motif] ?? l.motif} du ${jour(l.debut)}`;
  if (l.nature === '05' && l.date_reprise) {
    return `Reprise anticipée le ${jour(l.date_reprise)} (${arret})`;
  }
  return `A${arret.slice(1)} au ${jour(l.fin_prevue)}`;
}

export function echeance(l: SignalementLigne): { texte: string; urgent: boolean } {
  const avant = `déposer avant le ${jour(l.a_deposer_avant)}`;
  return l.en_retard
    ? { texte: `En retard : à ${avant}`, urgent: true }
    : { texte: `À ${avant}`, urgent: false };
}

export function libelleFait(f: SignalementFait): string {
  const genere = `${f.essai ? 'Essai' : 'Réel'}`;
  if (f.nature === '07') return `${genere} · fin de contrat du ${jour(f.debut)} · généré le ${jour(f.genere_le)}`;
  const quoi = f.nature === '05' ? 'reprise' : 'arrêt';
  return `${f.essai ? 'Essai' : 'Réel'} · ${quoi}, ${MOTIFS[f.motif] ?? f.motif} du ${jour(f.debut)} · généré le ${jour(f.genere_le)}`;
}

export interface StatutSignalement {
  texte: string;
  urgent: boolean;
  fait: boolean;
}

/**
 * Où en est le signalement DSN d'un arrêt, pour l'écran des absences. La DSN se
 * dépose hors de Martine : un fichier généré n'est pas la preuve d'un dépôt, et
 * le texte ne le prétend pas. Rien quand Martine n'a rien à en dire (arrêt suivi
 * par l'ancien logiciel, prolongation).
 */
export function statutSignalementDeLArret(
  arret: { employee_id: string; selected_days?: string[] | null },
  signalements: SignalementsResponse | undefined,
): StatutSignalement | null {
  const premier = [...(arret.selected_days ?? [])].sort()[0];
  if (!premier || !signalements) return null;
  const couvre = (s: { employee_id: string; debut: string; fin_prevue: string }) =>
    s.employee_id === arret.employee_id && s.debut <= premier && premier <= s.fin_prevue;

  const aFaire = signalements.a_faire.find((l) => l.nature !== '07' && couvre(l));
  if (aFaire) {
    const { texte, urgent } = echeance(aFaire);
    return {
      texte: urgent
        ? `Signalement DSN en retard : à déposer avant le ${jour(aFaire.a_deposer_avant)}`
        : `Signalement DSN ${texte.charAt(0).toLowerCase()}${texte.slice(1)}`,
      urgent,
      fait: false,
    };
  }
  const fait = signalements.faits.find((f) => !f.essai && f.nature === '04' && couvre(f));
  return fait
    ? { texte: `Signalement DSN : fichier généré le ${jour(fait.genere_le)}`, urgent: false, fait: true }
    : null;
}
