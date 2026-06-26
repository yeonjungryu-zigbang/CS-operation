import os
import logging
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
from dotenv import load_dotenv

from sheets import get_all_data_as_text, get_default_sheet_data_as_text, get_pricing_rows
from claude_client import answer_cs_question
from pricing_engine import answer_pricing_question

load_dotenv()
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Slack Bolt 앱 초기화
bolt_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
)

# 데이터 캐시 (매번 API 호출 방지)
_sheet_cache: dict = {"data": None}
_pricing_cache: dict = {"data": None}

# 가격 조회 관련 키워드
_PRICING_KEYWORDS = (
    "사입가", "purchase price", "출고가", "공헌이익", "공헌이익율",
    "환율", "모델", "model",
)


def _is_pricing_question(text: str) -> bool:
    """가격 조회 질문 여부 판단"""
    lower = text.lower()
    return any(kw in lower for kw in _PRICING_KEYWORDS)


def get_sheet_data_cached() -> str:
    """시트 데이터 캐시 반환 (없으면 새로 조회)"""
    if _sheet_cache["data"] is None:
        logger.info("Google Sheets 데이터 로딩 중...")
        try:
            _sheet_cache["data"] = get_all_data_as_text()
            logger.info("Google Sheets 데이터 로딩 완료")
        except Exception as e:
            logger.error(f"Sheets 데이터 로딩 실패: {e}")
            return f"데이터 로딩 실패: {e}"
    return _sheet_cache["data"]


def get_pricing_data_cached() -> list:
    """가격 시트 raw rows 캐시 반환 (없으면 새로 조회)"""
    if _pricing_cache["data"] is None:
        logger.info("가격 Sheets 데이터 로딩 중...")
        try:
            _pricing_cache["data"] = get_pricing_rows()
            logger.info("가격 Sheets 데이터 로딩 완료")
        except Exception as e:
            logger.error(f"가격 Sheets 데이터 로딩 실패: {e}")
            return []
    return _pricing_cache["data"]


def refresh_cache():
    """캐시 초기화 (데이터 갱신 시 사용)"""
    _sheet_cache["data"] = None
    _pricing_cache["data"] = None
    logger.info("캐시가 초기화되었습니다.")


# ─── 봇 멘션 처리 ───────────────────────────────────────────────
@bolt_app.event("app_mention")
def handle_mention(event, say, client):
    """봇을 @멘션하면 질문으로 처리"""
    user = event.get("user")
    text = event.get("text", "")
    thread_ts = event.get("thread_ts") or event.get("ts")

    # 멘션 부분 제거 후 질문만 추출
    question = _extract_question(text)
    if not question:
        say(
            text="안녕하세요! CS 운영현황에 대해 질문해주세요. 예: `@claude 이번 달 접수 건수는?`",
            thread_ts=thread_ts,
        )
        return

    # 처리 중 메시지
    say(text=f"<@{user}> 데이터를 조회 중입니다... :hourglass_flowing_sand:", thread_ts=thread_ts)

    try:
        if _is_pricing_question(question):
            sheet_data = get_pricing_data_cached()
            answer = answer_pricing_question(question, sheet_data)
        else:
            sheet_data = get_sheet_data_cached()
            answer = answer_cs_question(question, sheet_data)
        say(text=f"<@{user}>\n{answer}", thread_ts=thread_ts)
    except Exception as e:
        logger.error(f"오류 발생: {e}", exc_info=True)
        say(text=f"<@{user}> 오류가 발생했습니다: {e}", thread_ts=thread_ts)


# ─── DM 메시지 처리 ─────────────────────────────────────────────
@bolt_app.message("")
def handle_dm(message, say):
    """DM 및 채널 메시지 처리"""
    print(f"[DEBUG] 메시지 수신: channel_type={message.get('channel_type')}, text={message.get('text','')[:50]}", flush=True)
    # 봇 메시지 무시
    if message.get("subtype") or message.get("bot_id"):
        return
    channel_type = message.get("channel_type")
    if channel_type != "im":
        return

    user = message.get("user")
    question = message.get("text", "").strip()

    if not question:
        return

    # 특수 명령어
    if question in ("!refresh", "새로고침"):
        refresh_cache()
        say("데이터 캐시를 초기화했습니다. 다음 질문 시 최신 데이터를 불러옵니다. :recycle:")
        return

    say(f"데이터를 조회 중입니다... :hourglass_flowing_sand:")

    try:
        if _is_pricing_question(question):
            sheet_data = get_pricing_data_cached()
            answer = answer_pricing_question(question, sheet_data)
        else:
            sheet_data = get_sheet_data_cached()
            answer = answer_cs_question(question, sheet_data)
        say(answer)
    except Exception as e:
        logger.error(f"오류 발생: {e}", exc_info=True)
        say(f"오류가 발생했습니다: {e}")


def _extract_question(text: str) -> str:
    """멘션 태그 제거 후 순수 질문 반환"""
    import re
    question = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    return question


# ─── Flask 어댑터 (Slack Events API용) ──────────────────────────
flask_app = Flask(__name__)
handler = SlackRequestHandler(bolt_app)


@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)


@flask_app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    use_socket = os.environ.get("SLACK_APP_TOKEN")

    if use_socket:
        # Socket Mode (ngrok 없이 로컬 테스트 가능)
        from slack_bolt.adapter.socket_mode import SocketModeHandler
        logger.info("Socket Mode로 시작합니다...")
        SocketModeHandler(bolt_app, os.environ["SLACK_APP_TOKEN"]).start()
    else:
        # HTTP Mode (프로덕션)
        logger.info(f"HTTP Mode로 포트 {port}에서 시작합니다...")
        flask_app.run(host="0.0.0.0", port=port)
