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


# --- Relance d'un auteur extérieur quand le calendrier est réservé (13/11) ---

from postgrest.exceptions import APIError  # noqa: E402

from app.core.calendar_write_context import (  # noqa: E402
    CalendrierReserve,
    relancer_si_calendrier_reserve,
)


def _reserve() -> APIError:
    return APIError({"code": "PT409", "message": "Un enregistrement de ce calendrier est en cours.", "details": None, "hint": None})


class _Horloge:
    def __init__(self):
        self.t = 0.0
        self.attentes = []

    def maintenant(self):
        return self.t

    def dormir(self, s):
        self.attentes.append(s)
        self.t += s


def test_une_operation_refusee_pendant_une_reservation_est_rejouee_entiere():
    horloge, appels = _Horloge(), []

    def projection():
        appels.append("relit puis écrit")
        if len(appels) < 3:
            raise _reserve()
        return "projeté"

    assert relancer_si_calendrier_reserve(projection, dormir=horloge.dormir, maintenant=horloge.maintenant) == "projeté"
    assert appels == ["relit puis écrit"] * 3


def test_au_dela_du_delai_le_refus_est_explicite():
    horloge = _Horloge()

    def projection():
        raise _reserve()

    with pytest.raises(CalendrierReserve, match="en cours d’enregistrement"):
        relancer_si_calendrier_reserve(projection, delai_max=5, dormir=horloge.dormir, maintenant=horloge.maintenant)
    assert horloge.t >= 5


def test_une_autre_erreur_n_est_jamais_rejouee():
    horloge, appels = _Horloge(), []

    def projection():
        appels.append(1)
        raise APIError({"code": "23505", "message": "doublon", "details": None, "hint": None})

    with pytest.raises(APIError):
        relancer_si_calendrier_reserve(projection, dormir=horloge.dormir, maintenant=horloge.maintenant)
    assert appels == [1] and not horloge.attentes


def test_l_enregistrement_qui_tient_la_reservation_n_attend_pas():
    """Avec un jeton, PT409 veut dire « réservation expirée » : attendre ne changerait rien."""
    horloge, appels = _Horloge(), []

    def projection():
        appels.append(1)
        raise _reserve()

    with calendar_write_token("jeton"), pytest.raises(APIError):
        relancer_si_calendrier_reserve(projection, dormir=horloge.dormir, maintenant=horloge.maintenant)
    assert appels == [1] and not horloge.attentes
