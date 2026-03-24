# Commandes applicatives exports (écritures).
from app.modules.exports.application.dto import ExportRecordForInsert
from app.modules.exports.infrastructure import repository


def record_export_history(record: ExportRecordForInsert) -> str:
    """
    Enregistre un export dans l'historique (exports_history).
    Returns:
        export_id (str) ; chaîne vide si l'insertion n'a pas retourné d'id.
    """
    export_id = repository.insert_export_record(record)
    return export_id or ""
