from __future__ import annotations

from app.schemas import UserProfile


EMPLOYMENT_STATUS_ALIASES = {
    "취준생": "job_seeker",
    "취업준비생": "job_seeker",
    "구직자": "job_seeker",
    "구직중": "job_seeker",
    "구직 중": "job_seeker",
    "이직준비": "job_seeker",
    "이직 준비": "job_seeker",
    "이직 준비 중": "job_seeker",
    "백수": "unemployed",
    "무직": "unemployed",
    "미취업": "unemployed",
    "실업": "unemployed",
    "재직중": "employed",
    "재직 중": "employed",
    "직장인": "employed",
    "취업": "employed",
    "근로자": "employed",
}


def build_profile_from_cli() -> UserProfile:
    age = _parse_age(input("나이를 입력하세요: ").strip())
    region = input("거주 지역을 입력하세요 (예: 경기도): ").strip() or None
    status_text = input("현재 상태를 입력하세요 (예: 구직 중, 취준생, 재직 중): ").strip()

    return UserProfile(
        age=age,
        region=region,
        employment_status=normalize_employment_status(status_text),
        extra={},
    )


def normalize_employment_status(value: str | None) -> str | None:
    if not value:
        return None

    cleaned = value.strip().lower()
    if cleaned in {"job_seeker", "unemployed", "employed"}:
        return cleaned

    return EMPLOYMENT_STATUS_ALIASES.get(cleaned)


def _parse_age(value: str) -> int | None:
    if not value:
        return None

    digits = "".join(character for character in value if character.isdigit())
    if not digits:
        return None

    return int(digits)
