from __future__ import annotations

import json
from pathlib import Path

from app.schemas import IntentCategory, Policy, UserIntent, UserProfile


INTENT_POLICY_KEYWORDS = {
    IntentCategory.EMPLOYMENT: [
        "구직",
        "취업",
        "면접",
        "일자리",
        "일경험",
        "직업훈련",
        "고용",
    ],
    IntentCategory.HOUSING: [
        "월세",
        "전세",
        "보증금",
        "보증료",
        "주거",
        "주택",
        "임차",
        "청약",
    ],
    IntentCategory.SAVINGS: [
        "적금",
        "저축",
        "통장",
        "자산형성",
        "목돈",
    ],
    IntentCategory.EDUCATION: [
        "학자금",
        "교육",
        "대학",
        "자격증",
        "시험",
        "응시료",
    ],
    IntentCategory.BUSINESS: [
        "창업",
        "사업자",
        "예비창업",
        "사업계획",
    ],
}


def load_policies(path: Path) -> list[Policy]:
    with path.open(encoding="utf-8") as file:
        raw_policies = json.load(file)

    return [Policy.model_validate(policy) for policy in raw_policies]


def retrieve_policies(
    profile: UserProfile,
    policies: list[Policy],
    intent: UserIntent | None = None,
) -> list[Policy]:
    """Return broad candidates. Detailed filtering happens in eligibility.py."""
    if not profile.region:
        return _apply_intent_filter(policies, intent)

    region_candidates = []
    for policy in policies:
        if "전국" in policy.region or _matches_region(profile.region, policy.region):
            region_candidates.append(policy)

    return _apply_intent_filter(region_candidates, intent)


def _matches_region(user_region: str, policy_regions: list[str]) -> bool:
    return any(
        region in user_region or user_region in region
        for region in policy_regions
    )


def _apply_intent_filter(policies: list[Policy], intent: UserIntent | None) -> list[Policy]:
    if intent is None or intent.category == IntentCategory.ALL:
        return policies

    target_matches = [
        policy
        for policy in policies
        if intent.target_policy_keyword and _policy_contains(policy, [intent.target_policy_keyword])
    ]
    category_matches = [
        policy
        for policy in policies
        if _policy_contains(policy, INTENT_POLICY_KEYWORDS.get(intent.category, []))
    ]

    filtered = _deduplicate(target_matches + category_matches)
    return filtered or policies


def _policy_contains(policy: Policy, keywords: list[str]) -> bool:
    text = " ".join([policy.name, policy.description, policy.benefit])
    return any(keyword in text for keyword in keywords)


def _deduplicate(policies: list[Policy]) -> list[Policy]:
    deduplicated = []
    seen_policy_ids: set[str] = set()
    for policy in policies:
        if policy.id in seen_policy_ids:
            continue
        seen_policy_ids.add(policy.id)
        deduplicated.append(policy)
    return deduplicated
