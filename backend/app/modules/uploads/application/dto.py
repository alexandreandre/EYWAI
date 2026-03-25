"""
DTOs pour les cas d'usage uploads (résultats application → API).

Contrat aligné sur les réponses actuelles (api/routers/uploads.py).
"""


class UploadLogoResult:
    """Résultat de l'upload d'un logo."""

    __slots__ = ("logo_url", "message")

    def __init__(self, logo_url: str, message: str = "Logo uploadé avec succès"):
        self.logo_url = logo_url
        self.message = message


class DeleteLogoResult:
    """Résultat de la suppression d'un logo."""

    __slots__ = ("message",)

    def __init__(self, message: str):
        self.message = message


class LogoScaleResult:
    """Résultat de la mise à jour du facteur de zoom."""

    __slots__ = ("logo_scale", "message")

    def __init__(
        self,
        logo_scale: float,
        message: str = "Facteur de zoom mis à jour avec succès",
    ):
        self.logo_scale = logo_scale
        self.message = message
