from __future__ import annotations

from pathlib import Path

from app.answer_generator import generate_answer
from app.eligibility import check_all
from app.policy_sources import (
    SOURCE_COMBINED,
    load_gyeonggi_api_policies,
    load_policies_from_source,
    load_youthcenter_api_policies,
)
from app.retriever import load_policies, retrieve_policies
from app.schemas import Policy, UserIntent, UserProfile
from app.slot_filling import (
    choose_slot_filling_result,
    choose_slot_filling_result_by_user,
    fill_slots_for_result,
    should_continue_slot_filling,
)


def run_agent(
    profile: UserProfile,
    policy_path: Path,
    slot_fill: bool = False,
    intent: UserIntent | None = None,
) -> str:
    policies = load_policies(policy_path)
    return run_agent_with_policies(profile, policies, slot_fill=slot_fill, intent=intent)


def run_agent_from_youthcenter_api(
    profile: UserProfile,
    page_size: int = 20,
    pages: int = 5,
    slot_fill: bool = False,
    intent: UserIntent | None = None,
) -> str:
    policies = load_youthcenter_api_policies(page_size=page_size, pages=pages)
    return run_agent_with_policies(profile, policies, slot_fill=slot_fill, intent=intent)


def run_agent_from_gyeonggi_api(
    profile: UserProfile,
    page_size: int = 20,
    pages: int = 5,
    slot_fill: bool = False,
    intent: UserIntent | None = None,
    fetch_details: bool = True,
    detail_limit: int = 10,
) -> str:
    policies = load_gyeonggi_api_policies(
        page_size=page_size,
        pages=pages,
        fetch_details=fetch_details,
        detail_limit=detail_limit,
    )
    return run_agent_with_policies(profile, policies, slot_fill=slot_fill, intent=intent)


def run_agent_from_combined_api(
    profile: UserProfile,
    page_size: int = 20,
    pages: int = 5,
    slot_fill: bool = False,
    intent: UserIntent | None = None,
    fetch_details: bool = True,
    detail_limit: int = 10,
) -> str:
    policies = load_policies_from_source(
        SOURCE_COMBINED,
        sample_path=Path("data/policies.sample.json"),
        page_size=page_size,
        pages=pages,
        gyeonggi_fetch_details=fetch_details,
        gyeonggi_detail_limit=detail_limit,
    )
    return run_agent_with_policies(profile, policies, slot_fill=slot_fill, intent=intent)


def run_agent_with_policies(
    profile: UserProfile,
    policies: list[Policy],
    slot_fill: bool = False,
    intent: UserIntent | None = None,
) -> str:
    candidates = retrieve_policies(profile, policies, intent=intent)
    results = check_all(profile, candidates)
    if slot_fill:
        checked_policy_ids: set[str] = set()
        while True:
            slot_result = choose_slot_filling_result_by_user(
                results,
                excluded_policy_ids=checked_policy_ids,
            )
            if slot_result is None:
                break

            profile = fill_slots_for_result(profile, slot_result)
            checked_policy_ids.add(slot_result.policy.id)
            results = check_all(profile, candidates)

            if choose_slot_filling_result(results, excluded_policy_ids=checked_policy_ids) is None:
                break
            if not should_continue_slot_filling():
                break

    return generate_answer(profile, results)
