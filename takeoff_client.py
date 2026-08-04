from typing import Any, Dict, Optional

import requests

from config import get_settings


class TakeoffApiError(Exception):
    def __init__(self, status_code: int, url: str, body: str):
        self.status_code = status_code
        self.url = url
        self.body = body
        super().__init__(f"Takeoff API error {status_code} for {url}: {body[:500]}")


class TakeoffClient:
    """Client for the TakeOff Integrators API (https://webapi.takeoffcrm.com).

    Auth: pass either an api_key (sent as `x-api-key` header) or a JWT token
    (sent as `Authorization: Bearer ...`), per the API's security schemes.
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None, token: Optional[str] = None):
        if not api_key and not token:
            raise ValueError("Provide either api_key or token for authentication")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "takeoff-api-client/1.0",
            "Accept": "application/json",
        })

    def _build_headers(self) -> Dict[str, str]:
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        merged_headers = {**self._build_headers(), **headers}
        response = self.session.request(method, url, headers=merged_headers, **kwargs)
        if not response.ok:
            raise TakeoffApiError(response.status_code, url, response.text)
        return response

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def get_json(self, path: str, **kwargs) -> Any:
        return self.get(path, **kwargs).json()

    def post_json(self, path: str, **kwargs) -> Any:
        return self.post(path, **kwargs).json()

    @classmethod
    def from_settings(cls) -> "TakeoffClient":
        settings = get_settings()
        return cls(base_url=settings.takeoff_base_url, api_key=settings.takeoff_api_key, token=settings.takeoff_token)


if __name__ == "__main__":
    client = TakeoffClient.from_settings()
    # Smoke test: /api/me/infos returns the authenticated user, good for verifying credentials.
    data = client.get_json("/api/me/infos")
    print(data)
