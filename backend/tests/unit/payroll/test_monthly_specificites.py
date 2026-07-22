from app.modules.payroll.application.monthly_specificites import (
    resolve_monthly_specificites,
)


def test_resolve_monthly_specificites_deep_merge_exact_period():
    source = {
        "mutuelle": {
            "adhesion": False,
            "dsn": {"code_organisme": "AGGEEV"},
            "mutuelle_type_ids": ["current"],
        },
        "prevoyance": {"adhesion": False},
        "overrides_mensuels": {
            "2026-04": {
                "mutuelle": {
                    "adhesion": True,
                    "mutuelle_type_ids": ["april"],
                },
                "prevoyance": {"adhesion": True},
            }
        },
    }

    resolved = resolve_monthly_specificites(source, 2026, 4)

    assert resolved["mutuelle"] == {
        "adhesion": True,
        "dsn": {"code_organisme": "AGGEEV"},
        "mutuelle_type_ids": ["april"],
    }
    assert resolved["prevoyance"]["adhesion"] is True
    assert "overrides_mensuels" not in resolved
    assert source["mutuelle"]["adhesion"] is False


def test_resolve_monthly_specificites_without_override_keeps_current_config():
    source = {
        "mutuelle": {"adhesion": False},
        "overrides_mensuels": {"2026-04": {"mutuelle": {"adhesion": True}}},
    }

    assert resolve_monthly_specificites(source, 2026, 5) == {
        "mutuelle": {"adhesion": False}
    }
