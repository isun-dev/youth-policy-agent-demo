from __future__ import annotations

import unittest
from pathlib import Path

from app.policy_normalizer import normalize_youthcenter_json, normalize_youthcenter_response, normalize_youthcenter_xml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_XML_PATH = PROJECT_ROOT / "data" / "youthcenter.sample.xml"


class PolicyNormalizerTest(unittest.TestCase):
    def test_normalizes_sample_youthcenter_xml(self) -> None:
        xml_text = SAMPLE_XML_PATH.read_text(encoding="utf-8")

        policies = normalize_youthcenter_xml(xml_text)

        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0].id, "sample_youth_policy_001")
        self.assertEqual(policies[0].region, ["경기도"])
        self.assertEqual(policies[0].age_min, 19)
        self.assertEqual(policies[0].age_max, 34)
        self.assertEqual(policies[0].employment_status, ["job_seeker", "unemployed"])

    def test_normalizes_youthcenter_like_api_fields(self) -> None:
        xml_text = """
        <response>
          <youthPolicyList>
            <youthPolicy>
              <bizId>R2026001</bizId>
              <polyBizSjnm>청년 면접수당</polyBizSjnm>
              <polyBizSecd>경기</polyBizSecd>
              <ageInfo>만 18세 ~ 39세</ageInfo>
              <empmSttsCn>미취업 청년</empmSttsCn>
              <polyItcnCn>면접 활동을 지원합니다.</polyItcnCn>
              <sporCn>면접수당 지원</sporCn>
              <rqutUrla>https://apply.example.com</rqutUrla>
              <rfcSiteUrla1>https://source.example.com</rfcSiteUrla1>
            </youthPolicy>
          </youthPolicyList>
        </response>
        """

        policies = normalize_youthcenter_xml(xml_text, last_checked="2026-06-24")

        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0].id, "R2026001")
        self.assertEqual(policies[0].name, "청년 면접수당")
        self.assertEqual(policies[0].region, ["경기도"])
        self.assertEqual(policies[0].age_min, 18)
        self.assertEqual(policies[0].age_max, 39)
        self.assertEqual(policies[0].employment_status, ["job_seeker", "unemployed"])
        self.assertEqual(policies[0].last_checked, "2026-06-24")

    def test_normalizes_youthcenter_json_response(self) -> None:
        json_text = """
        {
          "result": {
            "youthPolicyList": [
              {
                "plcyNo": "P2026001",
                "plcyNm": "청년 구직 지원",
                "sprvsnInstCdNm": "경기",
                "sprtTrgtMinAge": "19",
                "sprtTrgtMaxAge": "34",
                "jobCdNm": "미취업",
                "plcyExplnCn": "구직 청년을 지원합니다.",
                "plcySprtCn": "구직활동비 지원",
                "aplyUrlAddr": "https://apply.example.com",
                "refUrlAddr": "https://source.example.com"
              }
            ]
          }
        }
        """

        policies = normalize_youthcenter_json(json_text, last_checked="2026-06-29")

        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0].id, "P2026001")
        self.assertEqual(policies[0].name, "청년 구직 지원")
        self.assertEqual(policies[0].region, ["경기도"])
        self.assertEqual(policies[0].age_min, 19)
        self.assertEqual(policies[0].age_max, 34)
        self.assertEqual(policies[0].employment_status, ["job_seeker", "unemployed"])

    def test_detects_json_response(self) -> None:
        policies = normalize_youthcenter_response(
            '{"youthPolicyList": [{"plcyNo": "P1", "plcyNm": "정책"}]}',
            last_checked="2026-06-29",
        )

        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0].id, "P1")

    def test_treats_zero_max_age_as_no_upper_limit(self) -> None:
        policies = normalize_youthcenter_response(
            '{"youthPolicyList": [{"plcyNo": "P1", "plcyNm": "정책", "sprtTrgtMinAge": "0", "sprtTrgtMaxAge": "0"}]}',
            last_checked="2026-06-29",
        )

        self.assertEqual(policies[0].age_min, 0)
        self.assertIsNone(policies[0].age_max)

    def test_infers_required_fields_from_policy_text(self) -> None:
        policies = normalize_youthcenter_response(
            """
            {
              "youthPolicyList": [
                {
                  "plcyNo": "P1",
                  "plcyNm": "전세보증금반환보증 보증료 지원",
                  "plcyExplnCn": "무주택 청년, 연소득 5천만원 이하, 임차보증금 3억원 이하",
                  "plcySprtCn": "전세보증금반환보증 보증료 지원"
                }
              ]
            }
            """,
            last_checked="2026-06-29",
        )

        self.assertIn("housing_status", policies[0].required_fields)
        self.assertIn("income_level", policies[0].required_fields)
        self.assertIn("lease_deposit", policies[0].required_fields)
        self.assertIn("guarantee_insurance_status", policies[0].required_fields)

    def test_zip_codes_override_supervising_agency_region(self) -> None:
        policies = normalize_youthcenter_response(
            """
            {
              "youthPolicyList": [
                {
                  "plcyNo": "P1",
                  "plcyNm": "광주 지역 정책",
                  "sprvsnInstCdNm": "행정안전부",
                  "zipCd": "29110,29140,29155,29170,29200"
                }
              ]
            }
            """,
            last_checked="2026-06-30",
        )

        self.assertEqual(policies[0].region, ["광주광역시"])

    def test_many_zip_codes_are_treated_as_national_region(self) -> None:
        zip_codes = ",".join(str(11000 + index) for index in range(200))
        policies = normalize_youthcenter_response(
            f'{{"youthPolicyList": [{{"plcyNo": "P1", "plcyNm": "전국 정책", "zipCd": "{zip_codes}"}}]}}',
            last_checked="2026-06-30",
        )

        self.assertEqual(policies[0].region, ["전국"])


if __name__ == "__main__":
    unittest.main()
