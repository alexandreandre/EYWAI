"""Tests unitaires — traduction erreurs DB."""

import pytest
from fastapi import HTTPException
from postgrest.exceptions import APIError

from app.shared.db_errors import raise_http_for_db_error


def test_raise_http_for_db_error_fk_maps_to_409():
    exc = APIError({"message": "violates foreign key", "code": "23503"})
    with pytest.raises(HTTPException) as err:
        raise_http_for_db_error(exc)
    assert err.value.status_code == 409
    assert "données liées" in err.value.detail


def test_raise_http_for_db_error_generic_maps_to_500():
    with pytest.raises(HTTPException) as err:
        raise_http_for_db_error(RuntimeError("boom"))
    assert err.value.status_code == 500
    assert "{" not in err.value.detail
