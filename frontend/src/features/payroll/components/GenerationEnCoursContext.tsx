import { createContext, useContext } from 'react';

/** Vrai pendant que la génération du mois tourne : les actions de ligne se taisent. */
const GenerationEnCoursContext = createContext(false);

export const GenerationEnCoursProvider = GenerationEnCoursContext.Provider;

export function useGenerationEnCours(): boolean {
  return useContext(GenerationEnCoursContext);
}
