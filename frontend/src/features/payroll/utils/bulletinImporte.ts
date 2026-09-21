/** Un bulletin repris de l'ancien logiciel à la bascule ne se modifie pas, ne se
 * supprime pas et ne se recalcule pas : il ne pourrait pas être recalculé. */
export const MOTIF_BULLETIN_IMPORTE =
  'Bulletin repris de l’ancien logiciel : il ne se modifie pas, ne se supprime pas et ne se recalcule pas.';

export function estBulletinImporte(payslip: { origine?: string | null } | null | undefined): boolean {
  return payslip?.origine === 'importe';
}
