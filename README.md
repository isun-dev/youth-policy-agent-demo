# 청년 정책 AI AGENT(계속 개발중입니다)

청년의 상황과 정책 자격요건을 비교해 신청 가능성을 안내하는 Python 기반 AI Agent 프로젝트입니다.

사용자가 자연어로 자신의 상황을 입력하면 조건을 구조화하고, 정책별로 충족 조건, 부족한 조건, 어려운 조건을 분리해 보여줍니다.

## Streamlit 배포 설정

기본 데모 설정:

```toml
DEMO_PASSWORD = "원하는비밀번호"
SHOW_DEVELOPER_UI = "false"
USER_DATA_SOURCE = "sample"
```

온통청년 API를 사용자 화면에서 사용하려면:

```toml
USER_DATA_SOURCE = "api"
USER_API_PAGE_SIZE = "20"
USER_API_PAGES = "2"
YOUTHCENTER_API_KEY = "..."
YOUTHCENTER_API_BASE_URL = "https://www.youthcenter.go.kr/go/ythip/getPlcy"
```

OpenAI 기반 문장 해석을 사용하려면:

```toml
OPENAI_API_KEY = "..."
OPENAI_MODEL = "gpt-4o-mini"
```

## 참고

- 이 저장소는 공개 데모용이며, 완성된 상용 서비스가 아닙니다.
- 샘플 정책 데이터는 실제 신청 가능 여부를 보장하지 않습니다.
- 실제 정책 정보는 바뀔 수 있으므로 공식 출처와 최신 공고 확인이 필요합니다.
