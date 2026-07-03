from __future__ import annotations

import os
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

from app.sensitive import redact_sensitive_text


GYEONGGI_API_BASE_URL = "https://openapi.gg.go.kr"
GYEONGGI_JOB_ENDPOINTS = [
    "JobFndtnEduTraing",
    "JobFndtnTosAct",
    "JobFndtnSportPolocy",
]


class GyeonggiAPIError(RuntimeError):
    """Raised when a 경기도 OpenAPI request fails safely."""


@dataclass(frozen=True)
class GyeonggiConfig:
    api_key: str
    base_url: str = GYEONGGI_API_BASE_URL


def load_gyeonggi_config() -> GyeonggiConfig:
    load_dotenv()

    api_key = os.getenv("GYEONGGI_API_KEY", "").strip()
    base_url = os.getenv("GYEONGGI_API_BASE_URL", GYEONGGI_API_BASE_URL).strip()

    if not api_key:
        raise ValueError(".env에 GYEONGGI_API_KEY 값을 설정해야 합니다.")
    if "?" in base_url:
        raise ValueError(
            "GYEONGGI_API_BASE_URL에는 쿼리스트링을 넣지 말고 기본 URL만 설정해야 합니다. "
            "예: https://openapi.gg.go.kr"
        )

    return GyeonggiConfig(api_key=api_key, base_url=base_url.rstrip("/"))


class GyeonggiClient:
    """Small wrapper for 경기도 OpenAPI calls used by the Agent."""

    def __init__(self, api_key: str, base_url: str = GYEONGGI_API_BASE_URL) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    @classmethod
    def from_config(cls, config: GyeonggiConfig) -> "GyeonggiClient":
        return cls(api_key=config.api_key, base_url=config.base_url)

    def fetch_endpoint(
        self,
        endpoint: str,
        page: int = 1,
        page_size: int = 20,
        extra_params: dict[str, str] | None = None,
    ) -> str:
        if endpoint not in GYEONGGI_JOB_ENDPOINTS:
            raise ValueError(f"지원하지 않는 경기도 OpenAPI endpoint입니다: {endpoint}")

        params = {
            "KEY": self.api_key,
            "Type": "json",
            "pIndex": page,
            "pSize": page_size,
        }
        if extra_params:
            params.update(extra_params)

        response: requests.Response | None = None
        try:
            response = requests.get(f"{self.base_url}/{endpoint}", params=params, timeout=10)
            response.raise_for_status()
        except requests.HTTPError as error:
            status_code = getattr(error.response, "status_code", None)
            if status_code is None and response is not None:
                status_code = response.status_code
            if status_code is None:
                status_code = "unknown"
            safe_error = redact_sensitive_text(error, extra_values=[self.api_key])
            raise GyeonggiAPIError(
                f"경기도 OpenAPI 응답 오류가 발생했습니다. HTTP 상태: {status_code}. {safe_error}"
            ) from None
        except requests.RequestException as error:
            safe_error = redact_sensitive_text(error, extra_values=[self.api_key])
            raise GyeonggiAPIError(f"경기도 OpenAPI 요청에 실패했습니다: {safe_error}") from None

        return response.text
