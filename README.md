# 이러닝 콘텐츠 제작 견적 챗봇

2026년 SW기술자 노임단가 기준으로 이러닝 제작 예상 견적을 계산해 엑셀 견적서로 내려주는 Streamlit 챗봇입니다.

## 상담 흐름

```text
"어떤 견적이 필요하신가요?"
   ├─ 구체적 (유형·차시·분량 중 2개 이상) ──▶ 대화형 상담 (AI)
   └─ 넓음 ("20분짜리 영상 견적") ─────────▶ 단계별 접수 (11단계, AI 불필요)
                                              └─ 견적·예산 비교 ─▶ [AI와 더 자세히 상담하기]
```
- 금액은 항상 `quote_engine.py`가 `pricing.py` 기준으로 계산합니다. AI는 조건 수집과 설명만 합니다.
- API 키가 없으면 단계별 접수만 제공합니다.
- `LLM_PROVIDER`로 OpenAI ↔ Claude 전환 (`secrets.toml` 한 줄).
`문서/종합실습.ipynb` 가이드의 구조(Streamlit 화면 + 모드 선택 + LangGraph 웹 검색 + Secrets 키 관리)를 따랐습니다.

## 폴더 구성

```text
17_이러닝콘텐츠 제작견적 챗봇/
├── app.py              # Streamlit 화면과 실행 흐름
├── pricing.py          # ★ 단가·투입공수·요율 설정 (금액 조정은 여기서만)
├── quote_engine.py     # 견적 계산 (AI 없이 파이썬이 계산)
├── router.py           # 첫 답변이 구체적인지 판단 (규칙 기반)
├── wizard.py           # 단계별 접수 질문 목록·예산 비교
├── chat_agent.py       # 대화형 상담 AI (조건 수집 → 계산 도구 호출)
├── llm.py              # OpenAI / Claude 연결 (공급자 전환)
├── web_search.py       # 웹에서 찾기 모드 (LangGraph + SerpAPI)
├── excel_export.py     # 엑셀 견적서 생성
├── requirements.txt
├── .gitignore
└── .streamlit/
    └── secrets.toml.example   # 복사해서 secrets.toml로 저장
```

## 로컬 실행

```bash
cd "D:\01_프로젝트\17_이러닝콘텐츠 제작견적 챗봇"
pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # 키 입력
python quote_engine.py        # 계산만 먼저 확인 (API 키 불필요)
streamlit run app.py
```

## 필수 테스트 (가이드 기준)

| 시험 상황 | 기대 결과 |
|---|---|
| "애니메이션 10차시 25분 성우 포함" | 대화형 상담으로 바로 견적 |
| "20분짜리 영상 제작 견적" | 단계별 접수, 분량 20분 미리 채움 |
| 단계별 접수 완료 | 견적 카드·예산 비교·엑셀 다운로드 |
| [AI와 더 자세히 상담하기] | 접수 내용을 다시 묻지 않고 세부 질문 |
| API 키 없음 | 단계별 견적만 동작, 키 노출 없음 |
| 빈 입력 | API를 호출하지 않고 입력 안내 |
| 웹 검색 질문 | 답변 + 출처 링크 |
| 검색 오류 / 결과 없음 | 서로 다른 안내 문구 |

## 다음 단계 (기획 방향 중 미구현)
- 견적서 PDF 발급
- 견적 확정 시 담당자 알림(이메일/슬랙)
- 홈페이지 삽입 위젯 (배포 URL을 iframe으로 삽입)
