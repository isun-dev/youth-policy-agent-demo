from __future__ import annotations

from collections.abc import Mapping
import os
import re


REDACTED_SECRET = "[REDACTED]"
SECRET_NAME_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|passwd|credential|authorization|auth)"
)
SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)"
    r"((?:OPENAI_API_KEY|YOUTHCENTER_API_KEY|DEMO_PASSWORD|apiKeyNm|apiKey|api_key|"
    r"serviceKey|serviceKeyNm|token|secret|password|auth)"
    r"\s*[=:]\s*)"
    r"[^&\s,'\")]+"
)
BEARER_TOKEN_PATTERN = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+")
AUTHORIZATION_HEADER_PATTERN = re.compile(
    r"(?i)(authorization\s*:\s*(?:bearer\s+)?)"
    r"[A-Za-z0-9._~+/=-]+"
)


def redact_sensitive_text(
    text: object,
    extra_values: list[str] | tuple[str, ...] | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Return text with known secret-looking values removed."""
    redacted = str(text)

    for value in [*_secret_env_values(environ or os.environ), *(extra_values or [])]:
        if not value:
            continue
        redacted = redacted.replace(value, REDACTED_SECRET)

    redacted = AUTHORIZATION_HEADER_PATTERN.sub(rf"\1{REDACTED_SECRET}", redacted)
    redacted = BEARER_TOKEN_PATTERN.sub(rf"\1{REDACTED_SECRET}", redacted)
    return SENSITIVE_ASSIGNMENT_PATTERN.sub(rf"\1{REDACTED_SECRET}", redacted)


def _secret_env_values(environ: Mapping[str, str]) -> list[str]:
    values: list[str] = []
    for name, value in environ.items():
        if not value or len(value) < 4:
            continue
        if SECRET_NAME_PATTERN.search(name):
            values.append(value)
    return values
