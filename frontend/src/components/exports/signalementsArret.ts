// Libellés des signalements DSN d'arrêt (04) et de reprise anticipée (05).
import type { SignalementFait, SignalementLigne } from '@/api/exports';

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
  const quoi = f.nature === '05' ? 'reprise' : 'arrêt';
  return `${f.essai ? 'Essai' : 'Réel'} · ${quoi}, ${MOTIFS[f.motif] ?? f.motif} du ${jour(f.debut)} · généré le ${jour(f.genere_le)}`;
}
