from __future__ import annotations

from pathlib import Path

from app.answer_generator import generate_answer
from app.eligibility import check_all
from app.gyeonggi_client import GYEONGGI_JOB_ENDPOINTS, GyeonggiClient, load_gyeonggi_config
from app.policy_detail_enricher import enrich_policies_with_detail_pages
from app.policy_normalizer import normalize_gyeonggi_job_response, normalize_youthcenter_response
from app.retriever import load_policies, retrieve_policies
from app.schemas import Policy, UserIntent, UserProfile
from app.slot_filling import (
    choose_slot_filling_result,
    choose_slot_filling_result_by_user,
    fill_slots_for_result,
    should_continue_slot_filling,
)
from app.youthcenter_client import YouthCenterClient, load_youthcenter_config


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
    config = load_youthcenter_config()
    client = YouthCenterClient.from_config(config)
    policies: list[Policy] = []
    seen_policy_ids: set[str] = set()

    for page in range(1, pages + 1):
        response_text = client.fetch_policies(page=page, page_size=page_size)
        for policy in normalize_youthcenter_response(response_text):
            if policy.id in seen_policy_ids:
                continue
            seen_policy_ids.add(policy.id)
            policies.append(policy)

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
    config = load_gyeonggi_config()
    client = GyeonggiClient.from_config(config)
    policies: list[Policy] = []
    seen_policy_ids: set[str] = set()

    for endpoint in GYEONGGI_JOB_ENDPOINTS:
        for page in range(1, pages + 1):
            response_text = client.fetch_endpoint(endpoint, page=page, page_size=page_size)
            for policy in normalize_gyeonggi_job_response(response_text, endpoint=endpoint):
                if policy.id in seen_policy_ids:
                    continue
                seen_policy_ids.add(policy.id)
                policies.append(policy)

    if fetch_details:
        policies = enrich_policies_with_detail_pages(policies, detail_limit=detail_limit)

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
