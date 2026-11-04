/**
 * Bilan de « Valider la semaine » de la badgeuse : chaque jour est validé à part,
 * un échec ne doit plus passer en silence (audit R1, geste 8 : `try/finally`
 * sans `catch`, aucun message).
 */
export function bilanValidationSemaine(
  resultats: ReadonlyArray<PromiseSettledResult<unknown>>,
  jours: readonly string[],
): { reussi: boolean; message: string; premierEchec?: unknown } {
  const echecs = resultats
    .map((r, i) => ({ r, jour: jours[i] }))
    .filter((x): x is { r: PromiseRejectedResult; jour: string } => x.r.status === 'rejected');
  const total = resultats.length;
  if (echecs.length === 0) {
    return { reussi: true, message: `Semaine validée : ${total} jour${total > 1 ? 's' : ''}.` };
  }
  const n = echecs.length;
  const dates = echecs.map((e) => `${e.jour.slice(8, 10)}/${e.jour.slice(5, 7)}`).join(', ');
  return {
    reussi: false,
    message: `${n} jour${n > 1 ? 's' : ''} sur ${total} non validé${n > 1 ? 's' : ''} (${dates}).`,
    premierEchec: echecs[0].r.reason,
  };
}
