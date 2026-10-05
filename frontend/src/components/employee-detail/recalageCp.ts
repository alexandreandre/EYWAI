/**
 * Recalage RH des congés payés N-1 et N à la fin d'un mois écoulé.
 *
 * Le serveur l'enregistre comme une reprise datée (même mécanique que l'import
 * d'un bulletin) : le pied de bulletin et l'indemnité de départ la relisent.
 */
import type { CpRecalageResponse } from '@/api/leaveSettings';

const LIGNES_CP: readonly string[] = [
  'Congés Payés (période précédente)',
  'Congés Payés (période en cours)',
  'Congés Payés',
];

/** La ligne du tableau des soldes ouvre-t-elle le recalage des CP ? */
export function estLigneCp(type: string): boolean {
  return LIGNES_CP.includes(type);
}

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

export interface MoisRecalage {
  year: number;
  month: number;
  /** « septembre 2026 » */
  libelle: string;
  /** « 30/09/2026 » : la date à laquelle les soldes saisis s'appliquent. */
  dateFin: string;
  /** « 2026-09 » : clé de la liste déroulante. */
  valeur: string;
}

function deuxChiffres(n: number): string {
  return String(n).padStart(2, '0');
}

/** Les mois écoulés (dernier jour passé ou aujourd'hui), le plus récent en premier. */
export function moisDeRecalage(aujourdhui: Date, nombre = 12): MoisRecalage[] {
  const jour = new Date(aujourdhui.getFullYear(), aujourdhui.getMonth(), aujourdhui.getDate());
  const mois: MoisRecalage[] = [];
  let annee = jour.getFullYear();
  let m = jour.getMonth() + 1;
  while (mois.length < nombre) {
    const dernierJour = new Date(annee, m, 0);
    if (dernierJour <= jour) {
      mois.push({
        year: annee,
        month: m,
        libelle: `${MOIS[m - 1]} ${annee}`,
        dateFin: `${deuxChiffres(dernierJour.getDate())}/${deuxChiffres(m)}/${annee}`,
        valeur: `${annee}-${deuxChiffres(m)}`,
      });
    }
    m -= 1;
    if (m === 0) {
      m = 12;
      annee -= 1;
    }
  }
  return mois;
}

/** « 12,5 » ou « 12.5 » → 12,5 ; vide ou illisible → null. */
export function lireJours(saisie: string): number | null {
  const texte = saisie.trim().replace(',', '.');
  if (!texte) return null;
  const valeur = Number(texte);
  return Number.isFinite(valeur) ? valeur : null;
}

export function erreursRecalageCp(saisie: { n1: string; n: string; note: string }): string[] {
  const erreurs: string[] = [];
  if (lireJours(saisie.n1) === null) erreurs.push('Saisissez le solde CP N-1 (0 s’il est vide).');
  if (lireJours(saisie.n) === null) erreurs.push('Saisissez le solde CP N (0 s’il est vide).');
  if (!saisie.note.trim()) {
    erreurs.push('Dites en commentaire pourquoi vous recalez (il reste dans l’historique).');
  }
  return erreurs;
}

function jours(valeur: number): string {
  return `${valeur.toFixed(2).replace('.', ',')} j`;
}

function dateFr(iso: string): string {
  const [annee, mois, jour] = iso.slice(0, 10).split('-');
  return `${jour}/${mois}/${annee}`;
}

const A_RECALCULER = 'Les bulletins concernés passent « À recalculer ».';

/** Ce que le bulletin du mois imprime après le recalage, relu par le serveur. */
export function messageRecalageCp(reponse: CpRecalageResponse): string {
  const date = dateFr(reponse.date_reference);
  if (reponse.cp_n1_solde == null || reponse.cp_n_solde == null) {
    return (
      `Soldes enregistrés au ${date}. Le bulletin de ce mois n’imprime pas de ` +
      `compteur de congés. ${A_RECALCULER}`
    );
  }
  return (
    `Au ${date}, le bulletin imprime CP N-1 ${jours(reponse.cp_n1_solde)} et ` +
    `CP N ${jours(reponse.cp_n_solde)}. ${A_RECALCULER}`
  );
}
