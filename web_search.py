"""
웹 검색 모드 (가이드의 'LangGraph + SerpAPI' 구조)

그래프:  search(검색) ──결과 있음──▶ answer(LLM 답변) ──▶ 끝
                   └─오류/결과 없음──────────────────────▶ 끝
"""

from typing import TypedDict

import requests
from langgraph.graph import END, StateGraph


class SearchState(TypedDict, total=False):
    question: str
    serpapi_key: str
    llm: object         # llm.LLM (OpenAI 또는 Claude)
    results: list       # [{title, link, date, snippet}]
    status: str         # "ok" | "error" | "empty"
    answer: str


def search_node(state: SearchState):
    try:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={"q": state["question"], "api_key": state["serpapi_key"],
                    "hl": "ko", "gl": "kr", "num": 5},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data and "organic_results" not in data:
            # SerpAPI는 '결과 없음'도 error 필드로 알려 줌 → 구분
            if "hasn't returned any results" in data["error"]:
                return {"status": "empty", "results": []}
            return {"status": "error", "results": [], "answer": "검색 서비스 오류가 발생했습니다."}
    except requests.RequestException:
        return {"status": "error", "results": [],
                "answer": "검색 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요."}

    results = [{"title": r.get("title", ""), "link": r.get("link", ""),
                "date": r.get("date", ""), "snippet": r.get("snippet", "")}
               for r in data.get("organic_results", [])[:5]]
    if not results:
        return {"status": "empty", "results": []}
    return {"status": "ok", "results": results}


def answer_node(state: SearchState):
    sources = "\n".join(
        f"[{i}] {r['title']} ({r['date'] or '날짜 없음'})\n{r['snippet']}"
        for i, r in enumerate(state["results"], 1)
    )
    prompt = ("아래 검색 결과만 근거로 질문에 한국어로 답하세요. "
              "근거 문장 끝에 [번호]를 붙이고, 결과에 없는 내용은 모른다고 하세요.\n\n"
              f"질문: {state['question']}\n\n검색 결과:\n{sources}")
    return {"answer": state["llm"].text(prompt)}


def _route(state: SearchState):
    return "answer" if state.get("status") == "ok" else END


def build_graph():
    g = StateGraph(SearchState)
    g.add_node("search", search_node)
    g.add_node("answer", answer_node)
    g.set_entry_point("search")
    g.add_conditional_edges("search", _route, {"answer": "answer", END: END})
    g.add_edge("answer", END)
    return g.compile()


graph_app = build_graph()


def web_answer(question, llm, serpapi_key):
    """반환: (답변, 출처 목록, 상태)"""
    state = graph_app.invoke({"question": question, "llm": llm, "serpapi_key": serpapi_key})
    status = state.get("status")
    if status == "empty":
        return "검색 결과가 없습니다. 검색어를 바꿔 보세요.", [], status
    return state.get("answer", ""), state.get("results", []), status
