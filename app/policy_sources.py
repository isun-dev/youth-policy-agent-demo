from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path

from app.gyeonggi_client import GYEONGGI_JOB_ENDPOINTS, GyeonggiClient, load_gyeonggi_config
from app.policy_detail_enricher import enrich_policies_with_detail_pages
from app.retriever import load_policies
from app.schemas import Policy
from app.sensitive import redact_sensitive_text
from app.youthcenter_client import YouthCenterClient, load_youthcenter_config


SOURCE_SAMPLE = "sample"
SOURCE_YOUTHCENTER = "api"
SOURCE_YOUTHCENTER_ALIAS = "youthcenter"
SOURCE_GYEONGGI = "gyeonggi"
SOURCE_COMBINED = "combined"
VALID_POLICY_SOURCES = [
    SOURCE_SAMPLE,
    SOURCE_YOUTHCENTER,
    SOURCE_YOUTHCENTER_ALIAS,
    SOURCE_GYEONGGI,
    SOURCE_COMBINED,
]


def load_policies_from_source(
    source: str,
    sample_path: Path,
    page_size: int = 20,
    pages: int = 5,
    gyeonggi_fetch_details: bool = True,
    gyeonggi_detail_limit: int = 10,
    progress_callback: Callable[[str], None] | None = None,
) -> list[Policy]:
    if source == SOURCE_SAMPLE:
        return load_policies(sample_path)
    if source in {SOURCE_YOUTHCENTER, SOURCE_YOUTHCENTER_ALIAS}:
        return load_youthcenter_api_policies(
            page_size=page_size,
            pages=pages,
            progress_callback=progress_callback,
        )
    if source == SOURCE_GYEONGGI:
        return load_gyeonggi_api_policies(
            page_size=page_size,
            pages=pages,
            fetch_details=gyeonggi_fetch_details,
            detail_limit=gyeonggi_detail_limit,
            progress_callback=progress_callback,
        )
    if source == SOURCE_COMBINED:
        policies: list[Policy] = []
        errors: list[str] = []

        try:
            policies.extend(
                load_youthcenter_api_policies(
                    page_size=page_size,
                    pages=pages,
                    progress_callback=progress_callback,
                )
            )
        except Exception as error:  # noqa: BLE001 - combined mode should keep partial results.
            errors.append(f"온통청년 API: {redact_sensitive_text(error)}")
            _notify(progress_callback, "온통청년 API를 불러오지 못해 경기도 API 결과만 확인합니다.")

        try:
            policies.extend(
                load_gyeonggi_api_policies(
                    page_size=page_size,
                    pages=pages,
                    fetch_details=gyeonggi_fetch_details,
                    detail_limit=gyeonggi_detail_limit,
                    progress_callback=progress_callback,
                )
            )
        except Exception as error:  # noqa: BLE001 - combined mode should keep partial results.
            errors.append(f"경기도 잡아바 API: {redact_sensitive_text(error)}")
            _notify(progress_callback, "경기도 잡아바 API를 불러오지 못해 온통청년 API 결과만 확인합니다.")

        if policies:
            return _deduplicate_policies(policies)

        raise RuntimeError("통합 API 출처를 모두 불러오지 못했습니다. " + " / ".join(errors))

    raise ValueError(f"지원하지 않는 정책 데이터 출처입니다: {source}")


def load_youthcenter_api_policies(
    page_size: int = 20,
    pages: int = 5,
    progress_callback: Callable[[str], None] | None = None,
) -> list[Policy]:
    from app.policy_normalizer import normalize_youthcenter_response

    config = load_youthcenter_config()
    client = YouthCenterClient.from_config(config)
    policies: list[Policy] = []
    seen_policy_ids: set[str] = set()

    for page in range(1, pages + 1):
        if progress_callback is not None:
            progress_callback(f"온통청년 API에서 정책 데이터를 가져오는 중입니다. ({page}/{pages})")
        response_text = client.fetch_policies(page=page, page_size=page_size)
        for policy in normalize_youthcenter_response(response_text):
            if policy.id in seen_policy_ids:
                continue
            seen_policy_ids.add(policy.id)
            policies.append(policy)

    return policies


