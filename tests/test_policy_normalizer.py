from __future__ import annotations

import unittest
from pathlib import Path

from app.policy_normalizer import (
    normalize_gyeonggi_job_json,
    normalize_gyeonggi_job_response,
    normalize_youthcenter_json,
    normalize_youthcenter_response,
    normalize_youthcenter_xml,
)


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

    def test_builds_conditions_with_api_evidence_text(self) -> None:
        policies = normalize_youthcenter_response(
            """
            {
              "youthPolicyList": [
                {
                  "plcyNo": "P1",
                  "plcyNm": "국민취업지원제도",
                  "sprtTrgtCn": "기준중위소득 60% 이하이고 가구 재산 4억원 이하인 구직자",
                  "plcyExplnCn": "취업지원 서비스를 제공합니다.",
                  "refUrlAddr": "https://source.example.com"
                }
              ]
            }
            """,
            last_checked="2026-07-02",
        )

        policy = policies[0]
        conditions_by_field = {condition.field: condition for condition in policy.conditions}

        self.assertIn("income_level", policy.required_fields)
        self.assertIn("assets", policy.required_fields)
        self.assertIn("income_level", conditions_by_field)
        self.assertIn("assets", conditions_by_field)
        self.assertIn("기준중위소득", conditions_by_field["income_level"].source_text)
        self.assertIn("가구 재산", conditions_by_field["assets"].source_text)
        self.assertEqual(conditions_by_field["income_level"].source_url, "https://source.example.com")
        self.assertTrue(any("기준중위소득" in text for text in policy.evidence_texts))

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

    def test_normalizes_gyeonggi_job_row_response(self) -> None:
        json_text = """
        {
          "JobFndtnSportPolocy": [
            {
              "head": [
                {"list_total_count": 1},
                {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다."}}
              ]
            },
            {
              "row": [
                {
                  "POLICY_ID": "GG-001",
                  "POLICY_NM": "경기도 청년 면접 지원",
                  "SIGUN_NM": "의정부시",
                  "TRGET_AGE": "만 18세 ~ 39세",
                  "SPRT_TRGET_CN": "경기도 거주 미취업 청년",
                  "SPRT_CN": "면접 준비 비용 지원",
                  "APPLY_URL": "https://apply.example.com"
                }
              ]
            }
          ]
        }
        """

        policies = normalize_gyeonggi_job_json(
            json_text,
            endpoint="JobFndtnSportPolocy",
            last_checked="2026-07-03",
        )

        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0].id, "GG-001")
        self.assertEqual(policies[0].name, "경기도 청년 면접 지원")
        self.assertEqual(policies[0].region, ["의정부시"])
        self.assertEqual(policies[0].age_min, 18)
        self.assertEqual(policies[0].age_max, 39)
        self.assertEqual(policies[0].employment_status, ["job_seeker", "unemployed"])
        self.assertEqual(policies[0].benefit, "면접 준비 비용 지원")
        self.assertEqual(policies[0].apply_url, "https://apply.example.com")
        self.assertEqual(policies[0].last_checked, "2026-07-03")

    def test_gyeonggi_response_keeps_text_as_condition_evidence(self) -> None:
        policies = normalize_gyeonggi_job_response(
            """
            {
              "JobFndtnEduTraing": [
                {
                  "row": [
                    {
                      "EDU_TRAING_NM": "청년 취업 교육",
                      "TRGET_CN": "소득 기준 확인이 필요한 구직 청년",
                      "EDU_TRAING_CN": "직무 교육과 취업활동을 지원합니다."
                    }
                  ]
                }
              ]
            }
            """,
            endpoint="JobFndtnEduTraing",
            last_checked="2026-07-03",
        )

        policy = policies[0]
        self.assertIn("income_level", policy.required_fields)
        self.assertTrue(any("소득 기준" in text for text in policy.evidence_texts))
        self.assertEqual(policy.conditions[0].source_url, "https://openapi.gg.go.kr/JobFndtnEduTraing")

    def test_gyeonggi_list_only_response_requires_official_detail_check(self) -> None:
        policies = normalize_gyeonggi_job_response(
            """
            {
              "JobFndtnEduTraing": [
                {
                  "row": [
                    {
                      "PBLANC_TITLE": "경기도 청년 교육훈련 모집",
                      "INST_NM": "경기도일자리재단",
                      "RECRUT_BEGIN_DE": "2026-07-01",
                      "RECRUT_END_DE": "2026-07-31",
                      "DIV_NM": "교육훈련",
                      "REGION_NM": "의정부시",
                      "DETAIL_PAGE_URL": "https://apply.example.com/detail"
                    }
                  ]
                }
              ]
            }
            """,
            endpoint="JobFndtnEduTraing",
            last_checked="2026-07-03",
        )

        policy = policies[0]
        self.assertEqual(policy.name, "경기도 청년 교육훈련 모집")
        self.assertEqual(policy.region, ["의정부시"])
        self.assertEqual(policy.apply_url, "https://apply.example.com/detail")
        self.assertEqual(policy.source_url, "https://apply.example.com/detail")
        self.assertIn("official_detail_criteria", policy.required_fields)
        self.assertIn("상세 자격요건", policy.conditions[0].label)


if __name__ == "__main__":
    unittest.main()
