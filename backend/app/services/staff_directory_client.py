"""Bounded, sequential requests to the staff directory. No implicit HTTP retries."""
from __future__ import annotations

import math
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter

FIELD_LIMITS = {
    "cardnumber": 128,
    "fio_short": 256,
    "position_name": 256,
    "position_short_name": 256,
    "formal_department_short_name": 256,
    "formal_department_name": None,
}


class StaffDirectoryError(Exception):
    """Safe error code: never includes the URL, API key or response body."""

    def __init__(self, code, *, fatal=False, cooldown=0):
        super().__init__(code)
        self.code = code
        self.fatal = fatal
        self.cooldown = cooldown


def retry_after_seconds(value, now=None):
    if not value:
        return 0
    try:
        if value.strip().isdigit():
            return min(int(value.strip()), 31536000)
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return min(max(0, (parsed - (now or datetime.now(timezone.utc))).total_seconds()), 31536000)
    except (ValueError, TypeError, OverflowError):
        return 0


def validate_people(data):
    if not isinstance(data, dict) or not isinstance(data.get("people"), list):
        raise StaffDirectoryError("invalid_response")
    people = []
    for item in data["people"]:
        if not isinstance(item, dict):
            raise StaffDirectoryError("invalid_response")
        selected = {}
        for key, limit in FIELD_LIMITS.items():
            if key not in item:
                continue
            value = item[key]
            if value is not None and not isinstance(value, str):
                raise StaffDirectoryError("invalid_field_type")
            value = value.strip() if value is not None else None
            if limit and value and len(value) > limit:
                raise StaffDirectoryError("field_too_long")
            selected[key] = value or None
        people.append(selected)
    return people


class StaffDirectoryClient:
    def __init__(self, config, *, session=None, clock=None, sleep=None, jitter=None):
        self.base_url = config.get("STAFF_DIRECTORY_BASE_URL", "").rstrip("/")
        self.api_key = config.get("STAFF_DIRECTORY_API_KEY", "")
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or not self.api_key:
            raise StaffDirectoryError("invalid_configuration", fatal=True)
        self.timeout = float(config.get("STAFF_DIRECTORY_TIMEOUT", 30))
        self.interval = float(config.get("STAFF_DIRECTORY_REQUEST_INTERVAL", 2))
        self.max_retries = int(config.get("STAFF_DIRECTORY_MAX_RETRIES", 2))
        self.max_requests = int(config.get("STAFF_DIRECTORY_MAX_REQUESTS", 500))
        self.max_seconds = float(config.get("STAFF_DIRECTORY_MAX_RUN_SECONDS", 1800))
        if (not all(math.isfinite(v) for v in (self.timeout, self.interval, self.max_seconds))
                or self.timeout <= 0 or self.interval < 1 or self.max_seconds <= 0
                or not 0 <= self.max_retries <= 5 or self.max_requests < 1):
            raise StaffDirectoryError("invalid_configuration", fatal=True)
        self.session = session or requests.Session()
        # All retries are paced here, never inside urllib3. Redirects are disabled too.
        if session is None:
            self.session.mount("https://", HTTPAdapter(max_retries=0))
            self.session.mount("http://", HTTPAdapter(max_retries=0))
        self.clock = clock or time.monotonic
        self.sleep = sleep or time.sleep
        self.jitter = jitter or (lambda: random.uniform(0, 0.5))
        self.deadline = self.clock() + self.max_seconds
        self.next_request_at = self.clock()
        self.requests_made = 0

    def close(self):
        self.session.close()

    def _wait(self, backoff):
        delay = max(0, self.next_request_at - self.clock(), backoff)
        if self.requests_made >= self.max_requests or self.clock() + delay >= self.deadline:
            raise StaffDirectoryError("run_budget_exhausted", fatal=True)
        # Short sleeps keep the process interruptible even after network failures.
        remaining = delay
        while remaining > 0:
            step = min(remaining, 30)
            self.sleep(step)
            remaining -= step

    def find_staff_by_fio(self, last_name, first_name, patronymic=None):
        params = {"last_name": last_name, "first_name": first_name}
        if patronymic:
            params["patronymic"] = patronymic
        for attempt in range(self.max_retries + 1):
            self._wait(0 if attempt == 0 else 2 ** attempt + self.jitter())
            self.requests_made += 1
            try:
                response = self.session.get(
                    self.base_url + "/staff/placement/public/",
                    params=params,
                    headers={"X-Api-Key": self.api_key},
                    timeout=min(self.timeout, max(0.001, self.deadline - self.clock())),
                    allow_redirects=False,
                )
            except (requests.Timeout, requests.ConnectionError):
                if attempt == self.max_retries:
                    raise StaffDirectoryError("network_error") from None
                continue
            except requests.RequestException:
                raise StaffDirectoryError("request_error") from None
            finally:
                self.next_request_at = self.clock() + self.interval + self.jitter()
            try:
                status = response.status_code
                cooldown = retry_after_seconds(response.headers.get("Retry-After"))
                if status in (401, 403):
                    raise StaffDirectoryError("unauthorized", fatal=True, cooldown=3600)
                if status == 429:
                    # Never retry a throttled request within this run.
                    raise StaffDirectoryError("rate_limited", fatal=True, cooldown=max(60, cooldown))
                if status >= 500:
                    if cooldown:
                        raise StaffDirectoryError("service_unavailable", fatal=True, cooldown=cooldown)
                    if attempt < self.max_retries:
                        continue
                    raise StaffDirectoryError("service_unavailable")
                if not 200 <= status < 300:
                    raise StaffDirectoryError("http_" + str(status))
                response.raise_for_status()
                try:
                    return validate_people(response.json())
                except ValueError:
                    raise StaffDirectoryError("invalid_json") from None
            finally:
                response.close()
