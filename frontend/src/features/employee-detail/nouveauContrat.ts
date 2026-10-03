import type { NewContractBody, NewContractPreview } from '@/api/contractPeriods';

/** Statuts d'un salarié parti : seule sa fiche propose « Nouveau contrat ». */
const STATUTS_PARTIS = ['parti', 'sorti', 'inactif'];

export interface FormulaireNouveauContrat {
  dateDebut: string;
  typeContrat: string;
  dateFin: string;
  duree: string;
  salaire: string;
  poste: string;
  reprendreAnciennete: boolean;
}

export function peutCreerUnNouveauContrat(statut: string | null | undefined): boolean {
  return STATUTS_PARTIS.includes((statut ?? '').toLowerCase());
}

function jjmmaaaa(iso: string | null | undefined): string {
  const [annee, mois, jour] = (iso ?? '').slice(0, 10).split('-');
  return annee && mois && jour ? `${jour}/${mois}/${annee}` : '';
}

function nombre(texte: string): number {
  const propre = texte.replace(/\s/g, '').replace(',', '.');
  return propre ? Number(propre) : Number.NaN;
}

function estUnCdd(type: string): boolean {
  const t = type.toLowerCase();
  return t.includes('cdd') && !t.includes('cdi');
}

export function avecDateDeFin(type: string): boolean {
  return type !== 'CDI';
}

export function formulaireInitial(apercu: NewContractPreview): FormulaireNouveauContrat {
  const p = apercu.prerempli;
  return {
    dateDebut: '',
    typeContrat: p.contract_type,
    dateFin: '',
    duree: p.duree_hebdomadaire != null ? String(p.duree_hebdomadaire) : '',
    salaire: p.salaire_mensuel != null ? String(p.salaire_mensuel) : '',
    poste: p.job_title ?? '',
    reprendreAnciennete: false,
  };
}

/** Même contrôle que le serveur, dit avant l'envoi. Le serveur reste juge. */
export function erreurDuFormulaire(
  form: FormulaireNouveauContrat,
  apercu: NewContractPreview,
): string | null {
  if (!form.dateDebut) return 'Indiquez la date de début du nouveau contrat.';
  const premier = apercu.premier_jour_possible;
  if (premier && form.dateDebut < premier) {
    return `Le nouveau contrat peut commencer le ${jjmmaaaa(premier)} au plus tôt (le précédent se termine le ${jjmmaaaa(apercu.contrat_precedent?.date_fin)}).`;
  }
  if (estUnCdd(form.typeContrat) && !form.dateFin) return 'Indiquez la date de fin du CDD.';
  if (avecDateDeFin(form.typeContrat) && form.dateFin && form.dateFin < form.dateDebut) {
    return 'La date de fin est avant la date de début.';
  }
  const duree = nombre(form.duree);
  if (!Number.isFinite(duree) || duree <= 0 || duree > 48) {
    return 'Indiquez une durée hebdomadaire entre 1 et 48 heures.';
  }
  const salaire = nombre(form.salaire);
  if (!Number.isFinite(salaire) || salaire <= 0) return 'Indiquez le salaire de base mensuel.';
  return null;
}

export function corpsDeLaRequete(form: FormulaireNouveauContrat): NewContractBody {
  return {
    date_debut: form.dateDebut,
    contract_type: form.typeContrat,
    date_fin: avecDateDeFin(form.typeContrat) && form.dateFin ? form.dateFin : null,
    duree_hebdomadaire: nombre(form.duree),
    salaire_mensuel: nombre(form.salaire),
    job_title: form.poste.trim() || null,
    reprendre_anciennete: form.reprendreAnciennete,
  };
}

/** La date d'ancienneté que la fiche portera, dite avant l'enregistrement. */
export function dateAncienneteRetenue(
  form: FormulaireNouveauContrat,
  apercu: NewContractPreview,
): string {
  if (form.reprendreAnciennete) {
    return `Date d’ancienneté retenue : ${jjmmaaaa(apercu.date_anciennete)}, celle du contrat précédent.`;
  }
  if (!form.dateDebut) return 'Date d’ancienneté retenue : le début du nouveau contrat.';
  return `Date d’ancienneté retenue : ${jjmmaaaa(form.dateDebut)}, le début du nouveau contrat.`;
}
