from __future__ import annotations

from collections.abc import Callable
import hmac
import os
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from app.answer_generator import STATUS_LABELS
from app.eligibility import check_all
from app.input_parser import normalize_employment_status
from app.natural_language_parser import parse_natural_language_input
from app.policy_normalizer import normalize_youthcenter_response
from app.retriever import load_policies, retrieve_policies
from app.schemas import EligibilityResult, Policy, UserIntent, UserProfile
from app.slot_questions import label_for_field, question_for_field
from app.youthcenter_client import YouthCenterClient, load_youthcenter_config


POLICY_PATH = PROJECT_ROOT / "data" / "policies.sample.json"
ANSWER_OPTIONS = {
    "해당함": True,
    "해당하지 않음": False,
    "모름": None,
}
DATA_SOURCE_OPTIONS = {
    "샘플 데이터": "sample",
    "온통청년 API": "api",
}
EMPLOYMENT_STATUS_LABELS = {
    "job_seeker": "구직 중",
    "unemployed": "미취업",
    "employed": "재직 중",
}


def main() -> None:
    st.set_page_config(page_title="경기도 청년 정책 지원 찾기", layout="wide")
    if not _render_password_gate():
        return

    st.title("경기도 청년 정책 지원 찾기")
    st.caption("경기도 거주 상황을 입력하면 받을 수 있는 지원을 찾아보고, 필요한 조건만 추가로 확인합니다.")

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
                progress_callback=lambda message: st.write(message),
            )
        except Exception as error:  # noqa: BLE001 - UI should show external API/setup errors.
            status.update(label="정책 데이터를 불러오지 못했습니다.", state="error", expanded=True)
            st.error(f"정책 데이터를 불러오지 못했습니다: {error}")
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
    progress_callback: Callable[[str], None] | None = None,
) -> list[Policy]:
    if data_source == "sample":
        return load_policies(POLICY_PATH)

    config = load_youthcenter_config()
    client = YouthCenterClient.from_config(config)
    policies: list[Policy] = []
    seen_policy_ids: set[str] = set()

    for page in range(1, pages + 1):
        if progress_callback is not None:
            progress_callback(f"온통청년 API에서 정책 데이터를 가져오는 중입니다. ({page}/{pages})")
        response_text = client.fetch_policies(page=page, page_size=page_size)
        for policy in normalize_youthcenter_response(response_text):
            if policy.id in seen_policy_ids:
                continue
            seen_policy_ids.add(policy.id)
            policies.append(policy)

    return policies


def _loading_source_message(data_source: str) -> str:
    if data_source == "api":
        return "온통청년 API에서 최신 정책 후보를 확인하고 있습니다."
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
    st.subheader("후보 정책")
    for index, result in enumerate(_sort_results(results), start=1):
        policy = result.policy
        with st.container(border=True):
            st.markdown(f"**{index}. {policy.name}**")
            st.caption(f"판정: {STATUS_LABELS[result.status]}")
            st.write(f"대상 지역: {_format_region(policy.region)}")
            st.write(f"충족 조건: {_format_labels(result.matched_conditions)}")
            st.write(f"부족한 정보: {_format_labels(result.missing_fields)}")
            st.write(f"어려운 조건: {_format_labels(result.failed_conditions)}")
            if result.reasons:
                st.write(" ".join(result.reasons))
            if policy.benefit:
                with st.expander("지원 내용"):
                    st.write(policy.benefit)
            if policy.apply_url:
                st.link_button("신청 링크", policy.apply_url)


def _render_slot_filling(results: list[EligibilityResult], key_prefix: str) -> None:
    st.subheader("선택 정책 추가 확인")
    candidates = [result for result in _sort_results(results) if result.missing_fields]
    if not candidates:
        st.success("추가 확인이 필요한 후보 정책이 없습니다.")
        return

    policy_options = {result.policy.name: result.policy.id for result in candidates}
    selected_name = st.selectbox(
        "자세히 확인할 정책",
        list(policy_options.keys()),
        key=f"{key_prefix}:slot_policy_select",
    )
    selected_policy_id = policy_options[selected_name]
    selected_result = next(result for result in candidates if result.policy.id == selected_policy_id)

    st.session_state.selected_policy_id = selected_policy_id
    with st.form(f"{key_prefix}:slot_form"):
        st.write("각 조건이 본인에게 해당하는지 선택하세요. 확실하지 않으면 모름을 선택하세요.")
        answers = {}
        for field in selected_result.missing_fields:
            answers[field] = st.radio(
                question_for_field(field, policy_name=selected_result.policy.name),
                list(ANSWER_OPTIONS.keys()),
                key=f"{key_prefix}:{selected_policy_id}:{field}",
                horizontal=True,
                index=2,
            )

        submitted = st.form_submit_button("답변 반영 후 재판정", type="primary")

    if submitted:
        updated_extra = dict(st.session_state.profile.extra)
        for field, answer_label in answers.items():
            updated_extra[field] = ANSWER_OPTIONS[answer_label]
        st.session_state.profile = st.session_state.profile.model_copy(update={"extra": updated_extra})
        st.session_state.last_answered_policy_id = selected_policy_id
        st.rerun()

    if st.session_state.last_answered_policy_id == selected_policy_id:
        refreshed_result = _find_result_by_policy_id(_current_results(), selected_policy_id)
        if refreshed_result is not None:
            st.divider()
            st.markdown("**재판정 결과**")
            st.write(f"판정: {STATUS_LABELS[refreshed_result.status]}")
            st.write(f"충족 조건: {_format_labels(refreshed_result.matched_conditions)}")
            st.write(f"부족한 정보: {_format_labels(refreshed_result.missing_fields)}")
            st.write(f"어려운 조건: {_format_labels(refreshed_result.failed_conditions)}")
            if refreshed_result.reasons:
                st.write(" ".join(refreshed_result.reasons))


def _find_result_by_policy_id(
    results: list[EligibilityResult],
    policy_id: str,
) -> EligibilityResult | None:
    for result in results:
        if result.policy.id == policy_id:
            return result
    return None


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
    configured_source = os.getenv("USER_DATA_SOURCE", "sample").strip().lower()
    if configured_source in {"sample", "api"}:
        return configured_source
    return "sample"


def _default_user_api_page_size() -> int:
    return _integer_from_env("USER_API_PAGE_SIZE", default=20, minimum=1, maximum=100)


def _default_user_api_pages() -> int:
    return _integer_from_env("USER_API_PAGES", default=5, minimum=1, maximum=20)


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
