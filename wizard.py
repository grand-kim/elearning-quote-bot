"""
단계별 접수 — 질문 목록과 예산 비교

질문을 추가·삭제·순서 변경하려면 STEPS 리스트만 고치면 됩니다.
kind 종류: text, textarea, select, type(콘텐츠 유형), volume(분량), options(추가 옵션)
"""

import pricing as P
from quote_engine import calculate_quote

# 예산 범위 (합계·VAT 포함 기준, 단위: 원)
BUDGETS = {
    "1천만원 미만": (0, 10_000_000),
    "1천만~3천만원": (10_000_000, 30_000_000),
    "3천만~5천만원": (30_000_000, 50_000_000),
    "5천만~1억원": (50_000_000, 100_000_000),
    "1억원 이상": (100_000_000, None),
    "아직 미정": None,
}

UNSURE = "잘 모르겠어요 (기본형으로 먼저 산정)"

STEPS = [
    {"key": "client_name", "kind": "text", "q": "먼저 기관(회사)명을 알려 주세요.",
     "placeholder": "예: OO공사 인재개발원"},
    {"key": "domain", "kind": "select", "q": "기관 유형(도메인)은 어디에 해당하나요?",
     "options": ["공공기관", "대학·교육기관", "기업", "협회·단체", "기타"]},
    {"key": "audience", "kind": "text", "q": "교육 대상은 누구인가요?",
     "placeholder": "예: 신규 입사자, 전 직원, 현장 관리자"},
    {"key": "course_title", "kind": "text", "q": "과정 주제(과정명)를 알려 주세요.",
     "placeholder": "예: 개인정보보호 기본교육"},
    {"key": "content_type", "kind": "type", "q": "원하시는 콘텐츠 유형을 골라 주세요."},
    {"key": "volume", "kind": "volume", "q": "분량을 알려 주세요."},
    {"key": "options", "kind": "options", "q": "추가 옵션을 선택해 주세요."},
    {"key": "budget", "kind": "select", "q": "예산 범위는 어느 정도로 생각하고 계신가요? (VAT 포함)",
     "options": list(BUDGETS)},
    {"key": "deadline", "kind": "text", "q": "희망 납기(오픈 시기)는 언제인가요?",
     "placeholder": "예: 2027년 2월 말", "optional": True},
    {"key": "reference", "kind": "textarea", "optional": True,
     "q": "참고할 레퍼런스가 있으면 알려 주세요. (URL, 비슷한 과정, 원하는 느낌 등)"},
    {"key": "contact", "kind": "text", "q": "마지막으로 담당자 성함과 연락처(이메일/전화)를 남겨 주세요.",
     "placeholder": "예: 홍길동 / hong@example.com"},
]


def answer_text(step, a):
    """사용자 답변을 말풍선용 문장으로 만듭니다."""
    k = step["kind"]
    if k == "volume":
        return f"{a['sessions']}차시 × {a['minutes_per_session']}분"
    if k == "options":
        opts = [name for name, on in [("성우", a["voice_over"]), ("자막", a["subtitles"])] if on]
        if a["filming_days"]:
            opts.append(f"촬영 {a['filming_days']}일")
        return ", ".join(opts) or "추가 옵션 없음"
    if k == "type" and a.get("type_unsure"):
        return UNSURE
    return a.get(step["key"]) or "(건너뜀)"


def calc_args(a):
    return {k: a[k] for k in ("content_type", "sessions", "minutes_per_session",
                              "voice_over", "subtitles", "filming_days")}


def budget_check(quote, a):
    """예산과 비교한 안내 문장(마크다운)을 돌려줍니다."""
    rng = BUDGETS.get(a.get("budget"))
    if not rng:
        return ""
    low, high = rng
    total = quote["합계"]
    if high is None or total <= high:
        if total < low:
            return "✅ 예산 범위보다 낮게 산정되었습니다. 남는 예산으로 유형 상향이나 옵션 추가도 가능합니다."
        return "✅ 말씀하신 예산 범위 안에 들어옵니다."

    over = total - high
    msg = f"⚠️ 예산 상한보다 **{over:,}원** 높습니다."
    alts = []
    for ctype in P.CONTENT_TYPES:
        if ctype == a["content_type"]:
            continue
        args = calc_args(a) | {"content_type": ctype}
        if ctype not in ("촬영형", "혼합형"):
            args["filming_days"] = 0
        q = calculate_quote(**args)
        if q["합계"] <= high:
            alts.append(f"- **{ctype}**으로 바꾸면 합계 {q['합계']:,}원")
    if alts:
        msg += " 같은 분량에서 예산 안에 들어오는 대안입니다.\n" + "\n".join(alts)
    else:
        msg += " 차시 수를 줄이거나 옵션을 조정하는 방향으로 상담해 드릴게요."
    return msg


def context_for_ai(a, quote):
    """대화형 상담으로 넘길 때 AI에게 줄 접수 요약."""
    lines = [f"- {s['q']} → {answer_text(s, a)}" for s in STEPS]
    lines.append(f"- 산정 견적: 합계 {quote['합계']:,}원 (공급가액 {quote['공급가액']:,}원)")
    return "\n".join(lines)
