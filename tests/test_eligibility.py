from __future__ import annotations

import unittest
from pathlib import Path

from app.eligibility import check_eligibility
from app.retriever import load_policies
from app.schemas import EligibilityStatus, Policy, UserProfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "data" / "policies.sample.json"


class EligibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policies = {policy.id: policy for policy in load_policies(POLICY_PATH)}

    def test_gyeonggi_interview_support_needs_interview_experience(self) -> None:
        profile = UserProfile(age=26, region="경기도", employment_status="job_seeker")

        result = check_eligibility(profile, self.policies["gyeonggi_interview_support"])

        self.assertEqual(result.status, EligibilityStatus.NEED_MORE_INFO)
        self.assertIn("나이", result.matched_conditions)
        self.assertIn("지역", result.matched_conditions)
        self.assertIn("취업상태", result.matched_conditions)
        self.assertIn("interview_experience", result.missing_fields)

    def test_gyeonggi_basic_income_fails_age_for_26_year_old(self) -> None:
        profile = UserProfile(age=26, region="경기도", employment_status="job_seeker")

        result = check_eligibility(profile, self.policies["gyeonggi_youth_basic_income"])

        self.assertEqual(result.status, EligibilityStatus.NOT_ELIGIBLE_LIKELY)
        self.assertIn("나이", result.failed_conditions)

    def test_employed_only_policy_fails_job_seeker(self) -> None:
        profile = UserProfile(age=26, region="경기도", employment_status="job_seeker")

        result = check_eligibility(profile, self.policies["gyeonggi_youth_welfare_points"])

        self.assertEqual(result.status, EligibilityStatus.NOT_ELIGIBLE_LIKELY)
        self.assertIn("취업상태", result.failed_conditions)

    def test_extra_false_fails_required_condition(self) -> None:
        policy = Policy(
            id="lease_support",
            name="전세보증금반환보증 보증료 지원",
            region=["전국"],
            age_min=19,
            age_max=34,
            employment_status=["unemployed"],
            required_fields=["housing_status", "lease_contract", "lease_deposit"],
        )
        profile = UserProfile(
            age=26,
            region="경기도 의정부",
            employment_status="unemployed",
            extra={
                "housing_status": True,
                "lease_contract": False,
                "lease_deposit": None,
            },
        )

        result = check_eligibility(profile, policy)

        self.assertEqual(result.status, EligibilityStatus.NOT_ELIGIBLE_LIKELY)
        self.assertIn("주거 상태", result.matched_conditions)
        self.assertIn("임대차 계약", result.failed_conditions)
        self.assertIn("lease_deposit", result.missing_fields)

    def test_reason_uses_natural_topic_marker(self) -> None:
        policy = Policy(
            id="kua",
            name="국민취업지원제도",
            region=["전국"],
            age_min=15,
            age_max=69,
            employment_status=["job_seeker"],
            required_fields=["recent_employment_history"],
        )
        profile = UserProfile(
            age=26,
            region="경기도",
            employment_status="job_seeker",
            extra={"recent_employment_history": False},
        )

        result = check_eligibility(profile, policy)

        self.assertIn("국민취업지원제도는 최근 취업 이력 조건을 충족해야 합니다.", result.reasons)


if __name__ == "__main__":
    unittest.main()
