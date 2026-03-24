// src/contexts/AuthContext.tsx 
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import apiClient from '@/api/apiClient';
import { CompanyAccess } from "./CompanyContext"; // utile si besoin futur

// === Types ===

interface User {
  id: string;
  email: string;
  role?: 'rh' | 'collaborateur' | 'collaborateur_rh' | 'admin' | 'super_admin' | 'custom'; // ⚠️ devient optionnel car le backend ne le renvoie pas
  first_name: string;
  last_name?: string;
  is_super_admin?: boolean;
  is_group_admin?: boolean;

  // Ajout :
  active_company?: CompanyAccess; // pour fallback du rôle
}

interface AuthContextType {
  user: User | null;
  login: (token: string) => Promise<void>;
  logout: () => Promise<void>;
  isLoading: boolean;
}

// === Context ===

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// === Normalisation du user (correction CLÉ) ===

function normalizeUser(u: any): User {
  console.log("%c[AuthContext] 🔧 Normalisation du user brut :", "color: darkcyan", u);

  // Si aucun rôle n'est renvoyé → on prend celui de l’entreprise active
  const role =
    u.role ||
    u.active_company?.role ||
    null;

  console.log("%c[AuthContext] 🔧 Rôle final utilisé :", "color: darkcyan", role);

  return {
    ...u,
    role,
  };
}

// === Provider ===

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  console.log("%c[AuthContext] 🟣 AuthProvider rendu", "color: purple");

  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // ======================
  // RESTAURATION DE SESSION
  // ======================
  useEffect(() => {
    console.log('%c[AuthContext] 🔄 Vérification de session...', 'background: purple; color: white');

    const token = localStorage.getItem('authToken');

    if (!token) {
      console.log('%c[AuthContext] 🤷 Aucun token trouvé.', 'color: gray');
      setIsLoading(false);
      return;
    }

    console.log('%c[AuthContext] 🔑 Token trouvé. Appel /api/auth/me...', 'color: purple');

    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;

    apiClient.get('/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((response) => {
        console.log('%c[AuthContext] ✔️ Session restaurée. User brut =', 'color: green; font-weight: bold', response.data);

        const normalized = normalizeUser(response.data);

        console.log('%c[AuthContext] ✔️ User normalisé =', 'color: green', normalized);

        setUser(normalized);
      })
      .catch((error) => {
        console.error('%c[AuthContext] ❌ Token invalide → suppression', "background:red;color:white", error);
        localStorage.removeItem('authToken');
        delete apiClient.defaults.headers.common['Authorization'];
      })
      .finally(() => {
        setIsLoading(false);
        console.log('%c[AuthContext] 🏁 Chargement terminé', 'color: purple');
      });

  }, []);

  // ================
  // LOGIN
  // ================
  const login = async (token: string) => {
    console.log('%c[AuthContext] 🚀 Tentative de connexion...', 'color: blue; font-weight: bold;');

    const clean = token.startsWith("Bearer ") ? token.split(" ")[1] : token;
    const authHeader = `Bearer ${clean}`;
    localStorage.setItem("authToken", clean);
    apiClient.defaults.headers.common["Authorization"] = authHeader;

    try {
      console.log('%c[AuthContext] 📡 Appel /api/auth/me...', 'color: blue');

      const response = await apiClient.get("/api/auth/me", {
        headers: { Authorization: authHeader }
      });

      console.log('%c[AuthContext] ✔️ User récupéré =', 'color: green', response.data);

      const normalized = normalizeUser(response.data);

      console.log('%c[AuthContext] ✔️ User normalisé =', 'color: green', normalized);

      setUser(normalized);

    } catch (error) {
      console.error('%c[AuthContext] ❌ Échec login', 'color:red', error);
      await logout();
      throw error;
    }
  };

  // ================
  // LOGOUT
  // ================
  const logout = async () => {
    console.log('%c[AuthContext] 🚪 Déconnexion...', 'color: orange; font-weight:bold');

    try {
      await apiClient.post("/api/auth/logout");
      console.log('%c[AuthContext] ✔️ Token révoqué côté backend', 'color: green');
    } catch (err) {
      console.error('%c[AuthContext] ⚠️ Erreur révocation, mais on continue', 'color: orange');
    }

    setUser(null);
    localStorage.removeItem("authToken");
    delete apiClient.defaults.headers.common["Authorization"];
    console.log('%c[AuthContext] ✔️ Session locale nettoyée', 'color: green');
  };

  // ================
  // RENDER
  // ================
  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
      {!isLoading && children}
    </AuthContext.Provider>
  );
};

// === Hook ===

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
};

// === Helper functions ===

/**
 * Vérifie si un utilisateur a accès RH dans une entreprise
 * Inclut: rh, collaborateur_rh, admin, et custom avec permissions RH
 */
export function hasRhAccess(user: User | null, companyId: string): boolean {
  if (!user) return false;
  
  // Super admin a toujours accès
  if (user.is_super_admin) return true;
  
  // Rôles système avec accès RH
  if (user.role === 'rh' || user.role === 'collaborateur_rh' || user.role === 'admin') {
    return true;
  }
  
  // Pour les rôles custom, vérifier via API si l'utilisateur a au moins une permission RH
  // Note: Cette vérification nécessite un appel API, donc pour l'instant on retourne false
  // et la vérification sera faite côté composant avec un appel API si nécessaire
  if (user.role === 'custom') {
    // TODO: Implémenter vérification via API si nécessaire
    return false;
  }
  
  return false;
}

/**
 * Vérifie si un utilisateur est collaborateur_rh
 */
export function isCollaborateurRh(user: User | null): boolean {
  if (!user) return false;
  return user.role === 'collaborateur_rh';
}
