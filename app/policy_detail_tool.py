from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import re

import requests

from app.sensitive import redact_sensitive_text


class PolicyDetailToolError(RuntimeError):
    """Raised when an official detail page cannot be fetched safely."""


@dataclass(frozen=True)
class PolicyDetail:
    source_url: str
    plain_text: str
    fetch_status: str
    error_message: str = ""


class PolicyDetailTool:
    """Fetch official policy detail pages and extract readable text."""

    def __init__(self, timeout: int = 10, max_chars: int = 12000) -> None:
        self.timeout = timeout
        self.max_chars = max_chars

    def fetch(self, url: str) -> PolicyDetail:
        if not url:
            return PolicyDetail(source_url="", plain_text="", fetch_status="skipped")

        try:
            response = requests.get(
                url,
                timeout=self.timeout,
                headers={"User-Agent": "youth-policy-agent-demo/0.1"},
            )
            response.raise_for_status()
        except requests.RequestException as error:
            safe_error = redact_sensitive_text(error)
            raise PolicyDetailToolError(f"정책 상세 페이지 요청에 실패했습니다: {safe_error}") from None

        response.encoding = response.encoding or response.apparent_encoding
        text = _extract_visible_text(response.text)
        if not text:
            return PolicyDetail(source_url=url, plain_text="", fetch_status="empty")
        return PolicyDetail(source_url=url, plain_text=text[: self.max_chars], fetch_status="ok")


def _extract_visible_text(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    parser.close()
    return _normalize_text(" ".join(parser.text_chunks))


def _normalize_text(value: str) -> str:
    value = unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_chunks: list[str] = []
        self._ignored_tag_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._ignored_tag_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._ignored_tag_depth:
            self._ignored_tag_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_tag_depth:
            return
        text = data.strip()
        if text:
            self.text_chunks.append(text)
