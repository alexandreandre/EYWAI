# DTOs internes du module exports.
# Structures pour l'enregistrement en base et données intermédiaires (sans dépendance aux schémas API).
from typing import Any, Dict, List, Optional

# Enregistrement inséré dans exports_history (structure attendue par repository.insert_export_record).
# Clés : company_id, export_type, period, parameters, file_paths, report, status, generated_by
ExportRecordForInsert = Dict[str, Any]

# Résultat brut d'une prévisualisation (retour des providers avant mapping vers ExportPreviewResponse).
# Clés typiques : employees_count, totals (dict), anomalies (list), warnings (list), can_generate, period?, nombre_salaries? (DSN)
PreviewResultRaw = Dict[str, Any]

# Une entrée export pour l'historique (ligne DB + infos dérivées comme generated_by_name).
ExportHistoryRow = Dict[str, Any]
