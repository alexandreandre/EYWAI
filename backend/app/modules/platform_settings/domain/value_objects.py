"""Value objects configuration e-mail plateforme."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

SmtpSecurity = Literal["starttls", "ssl", "none"]

DEFAULT_SUPPORT_RECIPIENTS = ("contact@eywai.fr",)


@dataclass(frozen=True)
class ResolvedEmailConfig:
    """Configuration SMTP effective pour l'envoi (DB active ou repli env)."""

    smtp_host: str
    smtp_port: int
    smtp_user: Optional[str]
    smtp_password: Optional[str]
    smtp_security: SmtpSecurity
    from_email: Optional[str]
    from_name: str
    reply_to: Optional[str]
    support_recipients: tuple[str, ...]
    frontend_url: str
    source: Literal["database", "environment"]

    @property
    def is_configured(self) -> bool:
        return bool(self.smtp_user and self.smtp_password)

    @property
    def from_header(self) -> str:
        email = self.from_email or self.smtp_user or "noreply@eywai.fr"
        return f"{self.from_name} <{email}>"
