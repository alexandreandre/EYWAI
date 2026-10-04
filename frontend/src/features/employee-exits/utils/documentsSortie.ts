/**
 * Les documents de sortie (solde, attestation, certificat) reprennent les
 * sommes du bulletin du mois de sortie. Tant qu'il n'existe pas, on ne les
 * génère pas : l'écran le dit et les boutons restent grisés.
 */

export const MESSAGE_GENERER_DABORD_BULLETIN =
  "Générez d'abord le bulletin de sortie";

export function documentsDeSortieGrises(
  bulletinDeSortie: { mois?: string } | null | undefined
): boolean {
  return bulletinDeSortie == null;
}

/**
 * Notes du départ qui mettent des documents générés « à revoir » : type ou date
 * de départ changés, et bulletin recalculé après leur génération (le solde de
 * tout compte et l'attestation employeur en reprennent les montants). Un
 * document régénéré après la note n'est plus à revoir.
 */
const NOTES_DE_REVUE = ['exit_type_change', 'last_working_day_change', 'bulletin_recalcule'] as const;

const LIBELLES_DOCUMENTS: Record<string, string> = {
  certificat_travail: 'Certificat de travail',
  attestation_pole_emploi: 'Attestation employeur',
  solde_tout_compte: 'Solde de tout compte',
};

type DocumentGenere = {
  document_type: string;
  document_category?: string | null;
  generated_at?: string | null;
  created_at?: string | null;
};

function instant(valeur: unknown): number {
  if (typeof valeur !== 'string') return 0;
  const t = new Date(valeur).getTime();
  return Number.isNaN(t) ? 0 : t;
}

export function documentsARevoir(
  exitNotes: Record<string, unknown> | null | undefined,
  documents: DocumentGenere[]
): string[] {
  const generes = documents.filter((doc) => doc.document_category === 'generated');
  const aRevoir: string[] = [];
  for (const cle of NOTES_DE_REVUE) {
    const note = exitNotes?.[cle] as
      | { timestamp?: unknown; generated_documents_to_review?: unknown }
      | undefined;
    const changeLe = instant(note?.timestamp);
    if (!changeLe) continue;
    const types = Array.isArray(note?.generated_documents_to_review)
      ? note.generated_documents_to_review.filter((t): t is string => typeof t === 'string')
      : [];
    for (const type of types) {
      const regenere = generes.some(
        (doc) => doc.document_type === type && instant(doc.generated_at || doc.created_at) > changeLe
      );
      if (!regenere && !aRevoir.includes(type)) aRevoir.push(type);
    }
  }
  return aRevoir;
}

export function messageDocumentsARevoir(types: string[]): string {
  const noms = types.map((type) => LIBELLES_DOCUMENTS[type] ?? type).join(', ');
  return (
    `Le départ ou un bulletin a changé après leur génération : régénérez ${noms} ` +
    'avant publication ou remise au collaborateur.'
  );
}
