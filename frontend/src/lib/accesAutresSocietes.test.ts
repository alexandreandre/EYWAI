import { describe, expect, it } from 'vitest';
import type { AccessibleCompany } from '@/api/permissions';
import {
  listerNoms,
  messageErreurCreation,
  messageResultatAcces,
  roleParDefaut,
  rolesDonnables,
  societesProposables,
} from './accesAutresSocietes';

function societe(id: string, nom: string, roles: string[]): AccessibleCompany {
  return { company_id: id, company_name: nom, creator_role: 'admin', can_create_roles: roles };
}

const ADMIN = ['rh', 'collaborateur_rh', 'collaborateur', 'custom'];
const RH = ['collaborateur_rh', 'collaborateur', 'custom'];

describe('societesProposables', () => {
  it("écarte les sociétés où l'utilisateur a déjà accès et trie par nom", () => {
    const administrables = [
      societe('c', 'Zèbre', ADMIN),
      societe('a', 'Atelier', ADMIN),
      societe('b', 'Bureau', RH),
    ];
    const res = societesProposables(administrables, [{ company_id: 'b' }]);
    expect(res.map((s) => s.company_id)).toEqual(['a', 'c']);
  });

  it("écarte une société où l'on ne peut donner que le rôle personnalisé", () => {
    const res = societesProposables([societe('a', 'A', ['custom'])], []);
    expect(res).toEqual([]);
  });
});

describe('rolesDonnables', () => {
  it('garde les rôles communs à toutes les sociétés cochées, sans le personnalisé', () => {
    expect(rolesDonnables([societe('a', 'A', ADMIN)])).toEqual([
      'rh',
      'collaborateur_rh',
      'collaborateur',
    ]);
    expect(rolesDonnables([societe('a', 'A', ADMIN), societe('b', 'B', RH)])).toEqual([
      'collaborateur_rh',
      'collaborateur',
    ]);
  });

  it('ne propose rien tant que rien n’est coché', () => {
    expect(rolesDonnables([])).toEqual([]);
  });
});

describe('roleParDefaut', () => {
  it('reprend le rôle actuel de la personne quand il est permis', () => {
    expect(roleParDefaut(['rh', 'collaborateur'], 'rh')).toBe('rh');
  });

  it('sinon le rôle le plus restreint', () => {
    expect(roleParDefaut(['collaborateur_rh', 'collaborateur'], 'admin')).toBe('collaborateur');
    expect(roleParDefaut(['collaborateur_rh', 'collaborateur'], 'custom')).toBe('collaborateur');
    expect(roleParDefaut([], 'rh')).toBe('');
  });
});

describe('messageResultatAcces', () => {
  it('nomme les sociétés ouvertes et le rôle', () => {
    const { succes, erreur } = messageResultatAcces(['Atelier', 'Bureau'], [], 'rh');
    expect(succes).toContain('Accès donné à Atelier et Bureau (rôle : Ressources Humaines)');
    expect(erreur).toBeNull();
  });

  it('nomme aussi les échecs avec leur raison', () => {
    const { succes, erreur } = messageResultatAcces(
      ['Atelier'],
      [{ nom: 'Bureau', raison: 'droits insuffisants' }],
      'collaborateur',
    );
    expect(succes).toContain('Atelier');
    expect(erreur).toBe('Accès non donné à Bureau (droits insuffisants).');
  });

  it('listerNoms', () => {
    expect(listerNoms(['A'])).toBe('A');
    expect(listerNoms(['A', 'B', 'C'])).toBe('A, B et C');
  });
});

describe('messageErreurCreation', () => {
  it('oriente vers « Donner accès à d’autres sociétés » quand l’e-mail existe', () => {
    const msg = messageErreurCreation(
      "Erreur lors de la création de l'utilisateur: A user with this email address has already been registered",
    );
    expect(msg).toContain('Un compte existe déjà avec cet e-mail');
    expect(msg).toContain("Donner accès à d'autres sociétés");
  });

  it('laisse passer les autres erreurs telles quelles', () => {
    expect(messageErreurCreation('Mot de passe trop court')).toBe('Mot de passe trop court');
    expect(messageErreurCreation(undefined)).toBe("Erreur lors de la création de l'utilisateur");
  });
});
