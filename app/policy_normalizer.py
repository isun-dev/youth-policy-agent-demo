from __future__ import annotations

from datetime import date
import json
import re
import xml.etree.ElementTree as ET

from app.schemas import Policy


def normalize_youthcenter_policy(raw_policy: dict) -> Policy:
    """Convert one 온통청년 API item into the internal Policy schema."""
    required_fields = _merge_required_fields(
        _split_csv(raw_policy.get("required_fields")),
        _infer_required_fields(raw_policy),
    )

    return Policy(
        id=raw_policy.get("id", ""),
        name=raw_policy.get("name", ""),
        region=_split_csv(raw_policy.get("region")),
        age_min=_parse_int(raw_policy.get("age_min")),
        age_max=_parse_int(raw_policy.get("age_max")),
        employment_status=_split_csv(raw_policy.get("employment_status")),
        required_fields=required_fields,
        description=raw_policy.get("description", ""),
        benefit=raw_policy.get("benefit", ""),
        apply_url=raw_policy.get("apply_url", ""),
        source_url=raw_policy.get("source_url", ""),
        last_checked=raw_policy.get("last_checked", ""),
    )


def normalize_youthcenter_response(response_text: str, last_checked: str | None = None) -> list[Policy]:
    text = response_text.strip()
    if not text:
        return []
    if text.startswith("{") or text.startswith("["):
        return normalize_youthcenter_json(text, last_checked=last_checked)
    return normalize_youthcenter_xml(text, last_checked=last_checked)


def normalize_youthcenter_json(json_text: str, last_checked: str | None = None) -> list[Policy]:
    data = json.loads(json_text)
    items = _find_policy_dicts(data)
    return [
        normalize_youthcenter_policy(_raw_policy_from_dict(item, last_checked=last_checked))
        for item in items
    ]


def normalize_youthcenter_xml(xml_text: str, last_checked: str | None = None) -> list[Policy]:
    root = ET.fromstring(xml_text)
    policies: list[Policy] = []

    for item in _find_policy_items(root):
        raw_policy = _raw_policy_from_xml(item, last_checked=last_checked)
        policies.append(normalize_youthcenter_policy(raw_policy))

    return policies


def _raw_policy_from_xml(item: ET.Element, last_checked: str | None = None) -> dict:
    return {
        "id": _first_text(item, ["id", "bizId", "plcyNo"]),
        "name": _first_text(item, ["name", "polyBizSjnm", "plcyNm"]),
        "region": _normalize_region_from_zip_codes(_first_text(item, ["zipCd"]))
        or _normalize_region(_first_text(item, ["region", "polyBizSecd", "polyBizTy", "sprvsnInstCdNm"])),
        "age_min": _parse_age_min(_first_text(item, ["ageMin", "ageInfo", "sprtTrgtMinAge"])),
        "age_max": _parse_age_max(_first_text(item, ["ageMax", "ageInfo", "sprtTrgtMaxAge"])),
        "employment_status": _normalize_employment_status(
            _first_text(item, ["employmentStatus", "empmSttsCn", "jobCdNm"])
        ),
        "required_fields": _first_text(item, ["requiredFields"]),
        "description": _first_text(item, ["description", "polyItcnCn", "plcyExplnCn"]),
        "benefit": _first_text(item, ["benefit", "sporCn", "plcySprtCn"]),
        "apply_url": _first_text(item, ["applyUrl", "rqutUrla", "aplyUrlAddr"]),
        "source_url": _first_text(item, ["sourceUrl", "rfcSiteUrla1", "rfcSiteUrla2", "refUrlAddr"]),
        "last_checked": _first_text(item, ["lastChecked"]) or last_checked or date.today().isoformat(),
    }


