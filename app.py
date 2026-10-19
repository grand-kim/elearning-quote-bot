"""
이러닝 콘텐츠 제작 견적 챗봇 — Streamlit 화면

실행:  streamlit run app.py

화면 흐름
  start  : "어떤 견적이 필요하신가요?" → 답변을 보고 아래 둘 중 하나로 이동
  chat   : 대화형 상담 (구체적인 요청, AI 필요)
  wizard : 단계별 접수 (넓은 요청 또는 AI 키 없음)
  done   : 단계별 접수 완료 → 견적 표시, [AI와 더 자세히 상담하기]로 chat 이동 가능
"""

import pandas as pd
import streamlit as st

import pricing as P
import wizard as W
from chat_agent import run_turn, system_prompt
from excel_export import make_quote_xlsx
from llm import LLMError, make_llm
from quote_engine import calculate_quote
from router import detect
from web_search import web_answer

st.set_page_config(page_title="이러닝 제작 견적 상담", page_icon="💬")


# ── 1. 비밀 키 읽기 (키 값은 절대 화면에 출력하지 않음) ────────────
def get_secret(name, default=None):
    if not name:
        return default
    try:
        return st.secrets.get(name, default)
    except Exception:           # secrets.toml 자체가 없을 때
        return default


llm = make_llm(get_secret)       # 키가 없으면 None → 단계별 견적만 사용
SERPAPI_KEY = get_secret("SERPAPI_KEY")

GREETING = (f"안녕하세요, {P.COMPANY_NAME} 이러닝 콘텐츠 제작 견적 상담입니다. 😊\n\n"
            "**어떤 견적이 필요하신가요?**\n\n"
            "- 구체적으로 말씀해 주시면 바로 대화로 상담해 드려요. "
            "(예: *애니메이션형 10차시, 차시당 25분, 성우 포함*)\n"
            "- 아직 정해진 게 많지 않다면 단계별로 하나씩 여쭤볼게요. "
            "(예: *20분짜리 영상 제작 견적*)")


# ── 2. 상태 초기화 (st.session_state: 화면이 새로 그려져도 유지) ─────
def reset():
    s = st.session_state
    s.stage = "start"
    s.history = [{"role": "assistant", "content": GREETING}]
    s.step = 0              # 단계별 접수 진행 위치
    s.answers = {}          # 단계별 접수 답변
    s.system = system_prompt()
    s.llm_messages = []     # AI 대화 기록
    s.quote = None
    s.quote_info = {}


if "stage" not in st.session_state:
    reset()
if "web_history" not in st.session_state:
    st.session_state.web_history = []
S = st.session_state


def say(role, text):
    S.history.append({"role": role, "content": text})


def ai_reply(user_text=None, hidden=False):
    """AI에게 메시지를 보내고 답변을 대화창에 추가. 실패하면 False."""
    if user_text:
        S.llm_messages.append({"role": "user", "content": user_text})
    try:
        with st.spinner("답변 작성 중..."):
            reply, quote, info = run_turn(llm, S.system, S.llm_messages)
    except LLMError:
        if user_text:
            S.llm_messages.pop()
        st.error("AI 서비스 호출에 실패했습니다. API 키·사용량을 확인하거나 잠시 후 다시 시도해 주세요.")
        return False
    say("assistant", reply)
    if quote:
        S.quote = quote
        S.quote_info.update({k: v for k, v in info.items() if v})
    return True


def start_wizard(prefill=None):
    S.stage = "wizard"
    S.step = 0
    S.answers = {"sessions": 1, "minutes_per_session": P.BASE_MINUTES,
                 "voice_over": False, "subtitles": False, "filming_days": 0}
    S.answers.update({k: v for k, v in (prefill or {}).items() if k != "is_specific"})
    say("assistant", "좋습니다. 정확한 견적을 위해 몇 가지를 단계별로 여쭤볼게요. "
                     "말씀하신 내용은 미리 채워 두었습니다.")


