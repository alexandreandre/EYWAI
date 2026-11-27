import { describe, expect, it } from 'vitest';
import { champsDeLaSaisie } from './sensSaisie';
import { afficherBlocPanier, casesApresNouveauNom, champsDuPanier, panierNonSoumisParDefaut,
  libelleNombreDePaniers,
  lireNombreDePaniers,
  nombreDePaniersModifiable,
} from './panierSaisie';

const SOUMIS = { is_socially_taxed: true, is_taxable: true };
const NON_SOUMIS = { is_socially_taxed: false, is_taxable: false };

/** Corps tel que SaisieModal le construit pour une prime tapée à la main. */
function corps(nom: string, cases: typeof SOUMIS, nombre: number | '' = 20) {
  const champs = champsDeLaSaisie('prime', 150, cases);
  return { name: nom, ...champs, ...champsDuPanier(nom, champs, nombre, 'sur_lieu_travail') };
}

describe('panier tapé à la main', () => {
  it('« Panier repas » part non soumis, avec le nombre et la situation', () => {
    const cases = casesApresNouveauNom('', 'Panier repas', SOUMIS);
    expect(cases).toEqual(NON_SOUMIS);
    expect(corps('Panier repas', cases)).toMatchObject({
      is_socially_taxed: false,
      is_taxable: false,
      payroll_quantity: 20,
      quantity_kind: 'count',
      situation_repas: 'sur_lieu_travail',
    });
  });

  it('« Prime panier soumises » reste soumis, sans nombre ni situation', () => {
    const cases = casesApresNouveauNom('', 'Prime panier soumises', SOUMIS);
    expect(cases).toEqual(SOUMIS);
    const c = corps('Prime panier soumises', cases);
    expect(c).toMatchObject({ is_socially_taxed: true, is_taxable: true });
    expect(c).not.toHaveProperty('situation_repas');
    expect(c).not.toHaveProperty('payroll_quantity');
  });

  it('« non soumis » dans le nom compte comme exonéré ; avantage en nature repas reste soumis', () => {
    expect(panierNonSoumisParDefaut('Paniers non soumis')).toBe(true);
    expect(panierNonSoumisParDefaut('Avantage en nature repas')).toBe(false);
    expect(panierNonSoumisParDefaut('Prime de fin d’année')).toBe(false);
  });

  it('la case cochée à la main reste tant que le nom reste un panier', () => {
    expect(casesApresNouveauNom('Panier', 'Panier repas', SOUMIS)).toEqual(SOUMIS);
    // le nom redevient une prime ordinaire : retour à « soumise »
    expect(casesApresNouveauNom('Panier repas', 'Prime', NON_SOUMIS)).toEqual(SOUMIS);
    // « soumis » ajouté au nom : retour à « soumise »
    expect(casesApresNouveauNom('Panier repas', 'Panier repas soumis', NON_SOUMIS)).toEqual(SOUMIS);
  });

  it('ne renvoie que les deux cases, jamais le reste du formulaire (le nom tapé n’est pas écrasé)', () => {
    const formulaire = { ...SOUMIS, name: '', amount: '', selectedEmployees: [] as string[] };
    // Touche par touche : « P », « Pr »… la nature du nom ne change pas.
    for (const [avant, apres] of [['', 'P'], ['P', 'Pr'], ['Prime', 'Prime e'], ['Pan', 'Pani']]) {
      const formulaireComplet = { ...formulaire, name: avant };
      expect(Object.keys(casesApresNouveauNom(avant, apres, formulaireComplet)).sort()).toEqual([
        'is_socially_taxed',
        'is_taxable',
      ]);
    }
    // Simulation du setFormData de SaisieModal, lettre par lettre.
    let etat = { ...formulaire };
    for (const lettre of 'Panier repas') {
      const valeur = etat.name + lettre;
      etat = { ...etat, ...casesApresNouveauNom(etat.name, valeur, etat), name: valeur };
    }
    expect(etat.name).toBe('Panier repas');
    expect(etat).toMatchObject(NON_SOUMIS);
    etat = { ...formulaire };
    for (const lettre of 'Prime exceptionnelle') {
      const valeur = etat.name + lettre;
      etat = { ...etat, ...casesApresNouveauNom(etat.name, valeur, etat), name: valeur };
    }
    expect(etat.name).toBe('Prime exceptionnelle');
    expect(etat).toMatchObject(SOUMIS);
  });

  it('panier coché « soumise » à la main : pas de bloc, rien de plus envoyé', () => {
    expect(afficherBlocPanier('Panier repas', SOUMIS)).toBe(false);
    expect(corps('Panier repas', SOUMIS)).not.toHaveProperty('situation_repas');
  });

  it('versement sur le net : pas de bloc panier', () => {
    const champs = champsDeLaSaisie('versement_net', 50, NON_SOUMIS);
    expect(afficherBlocPanier('Panier repas', champs)).toBe(false);
  });
});

describe('nombre de paniers modifiable dans Primes du mois (L19, 27/11)', () => {
  const saisie = (champs: Record<string, unknown>) => ({
    name: 'Panier',
    is_socially_taxed: false,
    sur_le_net: false,
    payroll_quantity: 15,
    quantity_kind: 'count',
    ...champs,
  }) as never;

  it('un panier non soumis compté en nombre se modifie', () => {
    expect(nombreDePaniersModifiable(saisie({}))).toBe(true);
    expect(nombreDePaniersModifiable(saisie({ quantity_kind: null }))).toBe(true);
    expect(nombreDePaniersModifiable(saisie({ payroll_quantity: null }))).toBe(true);
  });

  it("ni une valeur unitaire, ni un panier soumis, ni une autre prime", () => {
    expect(nombreDePaniersModifiable(saisie({ quantity_kind: 'unit_value' }))).toBe(false);
    expect(nombreDePaniersModifiable(saisie({ is_socially_taxed: true }))).toBe(false);
    expect(nombreDePaniersModifiable(saisie({ name: 'Prime de présence' }))).toBe(false);
  });

  it('lit un nombre positif, virgule comprise', () => {
    expect(lireNombreDePaniers('15')).toBe(15);
    expect(lireNombreDePaniers('14,5')).toBe(14.5);
    expect(lireNombreDePaniers('0')).toBeNull();
    expect(lireNombreDePaniers('abc')).toBeNull();
  });

  it('dit le nombre', () => {
    expect(libelleNombreDePaniers(15)).toBe('15 paniers');
    expect(libelleNombreDePaniers(1)).toBe('1 panier');
    expect(libelleNombreDePaniers(14.5)).toBe('14,5 paniers');
    expect(libelleNombreDePaniers(null)).toBe('Nombre de paniers ?');
  });
});
