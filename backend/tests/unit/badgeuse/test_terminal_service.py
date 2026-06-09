from unittest.mock import patch

from app.modules.badgeuse.application.terminal_service import activate_terminal_device_here


@patch("app.modules.badgeuse.application.terminal_service.create_terminal_device")
def test_activate_terminal_device_here_uses_provided_label(mock_create):
    mock_create.return_value = {"device": {"label": "iPad · 09/06/2026"}, "token": "raw"}

    result = activate_terminal_device_here(
        company_id="co-1",
        created_by="user-1",
        label="Entrée usine",
    )

    assert result["token"] == "raw"
    mock_create.assert_called_once_with(
        company_id="co-1",
        label="Entrée usine",
        created_by="user-1",
    )


@patch("app.modules.badgeuse.application.terminal_service.create_terminal_device")
def test_activate_terminal_device_here_generates_default_label(mock_create):
    mock_create.return_value = {"device": {"label": "Appareil · 09/06/2026"}, "token": "raw"}

    activate_terminal_device_here(
        company_id="co-1",
        created_by="user-1",
        label=None,
    )

    label = mock_create.call_args.kwargs["label"]
    assert label.startswith("Appareil · ")
    mock_create.assert_called_once_with(
        company_id="co-1",
        label=label,
        created_by="user-1",
    )
