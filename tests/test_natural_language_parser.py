from __future__ import annotations

import unittest

from app.natural_language_parser import _merge_profile, parse_natural_language_input
from app.schemas import IntentCategory, UserProfile


class NaturalLanguageParserTest(unittest.TestCase):
    def test_extracts_profile_and_employment_intent_from_sentence(self) -> None:
        parsed = parse_natural_language_input("26살이고 의정부 사는 구직 중 청년인데 구직지원금 있어?")

        self.assertEqual(parsed.profile.age, 26)
        self.assertEqual(parsed.profile.region, "경기도 의정부")
        self.assertEqual(parsed.profile.employment_status, "job_seeker")
        self.assertEqual(parsed.intent.category, IntentCategory.EMPLOYMENT)
        self.assertEqual(parsed.intent.target_policy_keyword, "구직지원금")

    def test_extracts_housing_intent(self) -> None:
        parsed = parse_natural_language_input("만 24세 의정부 거주자인데 월세 지원 받을 수 있어?")

        self.assertEqual(parsed.profile.age, 24)
        self.assertEqual(parsed.profile.region, "경기도 의정부")
        self.assertEqual(parsed.intent.category, IntentCategory.HOUSING)
        self.assertEqual(parsed.intent.target_policy_keyword, "월세")

    def test_avoids_treating_general_job_phrase_as_employed(self) -> None:
        parsed = parse_natural_language_input("취업하고 싶은 25세 서울 청년이야")

        self.assertIsNone(parsed.profile.employment_status)
        self.assertEqual(parsed.profile.region, "서울특별시")
        self.assertEqual(parsed.intent.category, IntentCategory.EMPLOYMENT)

    def test_merge_profile_keeps_rule_based_region_normalization(self) -> None:
        merged = _merge_profile(
            UserProfile(age=26, region="경기도 의정부", employment_status="unemployed"),
            UserProfile(age=26, region="의정부", employment_status="unemployed"),
        )

        self.assertEqual(merged.region, "경기도 의정부")


if __name__ == "__main__":
    unittest.main()
