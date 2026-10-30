"""Pacing and bounded retries, using a virtual clock and no real HTTP."""
from unittest.mock import Mock
from datetime import datetime, timezone
import pytest
import requests
from app.services.staff_directory_client import StaffDirectoryClient, StaffDirectoryError, retry_after_seconds


def response(data=None, status=200, headers=None):
    r = Mock(status_code=status, headers=headers or {})
    r.json.return_value = {"people": []} if data is None else data
    return r


def client_for(responses, **config):
    now, starts = [0], []
    source = iter(responses)
    def get(*args, **kwargs):
        starts.append(now[0])
        item = next(source)
        if isinstance(item, Exception):
            raise item
        return item
    def sleep(seconds):
        now[0] += seconds
    session = Mock()
    session.get.side_effect = get
    settings = dict(STAFF_DIRECTORY_BASE_URL="https://staff.example", STAFF_DIRECTORY_API_KEY="secret-key")
    settings.update(config)
    return StaffDirectoryClient(settings, session=session, clock=lambda: now[0], sleep=sleep, jitter=lambda: 0), session, starts


def test_160_employees_are_paced():
    client, session, starts = client_for([response()] * 160)
    for _ in range(160):
        assert client.find_staff_by_fio("Иванов", "Иван") == []
    assert len(starts) == 160 and starts[-1] == 318
    assert min(b-a for a,b in zip(starts, starts[1:])) >= 2
    assert client.requests_made == 160
    assert session.get.call_args.kwargs["params"] == {"last_name": "Иванов", "first_name": "Иван"}
    assert session.get.call_args.kwargs["allow_redirects"] is False


def test_retries_are_also_paced_and_counted():
    client, session, starts = client_for([requests.Timeout(), response(status=500), response()])
    client.find_staff_by_fio("Иванов", "Иван", "Иванович")
    assert starts == [0, 2, 6] and client.requests_made == 3
    assert session.get.call_args.kwargs["params"]["patronymic"] == "Иванович"


@pytest.mark.parametrize("status,code", [(400,"http_400"),(401,"unauthorized"),(403,"unauthorized"),(302,"http_302"),(429,"rate_limited")])
def test_no_retry_for_client_errors_or_throttling(status, code):
    client, session, _ = client_for([response(status=status, headers={"Retry-After":"7200"})])
    with pytest.raises(StaffDirectoryError) as caught:
        client.find_staff_by_fio("Иванов", "Иван")
    assert caught.value.code == code and session.get.call_count == 1
    assert "secret-key" not in str(caught.value)
    if status == 429:
        assert caught.value.fatal and caught.value.cooldown == 7200


@pytest.mark.parametrize("data", [{},{"people":{}},{"people":[7]},{"people":[{"cardnumber":123}]},{"people":[{"fio_short":"x"*257}]}])
def test_invalid_response(data):
    client, *_ = client_for([response(data)])
    with pytest.raises(StaffDirectoryError):
        client.find_staff_by_fio("Иванов", "Иван")


def test_field_allowlist_and_leading_zeroes():
    client, *_ = client_for([response({"people":[{"cardnumber":"0012","rank":"junior","staff_id":7,"formal_department_name":None}]})])
    assert client.find_staff_by_fio("Иванов", "Иван") == [{"cardnumber":"0012","formal_department_name":None}]


@pytest.mark.parametrize("config", [{"STAFF_DIRECTORY_MAX_REQUESTS":2},{"STAFF_DIRECTORY_MAX_RUN_SECONDS":3}])
def test_run_budget(config):
    client, session, _ = client_for([response()] * 3, **config)
    client.find_staff_by_fio("Иванов", "Иван")
    client.find_staff_by_fio("Иванов", "Иван")
    with pytest.raises(StaffDirectoryError, match="run_budget_exhausted"):
        client.find_staff_by_fio("Иванов", "Иван")
    assert session.get.call_count == 2


def test_http_date_retry_after():
    assert retry_after_seconds("Thu, 29 Oct 2026 14:00:00 GMT", datetime(2026,10,29,12,tzinfo=timezone.utc)) == 7200
    assert retry_after_seconds("invalid") == 0