def _raw_policy_from_dict(item: dict, last_checked: str | None = None) -> dict:
    return {
        "id": _first_dict_value(item, ["id", "bizId", "plcyNo"]),
        "name": _first_dict_value(item, ["name", "polyBizSjnm", "plcyNm"]),
        "region": _normalize_region_from_zip_codes(_first_dict_value(item, ["zipCd"]))
        or _normalize_region(
            _first_dict_value(item, ["region", "polyBizSecd", "polyBizTy", "sprvsnInstCdNm"])
        ),
        "age_min": _parse_age_min(_first_dict_value(item, ["ageMin", "ageInfo", "sprtTrgtMinAge"])),
        "age_max": _parse_age_max(_first_dict_value(item, ["ageMax", "ageInfo", "sprtTrgtMaxAge"])),
        "employment_status": _normalize_employment_status(
            _first_dict_value(item, ["employmentStatus", "empmSttsCn", "jobCdNm"])
        ),
        "required_fields": _first_dict_value(item, ["requiredFields"]),
        "description": _first_dict_value(item, ["description", "polyItcnCn", "plcyExplnCn"]),
        "benefit": _first_dict_value(item, ["benefit", "sporCn", "plcySprtCn"]),
        "apply_url": _first_dict_value(item, ["applyUrl", "rqutUrla", "aplyUrlAddr"]),
        "source_url": _first_dict_value(item, ["sourceUrl", "rfcSiteUrla1", "rfcSiteUrla2", "refUrlAddr"]),
        "last_checked": _first_dict_value(item, ["lastChecked"]) or last_checked or date.today().isoformat(),
    }


def _find_policy_dicts(data: object) -> list[dict]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if not isinstance(data, dict):
        return []

    for key in ["youthPolicyList", "policyList", "resultList", "list", "items", "data"]:
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            found = _find_policy_dicts(value)
            if found:
                return found

    for value in data.values():
        found = _find_policy_dicts(value)
        if found:
            return found

    return []


def _find_policy_items(root: ET.Element) -> list[ET.Element]:
    items = root.findall(".//policy")
    if items:
        return items

    youth_policy_items = root.findall(".//youthPolicy")
    if youth_policy_items:
        return youth_policy_items

    return root.findall(".//item")


def _text(item: ET.Element, tag: str) -> str:
    child = item.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _first_text(item: ET.Element, tags: list[str]) -> str:
    for tag in tags:
        value = _text(item, tag)
        if value:
            return value
    return ""


def _first_dict_value(item: dict, keys: list[str]) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_age_min(value: str | None) -> str:
    if not value:
        return ""
    numbers = re.findall(r"\d+", value)
    return numbers[0] if numbers else ""


def _parse_age_max(value: str | None) -> str:
    if not value:
        return ""
    numbers = re.findall(r"\d+", value)
    if not numbers or numbers[-1] == "0":
        return ""
    return numbers[-1]


def _normalize_region(value: str | None) -> str:
    if not value:
        return ""

    central_agency_names = [
        "고용노동부",
        "과학기술정보통신부",
        "교육부",
        "국무조정실",
        "국방부",
        "국토교통부",
        "기획재정부",
        "금융위원회",
        "농림축산식품부",
        "문화체육관광부",
        "법무부",
        "보건복지부",
        "산림청",
        "여성가족부",
        "중소벤처기업부",
        "행정안전부",
        "환경부",
    ]
    if any(agency in value for agency in central_agency_names):
        return "전국"

    region_aliases = {
        "중앙부처": "전국",
        "전국": "전국",
        "서울": "서울특별시",
        "부산": "부산광역시",
        "대구": "대구광역시",
        "인천": "인천광역시",
        "광주": "광주광역시",
        "대전": "대전광역시",
        "울산": "울산광역시",
        "세종": "세종특별자치시",
        "경기": "경기도",
        "강원": "강원특별자치도",
        "충북": "충청북도",
        "충남": "충청남도",
        "전북": "전북특별자치도",
        "전남": "전라남도",
        "경북": "경상북도",
        "경남": "경상남도",
        "제주": "제주특별자치도",
    }

    regions = []
    for part in re.split(r"[,/|·\s]+", value):
        normalized = region_aliases.get(part.strip(), part.strip())
        if normalized and normalized not in regions:
            regions.append(normalized)
    return ",".join(regions)


