export const WORK_TIME_TABS = ['contingent', 'compte-heures'] as const;

export type WorkTimeTab = (typeof WORK_TIME_TABS)[number];

export const DEFAULT_WORK_TIME_TAB: WorkTimeTab = 'contingent';

export function isWorkTimeTab(value: string | null | undefined): value is WorkTimeTab {
  return WORK_TIME_TABS.includes(value as WorkTimeTab);
}

export function parseWorkTimeTab(value: string | null | undefined): WorkTimeTab {
  if (isWorkTimeTab(value)) return value;
  return DEFAULT_WORK_TIME_TAB;
}

export function buildWorkTimeSearchParams(options: {
  tab?: WorkTimeTab;
  employee?: string | null;
}): URLSearchParams {
  const params = new URLSearchParams();
  const tab = options.tab ?? DEFAULT_WORK_TIME_TAB;
  if (tab !== DEFAULT_WORK_TIME_TAB) {
    params.set('tab', tab);
  }
  if (options.employee) {
    params.set('employee', options.employee);
  }
  return params;
}

export function workTimeHubPath(options?: {
  tab?: WorkTimeTab;
  employee?: string | null;
}): string {
  const params = buildWorkTimeSearchParams(options ?? {});
  const query = params.toString();
  return query ? `/suivi-temps-travail?${query}` : '/suivi-temps-travail';
}
