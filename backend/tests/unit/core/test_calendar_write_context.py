from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
import pytest

from app.core.calendar_write_context import CALENDAR_TOKEN_HEADER, calendar_write_token
from app.core.lecture_seule import (
    ClientHttpSupabase,
    EcritureEnLectureSeule,
    lecture_seule,
)


def test_token_is_scoped_to_request_and_reset_after_exception():
    seen = []
    def transport(request):
        seen.append(request.headers.get(CALENDAR_TOKEN_HEADER))
        return httpx.Response(200, json={})
    with ClientHttpSupabase(transport=httpx.MockTransport(transport)) as client:
        client.get("https://example.test/rest/v1/employee_schedules")
        with calendar_write_token("outer"):
            client.post("https://example.test/rest/v1/employee_schedules", json={})
            with pytest.raises(ValueError), calendar_write_token("inner"):
                client.get("https://example.test/rest/v1/employee_schedules")
                raise ValueError("simulated")
            client.get("https://example.test/rest/v1/employee_schedules")
            client.get("https://example.test/storage/v1/object/test")
        client.get("https://example.test/rest/v1/employee_schedules", headers={CALENDAR_TOKEN_HEADER: "residual"})
    assert seen == [None, "outer", "inner", "outer", None, None]


def test_shared_http_client_does_not_share_tokens_between_threads():
    barrier = Barrier(2)
    def transport(request):
        barrier.wait(timeout=2)
        return httpx.Response(200, json={"token": request.headers.get(CALENDAR_TOKEN_HEADER)})
    with ClientHttpSupabase(transport=httpx.MockTransport(transport)) as client:
        def send(token):
            with calendar_write_token(token):
                return client.get("https://example.test/rest/v1/employee_schedules").json()["token"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(send, token) for token in ["rh-a", "rh-b"]]
            assert [f.result() for f in futures] == ["rh-a", "rh-b"]
        assert CALENDAR_TOKEN_HEADER not in client.headers


def test_token_does_not_bypass_read_only_guard():
    def unexpected(_request):
        raise AssertionError("No request should leave the read-only context")
    with (
        ClientHttpSupabase(transport=httpx.MockTransport(unexpected)) as client,
        calendar_write_token("owner"), lecture_seule(), pytest.raises(EcritureEnLectureSeule),
    ):
        client.post("https://example.test/rest/v1/employee_schedules", json={})
