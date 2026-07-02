from __future__ import annotations

from app.schemas import EligibilityResult, EligibilityStatus, Policy, UserProfile
from app.slot_questions import label_for_field


def check_eligibility(profile: UserProfile, policy: Policy) -> EligibilityResult:
    matched: list[str] = []
    failed: list[str] = []
    missing: list[str] = []
    reasons: list[str] = []

    if profile.age is None:
        missing.append("age")
    elif policy.age_min is not None and profile.age < policy.age_min:
        failed.append("나이")
        reasons.append(f"{_topic(policy.name)} 만 {policy.age_min}세 이상이 대상입니다.")
    elif policy.age_max is not None and profile.age > policy.age_max:
        failed.append("나이")
        reasons.append(f"{_topic(policy.name)} 만 {policy.age_max}세 이하가 대상입니다.")
    else:
        matched.append("나이")

    if not profile.region:
        missing.append("region")
    elif policy.region and "전국" not in policy.region:
        if any(region in profile.region for region in policy.region):
            matched.append("지역")
        else:
            failed.append("지역")
            reasons.append(f"{_topic(policy.name)} {', '.join(policy.region)} 대상 정책입니다.")
    else:
        matched.append("지역")

    if not profile.employment_status:
        missing.append("employment_status")
    elif policy.employment_status:
        if profile.employment_status in policy.employment_status:
            matched.append("취업상태")
        else:
            failed.append("취업상태")
            reasons.append(f"{policy.name}의 대상 취업상태와 현재 입력값이 다릅니다.")
    else:
        matched.append("취업상태")

    for field in policy.required_fields:
        value = profile.extra.get(field)
        if field not in profile.extra or value is None:
            missing.append(field)
        elif value is False:
            label = label_for_field(field)
            failed.append(label)
            reasons.append(f"{_topic(policy.name)} {label} 조건을 충족해야 합니다.")
        else:
            matched.append(label_for_field(field))

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
        reasons=reasons,
    )


def check_all(profile: UserProfile, policies: list[Policy]) -> list[EligibilityResult]:
    return [check_eligibility(profile, policy) for policy in policies]


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