# ── 3. 사이드바 ───────────────────────────────────────────────
with st.sidebar:
    mode = st.radio("모드", ["견적 받기", "웹에서 찾기"])
    if st.button("처음부터 다시", use_container_width=True):
        reset()
        st.rerun()
    if llm:
        st.caption(f"AI 상담: 켜짐 ({llm.provider} · {llm.model})")
    else:
        st.caption("AI 상담: 꺼짐 (API 키 없음) — 단계별 견적만 제공")
    with st.expander("견적 산정 기준"):
        st.caption(P.WAGE_SOURCE)
        st.dataframe(pd.DataFrame([{"직무": v["label"], "적용 SW직무": v["sw_job"],
                                    "일 단가(원)": f"{P.SW_DAILY_WAGE[v['sw_job']]:,}"}
                                   for v in P.ROLES.values()]), hide_index=True)
        st.caption(f"제경비 {P.OVERHEAD_RATE:.0%} · 기술료 {P.TECH_FEE_RATE:.0%} · VAT {P.VAT_RATE:.0%}")


# ── 4. 견적 카드 ───────────────────────────────────────────────
def show_quote(q, info):
    with st.container(border=True):
        st.subheader("📄 예상 견적")
        c1, c2, c3 = st.columns(3)
        c1.metric("공급가액", f"{q['공급가액']:,}원")
        c2.metric("부가세", f"{q['부가세']:,}원")
        c3.metric("합계", f"{q['합계']:,}원")
        st.caption(f"차시당 약 {q['차시당 단가']:,}원 (VAT 별도) · {q['단가 기준']}")
        with st.expander("상세 내역 보기"):
            st.dataframe(pd.DataFrame(q["인건비 내역"]).style.format({"일 단가": "{:,}", "금액": "{:,}"}),
                         hide_index=True)
            if q["직접경비 내역"]:
                st.dataframe(pd.DataFrame(q["직접경비 내역"]).style.format({"금액": "{:,}"}),
                             hide_index=True)
            st.write(f"직접인건비 {q['직접인건비']:,} + 제경비 {q['제경비']:,} + "
                     f"기술료 {q['기술료']:,} + 직접경비 {q['직접경비']:,}")
        st.download_button(
            "견적서 다운로드 (Excel)", data=make_quote_xlsx(q, info),
            file_name=f"이러닝제작견적_{info.get('client_name') or '고객'}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ── 5. 단계별 접수: 현재 질문 1개를 입력 폼으로 표시 ──────────────────
def wizard_form():
    step = W.STEPS[S.step]
    a = S.answers
    with st.chat_message("assistant"):
        st.markdown(f"**({S.step + 1}/{len(W.STEPS)})** {step['q']}")
        with st.form(f"step_{S.step}"):
            k = step["kind"]
            new = {}
            if k == "text":
                new[step["key"]] = st.text_input("답변", a.get(step["key"], ""),
                                                 placeholder=step.get("placeholder", ""),
                                                 label_visibility="collapsed")
            elif k == "textarea":
                new[step["key"]] = st.text_area("답변", a.get(step["key"], ""),
                                                label_visibility="collapsed")
            elif k == "select":
                opts = step["options"]
                cur = a.get(step["key"])
                new[step["key"]] = st.radio("선택", opts, index=opts.index(cur) if cur in opts else 0,
                                            label_visibility="collapsed")
            elif k == "type":
                opts = list(P.CONTENT_TYPES) + [W.UNSURE]
                cur = W.UNSURE if a.get("type_unsure") else a.get("content_type")
                pick = st.radio("유형", opts, index=opts.index(cur) if cur in opts else 0,
                                format_func=lambda t: t if t == W.UNSURE
                                else f"{t} — {P.CONTENT_TYPES[t]['desc']}",
                                label_visibility="collapsed")
                new["type_unsure"] = pick == W.UNSURE
                new["content_type"] = "기본형" if pick == W.UNSURE else pick
            elif k == "volume":
                c1, c2 = st.columns(2)
                new["sessions"] = c1.number_input("차시 수", 1, 200, int(a["sessions"]))
                new["minutes_per_session"] = c2.number_input("차시당 분량(분)", 5, 120,
                                                             int(a["minutes_per_session"]))
                st.caption("영상 1편이면 차시 수 1로 두세요.")
            elif k == "options":
                new["voice_over"] = st.checkbox("전문 성우 녹음", a["voice_over"])
                new["subtitles"] = st.checkbox("자막 제작", a["subtitles"])
                default_days = a["filming_days"] or (1 if a.get("content_type") in ("촬영형", "혼합형") else 0)
                new["filming_days"] = st.number_input("스튜디오 촬영 일수 (없으면 0)", 0, 60, int(default_days))

            c1, c2 = st.columns([1, 1])
            go = c1.form_submit_button("다음 ▶", type="primary", use_container_width=True)
            back = c2.form_submit_button("◀ 이전", use_container_width=True, disabled=S.step == 0)

    if back:
        S.step -= 1
        del S.history[-2:]          # 직전 질문·답변 말풍선 제거
        st.rerun()
    if go:
        if k in ("text", "textarea") and not step.get("optional") and not str(new[step["key"]]).strip():
            st.warning("내용을 입력해 주세요.")
            return
        a.update(new)
        say("assistant", step["q"])
        say("user", W.answer_text(step, a))
        S.step += 1
        if S.step == len(W.STEPS):
            finish_wizard()
        st.rerun()


def finish_wizard():
    a = S.answers
    S.quote = calculate_quote(**W.calc_args(a))
    S.quote_info = {k: a.get(k, "") for k in ("client_name", "domain", "audience", "course_title",
                                              "contact", "deadline", "budget", "reference")}
    msg = "접수해 주셔서 감사합니다. 말씀하신 조건으로 산정한 예상 견적입니다."
    check = W.budget_check(S.quote, a)
    if check:
        msg += "\n\n" + check
    if a.get("type_unsure"):
        msg += "\n\n💡 유형은 기본형으로 먼저 산정했습니다. 상담을 통해 더 맞는 유형을 추천해 드릴게요."
    say("assistant", msg)
    S.stage = "done"


# ── 6. 견적 받기 화면 ──────────────────────────────────────────
if mode == "견적 받기":
    st.title("💬 이러닝 콘텐츠 제작 견적 상담")

    for m in S.history:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # 시작: 첫 답변으로 방식 결정
    if S.stage == "start":
        if st.button("단계별로 안내받기"):
            start_wizard()
            st.rerun()
        text = st.chat_input("필요한 견적을 말씀해 주세요")
        if text is not None:
            text = text.strip()
            if not text:
                st.warning("내용을 입력해 주세요.")
                st.stop()
            say("user", text)
            found = detect(text)
            if found["is_specific"] and llm:
                S.stage = "chat"
                ai_reply(text)
            else:
                start_wizard(found)
            st.rerun()

    elif S.stage == "wizard":
        wizard_form()

    elif S.stage == "done":
        show_quote(S.quote, S.quote_info)
        if llm:
            if st.button("🗨️ AI와 더 자세히 상담하기", type="primary"):
                S.stage = "chat"
                S.system = system_prompt(W.context_for_ai(S.answers, S.quote))
                S.llm_messages = []
                ai_reply("(단계별 접수를 마쳤습니다. 견적을 더 정확히 하기 위한 질문을 시작해 주세요.)")
                st.rerun()
        else:
            st.info("담당자가 접수 내용을 확인한 뒤 연락드리겠습니다.")

    elif S.stage == "chat":
        if S.quote:
            show_quote(S.quote, S.quote_info)
        text = st.chat_input("메시지를 입력하세요")
        if text is not None:
            text = text.strip()
            if not text:
                st.warning("내용을 입력해 주세요.")
                st.stop()
            say("user", text)
            if not ai_reply(text):
                S.history.pop()
                st.stop()
            st.rerun()


# ── 7. 웹에서 찾기 (가이드의 LangGraph 웹 검색) ───────────────────
else:
    st.title("🔎 웹에서 찾기")
    st.caption("제작 트렌드, 노임단가 공표 소식 등 최신 정보를 웹 검색 결과로 답합니다.")
    for m in S.web_history:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    q = st.chat_input("검색할 질문을 입력하세요")
    if q is not None:
        q = q.strip()
        if not q:
            st.warning("질문을 입력해 주세요.")
            st.stop()
        if not llm or not SERPAPI_KEY:
            st.error("웹 검색에는 AI 키와 SERPAPI_KEY가 모두 필요합니다. Secrets 설정을 확인해 주세요.")
            st.stop()
        try:
            with st.spinner("검색 중..."):
                answer, sources, status = web_answer(q, llm, SERPAPI_KEY)
        except LLMError:
            st.error("AI 서비스 호출에 실패했습니다. 잠시 후 다시 시도해 주세요.")
            st.stop()
        if sources:
            answer += "\n\n**출처**\n" + "\n".join(
                f"{i}. [{s['title']}]({s['link']}) {s['date']}" for i, s in enumerate(sources, 1))
        if status == "error":
            answer = "⚠️ " + answer
        S.web_history += [{"role": "user", "content": q}, {"role": "assistant", "content": answer}]
        st.rerun()
