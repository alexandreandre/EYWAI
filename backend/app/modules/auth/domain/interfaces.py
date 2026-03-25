# Ports (abstractions) pour l'infrastructure auth.
# L'application dépend de ces interfaces ; l'infrastructure les implémente (Supabase, email).

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IAuthProvider(ABC):
    """Authentification : sign_in, sign_out, update_password, find_user_id_by_email (Supabase Auth)."""

    @abstractmethod
    def sign_in_with_password(self, email: str, password: str) -> dict[str, Any]:
        """Retourne session (access_token, user)."""
        ...

    @abstractmethod
    def sign_out(self) -> None:
        """Révoque la session courante."""
        ...

    @abstractmethod
    def update_user_password(self, user_id: str, new_password: str) -> None:
        """Met à jour le mot de passe (Admin API)."""
        ...

    @abstractmethod
    def get_user_by_token(self, token: str) -> Any:
        """Valide le token et retourne l'utilisateur Supabase."""
        ...

    @abstractmethod
    def find_user_id_by_email(self, email: str) -> str | None:
        """Recherche un utilisateur auth par email ; retourne son id ou None."""
        ...


class IUserByLoginResolver(ABC):
    """Résolution identifiant de connexion : username → email (table employees)."""

    @abstractmethod
    def resolve_email(self, username_or_email: str) -> str | None:
        """Retourne l'email si username fourni, ou l'input si déjà email."""
        ...


class IResetTokenStore(ABC):
    """Stockage des tokens de réinitialisation (table password_resets)."""

    @abstractmethod
    def create(self, user_id: str, email: str, token: str, expires_at: str) -> None:
        """Enregistre un token."""
        ...

    @abstractmethod
    def get_valid(self, token: str) -> dict | None:
        """Retourne la ligne si token valide et non utilisé, sinon None."""
        ...

    @abstractmethod
    def mark_used(self, token: str) -> None:
        """Marque le token comme utilisé."""
        ...


class IEmailSender(ABC):
    """Envoi d'emails (ex. réinitialisation mot de passe)."""

    @abstractmethod
    def send_password_reset(
        self, to_email: str, reset_token: str, user_name: str | None = None
    ) -> bool:
        """Envoie l'email de reset. Retourne True si succès."""
        ...


class IUserFromToken(ABC):
    """Récupération du contexte utilisateur à partir d’un token JWT (délègue à get_current_user)."""

    @abstractmethod
    def get_user(self, token: str) -> Any:
        """Valide le token et retourne l’objet User (profil, entreprises, rôle)."""
        ...
