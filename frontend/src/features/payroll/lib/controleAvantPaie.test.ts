import { describe, expect, it } from 'vitest';
import type { PreflightAnomaly } from '@/api/payrollPreflight';
import {
  etatVerrouPaie,
  MESSAGE_GENERER_SANS_CONTROLE,
  messageConfirmationGeneration,
} from './controleAvantPaie';

function anomalie(partiel: Partial<PreflightAnomaly>): PreflightAnomaly {
  return {
    id: 'a1',
    employee_id: 'e1',
    employee_name: 'Salarié A',
    type: 'ecart_heures',
    severity: 'bloquant',
    status: 'a_traiter',
    is_forfait_jour: false,
    detail_jours: [],
    conflict_days: [],
    ...partiel,
  };
}

describe('messageConfirmationGeneration', () => {
  it('ne demande rien quand le contrôle répond sans anomalie bloquante ouverte', () => {
    expect(messageConfirmationGeneration({ controleEnErreur: false, anomalies: [] })).toBeNull();
    expect(
      messageConfirmationGeneration({
        controleEnErreur: false,
        anomalies: [
          anomalie({ severity: 'a_verifier' }),
          anomalie({ id: 'a2', status: 'resolu' }),
        ],
      }),
    ).toBeNull();
  });

  it('garde le message d’avant pour des anomalies bloquantes ouvertes', () => {
    expect(
      messageConfirmationGeneration({
        controleEnErreur: false,
        anomalies: [anomalie({}), anomalie({ id: 'a2' })],
      }),
    ).toBe('2 anomalie(s) bloquante(s) ouverte(s). Générer quand même les bulletins ?');
  });

  it('demande une confirmation explicite quand le contrôle est en panne', () => {
    expect(messageConfirmationGeneration({ controleEnErreur: true, anomalies: [] })).toBe(
      MESSAGE_GENERER_SANS_CONTROLE,
    );
    expect(MESSAGE_GENERER_SANS_CONTROLE).toBe(
      "Le contrôle avant paie n'a pas pu être vérifié. Générer quand même ?",
    );
  });

  it('la panne l’emporte sur des anomalies gardées d’une lecture précédente', () => {
    expect(
      messageConfirmationGeneration({ controleEnErreur: true, anomalies: [anomalie({})] }),
    ).toBe(MESSAGE_GENERER_SANS_CONTROLE);
  });
});

describe('etatVerrouPaie', () => {
  it('s’ouvre quand toutes les étapes sont à zéro et que tout a répondu', () => {
    expect(etatVerrouPaie({ enChargement: false, enErreur: false, compteurs: [0, 0, 0] })).toBe(
      'ouvert',
    );
  });

  it('reste fermé tant qu’une étape a des actions à traiter', () => {
    expect(etatVerrouPaie({ enChargement: false, enErreur: false, compteurs: [0, 2, 0] })).toBe(
      'etapes_en_attente',
    );
  });

  it('ne s’ouvre pas en silence quand un compteur est en erreur', () => {
    expect(etatVerrouPaie({ enChargement: false, enErreur: true, compteurs: [0, 0, 0] })).toBe(
      'indisponible',
    );
  });

  it('signale la panne avant les étapes en attente', () => {
    expect(etatVerrouPaie({ enChargement: false, enErreur: true, compteurs: [3, 0, 0] })).toBe(
      'indisponible',
    );
  });

  it('attend la fin du chargement, y compris pendant un nouvel essai', () => {
    expect(etatVerrouPaie({ enChargement: true, enErreur: false, compteurs: [0, 0, 0] })).toBe(
      'verification',
    );
    expect(etatVerrouPaie({ enChargement: true, enErreur: true, compteurs: [0, 0, 0] })).toBe(
      'verification',
    );
  });
});
