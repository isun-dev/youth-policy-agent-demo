from __future__ import annotations

from dataclasses import dataclass
import re

from app.input_parser import EMPLOYMENT_STATUS_ALIASES
from app.sensitive import redact_sensitive_text
from app.schemas import IntentCategory, UserIntent, UserProfile


@dataclass(frozen=True)
class ParsedNaturalLanguageInput:
    profile: UserProfile
    intent: UserIntent
    warning: str | None = None


REGION_ALIASES = {
    "의정부시": "경기도 의정부",
    "의정부": "경기도 의정부",
    "수원시": "경기도 수원",
    "수원": "경기도 수원",
    "성남시": "경기도 성남",
    "성남": "경기도 성남",
    "고양시": "경기도 고양",
    "고양": "경기도 고양",
    "용인시": "경기도 용인",
    "용인": "경기도 용인",
    "부천시": "경기도 부천",
    "부천": "경기도 부천",
    "안양시": "경기도 안양",
    "안양": "경기도 안양",
    "남양주시": "경기도 남양주",
    "남양주": "경기도 남양주",
    "화성시": "경기도 화성",
    "화성": "경기도 화성",
    "서울": "서울특별시",
    "서울시": "서울특별시",
    "부산": "부산광역시",
    "대구": "대구광역시",
    "인천": "인천광역시",
    "광주": "광주광역시",
    "대전": "대전광역시",
    "울산": "울산광역시",
    "세종": "세종특별자치시",
    "경기": "경기도",
    "경기도": "경기도",
    "강원": "강원특별자치도",
    "충북": "충청북도",
    "충남": "충청남도",
    "전북": "전북특별자치도",
    "전남": "전라남도",
    "경북": "경상북도",
    "경남": "경상남도",
    "제주": "제주특별자치도",
}

INTENT_KEYWORDS = {
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
    IntentCategory.EMPLOYMENT: [
        "구직지원금",
        "취업지원",
        "취업",
        "구직",
        "취준",
        "면접",
        "일자리",
        "일경험",
        "직업훈련",
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
        "대학",
        "재학",
        "휴학",
        "졸업",
        "교육",
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

TARGET_POLICY_KEYWORDS = [
    "전세보증금",
    "보증료",
    "청년월세",
    "월세",
    "면접수당",
    "구직지원금",
    "국민취업지원제도",
    "청년내일",
    "청약통장",
]


def parse_natural_language_input(
    text: str,
    use_llm: bool = False,
) -> ParsedNaturalLanguageInput:
    rule_based = parse_natural_language_input_rule_based(text)
    if not use_llm:
        return rule_based

    try:
        from app.llm_parser import parse_natural_language_input_with_llm

        llm_profile, llm_intent = parse_natural_language_input_with_llm(text)
    except Exception as error:  # noqa: BLE001 - the caller should continue with rule parsing.
        return ParsedNaturalLanguageInput(
            profile=rule_based.profile,
            intent=rule_based.intent,
            warning=f"LLM 해석을 사용하지 못해 규칙 기반 해석으로 진행합니다: {redact_sensitive_text(error)}",
        )

    return ParsedNaturalLanguageInput(
        profile=_merge_profile(rule_based.profile, llm_profile),
        intent=_merge_intent(rule_based.intent, llm_intent),
    )


def parse_natural_language_input_rule_based(text: str) -> ParsedNaturalLanguageInput:
    profile = UserProfile(
        age=_extract_age(text),
        region=_extract_region(text),
        employment_status=_extract_employment_status(text),
        extra={},
    )
    intent = _extract_intent(text)
    return ParsedNaturalLanguageInput(profile=profile, intent=intent)


def _extract_age(text: str) -> int | None:
    match = re.search(r"(?:만\s*)?(\d{1,3})\s*(?:살|세)", text)
    if not match:
        return None

    age = int(match.group(1))
    if 0 <= age <= 120:
        return age
    return None


def _extract_region(text: str) -> str | None:
    for alias in sorted(REGION_ALIASES, key=len, reverse=True):
        if alias in text:
            return REGION_ALIASES[alias]
    return None


def _extract_employment_status(text: str) -> str | None:
    extra_aliases = {
        "취준": "job_seeker",
        "취준 중": "job_seeker",
        "일 안 함": "unemployed",
        "일 안해": "unemployed",
        "일 안 하고": "unemployed",
        "직장 없어": "unemployed",
        "회사 다님": "employed",
        "일하는 중": "employed",
    }
    aliases = {
        key: value
        for key, value in EMPLOYMENT_STATUS_ALIASES.items()
        if key != "취업"
    }
    aliases.update(extra_aliases)

    for alias in sorted(aliases, key=len, reverse=True):
        if alias in text:
            return aliases[alias]
    return None


def _extract_intent(text: str) -> UserIntent:
    target_policy_keyword = _extract_target_policy_keyword(text)
    category_scores = {
        category: sum(1 for keyword in keywords if keyword in text)
        for category, keywords in INTENT_KEYWORDS.items()
    }
    category, score = max(
        category_scores.items(),
        key=lambda item: item[1],
        default=(IntentCategory.ALL, 0),
    )
    if score == 0:
        category = IntentCategory.ALL

    confidence = min(1.0, 0.35 + (score * 0.2)) if score else 0.2
    if target_policy_keyword:
        confidence = max(confidence, 0.75)

    return UserIntent(
        category=category,
        target_policy_keyword=target_policy_keyword,
        confidence=confidence,
        source="rule",
    )


def _extract_target_policy_keyword(text: str) -> str | None:
    for keyword in TARGET_POLICY_KEYWORDS:
        if keyword in text:
            return keyword
    return None


def _merge_profile(rule_profile: UserProfile, llm_profile: UserProfile) -> UserProfile:
    return UserProfile(
        age=llm_profile.age if llm_profile.age is not None else rule_profile.age,
        region=rule_profile.region or llm_profile.region,
        employment_status=llm_profile.employment_status or rule_profile.employment_status,
        extra={**rule_profile.extra, **llm_profile.extra},
    )


def _merge_intent(rule_intent: UserIntent, llm_intent: UserIntent) -> UserIntent:
    category = (
        llm_intent.category
        if llm_intent.category != IntentCategory.ALL
        else rule_intent.category
    )
    return UserIntent(
        category=category,
        target_policy_keyword=llm_intent.target_policy_keyword or rule_intent.target_policy_keyword,
        confidence=max(rule_intent.confidence, llm_intent.confidence),
        source=llm_intent.source,
    )
