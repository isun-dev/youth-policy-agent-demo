from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from app.schemas import IntentCategory, UserIntent, UserProfile


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class LLMParserUnavailable(RuntimeError):
    pass


def parse_natural_language_input_with_llm(text: str) -> tuple[UserProfile, UserIntent]:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMParserUnavailable("OPENAI_API_KEY가 설정되어 있지 않습니다.")

    client = OpenAI(api_key=api_key)
    if hasattr(client, "responses"):
        data = _parse_with_responses_api(client, text)
    else:
        data = _parse_with_chat_completions_api(client, text)

    profile = UserProfile(
        age=data["age"],
        region=data["region"],
        employment_status=data["employment_status"],
        extra={},
    )
    intent = UserIntent(
        category=IntentCategory(data["intent_category"]),
        target_policy_keyword=data["target_policy_keyword"],
        confidence=float(data["confidence"]),
        source="llm",
    )
    return profile, intent


def _parse_with_responses_api(client: OpenAI, text: str) -> dict:
    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        instructions=_instructions(),
        input=text,
        text={
            "format": {
                "type": "json_schema",
                "name": "youth_policy_user_input",
                "strict": True,
                "schema": _json_schema(),
            }
        },
        temperature=0,
        max_output_tokens=600,
    )

    return json.loads(response.output_text)


def _parse_with_chat_completions_api(client: OpenAI, text: str) -> dict:
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        messages=[
            {"role": "system", "content": _instructions()},
            {"role": "user", "content": text},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "youth_policy_user_input",
                "strict": True,
                "schema": _json_schema(),
            },
        },
        temperature=0,
        max_tokens=600,
    )

    content = response.choices[0].message.content
    if not content:
        raise LLMParserUnavailable("LLM 응답이 비어 있습니다.")
    return json.loads(content)


def _instructions() -> str:
    return (
        "너는 한국 청년정책 자격 판정 서비스의 입력 해석기다. "
        "사용자 문장에서 나이, 거주지역, 취업상태, 정책 관심 의도를 추출한다. "
        "모르면 null 또는 all을 사용한다. 자격 가능 여부는 판단하지 않는다."
    )


def _json_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "age": {"type": ["integer", "null"], "minimum": 0, "maximum": 120},
            "region": {"type": ["string", "null"]},
            "employment_status": {
                "type": ["string", "null"],
                "enum": ["job_seeker", "unemployed", "employed", None],
            },
            "intent_category": {
                "type": "string",
                "enum": [category.value for category in IntentCategory],
            },
            "target_policy_keyword": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "age",
            "region",
            "employment_status",
            "intent_category",
            "target_policy_keyword",
            "confidence",
        ],
    }
