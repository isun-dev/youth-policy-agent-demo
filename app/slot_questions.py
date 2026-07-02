from __future__ import annotations


FIELD_QUESTIONS = {
    "age": "지원 연령에 해당하나요?",
    "region": "주민등록상 거주 지역이 어디인가요?",
    "employment_status": "현재 취업 상태가 지원대상에 해당하나요?",
    "income_level": "소득 기준에 해당하나요?",
    "assets": "재산 기준에 해당하나요?",
    "recent_employment_history": "최근 취업 이력 또는 고용보험 가입 이력이 있나요?",
    "interview_experience": "최근 취업 면접에 참여한 적이 있나요?",
    "housing_status": "현재 무주택자 또는 임차 거주자에 해당하나요?",
    "lease_deposit": "임차보증금이 지원 기준 이하인가요?",
    "guarantee_insurance_status": "전세보증금반환보증에 가입되어 있나요?",
    "parent_household_income": "부모님 가구 소득이 기준에 해당하나요?",
    "residence_period": "주민등록상 해당 지역 거주기간 요건을 충족하나요?",
    "recent_job_search_activity": "최근 구직활동 이력이 있나요?",
    "program_participation_history": "최근 유사한 지원사업에 참여한 적이 있나요?",
    "household_income": "가구 소득이 지원 기준에 해당하나요?",
    "work_income": "근로소득 또는 사업소득이 있나요?",
    "lease_contract": "본인 명의의 임대차 계약이 있나요?",
    "work_status": "현재 근로 또는 사업 참여 요건에 해당하나요?",
    "workplace_region": "현재 근무지가 해당 지역 소재 사업장인가요?",
    "employment_insurance": "현재 고용보험에 가입되어 있나요?",
    "student_or_graduate_status": "현재 재학, 휴학 중이거나 졸업 후 지원 가능 기간 안에 있나요?",
    "loan_history": "한국장학재단 학자금 대출을 받은 적이 있나요?",
    "artist_status": "예술인 또는 예술활동증명 대상자에 해당하나요?",
    "farming_status": "농업인 또는 영농정착 지원대상에 해당하나요?",
    "business_status": "창업자, 예비창업자 또는 사업자 요건에 해당하나요?",
    "certification_exam_status": "응시하려는 시험이 지원 대상 자격시험인가요?",
    "application_period": "현재 신청기간 내에 신청할 수 있나요?",
}


FIELD_LABELS = {
    "age": "나이",
    "region": "지역",
    "employment_status": "취업상태",
    "income_level": "소득 기준",
    "assets": "재산 기준",
    "recent_employment_history": "최근 취업 이력",
    "interview_experience": "면접 참여 이력",
    "housing_status": "주거 상태",
    "lease_deposit": "임차보증금 기준",
    "guarantee_insurance_status": "보증 가입 여부",
    "parent_household_income": "부모 가구 소득",
    "residence_period": "거주 기간",
    "recent_job_search_activity": "구직활동 이력",
    "program_participation_history": "유사사업 참여 이력",
    "household_income": "가구 소득",
    "work_income": "근로소득",
    "lease_contract": "임대차 계약",
    "work_status": "근로 상태",
    "workplace_region": "근무지 지역",
    "employment_insurance": "고용보험 가입",
    "student_or_graduate_status": "재학/졸업 상태",
    "loan_history": "학자금 대출 이력",
    "artist_status": "예술인 자격",
    "farming_status": "영농 상태",
    "business_status": "창업 상태",
    "certification_exam_status": "자격시험 조건",
    "application_period": "신청기간",
}


POLICY_QUESTION_OVERRIDES = [
    (
        ("전세보증금", "보증료"),
        {
            "income_level": "연소득이 해당 보증료 지원 기준 안에 들어오나요?",
            "housing_status": "현재 무주택 임차인에 해당하나요?",
            "lease_contract": "본인 명의 임대차 계약이 있나요?",
            "lease_deposit": "임차보증금이 해당 보증료 지원 기준 이하인가요?",
            "guarantee_insurance_status": "전세보증금반환보증에 가입되어 있나요?",
            "application_period": "현재 접수기간 안에 신청할 수 있나요?",
        },
    ),
    (
        ("면접",),
        {
            "interview_experience": "최근 취업 면접에 실제로 참여했고 증빙자료가 있나요?",
            "employment_status": "현재 구직 또는 미취업 상태에 해당하나요?",
            "application_period": "해당 면접일이 신청 가능한 기간 안에 있나요?",
        },
    ),
    (
        ("국민취업지원제도",),
        {
            "income_level": "가구 소득이 국민취업지원제도 기준에 해당하나요?",
            "assets": "가구 재산이 국민취업지원제도 기준에 해당하나요?",
            "recent_job_search_activity": "취업지원 서비스에 참여할 의사가 있나요?",
        },
    ),
    (
        ("월세",),
        {
            "income_level": "소득이 해당 월세 지원 기준 안에 들어오나요?",
            "housing_status": "현재 월세로 거주 중인가요?",
            "lease_contract": "본인 명의 임대차 계약이 있나요?",
            "lease_deposit": "보증금 또는 월세 금액이 지원 기준 이하인가요?",
        },
    ),
]


def question_for_field(field: str, policy_name: str | None = None) -> str:
    if policy_name:
        for keywords, questions in POLICY_QUESTION_OVERRIDES:
            if all(keyword in policy_name for keyword in keywords) and field in questions:
                return questions[field]
    return FIELD_QUESTIONS.get(field, f"{field} 조건에 해당하나요?")


def questions_for_fields(fields: list[str], policy_name: str | None = None) -> list[str]:
    return [question_for_field(field, policy_name=policy_name) for field in fields]


def label_for_field(field: str) -> str:
    return FIELD_LABELS.get(field, field)
