"""Façade badgeuse — réexporte _internals et les sous-services (compat router et tests)."""

from app.modules.badgeuse.application import _internals as _badgeuse_internals
from app.modules.badgeuse.application._internals import *  # noqa: F403
from app.modules.badgeuse.application.export_service import *  # noqa: F403
from app.modules.badgeuse.application.punch_service import *  # noqa: F403
from app.modules.badgeuse.application.qr_service import *  # noqa: F403

# Symboles « privés » (non exportés par import *) — patchables via application.service
_employee_repository = _badgeuse_internals._employee_repository
time_entry_repository = _badgeuse_internals.time_entry_repository
time_entry_validation_repository = _badgeuse_internals.time_entry_validation_repository
company_repository = _badgeuse_internals.company_repository
badge_credentials_repository = _badgeuse_internals.badge_credentials_repository
_employee_is_forfait_jour = _badgeuse_internals._employee_is_forfait_jour
_user_is_forfait_jour = _badgeuse_internals._user_is_forfait_jour
_insert_toggle_entry = _badgeuse_internals._insert_toggle_entry
_build_punch_response = _badgeuse_internals._build_punch_response
_resolve_next_event_type = _badgeuse_internals._resolve_next_event_type
_check_debounce = _badgeuse_internals._check_debounce
_status_response_payload = _badgeuse_internals._status_response_payload
DEBOUNCE_SECONDS = _badgeuse_internals.DEBOUNCE_SECONDS
