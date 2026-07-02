from __future__ import annotations

from app.schemas import EligibilityResult, EligibilityStatus, UserProfile
from app.slot_questions import questions_for_fields


STATUS_LABELS = {
    EligibilityStatus.ELIGIBLE_LIKELY: "가능성 높음",
    EligibilityStatus.NEED_MORE_INFO: "추가 확인 필요",
    EligibilityStatus.NOT_ELIGIBLE_LIKELY: "가능성 낮음",
}


def generate_answer(profile: UserProfile, results: list[EligibilityResult]) -> str:
    lines = [
        "현재 입력된 조건 기준으로 후보 정책을 판정했습니다.",
        "",
        f"- 나이: {profile.age if profile.age is not None else '미입력'}",
        f"- 지역: {profile.region or '미입력'}",
        f"- 취업상태: {profile.employment_status or '미입력'}",
        "",
    ]

    sorted_results = sorted(results, key=_sort_key)

    if not sorted_results:
        lines.append("조건에 맞는 후보 정책을 찾지 못했습니다.")
        lines.append("지역 또는 검색 범위를 넓혀 다시 확인해 주세요.")
        return "\n".join(lines).strip()

    for index, result in enumerate(sorted_results, start=1):
        policy = result.policy
        lines.extend(
            [
                f"{index}. {policy.name}",
                f"- 판정: {STATUS_LABELS[result.status]}",
                f"- 충족 조건: {_format_list(result.matched_conditions)}",
                f"- 부족한 정보: {_format_list(result.missing_fields)}",
                f"- 어려운 조건: {_format_list(result.failed_conditions)}",
            ]
        )

        if result.reasons:
            lines.append(f"- 이유: {' '.join(result.reasons)}")
        if result.status == EligibilityStatus.NEED_MORE_INFO and result.missing_fields:
            lines.append("- 추가 확인 질문:")
            for question in questions_for_fields(result.missing_fields, policy_name=policy.name):
                lines.append(f"  - {question}")
        if policy.benefit:
            lines.append(f"- 지원 내용: {policy.benefit}")
        if policy.apply_url:
            lines.append(f"- 신청 링크: {policy.apply_url}")
        if policy.source_url:
            lines.append(f"- 출처: {policy.source_url}")

        lines.append("")

    return "\n".join(lines).strip()


def _sort_key(result: EligibilityResult) -> int:
    order = {
        EligibilityStatus.ELIGIBLE_LIKELY: 0,
        EligibilityStatus.NEED_MORE_INFO: 1,
        EligibilityStatus.NOT_ELIGIBLE_LIKELY: 2,
    }
    return order[result.status]


def _format_list(values: list[str]) -> str:
    return ", ".join(values) if values else "없음"
