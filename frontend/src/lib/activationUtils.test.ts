import { describe, expect, it } from 'vitest';

import {
  getInvitationDisabledReason,
  getPasswordChecks,
  getPasswordStrength,
  isEmployeeInvitable,
  isPasswordAcceptable,
} from './activationUtils';

describe('isEmployeeInvitable', () => {
  it('refuse une adresse vide ou absente', () => {
    expect(isEmployeeInvitable(null)).toBe(false);
    expect(isEmployeeInvitable(undefined)).toBe(false);
    expect(isEmployeeInvitable('')).toBe(false);
    expect(isEmployeeInvitable('   ')).toBe(false);
  });

  it('refuse les adresses fabriquées par la plateforme', () => {
    expect(isEmployeeInvitable('x.dupont.dsn-import.local')).toBe(false);
    expect(isEmployeeInvitable('import.jdupont@dsn-import.eywai.fr')).toBe(false);
    expect(isEmployeeInvitable('jdupont@eywai.access.local')).toBe(false);
  });

  it('accepte une adresse réelle', () => {
    expect(isEmployeeInvitable('jean.dupont@exemple.fr')).toBe(true);
  });
});

describe('getInvitationDisabledReason', () => {
  it('explique une adresse manquante', () => {
    expect(getInvitationDisabledReason(null)).toMatch(/adresse e-mail/i);
  });

  it('explique une adresse fabriquée', () => {
    expect(
      getInvitationDisabledReason('import.jdupont@dsn-import.eywai.fr'),
    ).toMatch(/adresse e-mail/i);
  });

  it('ne donne aucune raison pour une adresse réelle', () => {
    expect(getInvitationDisabledReason('jean.dupont@exemple.fr')).toBeNull();
  });
});

describe('getPasswordChecks / isPasswordAcceptable', () => {
  it('exige 8 caractères, majuscule, minuscule et chiffre (règle du reset)', () => {
    const checks = getPasswordChecks('MotDePasse1');
    expect(checks).toEqual({
      longueur: true,
      majuscule: true,
      minuscule: true,
      chiffre: true,
    });
    expect(isPasswordAcceptable('MotDePasse1')).toBe(true);
  });

  it('refuse un mot de passe trop court ou incomplet', () => {
    expect(getPasswordChecks('Abc1').longueur).toBe(false);
    expect(getPasswordChecks('motdepasse1').majuscule).toBe(false);
    expect(getPasswordChecks('MOTDEPASSE1').minuscule).toBe(false);
    expect(getPasswordChecks('MotDePasse').chiffre).toBe(false);
    expect(isPasswordAcceptable('court')).toBe(false);
  });
});

describe('getPasswordStrength', () => {
  it('compte les critères remplis (0 à 4) pour la jauge', () => {
    expect(getPasswordStrength('')).toBe(0);
    expect(getPasswordStrength('abc')).toBe(1); // minuscule seule
    expect(getPasswordStrength('abcdefgh')).toBe(2); // + longueur
    expect(getPasswordStrength('Abcdefgh')).toBe(3); // + majuscule
    expect(getPasswordStrength('Abcdefg1')).toBe(4); // + chiffre
  });
});
