from __future__ import annotations

import unittest

from app.answer_generator import generate_answer
from app.eligibility import check_eligibility
from app.schemas import Policy, UserProfile


class AnswerGeneratorTest(unittest.TestCase):
    def test_answer_includes_condition_review_table(self) -> None:
        policy = Policy(
            id="interview",
            name="청년 면접 지원",
            region=["경기도"],
            age_min=18,
            age_max=39,
            employment_status=["job_seeker"],
            required_fields=["interview_experience"],
        )
        profile = UserProfile(age=26, region="경기도", employment_status="job_seeker")
        result = check_eligibility(profile, policy)

        answer = generate_answer(profile, [result])

        self.assertIn("- 조건별 심사:", answer)
        self.assertIn("나이: 충족", answer)
        self.assertIn("면접 참여 이력: 추가 확인 필요", answer)


if __name__ == "__main__":
    unittest.main()
