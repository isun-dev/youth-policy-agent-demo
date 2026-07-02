from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from app.schemas import EligibilityResult, UserProfile
from app.slot_questions import question_for_field


def choose_slot_filling_result(
    results: list[EligibilityResult],
    excluded_policy_ids: set[str] | None = None,
) -> EligibilityResult | None:
    excluded_policy_ids = excluded_policy_ids or set()

    for result in results:
        if result.policy.id not in excluded_policy_ids and result.missing_fields:
            return result

    return None


def choose_slot_filling_result_by_user(
    results: list[EligibilityResult],
    excluded_policy_ids: set[str] | None = None,
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> EligibilityResult | None:
    candidates = _slot_filling_candidates(results, excluded_policy_ids=excluded_policy_ids)
    if not candidates:
        return None

    print_func("")
    print_func("[정책 선택] 자세히 확인할 정책을 선택하세요.")
    for index, result in enumerate(candidates, start=1):
        fields = ", ".join(result.missing_fields)
        print_func(f"{index}. {result.policy.name}")
        print_func(f"   - 추가 확인: {fields}")

    while True:
        try:
            answer = input_func("번호를 입력하세요. 건너뛰려면 0을 입력하세요: ")
        except EOFError:
            return None

        selected_index = _parse_policy_selection(answer, max_index=len(candidates))
        if selected_index is None:
            print_func("목록에 있는 번호 또는 0을 입력해 주세요.")
            continue
        if selected_index == 0:
            return None
        return candidates[selected_index - 1]


def fill_slots_for_result(
    profile: UserProfile,
    result: EligibilityResult,
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> UserProfile:
    print_func("")
    print_func(f"[추가 확인] {result.policy.name}")

    updated_extra = dict(profile.extra)
    for field in result.missing_fields:
        answer = _ask_slot_question(
            field,
            policy_name=result.policy.name,
            input_func=input_func,
        )
        updated_extra[field] = answer

    return profile.model_copy(update={"extra": updated_extra})


def should_continue_slot_filling(
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> bool:
    while True:
        print_func("")
        try:
            answer = input_func("[계속 확인] 다른 정책도 추가 확인할까요? (예/아니오): ")
        except EOFError:
            return False
        parsed = parse_slot_answer(answer)
        if parsed is True:
            return True
        if parsed is False:
            return False
        print_func("예 또는 아니오로 입력해 주세요.")


def parse_slot_answer(value: str) -> Optional[bool]:
    cleaned = value.strip().lower()
    yes_values = {"예", "네", "y", "yes", "true", "맞아", "맞음"}
    no_values = {"아니오", "아니요", "아니", "n", "no", "false", "아님"}
    unknown_values = {"모름", "몰라", "unknown", "u", "?"}

    if cleaned in yes_values:
        return True
    if cleaned in no_values:
        return False
    if cleaned in unknown_values:
        return None

    return None


def _slot_filling_candidates(
    results: list[EligibilityResult],
    excluded_policy_ids: set[str] | None = None,
) -> list[EligibilityResult]:
    excluded_policy_ids = excluded_policy_ids or set()
    return [
        result
        for result in results
        if result.policy.id not in excluded_policy_ids and result.missing_fields
    ]


def _parse_policy_selection(value: str, max_index: int) -> int | None:
    cleaned = value.strip()
    if not cleaned.isdigit():
        return None
    selected_index = int(cleaned)
    if 0 <= selected_index <= max_index:
        return selected_index
    return None


def _ask_slot_question(
    field: str,
    policy_name: str,
    input_func: Callable[[str], str],
) -> Optional[bool]:
    while True:
        try:
            answer = input_func(
                f"{question_for_field(field, policy_name=policy_name)} (예/아니오/모름): "
            )
        except EOFError:
            return None
        cleaned = answer.strip().lower()
        if cleaned in {"예", "네", "y", "yes", "true", "맞아", "맞음"}:
            return True
        if cleaned in {"아니오", "아니요", "아니", "n", "no", "false", "아님"}:
            return False
        if cleaned in {"모름", "몰라", "unknown", "u", "?"}:
            return None
        print("예, 아니오, 모름 중 하나로 입력해 주세요.")
