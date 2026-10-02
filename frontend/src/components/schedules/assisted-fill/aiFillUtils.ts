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

/**
 * Message à afficher pour une erreur d'import : la phrase du serveur d'abord
 * (une erreur réseau est aussi une `Error`, dont le message technique « Request
 * failed with status code 409 » masquait « déjà importé »), sinon le message
 * d'une erreur locale.
 */
export function messageDeLErreur(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } } | null)?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (error instanceof Error && error.message) return error.message;
  return aiFillErrorMessage(error);
}
