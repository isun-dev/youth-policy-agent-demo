from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from app.agent import run_agent, run_agent_from_youthcenter_api
from app.input_parser import build_profile_from_cli
from app.natural_language_parser import parse_natural_language_input
from app.schemas import UserIntent, UserProfile


POLICY_PATH = PROJECT_ROOT / "data" / "policies.sample.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="경기도 청년 정책 지원 자격 판정 CLI")
    parser.add_argument(
        "--source",
        choices=["sample", "api"],
        default="sample",
        help="정책 데이터 출처를 선택합니다. 기본값은 sample입니다.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=20,
        help="API에서 가져올 정책 수입니다. --source api에서만 사용합니다.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=5,
        help="API에서 가져올 페이지 수입니다. --source api에서만 사용합니다.",
    )
    parser.add_argument(
        "--slot-fill",
        action="store_true",
        help="부족한 조건을 예/아니오/모름 질문으로 추가 확인한 뒤 재판정합니다.",
    )
    parser.add_argument(
        "--text",
        help="사용자 상황을 한 문장으로 입력합니다. 예: 26살이고 의정부 사는 구직 중 청년인데 구직지원금 있어?",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="OPENAI_API_KEY가 있으면 한 문장 해석에 LLM을 함께 사용합니다.",
    )
    args = parser.parse_args()

    profile, intent = _build_profile_and_intent(args.text, use_llm=args.use_llm)

    if args.source == "api":
        answer = run_agent_from_youthcenter_api(
            profile,
            page_size=args.page_size,
            pages=args.pages,
            slot_fill=args.slot_fill,
            intent=intent,
        )
    else:
        answer = run_agent(profile, POLICY_PATH, slot_fill=args.slot_fill, intent=intent)

    print(answer)


def _build_profile_and_intent(
    text: str | None,
    use_llm: bool,
) -> tuple[UserProfile, UserIntent | None]:
    if not text:
        return build_profile_from_cli(), None

    parsed = parse_natural_language_input(text, use_llm=use_llm)
    print("[입력 해석]")
    print(f"- 나이: {parsed.profile.age if parsed.profile.age is not None else '미입력'}")
    print(f"- 지역: {parsed.profile.region or '미입력'}")
    print(f"- 취업상태: {parsed.profile.employment_status or '미입력'}")
    print(f"- 관심 분야: {parsed.intent.category.value}")
    if parsed.intent.target_policy_keyword:
        print(f"- 관심 키워드: {parsed.intent.target_policy_keyword}")
    if parsed.warning:
        print(f"- 참고: {parsed.warning}")
    print("")
    return parsed.profile, parsed.intent


if __name__ == "__main__":
    main()
