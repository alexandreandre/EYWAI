import { describe, expect, it } from 'vitest';
import { TRANSMISSION_MODE_LABELS } from '@/api/netEntreprises';
import { MODES_DEPOT_PROPOSES, optionModeDepot, optionsModeDepot } from './modesDepot';

const toutLeTexte = (o: { label: string; hint: string }) => `${o.label} ${o.hint}`;

describe('modes de dépôt de la DSN', () => {
  it('ne propose plus le certificat, et ne parle de certificat nulle part', () => {
    expect(MODES_DEPOT_PROPOSES.map((o) => o.value)).not.toContain('api_certificat');
    for (const o of optionsModeDepot('api_certificat')) {
      expect(toutLeTexte(o).toLowerCase()).not.toContain('certificat');
    }
    for (const libelle of Object.values(TRANSMISSION_MODE_LABELS)) {
      expect(libelle.toLowerCase()).not.toContain('certificat');
    }
  });

  it('seul le dépôt manuel se choisit : l’envoi direct n’est pas branché', () => {
    const selectionnables = MODES_DEPOT_PROPOSES.filter((o) => o.selectionnable).map((o) => o.value);
    expect(selectionnables).toEqual(['manual']);
    expect(optionModeDepot('api_declarant').hint).toContain('pas encore branché');
  });

  it('un ancien réglage « certificat » s’affiche lisiblement au lieu de laisser la liste muette', () => {
    const options = optionsModeDepot('api_certificat');
    const ancien = options.find((o) => o.value === 'api_certificat');
    expect(ancien?.label).toBe('Envoi par l’API (ancien réglage, inactif)');
    expect(ancien?.selectionnable).toBe(false);
    expect(optionModeDepot('api_certificat').hint).toContain('à déposer à la main');
  });

  it('un réglage inconnu s’affiche aussi, sans planter', () => {
    expect(optionModeDepot('autre_chose').label).toBe('Réglage inconnu (autre_chose)');
    expect(optionsModeDepot('')).toHaveLength(MODES_DEPOT_PROPOSES.length + 1);
  });

  it('un mode proposé n’est pas ajouté deux fois', () => {
    expect(optionsModeDepot('manual')).toHaveLength(MODES_DEPOT_PROPOSES.length);
    expect(optionsModeDepot('api_declarant')).toHaveLength(MODES_DEPOT_PROPOSES.length);
  });
});
