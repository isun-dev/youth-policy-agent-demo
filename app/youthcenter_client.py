from __future__ import annotations

import os
from dataclasses import dataclass

import requests
from dotenv import load_dotenv


DEFAULT_API_KEY_PARAM = "apiKeyNm"


@dataclass(frozen=True)
class YouthCenterConfig:
    api_key: str
    base_url: str


def load_youthcenter_config() -> YouthCenterConfig:
    load_dotenv()

    api_key = os.getenv("YOUTHCENTER_API_KEY", "").strip()
    base_url = os.getenv("YOUTHCENTER_API_BASE_URL", "").strip()

    missing = []
    if not api_key:
        missing.append("YOUTHCENTER_API_KEY")
    if not base_url:
        missing.append("YOUTHCENTER_API_BASE_URL")

    if missing:
        raise ValueError(f".env에 {', '.join(missing)} 값을 설정해야 합니다.")

    return YouthCenterConfig(
        api_key=api_key,
        base_url=base_url,
    )


class YouthCenterClient:
    """Small wrapper for 온통청년 Open API calls."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url

    @classmethod
    def from_config(cls, config: YouthCenterConfig) -> "YouthCenterClient":
        return cls(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    def fetch_policies(
        self,
        page: int = 1,
        page_size: int = 20,
        extra_params: dict[str, str] | None = None,
    ) -> str:
        params = {
            DEFAULT_API_KEY_PARAM: self.api_key,
            "pageNum": page,
            "pageSize": page_size,
            "rtnType": "json",
        }
        if extra_params:
            params.update(extra_params)

        response = requests.get(self.base_url, params=params, timeout=10)
        response.raise_for_status()
        return response.text
