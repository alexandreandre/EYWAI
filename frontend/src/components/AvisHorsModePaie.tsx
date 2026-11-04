import { useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { toast } from '@/hooks/use-toast';
import { messageHorsModePaie } from '@/lib/payrollFocus';

/**
 * Après le renvoi d'une page hors mode paie vers l'accueil, le dit une fois,
 * puis efface l'état de navigation (un rechargement ne le redit pas).
 */
export function AvisHorsModePaie() {
  const location = useLocation();
  const navigate = useNavigate();
  const dejaDit = useRef<string | null>(null);
  const message = messageHorsModePaie(location.state);

  useEffect(() => {
    if (!message || dejaDit.current === location.key) return;
    dejaDit.current = location.key;
    toast({ title: 'Page hors du mode paie', description: message });
    navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
  }, [message, location.key, location.pathname, location.search, navigate]);

  return null;
}
