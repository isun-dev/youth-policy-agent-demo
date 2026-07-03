from __future__ import annotations

from collections.abc import Callable

from app.policy_detail_tool import PolicyDetailTool, PolicyDetailToolError
from app.schemas import Policy


def enrich_policies_with_detail_pages(
    policies: list[Policy],
    detail_limit: int = 10,
    progress_callback: Callable[[str], None] | None = None,
    detail_tool: PolicyDetailTool | None = None,
) -> list[Policy]:
    """Fetch official detail pages for a bounded number of policies."""
    if detail_limit <= 0:
        return policies

    tool = detail_tool or PolicyDetailTool()
    enriched_policies: list[Policy] = []
    fetched_count = 0

    for policy in policies:
        detail_url = policy.source_url or policy.apply_url
        if not detail_url or fetched_count >= detail_limit:
            enriched_policies.append(policy)
            continue

        fetched_count += 1
        if progress_callback is not None:
            progress_callback(f"공식 상세 페이지에서 근거 문장을 확인하는 중입니다. ({fetched_count}/{detail_limit})")

        try:
            detail = tool.fetch(detail_url)
        except PolicyDetailToolError:
            enriched_policies.append(policy)
            continue

        if detail.fetch_status != "ok":
            enriched_policies.append(policy)
            continue

        try:
            from app.policy_normalizer import enrich_policy_with_detail_text
        except ImportError:
            enriched_policies.append(policy)
            continue

        enriched_policies.append(
            enrich_policy_with_detail_text(
                policy,
                detail_text=detail.plain_text,
                source_url=detail.source_url,
            )
        )

    return enriched_policies
