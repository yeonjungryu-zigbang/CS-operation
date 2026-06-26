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
