"""
견적 계산 엔진

AI(LLM)는 금액을 직접 계산하지 않습니다.
AI는 고객과 대화하며 조건(차시 수, 유형 등)만 모으고,
실제 금액은 항상 이 파일의 calculate_quote() 함수가 계산합니다.
→ 같은 조건이면 언제나 같은 금액이 나옵니다.
"""

import pricing as P


def calculate_quote(sessions, minutes_per_session, content_type,
                    voice_over=False, subtitles=False, filming_days=0):
    """제작 조건을 받아 견적 내역(dict)을 돌려줍니다."""

    # 1) 입력값 검증 ─ 잘못된 값이면 이유를 알려 주는 오류를 냅니다.
    if content_type not in P.CONTENT_TYPES:
        raise ValueError(f"콘텐츠 유형은 {', '.join(P.CONTENT_TYPES)} 중 하나여야 합니다.")
    sessions = int(sessions)
    minutes_per_session = int(minutes_per_session)
    filming_days = int(filming_days or 0)
    if not 1 <= sessions <= 200:
        raise ValueError("차시 수는 1~200 사이여야 합니다.")
    if not 5 <= minutes_per_session <= 120:
        raise ValueError("차시당 분량은 5~120분 사이여야 합니다.")
    if filming_days < 0:
        raise ValueError("촬영 일수는 0 이상이어야 합니다.")

    total_minutes = sessions * minutes_per_session
    scale = minutes_per_session / P.BASE_MINUTES  # 25분 대비 분량 비율

    # 2) 직무별 투입일수 = (차시당 공수 × 분량비율 × 차시 수) + 과정 공통 공수
    effort = P.CONTENT_TYPES[content_type]["effort"]
    labor_lines = []
    direct_labor = 0
    for role, info in P.ROLES.items():
        days = effort.get(role, 0) * scale * sessions + P.PROJECT_SETUP_EFFORT.get(role, 0)
        days = round(days, 1)
        if days == 0:
            continue
        wage = P.SW_DAILY_WAGE[info["sw_job"]]
        amount = round(days * wage)
        direct_labor += amount
        labor_lines.append({
            "항목": info["label"],
            "적용 직무": info["sw_job"],
            "투입일수": days,
            "일 단가": wage,
            "금액": amount,
        })

    # 3) 제경비·기술료
    overhead = round(direct_labor * P.OVERHEAD_RATE)
    tech_fee = round((direct_labor + overhead) * P.TECH_FEE_RATE)

    # 4) 직접경비 (선택 옵션)
    expense_lines = []
    if voice_over:
        expense_lines.append({"항목": "전문 성우 녹음", "수량": f"{total_minutes}분",
                              "금액": total_minutes * P.DIRECT_COSTS["voice_over_per_min"]})
    if subtitles:
        expense_lines.append({"항목": "자막 제작", "수량": f"{total_minutes}분",
                              "금액": total_minutes * P.DIRECT_COSTS["subtitle_per_min"]})
    if filming_days > 0:
        expense_lines.append({"항목": "스튜디오 촬영", "수량": f"{filming_days}일",
                              "금액": filming_days * P.DIRECT_COSTS["filming_per_day"]})
    direct_expense = sum(line["금액"] for line in expense_lines)

    # 5) 합계
    raw_supply = direct_labor + overhead + tech_fee + direct_expense
    supply = raw_supply // P.ROUND_UNIT * P.ROUND_UNIT   # 천원 미만 절사
    vat = round(supply * P.VAT_RATE)

    return {
        "조건": {
            "콘텐츠 유형": content_type,
            "차시 수": sessions,
            "차시당 분량(분)": minutes_per_session,
            "총 분량(분)": total_minutes,
            "성우": "포함" if voice_over else "미포함",
            "자막": "포함" if subtitles else "미포함",
            "촬영 일수": filming_days,
        },
        "인건비 내역": labor_lines,
        "직접경비 내역": expense_lines,
        "직접인건비": direct_labor,
        "제경비": overhead,
        "기술료": tech_fee,
        "직접경비": direct_expense,
        "공급가액": supply,
        "부가세": vat,
        "합계": supply + vat,
        "차시당 단가": supply // sessions,
        "단가 기준": P.WAGE_SOURCE,
    }


def summary_text(q):
    """AI에게 돌려줄 짧은 요약(금액은 이 숫자 그대로 안내하게 함)."""
    return (
        f"[견적 계산 결과] 유형 {q['조건']['콘텐츠 유형']}, {q['조건']['차시 수']}차시 × "
        f"{q['조건']['차시당 분량(분)']}분 / 공급가액 {q['공급가액']:,}원, 부가세 {q['부가세']:,}원, "
        f"합계 {q['합계']:,}원 (차시당 약 {q['차시당 단가']:,}원, VAT 별도). "
        f"직접인건비 {q['직접인건비']:,}원, 제경비 {q['제경비']:,}원, 기술료 {q['기술료']:,}원, "
        f"직접경비 {q['직접경비']:,}원."
    )


# 이 파일만 단독 실행하면 예시 견적을 출력합니다:  python quote_engine.py
if __name__ == "__main__":
    q = calculate_quote(10, 25, "애니메이션형", voice_over=True, subtitles=True)
    print(summary_text(q))
    for line in q["인건비 내역"]:
        print(line)
