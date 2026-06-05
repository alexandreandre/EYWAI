export function aiFillErrorMessage(error: unknown): string {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail ===
      'string'
  ) {
    return (error as { response: { data: { detail: string } } }).response.data.detail;
  }
  return "L'analyse a échoué. Réessayez.";
}
