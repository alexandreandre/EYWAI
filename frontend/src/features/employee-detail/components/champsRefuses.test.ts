import { describe, expect, it } from 'vitest';
import { employeeProfileEditSchema } from './employeeProfileEditSchema';
import { buildDefaultValues } from './employeeProfileFormUtils';
import { champsRefuses } from './champsRefuses';
import type { Employee } from '@/features/employee-detail/types';

describe('fiche avec une ligne de prévoyance sans forfait social', () => {
  it("s'enregistre : le montant absent vaut 0", () => {
    const valeurs = buildDefaultValues({
      id: 'e1',
      first_name: 'Jeanne',
      last_name: 'Essai',
      statut: 'Non-Cadre',
      contract_type: 'CDI',
      specificites_paie: {
        prevoyance: { adhesion: true, lignes_specifiques: [{ id: 'p1', libelle: 'Prévoyance QA', salarial: 1.2, patronal: 2.4 }] },
      },
    } as unknown as Employee);
    const ligne = valeurs.specificites_paie.prevoyance.lignes_specifiques?.[0];
    expect(ligne?.forfait_social).toBe(0);
    const resultat = employeeProfileEditSchema.safeParse(valeurs);
    const surLaPrevoyance = resultat.success
      ? []
      : resultat.error.issues.filter((i) => i.path.join('.').startsWith('specificites_paie.prevoyance'));
    expect(surLaPrevoyance).toEqual([]);
  });
});

describe('fiche sans e-mail', () => {
  const fiche = {
    id: 'e2',
    first_name: 'Jeanne',
    last_name: 'Essai',
    email: null,
    statut: 'Non-Cadre',
    contract_type: 'CDI',
    specificites_paie: {},
  } as unknown as Employee;

  it("se complète sans inventer d'e-mail, et l'e-mail n'est pas envoyé", async () => {
    const { buildUpdatePayload } = await import('./employeeProfileFormUtils');
    const valeurs = buildDefaultValues(fiche);
    const resultat = employeeProfileEditSchema.safeParse(valeurs);
    const surEmail = resultat.success ? [] : resultat.error.issues.filter((i) => i.path[0] === 'email');
    expect(surEmail).toEqual([]);
    expect('email' in JSON.parse(JSON.stringify(buildUpdatePayload(valeurs, fiche)))).toBe(false);
  });

  it('un e-mail saisi doit être juste', () => {
    const resultat = employeeProfileEditSchema.safeParse({ ...buildDefaultValues(fiche), email: 'jeanne@' });
    expect(resultat.success ? [] : resultat.error.issues.filter((i) => i.path[0] === 'email').map((i) => i.message)).toEqual([
      'Adresse e-mail invalide.',
    ]);
  });
});

describe('champsRefuses', () => {
  it('nomme les champs refusés, même masqués', () => {
    expect(
      champsRefuses({
        specificites_paie: { prevoyance: { lignes_specifiques: [{ forfait_social: { message: 'Expected number, received nan' } }] } },
        residence_permit_expiry_date: { message: "Date d'expiration du titre de séjour requise." },
      })
    ).toEqual([
      'Prévoyance : Expected number, received nan',
      "Titre de séjour : Date d'expiration du titre de séjour requise.",
    ]);
  });
});
