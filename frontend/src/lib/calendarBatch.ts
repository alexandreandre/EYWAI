import { runWithConcurrency } from './concurrency';

export class CalendarBatchError extends Error {
  constructor(public failure: unknown, public completed: number, public total: number) {
    super(`${completed} calendrier(s) confirmé(s) sur ${total}.`);
    this.name = 'CalendarBatchError';
  }
}

/** Les écritures déjà lancées sont toutes terminées avant de rendre un échec. */
export async function runCalendarBatch<T>(tasks: (() => Promise<T>)[]): Promise<T[]> {
  const outcomes = await runWithConcurrency(tasks.map((task) => async () => {
    try { return { ok: true as const, value: await task() }; }
    catch (error) { return { ok: false as const, error }; }
  }), 5);
  const failed = outcomes.find((outcome) => !outcome.ok);
  if (failed && !failed.ok) throw new CalendarBatchError(failed.error, outcomes.filter((outcome) => outcome.ok).length, outcomes.length);
  return outcomes.map((outcome) => {
    if (!outcome.ok) throw outcome.error;
    return outcome.value;
  });
}
