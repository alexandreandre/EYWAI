export type ClassifiedSourceLink = {
  url: string;
  label: string;
};

export type ClassifiedRateSources = {
  official: ClassifiedSourceLink[];
  complementary: ClassifiedSourceLink[];
};

const LEGISOCIAL_HOST = 'legisocial.fr';

const OFFICIAL_HOST_SUFFIXES = [
  'gouv.fr',
  'urssaf.fr',
  'ameli.fr',
  'service-public.fr',
  'agirc-arrco.fr',
  'securite-sociale.fr',
  'unedic.org',
  'francetravail.fr',
  'net-entreprises.fr',
  'cnav.fr',
  'lassuranceretraite.fr',
  'assurance-retraite.fr',
] as const;

function parseHost(url: string): string | null {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return null;
  }
}

function parsePath(url: string): string {
  try {
    return new URL(url).pathname.toLowerCase();
  } catch {
    return '';
  }
}

export function isLegisocialSourceUrl(url: string): boolean {
  const host = parseHost(url);
  if (!host) return false;
  return host === LEGISOCIAL_HOST || host.endsWith(`.${LEGISOCIAL_HOST}`);
}

export function isOfficialSourceUrl(url: string): boolean {
  if (isLegisocialSourceUrl(url)) return false;
  const host = parseHost(url);
  if (!host) return false;
  return OFFICIAL_HOST_SUFFIXES.some(
    (suffix) => host === suffix || host.endsWith(`.${suffix}`),
  );
}

/** Libellé court pour une URL publique de l’État ou d’un opérateur de sécurité sociale. */
export function getOfficialSourceLabel(url: string): string {
  const host = parseHost(url) ?? '';
  const path = parsePath(url);

  if (host.includes('urssaf.fr')) {
    if (path.includes('montant-smic') || path.includes('augmentation-smic')) return 'URSSAF — SMIC';
    if (path.includes('plafonds-securite')) return 'URSSAF — Plafonds SS';
    if (path.includes('frais-professionnels')) return 'URSSAF — Frais professionnels';
    if (path.includes('avantages-en-nature')) return 'URSSAF — Avantages en nature';
    if (path.includes('formation-professionnelle')) return 'URSSAF — Formation pro.';
    if (path.includes('taux-cotisations')) return 'URSSAF — Cotisations privées';
    if (path.includes('taux-baremes')) return 'URSSAF — Taux et barèmes';
    if (host.includes('declaration')) return 'URSSAF — Tables de référence';
    return 'URSSAF';
  }

  if (host.includes('ameli.fr')) {
    if (path.includes('indemnites-journalieres')) return 'Ameli.fr — Plafonds IJSS';
    return 'Ameli.fr';
  }

  if (host.includes('service-public.fr') || host.includes('service-public.gouv.fr')) {
    if (host.includes('entreprendre')) {
      if (path.includes('f78') || path.includes('f33666') || path.includes('prevoyance')) {
        return 'Service-Public Entreprises — Prévoyance';
      }
      return 'Service-Public Entreprises';
    }
    if (path.includes('f14686')) return 'Service-Public.fr — Barème km';
    if (path.includes('f33666')) return 'Service-Public.fr — Prévoyance';
    return 'Service-Public.fr';
  }

  if (host.includes('boss.gouv.fr')) {
    if (path.includes('frais-professionnels')) return 'BOSS — Frais professionnels';
    if (path.includes('avantages-en-nature')) return 'BOSS — Avantages en nature';
    return 'BOSS';
  }

  if (host.includes('securite-sociale.fr')) return 'Sécurité sociale';

  if (host.includes('unedic.org')) return 'Unédic';

  if (host.includes('francetravail.fr')) return 'France Travail';

  if (host.includes('travail-emploi.gouv.fr') || host.includes('travail.gouv.fr')) {
    if (path.includes('heures-supplementaires')) return 'Ministère du Travail — Heures sup.';
    return 'Ministère du Travail';
  }

  if (host.includes('legifrance.gouv.fr')) return 'Légifrance';

  if (host.includes('impots.gouv.fr') || host.includes('bofip')) {
    if (path.includes('pas') || path.includes('prelevement')) return 'DGFiP — Prélèvement à la source';
    return 'DGFiP / BOFiP';
  }

  if (host.includes('agirc-arrco.fr')) return 'AGIRC ARRCO';

  return 'Source officielle';
}

/** Libellé pour une URL LegiSocial (recoupement éditorial, non officielle). */
export function getComplementarySourceLabel(url: string): string {
  if (!isLegisocialSourceUrl(url)) return 'Référence complémentaire';

  const path = parsePath(url);
  if (path.includes('montant-smic') || path.includes('/smic')) return 'LegiSocial — SMIC';
  if (path.includes('plafond-securite')) return 'LegiSocial — PSS';
  if (path.includes('indemnites-journalieres')) return 'LegiSocial — IJSS';
  if (path.includes('taux-cotisations')) return 'LegiSocial — Cotisations';
  if (path.includes('allocations-forfaitaires') || path.includes('frais-professionnels')) {
    return 'LegiSocial — Frais pro';
  }
  if (path.includes('avantage-en-nature-repas')) return 'LegiSocial — Repas';
  if (path.includes('avantage-en-nature-logement')) return 'LegiSocial — Logement';
  if (path.includes('cotisations-agirc-arrco')) return 'LegiSocial — AGIRC ARRCO';
  if (path.includes('kilometrique') || path.includes('barème')) return 'LegiSocial — Barème km';
  return 'LegiSocial';
}

export function classifyRateSourceLinks(
  links: string[] | null | undefined,
): ClassifiedRateSources {
  const official: ClassifiedSourceLink[] = [];
  const complementary: ClassifiedSourceLink[] = [];
  const seenOfficial = new Set<string>();
  const seenComplementary = new Set<string>();

  for (const raw of links ?? []) {
    const url = raw?.trim();
    if (!url) continue;

    if (isLegisocialSourceUrl(url)) {
      if (seenComplementary.has(url)) continue;
      seenComplementary.add(url);
      complementary.push({ url, label: getComplementarySourceLabel(url) });
      continue;
    }

    if (isOfficialSourceUrl(url)) {
      if (seenOfficial.has(url)) continue;
      seenOfficial.add(url);
      official.push({ url, label: getOfficialSourceLabel(url) });
      continue;
    }

    if (seenComplementary.has(url)) continue;
    seenComplementary.add(url);
    complementary.push({ url, label: getComplementarySourceLabel(url) });
  }

  return { official, complementary };
}
