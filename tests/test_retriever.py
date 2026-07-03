from __future__ import annotations

import unittest

from app.retriever import retrieve_policies
from app.schemas import IntentCategory, Policy, UserIntent, UserProfile


class RetrieverTest(unittest.TestCase):
    def test_returns_matching_region_and_national_policies(self) -> None:
        policies = [
            _policy("national", ["전국"]),
            _policy("gyeonggi", ["경기도"]),
            _policy("seoul", ["서울특별시"]),
        ]
        profile = UserProfile(age=26, region="경기도 의정부", employment_status="unemployed")

        candidates = retrieve_policies(profile, policies)

        self.assertEqual([policy.id for policy in candidates], ["national", "gyeonggi"])

    def test_does_not_fallback_to_all_policies_when_region_does_not_match(self) -> None:
        policies = [
            _policy("seoul", ["서울특별시"]),
            _policy("daegu", ["대구광역시"]),
        ]
        profile = UserProfile(age=26, region="경기도 의정부", employment_status="unemployed")

        candidates = retrieve_policies(profile, policies)

        self.assertEqual(candidates, [])

    def test_matches_gyeonggi_city_policy_without_treating_other_cities_as_match(self) -> None:
        policies = [
            _policy("seongnam", ["성남시"]),
            _policy("uijeongbu", ["의정부시"]),
            _policy("gyeonggi", ["경기도"]),
        ]
        profile = UserProfile(age=26, region="경기도 의정부", employment_status="unemployed")

        candidates = retrieve_policies(profile, policies)

        self.assertEqual([policy.id for policy in candidates], ["uijeongbu", "gyeonggi"])

    def test_filters_region_candidates_by_intent_when_possible(self) -> None:
        policies = [
            _policy("housing", ["전국"], name="청년월세지원"),
            _policy("employment", ["전국"], name="청년구직지원금"),
        ]
        profile = UserProfile(age=26, region="경기도 의정부", employment_status="unemployed")
        intent = UserIntent(category=IntentCategory.EMPLOYMENT, target_policy_keyword="구직지원금")

        candidates = retrieve_policies(profile, policies, intent=intent)

        self.assertEqual([policy.id for policy in candidates], ["employment"])

    def test_keeps_region_candidates_when_intent_has_no_match(self) -> None:
        policies = [
            _policy("national", ["전국"], name="청년 문화 지원"),
            _policy("gyeonggi", ["경기도"], name="청년 기본 지원"),
        ]
        profile = UserProfile(age=26, region="경기도 의정부", employment_status="unemployed")
        intent = UserIntent(category=IntentCategory.HOUSING)

        candidates = retrieve_policies(profile, policies, intent=intent)

        self.assertEqual([policy.id for policy in candidates], ["national", "gyeonggi"])


def _policy(policy_id: str, region: list[str], name: str | None = None) -> Policy:
    return Policy(id=policy_id, name=name or policy_id, region=region)


if __name__ == "__main__":
    unittest.main()
