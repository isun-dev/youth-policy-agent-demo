from __future__ import annotations

import unittest

from app.policy_detail_enricher import enrich_policies_with_detail_pages
from app.policy_detail_tool import PolicyDetail
from app.schemas import Policy


class PolicyDetailEnricherTest(unittest.TestCase):
    def test_enriches_policy_with_official_detail_text(self) -> None:
        policy = Policy(
            id="JobFndtnEduTraing:1",
            name="청년 교육훈련",
            region=["경기도"],
            required_fields=["official_detail_criteria"],
            source_url="https://example.com/detail",
            apply_url="https://example.com/detail",
        )
        detail_tool = _FakeDetailTool(
            "지원대상: 경기도 거주 구직 청년. 소득 기준 확인 필요. 신청기간 내 접수 가능."
        )

        enriched = enrich_policies_with_detail_pages([policy], detail_limit=1, detail_tool=detail_tool)

        self.assertEqual(len(enriched), 1)
        self.assertIn("official_detail_criteria", enriched[0].required_fields)
        self.assertIn("income_level", enriched[0].required_fields)
        self.assertIn("application_period", enriched[0].required_fields)
        self.assertTrue(any("소득 기준" in text for text in enriched[0].evidence_texts))

    def test_respects_detail_limit(self) -> None:
        policies = [
            Policy(id="P1", name="정책1", source_url="https://example.com/1"),
            Policy(id="P2", name="정책2", source_url="https://example.com/2"),
        ]
        detail_tool = _FakeDetailTool("소득 기준 확인 필요.")

        enrich_policies_with_detail_pages(policies, detail_limit=1, detail_tool=detail_tool)

        self.assertEqual(detail_tool.fetch_count, 1)


class _FakeDetailTool:
    def __init__(self, text: str) -> None:
        self.text = text
        self.fetch_count = 0

    def fetch(self, url: str) -> PolicyDetail:
        self.fetch_count += 1
        return PolicyDetail(source_url=url, plain_text=self.text, fetch_status="ok")


if __name__ == "__main__":
    unittest.main()
