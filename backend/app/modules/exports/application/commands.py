# Commandes applicatives exports (écritures).
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator

from app.modules.exports.application.dto import ExportRecordForInsert
from app.modules.exports.infrastructure import repository

# Export tiré par un compte en consultation (app/core/consultation.py) : le fichier
# lui est remis, mais rien n'entre dans l'historique de la société. Sinon ses
# téléchargements s'afficheraient sur l'écran du bulletin (« exports du mois »).
_sans_trace: ContextVar[bool] = ContextVar("exports_sans_trace", default=False)


@contextmanager
def exports_sans_trace(actif: bool = True) -> Iterator[None]:
    """Dans ce bloc, `record_export_history` n'écrit rien."""
    jeton = _sans_trace.set(actif)
    try:
        yield
    finally:
        _sans_trace.reset(jeton)


def record_export_history(record: ExportRecordForInsert) -> str:
    """
    Enregistre un export dans l'historique (exports_history).
    Returns:
        export_id (str) ; chaîne vide si l'insertion n'a pas retourné d'id.
    """
    if _sans_trace.get():
        return ""
    export_id = repository.insert_export_record(record)
    return export_id or ""
