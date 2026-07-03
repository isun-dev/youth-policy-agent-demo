from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from app.policy_sources import _normalize_gyeonggi_job_response_fallback, load_policies_from_source
from app.schemas import Policy


class PolicySourcesTest(unittest.TestCase):
    @patch("app.policy_sources.load_gyeonggi_api_policies")
    @patch("app.policy_sources.load_youthcenter_api_policies")
    def test_combined_source_loads_youthcenter_and_gyeonggi_policies(
        self,
        mock_youthcenter,
        mock_gyeonggi,
    ) -> None:
        mock_youthcenter.return_value = [Policy(id="Y1", name="온통청년 정책")]
        mock_gyeonggi.return_value = [Policy(id="G1", name="경기도 정책")]

        policies = load_policies_from_source(
            "combined",
            sample_path=Path("data/policies.sample.json"),
            page_size=2,
            pages=3,
            gyeonggi_fetch_details=True,
            gyeonggi_detail_limit=4,
        )

        self.assertEqual([policy.id for policy in policies], ["Y1", "G1"])
        mock_youthcenter.assert_called_once_with(
            page_size=2,
            pages=3,
            progress_callback=None,
        )
        mock_gyeonggi.assert_called_once_with(
            page_size=2,
            pages=3,
            fetch_details=True,
            detail_limit=4,
            progress_callback=None,
        )

    @patch("app.policy_sources.load_gyeonggi_api_policies")
    @patch("app.policy_sources.load_youthcenter_api_policies")
    def test_combined_source_deduplicates_by_policy_id(
        self,
        mock_youthcenter,
        mock_gyeonggi,
    ) -> None:
        mock_youthcenter.return_value = [Policy(id="P1", name="먼저 온 정책")]
        mock_gyeonggi.return_value = [Policy(id="P1", name="중복 정책")]

        policies = load_policies_from_source(
            "combined",
            sample_path=Path("data/policies.sample.json"),
        )

        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0].name, "먼저 온 정책")

    @patch("app.policy_sources.load_gyeonggi_api_policies")
    @patch("app.policy_sources.load_youthcenter_api_policies")
    def test_combined_source_keeps_youthcenter_results_when_gyeonggi_fails(
        self,
        mock_youthcenter,
        mock_gyeonggi,
    ) -> None:
        messages = []
        mock_youthcenter.return_value = [Policy(id="Y1", name="온통청년 정책")]
        mock_gyeonggi.side_effect = RuntimeError("GYEONGGI_API_KEY missing")

        policies = load_policies_from_source(
            "combined",
            sample_path=Path("data/policies.sample.json"),
            progress_callback=messages.append,
        )

        self.assertEqual([policy.id for policy in policies], ["Y1"])
        self.assertTrue(any("경기도 잡아바 API를 불러오지 못해" in message for message in messages))

    @patch("app.policy_sources.load_gyeonggi_api_policies")
    @patch("app.policy_sources.load_youthcenter_api_policies")
    def test_combined_source_raises_when_all_sources_fail(
        self,
        mock_youthcenter,
        mock_gyeonggi,
    ) -> None:
        mock_youthcenter.side_effect = RuntimeError("youth failed")
        mock_gyeonggi.side_effect = RuntimeError("gyeonggi failed")

        with self.assertRaises(RuntimeError) as context:
            load_policies_from_source(
                "combined",
                sample_path=Path("data/policies.sample.json"),
            )

        self.assertIn("통합 API 출처를 모두 불러오지 못했습니다", str(context.exception))

    def test_gyeonggi_fallback_normalizer_handles_list_response(self) -> None:
        policies = _normalize_gyeonggi_job_response_fallback(
            """
            {
              "JobFndtnEduTraing": [
                {
                  "row": [
                    {
                      "PBLANC_TITLE": "경기도 청년 교육훈련 모집",
                      "REGION_NM": "의정부시",
                      "DETAIL_PAGE_URL": "https://job.gg.go.kr/detail"
                    }
                  ]
                }
              ]
            }
            """,
            endpoint="JobFndtnEduTraing",
        )

        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0].name, "경기도 청년 교육훈련 모집")
        self.assertEqual(policies[0].region, ["의정부시"])
        self.assertEqual(policies[0].source_url, "https://job.gg.go.kr/detail")
        self.assertIn("official_detail_criteria", policies[0].required_fields)


if __name__ == "__main__":
    unittest.main()
