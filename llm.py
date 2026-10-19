"""
AI 공급자 연결 (OpenAI ↔ Claude 전환용)

secrets.toml 의 LLM_PROVIDER 값 하나로 바꿉니다.
  LLM_PROVIDER = "openai"     → OPENAI_API_KEY 사용 (실습용)
  LLM_PROVIDER = "anthropic"  → ANTHROPIC_API_KEY 사용 (Claude)
다른 파일은 공급자를 몰라도 되도록, 여기서 차이를 모두 감춥니다.
"""

DEFAULT_MODELS = {"openai": "gpt-4o-mini", "anthropic": "claude-haiku-5-5"}


class LLMError(Exception):
    """AI 호출 실패 (키 오류, 네트워크, 사용량 초과 등)."""


class LLM:
    def __init__(self, provider, api_key, model=None):
        self.provider = provider
        self.model = model or DEFAULT_MODELS[provider]
        if provider == "anthropic":
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
            self._errors = (anthropic.APIError,)
        else:
            import openai
            self.client = openai.OpenAI(api_key=api_key)
            self._errors = (openai.OpenAIError,)

    # ── 단순 질문 → 답변 (웹 검색 답변 생성에 사용) ──────────────
    def text(self, prompt):
        try:
            if self.provider == "anthropic":
                resp = self.client.messages.create(
                    model=self.model, max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}])
                return "".join(b.text for b in resp.content if b.type == "text")
            resp = self.client.chat.completions.create(
                model=self.model, temperature=0.2,
                messages=[{"role": "user", "content": prompt}])
            return resp.choices[0].message.content or ""
        except self._errors as e:
            raise LLMError(str(e)) from e

    # ── 도구(함수) 호출이 가능한 대화 ─────────────────────────────
    def run_tools(self, system, messages, tools, handler, max_rounds=3):
        """
        system   : 시스템 지시문(문자열)
        messages : 대화 기록 리스트 (이 함수가 직접 이어서 기록함)
        tools    : [{"name", "description", "parameters"}]
        handler  : handler(도구이름, 인자dict) → 결과 문자열
        반환     : AI의 최종 답변 텍스트
        """
        try:
            for _ in range(max_rounds):
                if self.provider == "anthropic":
                    done, reply = self._anthropic_round(system, messages, tools, handler)
                else:
                    done, reply = self._openai_round(system, messages, tools, handler)
                if done:
                    return reply
        except self._errors as e:
            raise LLMError(str(e)) from e
        return "죄송합니다. 답변을 만드는 중 문제가 생겼습니다. 다시 말씀해 주세요."

    def _openai_round(self, system, messages, tools, handler):
        import json
        resp = self.client.chat.completions.create(
            model=self.model, temperature=0.3,
            messages=[{"role": "system", "content": system}] + messages,
            tools=[{"type": "function", "function": t} for t in tools])
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            return True, msg.content or ""
        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments)
            except json.JSONDecodeError:
                args = {}
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": handler(call.function.name, args)})
        return False, None

    def _anthropic_round(self, system, messages, tools, handler):
        resp = self.client.messages.create(
            model=self.model, max_tokens=1024, system=system,
            tools=[{"name": t["name"], "description": t["description"],
                    "input_schema": t["parameters"]} for t in tools],
            messages=messages)
        # 응답 블록을 다음 요청에 그대로 다시 보낼 수 있는 형태로 저장
        blocks = []
        for b in resp.content:
            if b.type == "text":
                blocks.append({"type": "text", "text": b.text})
            elif b.type == "tool_use":
                blocks.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
        messages.append({"role": "assistant", "content": blocks})
        if resp.stop_reason != "tool_use":
            return True, "".join(b["text"] for b in blocks if b["type"] == "text")
        results = [{"type": "tool_result", "tool_use_id": b["id"],
                    "content": handler(b["name"], b["input"])}
                   for b in blocks if b["type"] == "tool_use"]
        messages.append({"role": "user", "content": results})
        return False, None


def make_llm(get_secret):
    """secrets에서 설정을 읽어 LLM을 만듭니다. 키가 없으면 None."""
    provider = (get_secret("LLM_PROVIDER") or "openai").lower()
    if provider not in DEFAULT_MODELS:
        provider = "openai"
    key_name = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    api_key = get_secret(key_name)
    if not api_key:
        return None
    model = get_secret("LLM_MODEL") or get_secret("OPENAI_MODEL" if provider == "openai" else "")
    return LLM(provider, api_key, model or None)
