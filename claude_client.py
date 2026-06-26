import os
import anthropic

_client = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def answer_pricing_question(question: str, sheet_data: str) -> str:
    """가격 데이터(사입가/출고가/공헌이익)를 기반으로 질문에 답변"""
    client = get_client()

    system_prompt = """당신은 제품 가격 데이터 분석 전문가입니다.
주어진 Google Sheets 가격 데이터를 분석하여 질문에 정확하고 간결하게 답변하세요.

데이터 구조 이해:
- Purchase Price(사입가): 제품 매입 원가 (외화 또는 원화)
- 출고가: 판매 출고 가격 (원화)
- 공헌이익 = 출고가 - 사입가(원화 환산)
- 공헌이익율 = 공헌이익 / 출고가 × 100 (%)

환율 계산 규칙:
- 사용자가 환율을 제시하면 (예: "환율 1350원") 해당 환율로 외화 사입가를 원화로 환산하세요
- 환산 공식: 원화 사입가 = 외화 사입가 × 환율
- 환산 후 공헌이익과 공헌이익율도 재계산하세요

답변 규칙:
- 모델명은 대소문자/공백 구분 없이 유연하게 검색하세요
- 숫자는 천 단위 콤마(,) 포함하여 표시하세요
- 금액 단위를 명확히 표시하세요 (원, USD, EUR 등)
- 공헌이익율은 소수점 1자리까지 표시하세요 (예: 35.2%)
- 데이터에 없는 모델이면 없다고 명확히 알려주세요
- Slack 마크다운 형식(*굵게*, `코드`)을 사용하세요
- 한국어로 답변하세요"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"""아래는 제품 가격 Google Sheets 데이터입니다:

{sheet_data}

---
질문: {question}""",
            }
        ],
    )
    return message.content[0].text


def answer_cs_question(question: str, sheet_data: str) -> str:
    """CS 운영현황 데이터를 기반으로 질문에 답변"""
    client = get_client()

    system_prompt = """당신은 CS(고객센터) 운영현황 데이터 분석 전문가입니다.
주어진 Google Sheets 데이터를 분석하여 질문에 정확하고 간결하게 답변하세요.

답변 규칙:
- 숫자 데이터는 정확히 인용하세요
- 표나 목록으로 정리하면 더 보기 좋을 경우 Slack 마크다운 형식(*굵게*, _기울임_, `코드`)을 사용하세요
- 데이터에 없는 내용은 없다고 명확히 알려주세요
- 한국어로 답변하세요"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"""아래는 26년 CS 고객센터 운영현황 Google Sheets 데이터입니다:

{sheet_data}

---
질문: {question}""",
            }
        ],
    )
    return message.content[0].text
