const STORAGE_PREFIX = 'eywai-company-setup-validated:';

export function loadValidatedSetupSteps(companyId: string): Set<string> {
  if (!companyId) return new Set();
  try {
    const raw = sessionStorage.getItem(`${STORAGE_PREFIX}${companyId}`);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((s): s is string => typeof s === 'string'));
  } catch {
    return new Set();
  }
}

export function saveValidatedSetupSteps(companyId: string, steps: ReadonlySet<string>): void {
  if (!companyId) return;
  try {
    const toSave = [...steps].filter((s) => s !== 'intro');
    sessionStorage.setItem(`${STORAGE_PREFIX}${companyId}`, JSON.stringify(toSave));
  } catch {
    /* quota / private mode */
  }
}

/** L'étape Préparation est validée dès qu'une filiale est sélectionnée. */
export function isSetupStepValidated(
  stepId: string,
  companyId: string,
  validatedSteps: ReadonlySet<string>,
): boolean {
  if (stepId === 'intro') return Boolean(companyId);
  return validatedSteps.has(stepId);
}

export function isSetupStepManuallyValidatable(stepId: string): boolean {
  return stepId !== 'intro' && stepId !== 'summary';
}
