"""
첫 답변이 '구체적'인지 판단 (AI 없이 규칙으로)

유형·차시 수·분량 3가지 중 2가지 이상이 들어 있으면 → 대화형 상담
그보다 적으면 → 단계별 접수 (찾아낸 값은 미리 채워 줌)
"""

import re

TYPE_KEYWORDS = {
    "애니메이션형": ["애니", "모션그래픽", "모션 그래픽", "캐릭터"],
    "촬영형": ["촬영", "스튜디오", "강사 영상"],
    "혼합형": ["혼합", "복합"],
    "기본형": ["기본형", "슬라이드", "텍스트형", "ppt", "피피티"],
}


def detect(text):
    """문장에서 견적 조건을 찾아 dict로 돌려줍니다."""
    t = text.lower()
    found = {}

    for ctype, words in TYPE_KEYWORDS.items():
        if any(w in t for w in words):
            found["content_type"] = ctype
            break

    m = re.search(r"(\d+)\s*(차시|강|편|회차|개\s*차시)", t)
    if m:
        found["sessions"] = int(m.group(1))

    m = re.search(r"(\d+)\s*분", t)
    if m:
        found["minutes_per_session"] = int(m.group(1))

    if "성우" in t:
        found["voice_over"] = True
    if "자막" in t:
        found["subtitles"] = True

    core = [k for k in ("content_type", "sessions", "minutes_per_session") if k in found]
    found["is_specific"] = len(core) >= 2
    return found
