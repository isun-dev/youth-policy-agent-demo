from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.gyeonggi_client import GYEONGGI_JOB_ENDPOINTS, GyeonggiClient, load_gyeonggi_config
from app.policy_detail_enricher import enrich_policies_with_detail_pages
from app.retriever import load_policies
from app.schemas import Policy
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
        policies = [
            *load_youthcenter_api_policies(
                page_size=page_size,
                pages=pages,
                progress_callback=progress_callback,
            ),
            *load_gyeonggi_api_policies(
                page_size=page_size,
                pages=pages,
                fetch_details=gyeonggi_fetch_details,
                detail_limit=gyeonggi_detail_limit,
                progress_callback=progress_callback,
            ),
        ]
        return _deduplicate_policies(policies)

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
    from app.policy_normalizer import normalize_gyeonggi_job_response

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
