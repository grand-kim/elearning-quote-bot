"""
대화형 견적 상담 (AI)

흐름:
  고객 메시지 → AI가 부족한 조건을 질문
             → 조건이 다 모이면 AI가 calculate_quote 도구를 '호출 요청'
             → 파이썬이 quote_engine으로 실제 계산 (AI는 금액을 만들지 않음)
             → 계산 결과를 AI에게 돌려주면 AI가 고객에게 설명
"""

import pricing as P
from quote_engine import calculate_quote, summary_text

_type_list = "\n".join(f"- {name}: {info['desc']}" for name, info in P.CONTENT_TYPES.items())

BASE_PROMPT = f"""당신은 {P.COMPANY_NAME}의 이러닝 콘텐츠 제작 견적 상담원입니다.
고객(발주처 담당자)과 친절하고 간결한 한국어로 대화합니다.

[견적 계산에 꼭 필요한 조건]
1. 콘텐츠 유형 (아래 중 하나)
{_type_list}
2. 차시 수
3. 차시당 분량(분) — 고객이 모르면 일반적인 {P.BASE_MINUTES}분을 제안
4. 옵션: 전문 성우 녹음, 자막, (촬영형·혼합형이면) 촬영 일수

[견적서에 기재할 정보] 과정명, 기관명, 담당자 연락처, 희망 납기

[규칙]
- 한 번에 질문은 1~2개만 합니다.
- 조건이 모두 모이면 한 줄로 요약해 확인받은 뒤 calculate_quote 도구를 호출합니다.
- 금액은 절대 직접 추정하지 말고, 도구 결과의 숫자만 안내합니다.
- 금액은 '부가세 별도/포함'을 명확히 하고, 최종 금액은 담당자 협의로 확정된다고 안내합니다.
- 단가표에 없는 요구(인터랙션, 다국어 등)는 금액을 말하지 말고 notes에 기록해 담당자 검토로 넘깁니다.
"""

DEEP_DIVE_PROMPT = """
[단계별 접수 내용 — 이미 받은 정보이므로 다시 묻지 마세요]
{context}

[지금 할 일]
견적을 더 정확히 하기 위해 아래를 1~2개씩 차례로 묻고, 답을 notes에 정리하세요.
- 학습 목표와 꼭 담아야 할 핵심 내용, 원고(교안) 보유 여부
- 퀴즈·실습 등 인터랙션 요구, 캐릭터·디자인 톤 (레퍼런스가 있으면 그 기준으로)
- 탑재할 LMS와 규격(SCORM 등), 모바일 지원 여부
- 검수(수정) 횟수와 발주처 내부 일정
조건(유형·분량·옵션)이 바뀌면 calculate_quote를 다시 호출해 새 금액을 안내하세요.
"""

TOOLS = [{
    "name": "calculate_quote",
    "description": "확인된 제작 조건으로 이러닝 콘텐츠 제작 견적을 계산한다.",
    "parameters": {
        "type": "object",
        "properties": {
            "content_type": {"type": "string", "enum": list(P.CONTENT_TYPES)},
            "sessions": {"type": "integer", "description": "차시 수"},
            "minutes_per_session": {"type": "integer", "description": "차시당 분량(분)"},
            "voice_over": {"type": "boolean", "description": "전문 성우 녹음 여부"},
            "subtitles": {"type": "boolean", "description": "자막 제작 여부"},
            "filming_days": {"type": "integer", "description": "스튜디오 촬영 일수 (없으면 0)"},
            "course_title": {"type": "string", "description": "과정명"},
            "client_name": {"type": "string", "description": "기관(회사)명"},
            "contact": {"type": "string", "description": "담당자 성함·연락처"},
            "deadline": {"type": "string", "description": "희망 납기"},
            "notes": {"type": "string", "description": "상담에서 확인한 세부 요구사항 메모"},
        },
        "required": ["content_type", "sessions", "minutes_per_session"],
    },
}]

_CALC_KEYS = ["content_type", "sessions", "minutes_per_session",
              "voice_over", "subtitles", "filming_days"]
_INFO_KEYS = ["course_title", "client_name", "contact", "deadline", "notes"]


def system_prompt(context=None):
    """대화형 상담용 지시문. 단계별 접수를 마치고 넘어온 경우 context를 붙입니다."""
    if context:
        return BASE_PROMPT + DEEP_DIVE_PROMPT.format(context=context)
    return BASE_PROMPT


def run_turn(llm, system, messages):
    """
    messages 끝에 고객 메시지가 들어 있는 상태로 호출합니다.
    반환: (AI 답변, 새 견적 dict 또는 None, 견적서 정보 dict 또는 None)
    """
    holder = {}

    def handler(name, args):
        if name != "calculate_quote":
            return "알 수 없는 도구입니다."
        try:
            quote = calculate_quote(**{k: args[k] for k in _CALC_KEYS if k in args})
        except (ValueError, TypeError, KeyError) as e:
            return f"[계산 실패] {e} — 고객에게 해당 조건을 다시 확인하세요."
        holder["quote"] = quote
        holder["info"] = {k: args.get(k, "") for k in _INFO_KEYS}
        return summary_text(quote)

    reply = llm.run_tools(system, messages, TOOLS, handler)
    return reply, holder.get("quote"), holder.get("info")