def load_gyeonggi_api_policies(
    page_size: int = 20,
    pages: int = 5,
    fetch_details: bool = True,
    detail_limit: int = 10,
    progress_callback: Callable[[str], None] | None = None,
) -> list[Policy]:
    try:
        from app.policy_normalizer import normalize_gyeonggi_job_response
    except ImportError:
        normalize_gyeonggi_job_response = _normalize_gyeonggi_job_response_fallback

    config = load_gyeonggi_config()
    client = GyeonggiClient.from_config(config)
    policies: list[Policy] = []
    seen_policy_ids: set[str] = set()

    for endpoint in GYEONGGI_JOB_ENDPOINTS:
        for page in range(1, pages + 1):
            if progress_callback is not None:
                progress_callback(f"경기도 잡아바 API에서 {endpoint} 데이터를 가져오는 중입니다. ({page}/{pages})")
            response_text = client.fetch_endpoint(endpoint, page=page, page_size=page_size)
            for policy in normalize_gyeonggi_job_response(response_text, endpoint=endpoint):
                if policy.id in seen_policy_ids:
                    continue
                seen_policy_ids.add(policy.id)
                policies.append(policy)

    if fetch_details:
        policies = enrich_policies_with_detail_pages(
            policies,
            detail_limit=detail_limit,
            progress_callback=progress_callback,
        )

    return policies


def _deduplicate_policies(policies: list[Policy]) -> list[Policy]:
    deduplicated = []
    seen_policy_ids: set[str] = set()
    for policy in policies:
        if policy.id in seen_policy_ids:
            continue
        seen_policy_ids.add(policy.id)
        deduplicated.append(policy)
    return deduplicated


def _notify(callback: Callable[[str], None] | None, message: str) -> None:
    if callback is not None:
        callback(message)


def _normalize_gyeonggi_job_response_fallback(response_text: str, endpoint: str) -> list[Policy]:
    """Minimal 경기도 OpenAPI normalizer used when deployment files are out of sync."""
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        return []

    policies = []
    for index, row in enumerate(_find_gyeonggi_rows(data), start=1):
        title = _first_row_value(
            row,
            ["PBLANC_TITLE", "POLICY_NM", "TITLE", "SUBJECT", "BIZ_NM", "name"],
        )
        detail_url = _first_row_value(
            row,
            ["DETAIL_PAGE_URL", "DETAIL_URL", "APPLY_URL", "URL", "HMPG_URL"],
        )
        region = _normalize_gyeonggi_region(
            _first_row_value(row, ["SIGUN_NM", "REGION_NM", "AREA_NM", "CITY_NM"])
        )
        period = " ".join(
            part
            for part in [
                _first_row_value(row, ["RECRUT_BEGIN_DE", "APPLY_BEGIN_DE"]),
                _first_row_value(row, ["RECRUT_END_DE", "APPLY_END_DE"]),
            ]
            if part
        )
        policies.append(
            Policy(
                id=_first_row_value(row, ["POLICY_ID", "BIZ_ID", "PBLANC_ID", "SEQ", "SN"])
                or f"{endpoint}:{title or index}:{index}",
                name=title,
                region=[region] if region else ["경기도"],
                required_fields=["official_detail_criteria"],
                evidence_texts=[text for text in [title, period] if text],
                description=title,
                apply_url=detail_url,
                source_url=detail_url or f"https://openapi.gg.go.kr/{endpoint}",
            )
        )
    return policies


def _find_gyeonggi_rows(data: object) -> list[dict]:
    if isinstance(data, list):
        rows: list[dict] = []
        for item in data:
            rows.extend(_find_gyeonggi_rows(item))
        return rows
    if not isinstance(data, dict):
        return []

    row = data.get("row")
    if isinstance(row, list):
        return [item for item in row if isinstance(item, dict)]
    if isinstance(row, dict):
        return [row]

    for value in data.values():
        found = _find_gyeonggi_rows(value)
        if found:
            return found
    return []


def _first_row_value(row: dict, keys: list[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _normalize_gyeonggi_region(value: str) -> str:
    if not value or value in {"경기도", "경기", "전체", "전지역", "경기도 전체", "경기전체"}:
        return "경기도"
    return value
