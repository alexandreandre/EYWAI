export type AccountingProviderKey =
  | 'manual'
  | 'cegid_quadra'
  | 'sage'
  | 'pennylane'
  | 'generic_sftp';

export type AccountingProviderMeta = {
  key: AccountingProviderKey;
  name: string;
  logoKey: string;
  brandColor: string;
  description: string;
  docUrl?: string;
};

export const ACCOUNTING_PROVIDER_CATALOG: Record<AccountingProviderKey, AccountingProviderMeta> = {
  manual: {
    key: 'manual',
    name: 'Manuel',
    logoKey: 'manual',
    brandColor: '#64748b',
    description: 'Téléchargez les fichiers et importez-les dans votre logiciel comptable.',
  },
  cegid_quadra: {
    key: 'cegid_quadra',
    name: 'Cegid / Quadra',
    logoKey: 'cegid',
    brandColor: '#003DA5',
    description: 'Transmission automatique des écritures FEC vers Cegid Loop (Quadra).',
    docUrl: 'https://developers.cegid.com/docreference/BusinessUnits/Loop-Api-Management-Docs/GetStart.html',
  },
  sage: {
    key: 'sage',
    name: 'Sage',
    logoKey: 'sage',
    brandColor: '#00DC00',
    description: 'Connecteur Sage — bientôt disponible.',
    docUrl: 'https://www.sage.com/fr-fr/',
  },
  pennylane: {
    key: 'pennylane',
    name: 'Pennylane',
    logoKey: 'pennylane',
    brandColor: '#1B4DFF',
    description: 'Connecteur Pennylane — bientôt disponible.',
    docUrl: 'https://www.pennylane.com/',
  },
  generic_sftp: {
    key: 'generic_sftp',
    name: 'Dépôt SFTP',
    logoKey: 'generic',
    brandColor: '#64748b',
    description: 'Dépôt automatique sur serveur SFTP — bientôt disponible.',
  },
};

export function getProviderMeta(key: string): AccountingProviderMeta {
  return (
    ACCOUNTING_PROVIDER_CATALOG[key as AccountingProviderKey] ??
    ACCOUNTING_PROVIDER_CATALOG.manual
  );
}
