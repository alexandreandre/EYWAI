import httpx
from supabase_auth.errors import AuthUnknownError

from app.core.supabase_resilience import (
    execute_with_retry,
    is_transient_supabase_error,
)


def test_cloudflare_522_http_status_error_is_transient():
    request = httpx.Request("GET", "https://example.supabase.co/auth/v1/user")
    response = httpx.Response(522, request=request)
    exc = httpx.HTTPStatusError(
        "Server error '522 <none>'", request=request, response=response
    )

    assert is_transient_supabase_error(exc) is True


def test_supabase_auth_unknown_error_with_522_is_transient():
    request = httpx.Request("GET", "https://example.supabase.co/auth/v1/user")
    response = httpx.Response(522, request=request)
    original_error = httpx.HTTPStatusError(
        "Server error '522 <none>'", request=request, response=response
    )
    exc = AuthUnknownError(
        "Server error '522 <none>' for url "
        "'https://example.supabase.co/auth/v1/user'",
        original_error,
    )

    assert is_transient_supabase_error(exc) is True


def test_execute_with_retry_retries_cloudflare_522_wrapped_message():
    calls = 0

    def flaky_call():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("Server error '522 <none>' for url")
        return "ok"

    assert execute_with_retry(flaky_call, base_delay_s=0) == "ok"
    assert calls == 3
