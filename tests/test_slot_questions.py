from __future__ import annotations

import unittest

from app.slot_questions import question_for_field, questions_for_fields


class SlotQuestionsTest(unittest.TestCase):
    def test_known_field_returns_korean_question(self) -> None:
        self.assertEqual(
            question_for_field("interview_experience"),
            "최근 취업 면접에 참여한 적이 있나요?",
        )

    def test_unknown_field_returns_fallback_question(self) -> None:
        self.assertEqual(
            question_for_field("unknown_field"),
            "unknown_field 조건에 해당하나요?",
        )

    def test_questions_for_fields_preserves_order(self) -> None:
        questions = questions_for_fields(["income_level", "assets"])

        self.assertEqual(
            questions,
            [
                "소득 기준에 해당하나요?",
                "재산 기준에 해당하나요?",
            ],
        )

    def test_policy_text_inferred_fields_have_questions(self) -> None:
        self.assertEqual(
            question_for_field("guarantee_insurance_status"),
            "전세보증금반환보증에 가입되어 있나요?",
        )
        self.assertEqual(
            question_for_field("artist_status"),
            "예술인 또는 예술활동증명 대상자에 해당하나요?",
        )

    def test_student_loan_and_residence_questions_ask_eligibility(self) -> None:
        self.assertEqual(
            question_for_field("student_or_graduate_status"),
            "현재 재학, 휴학 중이거나 졸업 후 지원 가능 기간 안에 있나요?",
        )
        self.assertEqual(
            question_for_field("loan_history"),
            "한국장학재단 학자금 대출을 받은 적이 있나요?",
        )
        self.assertEqual(
            question_for_field("residence_period"),
            "주민등록상 해당 지역 거주기간 요건을 충족하나요?",
        )

    def test_policy_specific_question_overrides_generic_question(self) -> None:
        self.assertEqual(
            question_for_field("income_level", policy_name="전세보증금반환보증 보증료 지원"),
            "연소득이 해당 보증료 지원 기준 안에 들어오나요?",
        )
        self.assertEqual(
            question_for_field("interview_experience", policy_name="경기도 청년면접수당"),
            "최근 취업 면접에 실제로 참여했고 증빙자료가 있나요?",
        )


if __name__ == "__main__":
    unittest.main()
