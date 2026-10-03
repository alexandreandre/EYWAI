import { describe, expect, it } from 'vitest';

import type { NewContractPreview } from '@/api/contractPeriods';
import {
  corpsDeLaRequete,
  dateAncienneteRetenue,
  erreurDuFormulaire,
  formulaireInitial,
  peutCreerUnNouveauContrat,
} from './nouveauContrat';

const APERCU: NewContractPreview = {
  possible: true,
  raison: null,
  contrat_precedent: { contract_type: 'CDD', date_debut: '2026-01-19', date_fin: '2026-05-31' },
  premier_jour_possible: '2026-06-01',
  date_anciennete: '2026-01-19',
  prerempli: {
    contract_type: 'CDD',
    duree_hebdomadaire: 39,
    salaire_mensuel: 1964.73,
    job_title: 'Opératrice polyvalente',
  },
  types: ['CDI', 'CDD', 'Apprentissage', 'Contrat de professionnalisation'],
};

const rempli = () => ({
  ...formulaireInitial(APERCU),
  dateDebut: '2026-09-01',
  dateFin: '2026-12-18',
  salaire: '2017.22',
});

describe('peutCreerUnNouveauContrat', () => {
  it('le bouton est sur la fiche d’un salarié parti', () => {
    expect(peutCreerUnNouveauContrat('parti')).toBe(true);
    expect(peutCreerUnNouveauContrat('sorti')).toBe(true);
    expect(peutCreerUnNouveauContrat('inactif')).toBe(true);
  });

  it('pas sur un salarié présent ni sur un départ en cours', () => {
    expect(peutCreerUnNouveauContrat('actif')).toBe(false);
    expect(peutCreerUnNouveauContrat('en_sortie')).toBe(false);
    expect(peutCreerUnNouveauContrat(null)).toBe(false);
  });
});

describe('formulaireInitial', () => {
  it('prérempli depuis le contrat précédent, dates et ancienneté à choisir', () => {
    expect(formulaireInitial(APERCU)).toEqual({
      dateDebut: '',
      typeContrat: 'CDD',
      dateFin: '',
      duree: '39',
      salaire: '1964.73',
      poste: 'Opératrice polyvalente',
      reprendreAnciennete: false,
    });
  });
});

describe('erreurDuFormulaire', () => {
  it('un formulaire complet passe', () => {
    expect(erreurDuFormulaire(rempli(), APERCU)).toBeNull();
  });

  it('la date de début est requise', () => {
    expect(erreurDuFormulaire({ ...rempli(), dateDebut: '' }, APERCU)).toBe(
      'Indiquez la date de début du nouveau contrat.',
    );
  });

  it('pas avant le premier jour possible', () => {
    expect(erreurDuFormulaire({ ...rempli(), dateDebut: '2026-05-20' }, APERCU)).toBe(
      'Le nouveau contrat peut commencer le 01/06/2026 au plus tôt (le précédent se termine le 31/05/2026).',
    );
  });

  it('un CDD a une date de fin', () => {
    expect(erreurDuFormulaire({ ...rempli(), dateFin: '' }, APERCU)).toBe(
      'Indiquez la date de fin du CDD.',
    );
  });

  it('la fin après le début', () => {
    expect(erreurDuFormulaire({ ...rempli(), dateFin: '2026-08-31' }, APERCU)).toBe(
      'La date de fin est avant la date de début.',
    );
  });

  it('un CDI se passe de date de fin', () => {
    expect(erreurDuFormulaire({ ...rempli(), typeContrat: 'CDI', dateFin: '' }, APERCU)).toBeNull();
  });

  it.each(['', '0', '49', 'abc'])('durée invalide « %s »', (duree) => {
    expect(erreurDuFormulaire({ ...rempli(), duree }, APERCU)).toBe(
      'Indiquez une durée hebdomadaire entre 1 et 48 heures.',
    );
  });

  it('le salaire est requis', () => {
    expect(erreurDuFormulaire({ ...rempli(), salaire: '' }, APERCU)).toBe(
      'Indiquez le salaire de base mensuel.',
    );
  });

  it('accepte une virgule décimale', () => {
    expect(erreurDuFormulaire({ ...rempli(), salaire: '2 017,22' }, APERCU)).toBeNull();
  });
});

describe('corpsDeLaRequete', () => {
  it('le corps attendu par le serveur', () => {
    expect(corpsDeLaRequete({ ...rempli(), salaire: '2 017,22' })).toEqual({
      date_debut: '2026-09-01',
      contract_type: 'CDD',
      date_fin: '2026-12-18',
      duree_hebdomadaire: 39,
      salaire_mensuel: 2017.22,
      job_title: 'Opératrice polyvalente',
      reprendre_anciennete: false,
    });
  });

  it('un CDI part sans date de fin, même si le champ garde une valeur', () => {
    const corps = corpsDeLaRequete({ ...rempli(), typeContrat: 'CDI' });
    expect(corps.date_fin).toBeNull();
  });

  it('un poste vide part vide', () => {
    expect(corpsDeLaRequete({ ...rempli(), poste: '  ' }).job_title).toBeNull();
  });
});

describe('dateAncienneteRetenue', () => {
  it('case décochée : le début du nouveau contrat', () => {
    expect(dateAncienneteRetenue(rempli(), APERCU)).toBe(
      'Date d’ancienneté retenue : 01/09/2026, le début du nouveau contrat.',
    );
  });

  it('case cochée : la date d’ancienneté du contrat précédent', () => {
    expect(dateAncienneteRetenue({ ...rempli(), reprendreAnciennete: true }, APERCU)).toBe(
      'Date d’ancienneté retenue : 19/01/2026, celle du contrat précédent.',
    );
  });

  it('sans date de début, on le dit', () => {
    expect(dateAncienneteRetenue({ ...rempli(), dateDebut: '' }, APERCU)).toBe(
      'Date d’ancienneté retenue : le début du nouveau contrat.',
    );
  });
});