def _normalize_region_from_zip_codes(value: str | None) -> str:
    if not value:
        return ""

    codes = [part.strip() for part in value.split(",") if part.strip()]
    if len(codes) >= 200:
        return "전국"

    prefix_regions = {
        "11": "서울특별시",
        "26": "부산광역시",
        "27": "대구광역시",
        "28": "인천광역시",
        "29": "광주광역시",
        "30": "대전광역시",
        "31": "울산광역시",
        "36": "세종특별자치시",
        "41": "경기도",
        "42": "강원특별자치도",
        "43": "충청북도",
        "44": "충청남도",
        "45": "전북특별자치도",
        "46": "전라남도",
        "47": "경상북도",
        "48": "경상남도",
        "50": "제주특별자치도",
        "51": "강원특별자치도",
        "52": "전북특별자치도",
    }

    regions = []
    for code in codes:
        normalized = prefix_regions.get(code[:2])
        if normalized and normalized not in regions:
            regions.append(normalized)

    return ",".join(regions)


def _normalize_employment_status(value: str | None) -> str:
    if not value:
        return ""

    statuses = []
    known_statuses = ["job_seeker", "unemployed", "employed"]
    tokens = {part.strip() for part in re.split(r"[,/|·\s]+", value) if part.strip()}
    for status in known_statuses:
        if status in tokens:
            statuses.append(status)
    if any(keyword in value for keyword in ["미취업", "구직", "취업준비", "실업"]):
        statuses.extend(["job_seeker", "unemployed"])
    if any(keyword in value for keyword in ["재직", "근로", "취업자"]):
        statuses.append("employed")
    if any(keyword in value for keyword in ["제한없음", "무관"]):
        return ""

    return ",".join(dict.fromkeys(statuses))


def _infer_required_fields(raw_policy: dict) -> list[str]:
    text = " ".join(
        str(raw_policy.get(key, ""))
        for key in ["name", "description", "benefit"]
        if raw_policy.get(key)
    )
    if not text:
        return []

    keyword_rules = [
        ("income_level", ["소득", "연소득", "중위소득", "기준중위소득", "건강보험료"]),
        ("assets", ["재산", "자산"]),
        ("housing_status", ["무주택", "주거", "임차", "월세", "전세"]),
        ("lease_contract", ["임대차", "전세계약", "임차계약", "임차보증금"]),
        ("lease_deposit", ["임차보증금", "전세보증금", "보증금"]),
        ("guarantee_insurance_status", ["전세보증금반환보증", "보증료", "보증 가입"]),
        ("work_income", ["근로소득", "사업소득"]),
        ("work_status", ["재직", "근로", "주 40시간", "근무"]),
        ("recent_job_search_activity", ["구직활동", "취업활동"]),
        ("program_participation_history", ["중복", "유사사업", "참여 이력", "참여이력"]),
        ("student_or_graduate_status", ["재학", "휴학", "졸업", "대학생"]),
        ("loan_history", ["학자금"]),
        ("artist_status", ["예술인", "예술활동증명", "예술활동"]),
        ("farming_status", ["농업인", "영농", "농업", "독립경영"]),
        ("business_status", ["창업", "사업자", "사업계획"]),
        ("certification_exam_status", ["국가기술자격", "자격증", "응시료", "시험"]),
        ("application_period", ["신청기간", "접수", "마감", "선착순"]),
    ]

    fields = []
    for field, keywords in keyword_rules:
        if any(keyword in text for keyword in keywords):
            fields.append(field)

    return fields


def _merge_required_fields(existing_fields: list[str], inferred_fields: list[str]) -> list[str]:
    return list(dict.fromkeys(existing_fields + inferred_fields))
