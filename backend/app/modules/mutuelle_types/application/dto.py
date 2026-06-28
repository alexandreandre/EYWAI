"""DTOs et exceptions applicatives du module mutuelle_types."""


class MutuelleTypeApplicationError(Exception):
    """Erreur métier ou validation à mapper par la couche API."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


__all__ = ["MutuelleTypeApplicationError"]
