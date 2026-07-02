from __future__ import annotations

from typing import Any

from app.schemas import (
    Condition,
    ConditionCheck,
    ConditionStatus,
    EligibilityResult,
    EligibilityStatus,
    Policy,
    UserProfile,
)
from app.slot_questions import label_for_field, question_for_condition


def check_eligibility(profile: UserProfile, policy: Policy) -> EligibilityResult:
    condition_checks = [
        _check_condition(profile, policy, condition)
        for condition in _conditions_for_policy(policy)
    ]
    matched = [
        check.label
        for check in condition_checks
        if check.status == ConditionStatus.MATCHED
    ]
    failed = [
        check.label
        for check in condition_checks
        if check.status == ConditionStatus.FAILED
    ]
    missing = [
        check.field
        for check in condition_checks
        if check.status == ConditionStatus.MISSING
    ]
    reasons = [
        check.reason
        for check in condition_checks
        if check.reason
    ]

    if failed:
        status = EligibilityStatus.NOT_ELIGIBLE_LIKELY
    elif missing:
        status = EligibilityStatus.NEED_MORE_INFO
    else:
        status = EligibilityStatus.ELIGIBLE_LIKELY

    return EligibilityResult(
        policy=policy,
        status=status,
        matched_conditions=matched,
        failed_conditions=failed,
        missing_fields=missing,
        condition_checks=condition_checks,
        reasons=reasons,
    )


def check_all(profile: UserProfile, policies: list[Policy]) -> list[EligibilityResult]:
    return [check_eligibility(profile, policy) for policy in policies]


def _conditions_for_policy(policy: Policy) -> list[Condition]:
    conditions = [
        Condition(
            field="age",
            operator="between",
            value=[policy.age_min, policy.age_max],
            label="나이",
        ),
        Condition(
            field="region",
            operator="region_any",
            value=policy.region,
            label="지역",
        ),
        Condition(
            field="employment_status",
            operator="in",
            value=policy.employment_status,
            label="취업상태",
        ),
    ]
    conditions.extend(
        Condition(
            field=field,
            operator="required",
            label=label_for_field(field),
        )
        for field in policy.required_fields
    )
    return _merge_conditions(conditions, policy.conditions)


def _merge_conditions(
    base_conditions: list[Condition],
    extra_conditions: list[Condition],
) -> list[Condition]:
    conditions_by_field = {condition.field: condition for condition in base_conditions}
    for condition in extra_conditions:
        conditions_by_field[condition.field] = condition
    return list(conditions_by_field.values())


def _check_condition(profile: UserProfile, policy: Policy, condition: Condition) -> ConditionCheck:
    label = condition.label or label_for_field(condition.field)
    question = condition.question or question_for_condition(condition, policy_name=policy.name)

    if condition.field == "age":
        return _check_age_condition(profile, policy, condition, label, question)
    if condition.field == "region":
        return _check_region_condition(profile, policy, condition, label, question)
    if condition.field == "employment_status":
        return _check_employment_condition(profile, policy, condition, label, question)

    return _check_required_extra_condition(profile, policy, condition, label, question)


def _check_age_condition(
    profile: UserProfile,
    policy: Policy,
    condition: Condition,
    label: str,
    question: str,
) -> ConditionCheck:
    age_min, age_max = _bounds(condition.value)
    if profile.age is None:
        return _condition_check(condition, label, ConditionStatus.MISSING, question=question)
    if age_min is not None and profile.age < age_min:
        return _condition_check(
            condition,
            label,
            ConditionStatus.FAILED,
            question=question,
            reason=f"{_topic(policy.name)} 만 {age_min}세 이상이 대상입니다.",
        )
    if age_max is not None and profile.age > age_max:
        return _condition_check(
            condition,
            label,
            ConditionStatus.FAILED,
            question=question,
            reason=f"{_topic(policy.name)} 만 {age_max}세 이하가 대상입니다.",
        )
    return _condition_check(condition, label, ConditionStatus.MATCHED, question=question)


def _check_region_condition(
    profile: UserProfile,
    policy: Policy,
    condition: Condition,
    label: str,
    question: str,
) -> ConditionCheck:
    regions = _as_list(condition.value)
    if not profile.region:
        return _condition_check(condition, label, ConditionStatus.MISSING, question=question)
    if regions and "전국" not in regions and not any(region in profile.region for region in regions):
        return _condition_check(
            condition,
            label,
            ConditionStatus.FAILED,
            question=question,
            reason=f"{_topic(policy.name)} {', '.join(regions)} 대상 정책입니다.",
        )
    return _condition_check(condition, label, ConditionStatus.MATCHED, question=question)


def _check_employment_condition(
    profile: UserProfile,
    policy: Policy,
    condition: Condition,
    label: str,
    question: str,
) -> ConditionCheck:
    allowed_statuses = _as_list(condition.value)
    if not profile.employment_status:
        return _condition_check(condition, label, ConditionStatus.MISSING, question=question)
    if allowed_statuses and profile.employment_status not in allowed_statuses:
        return _condition_check(
            condition,
            label,
            ConditionStatus.FAILED,
            question=question,
            reason=f"{policy.name}의 대상 취업상태와 현재 입력값이 다릅니다.",
        )
    return _condition_check(condition, label, ConditionStatus.MATCHED, question=question)


def _check_required_extra_condition(
    profile: UserProfile,
    policy: Policy,
    condition: Condition,
    label: str,
    question: str,
) -> ConditionCheck:
    value = profile.extra.get(condition.field)
    if condition.field not in profile.extra or value is None:
        return _condition_check(condition, label, ConditionStatus.MISSING, question=question)
    if value is False:
        return _condition_check(
            condition,
            label,
            ConditionStatus.FAILED,
            question=question,
            reason=f"{_topic(policy.name)} {label} 조건을 충족해야 합니다.",
        )
    return _condition_check(condition, label, ConditionStatus.MATCHED, question=question)


def _condition_check(
    condition: Condition,
    label: str,
    status: ConditionStatus,
    question: str | None = None,
    reason: str = "",
) -> ConditionCheck:
    return ConditionCheck(
        field=condition.field,
        label=label,
        status=status,
        question=question,
        reason=reason,
        source_text=condition.source_text,
        source_url=condition.source_url,
    )


def _bounds(value: Any) -> tuple[int | None, int | None]:
    values = _as_list(value)
    if not values:
        return None, None
    lower = values[0] if isinstance(values[0], int) else None
    upper = values[1] if len(values) > 1 and isinstance(values[1], int) else None
    return lower, upper


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _topic(policy_name: str) -> str:
    return f"{policy_name}{'은' if _has_final_consonant(policy_name) else '는'}"


def _has_final_consonant(value: str) -> bool:
    if not value:
        return False

    last_character = value[-1]
    code = ord(last_character)
    if not 0xAC00 <= code <= 0xD7A3:
        return True

    return (code - 0xAC00) % 28 != 0
