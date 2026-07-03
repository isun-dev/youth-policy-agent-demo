from __future__ import annotations

from collections.abc import Callable
import hmac
from html import escape
import os
import re
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from app.answer_generator import STATUS_LABELS
from app.eligibility import check_all
from app.input_parser import normalize_employment_status
from app.natural_language_parser import parse_natural_language_input
from app.policy_sources import load_policies_from_source
from app.retriever import load_policies, retrieve_policies
from app.schemas import (
    ConditionCheck,
    ConditionStatus,
    EligibilityResult,
    Policy,
    UserIntent,
    UserProfile,
)
from app.sensitive import redact_sensitive_text
from app.slot_questions import guide_for_field, label_for_field, question_for_field


POLICY_PATH = PROJECT_ROOT / "data" / "policies.sample.json"
ANSWER_OPTIONS = {
    "해당함": True,
    "해당하지 않음": False,
    "모름": None,
}
DATA_SOURCE_OPTIONS = {
    "샘플 데이터": "sample",
    "온통청년 API": "api",
    "경기도 잡아바 API": "gyeonggi",
    "통합 API": "combined",
}
EMPLOYMENT_STATUS_LABELS = {
    "job_seeker": "구직 중",
    "unemployed": "미취업",
    "employed": "재직 중",
}
CONDITION_STATUS_LABELS = {
    ConditionStatus.MATCHED: "충족",
    ConditionStatus.MISSING: "추가 확인 필요",
    ConditionStatus.FAILED: "어려움",
}


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .policy-head {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 14px;
        }
        .policy-title {
            font-size: 1.05rem;
            font-weight: 750;
            line-height: 1.35;
            color: #1f2937;
        }
        .policy-meta {
            margin-top: 4px;
            font-size: 0.86rem;
            color: #6b7280;
        }
        .status-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 92px;
            padding: 7px 11px;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 750;
            white-space: nowrap;
        }
        .status-eligible_likely {
            color: #075985;
            background: #e0f2fe;
            border: 1px solid #7dd3fc;
        }
        .status-need_more_info {
            color: #854d0e;
            background: #fef3c7;
            border: 1px solid #facc15;
        }
        .status-not_eligible_likely {
            color: #991b1b;
            background: #fee2e2;
            border: 1px solid #fca5a5;
        }
        .section-label {
            margin: 4px 0 8px;
            font-size: 0.9rem;
            font-weight: 750;
            color: #374151;
        }
        .condition-block {
            margin: 8px 0 14px;
        }
        .condition-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .condition-row {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 8px 12px;
            align-items: center;
            padding: 10px 12px;
            border: 1px solid #e5e7eb;
            border-left-width: 4px;
            border-radius: 8px;
            background: #ffffff;
        }
        .condition-main {
            display: flex;
            align-items: center;
            min-width: 0;
            gap: 9px;
        }
        .condition-label {
            color: #111827;
            font-size: 0.92rem;
            line-height: 1.35;
            overflow-wrap: anywhere;
        }
        .condition-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex: 0 0 8px;
        }
        .condition-matched {
            border-left-color: #0ea5e9;
            background: #f8fafc;
        }
        .condition-missing {
            border-left-color: #f59e0b;
            background: #fffbeb;
        }
        .condition-failed {
            border-left-color: #ef4444;
            background: #fef2f2;
        }
        .condition-matched .condition-dot {
            background: #0ea5e9;
        }
        .condition-missing .condition-dot {
            background: #f59e0b;
        }
        .condition-failed .condition-dot {
            background: #ef4444;
        }
        .condition-pill {
            border-radius: 999px;
            padding: 4px 9px;
            font-size: 0.76rem;
            font-weight: 750;
            white-space: nowrap;
        }
        .condition-pill-matched {
            color: #075985;
            background: #e0f2fe;
        }
        .condition-pill-missing {
            color: #854d0e;
            background: #fde68a;
        }
        .condition-pill-failed {
            color: #991b1b;
            background: #fecaca;
        }
        .condition-source {
            grid-column: 1 / -1;
            margin-left: 17px;
            color: #6b7280;
            font-size: 0.78rem;
            line-height: 1.35;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px;
            margin: 10px 0 12px;
        }
        .summary-item {
            padding: 9px 10px;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
            background: #ffffff;
            min-width: 0;
        }
        .summary-label {
            margin-bottom: 4px;
            color: #6b7280;
            font-size: 0.75rem;
            font-weight: 750;
        }
        .summary-value {
            color: #111827;
            font-size: 0.86rem;
            line-height: 1.35;
            overflow-wrap: anywhere;
        }
        .reason-box {
            margin: 10px 0 2px;
            padding: 10px 12px;
            border-radius: 8px;
            border: 1px solid #fecaca;
            background: #fff7f7;
            color: #7f1d1d;
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .privacy-note {
            margin: 4px 0 14px;
            padding: 11px 12px;
            border-radius: 8px;
            border: 1px solid #bfdbfe;
            background: #eff6ff;
            color: #1e3a8a;
            font-size: 0.86rem;
            line-height: 1.5;
        }
        .question-guide {
            margin: -4px 0 8px;
            padding: 9px 10px;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
            background: #f9fafb;
            color: #4b5563;
            font-size: 0.84rem;
            line-height: 1.45;
        }
        .condition-evidence {
            margin: 4px 0 10px;
            padding: 11px 12px;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
            background: #f9fafb;
            color: #374151;
            font-size: 0.83rem;
            line-height: 1.5;
        }
        .condition-evidence-title {
            margin-bottom: 6px;
            color: #111827;
            font-weight: 800;
        }
        .condition-evidence-text {
            overflow-wrap: anywhere;
        }
        .condition-evidence-list {
            margin: 0;
            padding-left: 18px;
        }
        .condition-evidence-list li {
            margin: 3px 0;
        }
        .condition-evidence a {
            display: inline-block;
            margin-top: 7px;
            color: #2563eb;
            font-weight: 750;
            text-decoration: underline;
        }
        .refreshed-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin: 2px 0 10px;
        }
        .demo-notice {
            margin: 12px 0 18px;
            padding: 13px 14px;
            border: 1px solid #d1d5db;
            border-left: 4px solid #2563eb;
            border-radius: 8px;
            background: #f8fafc;
        }
        .demo-notice-title {
            margin-bottom: 6px;
            color: #1f2937;
            font-size: 0.95rem;
            font-weight: 800;
        }
        .demo-notice-body {
            color: #4b5563;
            font-size: 0.87rem;
            line-height: 1.5;
        }
        .demo-notice-body strong {
            color: #1d4ed8;
        }
        @media (max-width: 760px) {
            .policy-head,
            .refreshed-head {
                flex-direction: column;
                align-items: flex-start;
            }
            .summary-grid {
                grid-template-columns: 1fr;
            }
            .condition-row {
                grid-template-columns: 1fr;
            }
            .condition-pill {
                width: fit-content;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    load_dotenv()
    st.set_page_config(page_title="경기도 청년 정책 지원 찾기", layout="wide")
    _inject_styles()
    if not _render_password_gate():
        return

    st.title("경기도 청년 정책 지원 찾기")
    st.caption("경기도 거주 상황을 입력하면 받을 수 있는 지원을 찾아보고, 필요한 조건만 추가로 확인합니다.")
    _render_demo_notice()

    _initialize_state()
    developer_ui_enabled = _developer_ui_enabled()

    if developer_ui_enabled:
        user_tab, developer_tab = st.tabs(["사용자용", "개발자용"])
        with user_tab:
            _render_user_page()
        with developer_tab:
            _render_developer_page()
        return

    _render_user_page()


def _render_demo_notice() -> None:
    st.markdown(
        """
        <div class="demo-notice">
            <div class="demo-notice-title">제한 접근 포트폴리오 데모</div>
            <div class="demo-notice-body">
                이 화면은 실제 운영 서비스가 아니라 자격 판정 Agent 흐름을 보여주는 데모입니다.
                입력한 조건은 현재 세션의 판정에만 사용되며 DB에 저장하지 않습니다.
                소득, 재산, 고용보험 등 개인정보성 조건은 <strong>해당 여부</strong> 중심으로만 확인하고,
                실제 신청 가능 여부는 반드시 공식 기관과 신청 페이지에서 최종 확인해야 합니다.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_user_page() -> None:
    if st.session_state.profile is None:
        _render_user_search_form(form_key="initial_user_search_form")
        return

    with st.expander("조건 다시 입력", expanded=False):
        _render_user_search_form(form_key="edit_user_search_form")

    _render_profile_summary(st.session_state.profile)
    results = _current_results()

    if not results:
        st.warning("조건에 맞는 후보 정책을 찾지 못했습니다.")
        return

    left, right = st.columns([1.1, 1])
    with left:
        _render_results(results)
    with right:
        _render_slot_filling(results, key_prefix="user")


def _render_developer_page() -> None:
    st.subheader("개발자 테스트")
    st.write("데이터 출처, LLM 사용 여부, API 호출 범위를 조절하면서 같은 판정 흐름을 확인합니다.")

    _render_search_form(
        form_key="developer_search_form",
        title="테스트 조건",
        show_data_source=True,
        show_llm_toggle=True,
        show_api_settings=True,
        default_use_llm=False,
    )

    if st.session_state.profile is None:
        return

    _render_profile_summary(st.session_state.profile)
    results = _current_results()
    if not results:
        st.warning("조건에 맞는 후보 정책을 찾지 못했습니다.")
        return

    left, right = st.columns([1.1, 1])
    with left:
        _render_results(results)
    with right:
        _render_slot_filling(results, key_prefix="developer")


def _initialize_state() -> None:
    defaults = {
        "profile": None,
        "intent": None,
        "parse_warning": None,
        "policies": [],
        "selected_policy_id": None,
        "last_answered_policy_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _set_session(
    profile: UserProfile,
    policies: list[Policy],
    intent: UserIntent | None,
    parse_warning: str | None,
) -> None:
    st.session_state.profile = profile
    st.session_state.intent = intent
    st.session_state.parse_warning = parse_warning
    st.session_state.policies = policies
    st.session_state.selected_policy_id = None
    st.session_state.last_answered_policy_id = None


def _render_user_search_form(form_key: str) -> None:
    _render_search_form(
        form_key=form_key,
        title="내 조건 입력",
        show_data_source=False,
        show_llm_toggle=False,
        show_api_settings=False,
        default_data_source=_default_user_data_source(),
        default_use_llm=True,
        default_page_size=_default_user_api_page_size(),
        default_pages=_default_user_api_pages(),
        default_detail_limit=_default_gyeonggi_detail_limit(),
    )


def _render_search_form(
    form_key: str,
    title: str,
    show_data_source: bool,
    show_llm_toggle: bool,
    show_api_settings: bool,
    default_data_source: str = "sample",
    default_use_llm: bool = False,
    default_page_size: int = 20,
    default_pages: int = 5,
    default_detail_limit: int = 10,
) -> None:
    st.subheader(title)
    st.write("한 문장으로 먼저 적고, 부족한 값은 아래 입력값으로 보완합니다.")

    with st.form(form_key):
        data_source = default_data_source
        if show_data_source:
            data_source_label = st.radio("정책 데이터", list(DATA_SOURCE_OPTIONS.keys()), horizontal=True)
            data_source = DATA_SOURCE_OPTIONS[data_source_label]

        natural_text = st.text_area(
            "한 문장 입력",
            value="",
            placeholder="예: 26살이고 의정부 사는 구직 중 청년인데 구직지원금 있어?",
            height=110,
        )
        use_llm = default_use_llm
        if show_llm_toggle:
            use_llm = st.checkbox("LLM으로 문장 해석", value=default_use_llm)

        col1, col2, col3 = st.columns([0.7, 1.2, 1])
        age = col1.number_input("나이", min_value=0, max_value=120, value=26, step=1)
        region = col2.text_input("거주 지역", value="경기도 의정부", placeholder="예: 경기도 의정부")
        status_text = col3.text_input("현재 상태", value="구직 중", placeholder="예: 구직 중, 취준생, 재직 중")

        page_size = default_page_size
        pages = default_pages
        detail_limit = default_detail_limit
        if show_api_settings:
            with st.expander("API 가져오기 설정", expanded=False):
                page_size = st.number_input(
                    "API 페이지당 정책 수",
                    min_value=1,
                    max_value=100,
                    value=default_page_size,
                    step=1,
                )
                pages = st.number_input(
                    "API 가져올 페이지 수",
                    min_value=1,
                    max_value=20,
                    value=default_pages,
                    step=1,
                )
                detail_limit = st.number_input(
                    "경기도 상세 페이지 확인 수",
                    min_value=0,
                    max_value=50,
                    value=default_detail_limit,
                    step=1,
                    help="경기도 API 목록 결과 중 공식 상세 페이지 HTML을 가져와 근거 문장을 보강할 최대 정책 수입니다.",
                )

        submitted = st.form_submit_button(
            "조건으로 찾아보기",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    with st.status("조건을 분석하고 정책을 확인하는 중입니다.", expanded=True) as status:
        st.write("입력 문장에서 조건을 정리하고 있습니다.")
        profile, intent, warning = _build_profile_from_inputs(
            natural_text=natural_text,
            use_llm=use_llm,
            age=int(age),
            region=region,
            status_text=status_text,
        )

        st.write(_loading_source_message(data_source))
        try:
            policies = _load_policies(
                data_source,
                page_size=int(page_size),
                pages=int(pages),
                detail_limit=int(detail_limit),
                progress_callback=lambda message: st.write(message),
            )
        except Exception as error:  # noqa: BLE001 - UI should show external API/setup errors.
            status.update(label="정책 데이터를 불러오지 못했습니다.", state="error", expanded=True)
            st.error("정책 데이터를 불러오지 못했습니다. .env 설정 또는 외부 API 응답 상태를 확인해 주세요.")
            if show_data_source:
                st.caption(f"개발자 참고: {redact_sensitive_text(error)}")
            return

        st.write("후보 정책을 정리하고 있습니다.")
        _set_session(profile=profile, policies=policies, intent=intent, parse_warning=warning)
        status.update(label="검색 준비가 완료되었습니다.", state="complete", expanded=False)
        st.rerun()


def _build_profile_from_inputs(
    natural_text: str,
    use_llm: bool,
    age: int,
    region: str,
    status_text: str,
) -> tuple[UserProfile, UserIntent | None, str | None]:
    manual_profile = UserProfile(
        age=age,
        region=region.strip() or None,
        employment_status=normalize_employment_status(status_text),
        extra={},
    )
    if not natural_text.strip():
        return manual_profile, None, None

    parsed = parse_natural_language_input(natural_text, use_llm=use_llm)
    profile = UserProfile(
        age=parsed.profile.age if parsed.profile.age is not None else manual_profile.age,
        region=parsed.profile.region or manual_profile.region,
        employment_status=parsed.profile.employment_status or manual_profile.employment_status,
        extra={},
    )
    return profile, parsed.intent, parsed.warning


def _load_policies(
    data_source: str,
    page_size: int,
    pages: int,
    detail_limit: int,
    progress_callback: Callable[[str], None] | None = None,
) -> list[Policy]:
    if data_source == "sample":
        return load_policies(POLICY_PATH)
    return load_policies_from_source(
        data_source,
        sample_path=POLICY_PATH,
        page_size=page_size,
        pages=pages,
        gyeonggi_fetch_details=_gyeonggi_fetch_details_enabled(),
        gyeonggi_detail_limit=detail_limit,
        progress_callback=progress_callback,
    )


def _loading_source_message(data_source: str) -> str:
    if data_source == "api":
        return "온통청년 API에서 최신 정책 후보를 확인하고 있습니다."
    if data_source == "gyeonggi":
        return "경기도 잡아바 API에서 일자리/교육/대외활동 후보를 확인하고 있습니다."
    if data_source == "combined":
        return "온통청년 API와 경기도 잡아바 API에서 후보를 함께 확인하고 있습니다."
    return "샘플 정책 데이터에서 후보를 확인하고 있습니다."


def _current_results() -> list[EligibilityResult]:
    candidates = retrieve_policies(
        st.session_state.profile,
        st.session_state.policies,
        intent=st.session_state.intent,
    )
    return check_all(st.session_state.profile, candidates)


def _render_profile_summary(profile: UserProfile) -> None:
    st.subheader("현재 조건")
    if st.session_state.parse_warning:
        st.warning(st.session_state.parse_warning)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("나이", profile.age if profile.age is not None else "미입력")
    col2.metric("지역", profile.region or "미입력")
    col3.metric("취업상태", _employment_status_label(profile.employment_status))
    col4.metric("관심 분야", _intent_label(st.session_state.intent))


def _render_results(results: list[EligibilityResult]) -> None:
    st.subheader("정책별 자격 심사")
    for index, result in enumerate(_sort_results(results), start=1):
        policy = result.policy
        with st.container(border=True):
            _render_policy_header(index, result)
            _render_condition_checks(result.condition_checks)
            _render_condition_summary(result)
            if result.reasons:
                _render_reason_text(" ".join(result.reasons))
            if policy.benefit:
                with st.expander("지원 내용"):
                    st.write(policy.benefit)
            if policy.apply_url:
                st.link_button("신청 링크", policy.apply_url)


def _render_policy_header(index: int, result: EligibilityResult) -> None:
    policy = result.policy
    st.markdown(
        f"""
        <div class="policy-head">
            <div>
                <div class="policy-title">{index}. {_safe(policy.name)}</div>
                <div class="policy-meta">대상 지역: {_safe(_format_region(policy.region))}</div>
            </div>
            <span class="status-badge status-{result.status.value}">
                {_safe(STATUS_LABELS[result.status])}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_condition_checks(condition_checks: list[ConditionCheck]) -> None:
    if not condition_checks:
        return

    rows = "\n".join(_condition_check_row(condition_check) for condition_check in condition_checks)
    st.markdown(
        f"""
        <div class="condition-block">
            <div class="section-label">조건별 심사</div>
            <div class="condition-list">{rows}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _condition_check_row(condition_check: ConditionCheck) -> str:
    source = ""
    if condition_check.source_text:
        source = f'<div class="condition-source">근거 조건: {_safe(condition_check.source_text)}</div>'

    return f"""
    <div class="condition-row condition-{condition_check.status.value}">
        <div class="condition-main">
            <span class="condition-dot"></span>
            <span class="condition-label">{_safe(condition_check.label)}</span>
        </div>
        <span class="condition-pill condition-pill-{condition_check.status.value}">
            {_safe(CONDITION_STATUS_LABELS[condition_check.status])}
        </span>
        {source}
    </div>
    """


def _render_condition_summary(result: EligibilityResult) -> None:
    st.markdown(
        f"""
        <div class="summary-grid">
            <div class="summary-item summary-matched">
                <div class="summary-label">충족</div>
                <div class="summary-value">{_safe(_format_labels(result.matched_conditions))}</div>
            </div>
            <div class="summary-item summary-missing">
                <div class="summary-label">추가 확인</div>
                <div class="summary-value">{_safe(_format_labels(result.missing_fields))}</div>
            </div>
            <div class="summary-item summary-failed">
                <div class="summary-label">어려움</div>
                <div class="summary-value">{_safe(_format_labels(result.failed_conditions))}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_reason_text(reason: str) -> None:
    st.markdown(
        f'<div class="reason-box">{_safe(reason)}</div>',
        unsafe_allow_html=True,
    )


def _render_slot_filling(results: list[EligibilityResult], key_prefix: str) -> None:
    st.subheader("선택 정책 추가 확인")
    last_answered_result = _last_answered_result(results)
    if last_answered_result is not None:
        _render_refreshed_result(last_answered_result, title="최근 재판정 결과")

    candidates = [result for result in _sort_results(results) if result.missing_fields]
    if not candidates:
        st.success("추가 확인이 필요한 후보 정책이 없습니다.")
        return

    policy_options = {result.policy.name: result.policy.id for result in candidates}
    selected_index = _selected_policy_index(candidates)
    selectbox_key = f"{key_prefix}:slot_policy_select"
    option_names = list(policy_options.keys())
    if st.session_state.get(selectbox_key) not in policy_options:
        st.session_state.pop(selectbox_key, None)
    selected_name = st.selectbox(
        "자세히 확인할 정책",
        option_names,
        key=selectbox_key,
        index=selected_index,
    )
    selected_policy_id = policy_options[selected_name]
    selected_result = next(result for result in candidates if result.policy.id == selected_policy_id)

    st.session_state.selected_policy_id = selected_policy_id
    with st.form(f"{key_prefix}:slot_form"):
        st.write("각 조건이 본인에게 해당하는지 선택하세요. 확실하지 않으면 모름을 선택하세요.")
        _render_privacy_note()
        answers = {}
        for condition_check in _missing_condition_checks(selected_result):
            field = condition_check.field
            question = _slot_question_for_condition_check(condition_check, selected_result.policy.name)
            guide = guide_for_field(field, policy_name=selected_result.policy.name)
            st.markdown(f"**{question}**")
            _render_condition_evidence(selected_result, condition_check)
            if guide:
                _render_question_guide(guide)
            answers[field] = st.radio(
                question,
                list(ANSWER_OPTIONS.keys()),
                key=f"{key_prefix}:{selected_policy_id}:{field}",
                horizontal=True,
                index=2,
                label_visibility="collapsed",
            )

        submitted = st.form_submit_button("답변 반영 후 재판정", type="primary")

    if submitted:
        updated_extra = dict(st.session_state.profile.extra)
        for field, answer_label in answers.items():
            updated_extra[field] = ANSWER_OPTIONS[answer_label]
        st.session_state.profile = st.session_state.profile.model_copy(update={"extra": updated_extra})
        st.session_state.last_answered_policy_id = selected_policy_id
        st.rerun()


def _render_privacy_note() -> None:
    st.markdown(
        """
        <div class="privacy-note">
            정확한 소득액, 재산액, 증빙자료 번호는 입력하지 않습니다.
            공식 기준을 확인한 뒤 해당 여부만 선택하고, 확실하지 않으면 모름을 선택하세요.
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_question_guide(guide: str) -> None:
    st.markdown(
        f'<div class="question-guide">{_safe(guide)}</div>',
        unsafe_allow_html=True,
    )


def _render_condition_evidence(
    result: EligibilityResult,
    condition_check: ConditionCheck,
) -> None:
    source_text = condition_check.source_text or _fallback_policy_evidence(result.policy)
    source_url = condition_check.source_url or result.policy.source_url or result.policy.apply_url
    if not source_text:
        source_text = "API 응답에서 이 조건의 세부 기준 문장을 찾지 못했습니다. 공식 상세 페이지에서 확인한 뒤 확실하지 않으면 모름을 선택하세요."

    title = "판단 근거" if condition_check.source_text else "정책 원문 참고"
    source_link = ""
    if source_url:
        source_link = f'<a href="{_safe(source_url)}" target="_blank" rel="noreferrer">출처 확인</a>'

    st.markdown(
        f"""
        <div class="condition-evidence">
            <div class="condition-evidence-title">{_safe(title)}</div>
            <div class="condition-evidence-text">{_evidence_html(source_text)}</div>
            {source_link}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _slot_question_for_condition_check(condition_check: ConditionCheck, policy_name: str) -> str:
    fallback_question = question_for_field(condition_check.field, policy_name=policy_name)
    if not condition_check.question:
        return fallback_question
    if len(condition_check.question) > 90:
        return fallback_question
    if condition_check.source_text and condition_check.source_text in condition_check.question:
        return fallback_question
    return condition_check.question


def _evidence_html(source_text: str) -> str:
    points = _split_evidence_points(source_text)
    if len(points) <= 1:
        return _safe(source_text)

    items = "\n".join(f"<li>{_safe(point)}</li>" for point in points[:6])
    remaining_count = len(points) - 6
    if remaining_count > 0:
        items += f"<li>{remaining_count}개 항목은 출처에서 추가 확인</li>"
    return f'<ul class="condition-evidence-list">{items}</ul>'


def _split_evidence_points(source_text: str) -> list[str]:
    normalized = " ".join(source_text.split())
    normalized = normalized.strip("'\" ")
    normalized = normalized.replace(" - ", "\n")
    parts = [
        part.strip(" -·•")
        for part in re.split(r"(?=[①②③④⑤⑥⑦⑧⑨⑩])|[\n;；]+", normalized)
        if part.strip(" -·•")
    ]
    return parts


def _missing_condition_checks(result: EligibilityResult) -> list[ConditionCheck]:
    missing_fields = set(result.missing_fields)
    return [
        condition_check
        for condition_check in result.condition_checks
        if condition_check.status == ConditionStatus.MISSING and condition_check.field in missing_fields
    ]


def _fallback_policy_evidence(policy: Policy) -> str:
    for text in policy.evidence_texts:
        if text and text != policy.name:
            return text
    return policy.description or policy.benefit


def _find_result_by_policy_id(
    results: list[EligibilityResult],
    policy_id: str,
) -> EligibilityResult | None:
    for result in results:
        if result.policy.id == policy_id:
            return result
    return None


def _last_answered_result(results: list[EligibilityResult]) -> EligibilityResult | None:
    policy_id = st.session_state.get("last_answered_policy_id")
    if not policy_id:
        return None
    return _find_result_by_policy_id(results, policy_id)


def _selected_policy_index(candidates: list[EligibilityResult]) -> int:
    selected_policy_id = st.session_state.get("selected_policy_id")
    for index, result in enumerate(candidates):
        if result.policy.id == selected_policy_id:
            return index
    return 0


def _render_refreshed_result(result: EligibilityResult, title: str) -> None:
    st.markdown(
        f"""
        <div class="refreshed-head">
            <div class="section-label">{_safe(title)}</div>
            <span class="status-badge status-{result.status.value}">
                {_safe(STATUS_LABELS[result.status])}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_condition_checks(result.condition_checks)
    _render_condition_summary(result)
    if result.reasons:
        _render_reason_text(" ".join(result.reasons))
    st.divider()


def _sort_results(results: list[EligibilityResult]) -> list[EligibilityResult]:
    order = {
        "eligible_likely": 0,
        "need_more_info": 1,
        "not_eligible_likely": 2,
    }
    return sorted(results, key=lambda result: order[result.status.value])


def _format_labels(values: list[str]) -> str:
    if not values:
        return "없음"
    return ", ".join(label_for_field(value) for value in values)


def _safe(value: object) -> str:
    return escape(str(value), quote=True)


def _format_region(values: list[str]) -> str:
    if not values:
        return "제한 없음 또는 확인 필요"
    if "전국" in values:
        return "전국"
    return ", ".join(values)


def _employment_status_label(value: str | None) -> str:
    if value is None:
        return "미입력"
    return EMPLOYMENT_STATUS_LABELS.get(value, value)


def _intent_label(intent: UserIntent | None) -> str:
    if intent is None:
        return "전체"
    labels = {
        "all": "전체",
        "employment": "취업/구직",
        "housing": "주거",
        "savings": "저축/자산",
        "education": "교육/자격",
        "business": "창업",
    }
    if intent.target_policy_keyword:
        return f"{labels.get(intent.category.value, intent.category.value)} / {intent.target_policy_keyword}"
    return labels.get(intent.category.value, intent.category.value)


def _developer_ui_enabled() -> bool:
    return os.getenv("SHOW_DEVELOPER_UI", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _default_user_data_source() -> str:
    configured_source = os.getenv("USER_DATA_SOURCE", "").strip().lower()
    if configured_source in {"sample", "api", "gyeonggi", "combined"}:
        return configured_source
    if (
        os.getenv("YOUTHCENTER_API_KEY", "").strip()
        and os.getenv("YOUTHCENTER_API_BASE_URL", "").strip()
        and os.getenv("GYEONGGI_API_KEY", "").strip()
    ):
        return "combined"
    if os.getenv("YOUTHCENTER_API_KEY", "").strip() and os.getenv("YOUTHCENTER_API_BASE_URL", "").strip():
        return "api"
    if os.getenv("GYEONGGI_API_KEY", "").strip():
        return "gyeonggi"
    return "sample"


def _default_user_api_page_size() -> int:
    return _integer_from_env("USER_API_PAGE_SIZE", default=20, minimum=1, maximum=100)


def _default_user_api_pages() -> int:
    return _integer_from_env("USER_API_PAGES", default=5, minimum=1, maximum=20)


def _default_gyeonggi_detail_limit() -> int:
    return _integer_from_env("GYEONGGI_DETAIL_LIMIT", default=10, minimum=0, maximum=50)


def _gyeonggi_fetch_details_enabled() -> bool:
    return os.getenv("GYEONGGI_FETCH_DETAILS", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _integer_from_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(max(value, minimum), maximum)


def _render_password_gate() -> bool:
    demo_password = _demo_password()
    if demo_password is None:
        return True

    if st.session_state.get("demo_authenticated") is True:
        return True

    st.title("경기도 청년 정책 지원 찾기")
    st.caption("데모 접근을 위해 비밀번호를 입력하세요.")

    with st.form("demo_password_form"):
        entered_password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("입장하기", type="primary")

    if not submitted:
        return False

    if hmac.compare_digest(entered_password, demo_password):
        st.session_state.demo_authenticated = True
        st.rerun()

    st.error("비밀번호가 올바르지 않습니다.")
    return False


def _demo_password() -> str | None:
    env_password = os.getenv("DEMO_PASSWORD", "").strip()
    if env_password:
        return env_password

    try:
        secret_password = st.secrets.get("DEMO_PASSWORD", "")
    except (FileNotFoundError, KeyError, RuntimeError):
        return None

    normalized_password = str(secret_password).strip()
    return normalized_password or None


if __name__ == "__main__":
    main()
