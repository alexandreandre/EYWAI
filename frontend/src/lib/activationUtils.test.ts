import { describe, expect, it } from 'vitest';

import {
  emailsMatch,
  getInvitationDisabledReason,
  getPasswordChecks,
  getPasswordStrength,
  isEmployeeInvitable,
  isPasswordAcceptable,
  raisonActivationImpossible,
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

describe('emailsMatch', () => {
  it('identifie la même adresse sans tenir compte de la casse ni des espaces', () => {
    expect(emailsMatch('  GMartel@maji-invest.fr ', 'gmartel@maji-invest.fr')).toBe(
      true,
    );
    expect(emailsMatch('vdupont@maji-invest.fr', 'gmartel@maji-invest.fr')).toBe(
      false,
    );
    expect(emailsMatch('', 'gmartel@maji-invest.fr')).toBe(false);
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

describe('raisonActivationImpossible — le bouton grisé dit pourquoi', () => {
  it('rien à dire tant que rien n’est saisi', () => {
    expect(raisonActivationImpossible('', '')).toBeNull();
  });

  it('un mot de passe trop faible renvoie à la jauge', () => {
    expect(raisonActivationImpossible('abc', '')).toBe(
      'Le mot de passe doit contenir au moins 8 caractères, dont une majuscule, une minuscule et un chiffre.',
    );
  });

  it('attend la confirmation', () => {
    expect(raisonActivationImpossible('Martine2026', '')).toBe('Confirmez le mot de passe.');
  });

  it('dit que les deux mots de passe diffèrent', () => {
    expect(raisonActivationImpossible('Martine2026', 'Martine2025')).toBe(
      'Les deux mots de passe ne sont pas identiques.',
    );
  });

  it('se tait quand tout est bon', () => {
    expect(raisonActivationImpossible('Martine2026', 'Martine2026')).toBeNull();
  });
});
