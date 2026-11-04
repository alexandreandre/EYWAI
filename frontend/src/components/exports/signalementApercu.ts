// Aperçu d'un signalement DSN : le masque du NIR et le rangement des blocs par partie.
import type { SignalementApercuBloc, SignalementApercuPartie } from '@/api/exports';

/** Rubrique du NIR dans le bloc individu (S21.G00.30). */
export const RUBRIQUE_NIR = 'S21.G00.30.001';

export const LIBELLES_PARTIES: Record<SignalementApercuPartie, string> = {
  envoi: 'Envoi',
  declarant: 'Déclarant et déclaration',
  entreprise: 'Entreprise et établissement',
  salarie: 'Salarié',
  contrat: 'Contrat',
  evenement: 'Événement',
  remuneration: 'Rémunération et cotisations',
  autre: 'Autres blocs',
};

export const PHRASE_TETE =
  "Ce fichier n'est pas encore envoyé. Cet aperçu n'enregistre rien et ne dépose rien : « Valider le format » ferme seulement la fenêtre.";
export const PHRASE_BRUT =
  "Texte du fichier tel qu'il serait déposé. Seul le NIR est masqué à l'écran (2 premiers et 2 derniers chiffres) ; le fichier déposé le porte en entier.";
export const ERREUR_PAR_DEFAUT = "L'aperçu n'a pas pu être construit : réessayez.";

/** Le message du serveur (detail), sinon la phrase par défaut. */
export function detailErreurApercu(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } } | null)?.response?.data?.detail;
  return typeof detail === 'string' && detail ? detail : ERREUR_PAR_DEFAUT;
}

const MASQUE = '•';

/**
 * Le NIR à l'écran : les 2 premiers et les 2 derniers caractères, le reste
 * masqué, longueur gardée. Une valeur sans plus de 4 chiffres en clair à la
 * suite (déjà masquée par le serveur) reste telle quelle.
 */
export function masquerNir(valeur: string): string {
  if (valeur.length <= 4 || !/\d{5,}/.test(valeur)) return valeur;
  return valeur.slice(0, 2) + MASQUE.repeat(valeur.length - 4) + valeur.slice(-2);
}

/** Le texte brut, NIR masqué sur sa ligne (filet si le serveur ne l'a pas fait). */
export function masquerNirDansBrut(brut: string): string {
  return brut.replace(
    /^(S21\.G00\.30\.001,')([^'\r\n]*)(')/gm,
    (_tout, avant: string, nir: string, apres: string) => avant + masquerNir(nir) + apres,
  );
}

export interface PartieApercu {
  partie: SignalementApercuPartie;
  libelle: string;
  blocs: SignalementApercuBloc[];
}

/** Les blocs dans l'ordre du fichier, regroupés quand des blocs voisins partagent leur partie. */
export function grouperParPartie(blocs: SignalementApercuBloc[]): PartieApercu[] {
  const parties: PartieApercu[] = [];
  for (const bloc of blocs) {
    const derniere = parties[parties.length - 1];
    if (derniere && derniere.partie === bloc.partie) {
      derniere.blocs.push(bloc);
    } else {
      parties.push({
        partie: bloc.partie,
        libelle: LIBELLES_PARTIES[bloc.partie] ?? LIBELLES_PARTIES.autre,
        blocs: [bloc],
      });
    }
  }
  return parties;
}
