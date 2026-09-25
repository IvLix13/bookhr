"""Nextcloud 26 user search and Talk direct-message client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from flask import current_app


@dataclass(frozen=True)
class NextcloudUser:
    user_id: str
    display_name: str


class NextcloudError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 0, response_body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class NextcloudNotConfigured(NextcloudError):
    pass


def _settings() -> tuple[str, tuple[str, str], bool]:
    base_url = current_app.config.get("NEXTCLOUD_BASE_URL", "").rstrip("/")
    username = current_app.config.get("NEXTCLOUD_USERNAME", "")
    app_password = current_app.config.get("NEXTCLOUD_APP_PASSWORD", "")
    verify_ssl = current_app.config.get("NEXTCLOUD_VERIFY_SSL", False)
    if not base_url or not username or not app_password:
        raise NextcloudNotConfigured(
            "Nextcloud not configured: NEXTCLOUD_BASE_URL, NEXTCLOUD_USERNAME and "
            "NEXTCLOUD_APP_PASSWORD are required"
        )
    return base_url, (username, app_password), verify_ssl


def _request(method: str, path: str, **kwargs: Any) -> requests.Response:
    base_url, auth, verify_ssl = _settings()
    headers = {
        "Accept": "application/json",
        "OCS-APIRequest": "true",
        **kwargs.pop("headers", {}),
    }
    last_error: requests.RequestException | None = None
    for _attempt in range(2):
        try:
            return requests.request(
                method,
                f"{base_url}{path}",
                auth=auth,
                headers=headers,
                timeout=15,
                verify=verify_ssl,
                **kwargs,
            )
        except requests.RequestException as exc:
            last_error = exc
    raise NextcloudError(str(last_error or "Nextcloud request failed"))


def _ocs_data(response: requests.Response) -> Any:
    if not 200 <= response.status_code < 300:
        raise NextcloudError(
            "Nextcloud request failed",
            status_code=response.status_code,
            response_body=response.text[:500],
        )
    try:
        payload = response.json()
        return payload["ocs"]["data"]
    except (KeyError, TypeError, ValueError) as exc:
        raise NextcloudError(
            "Nextcloud returned an invalid OCS response",
            status_code=response.status_code,
            response_body=response.text[:500],
        ) from exc


def search_users(query: str, *, limit: int = 20) -> list[NextcloudUser]:
    """Search users exactly as the Nextcloud 26 Talk new-conversation dialog does."""
    response = _request(
        "GET",
        "/ocs/v2.php/core/autocomplete/get",
        params=[
            ("search", query),
            ("itemType", "call"),
            ("itemId", "new"),
            ("shareTypes[]", "0"),
        ],
    )
    data = _ocs_data(response)
    if not isinstance(data, list):
        raise NextcloudError(
            "Nextcloud returned an invalid user list",
            status_code=response.status_code,
            response_body=response.text[:500],
        )

    users: list[NextcloudUser] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict) or item.get("source") != "users":
            continue
        user_id = str(item.get("id") or "").strip()
        if not user_id or user_id in seen:
            continue
        display_name = str(item.get("label") or user_id).strip() or user_id
        seen.add(user_id)
        users.append(NextcloudUser(user_id=user_id, display_name=display_name))
        if len(users) >= limit:
            break
    return users


def _direct_conversation_token(user_id: str) -> str:
    response = _request(
        "POST",
        "/ocs/v2.php/apps/spreed/api/v4/room",
        data={"roomType": 1, "invite": user_id},
    )
    data = _ocs_data(response)
    token = data.get("token") if isinstance(data, dict) else None
    if not token:
        raise NextcloudError(
            "Nextcloud did not return a Talk conversation token",
            status_code=response.status_code,
            response_body=response.text[:500],
        )
    return str(token)


def send_direct_message(user_id: str, message: str) -> tuple[int, str]:
    """Create or reuse a 1:1 Talk conversation and send a message to the user."""
    try:
        conversation_token = _direct_conversation_token(user_id)
        response = _request(
            "POST",
            f"/ocs/v2.php/apps/spreed/api/v1/chat/{conversation_token}",
            data={"message": message},
        )
        return response.status_code, response.text[:500]
    except NextcloudError as exc:
        return exc.status_code, exc.response_body or str(exc)[:500]
