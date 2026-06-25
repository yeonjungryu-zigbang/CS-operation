# CS 고객센터 운영현황 Slack Bot

Slack에서 질문하면 Google Sheets(26년 CS 운영현황) 데이터를 Claude가 분석해 자동 응답합니다.

## 사용법

- **채널에서**: `@봇이름 이번 달 접수 건수는?`
- **DM으로**: 봇에게 직접 질문 입력
- **캐시 갱신**: `!refresh` 또는 `새로고침` (시트 수정 후 최신 데이터 반영)

## 환경변수 설정

`.env.example`을 복사해 `.env` 파일 생성:

```bash
cp .env.example .env
```

필수 항목:
| 변수 | 설명 |
|------|------|
| `SLACK_BOT_TOKEN` | Slack Bot User OAuth Token (`xoxb-...`) |
| `SLACK_SIGNING_SECRET` | Slack App Signing Secret |
| `SLACK_APP_TOKEN` | Socket Mode용 App-Level Token (`xapp-...`) |
| `ANTHROPIC_API_KEY` | Claude API 키 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Service Account JSON (한 줄) |

## Slack App 설정

1. [api.slack.com/apps](https://api.slack.com/apps) → 앱 생성
2. **OAuth & Permissions** → Bot Token Scopes 추가:
   - `app_mentions:read`, `chat:write`, `im:history`, `im:read`, `im:write`, `channels:history`
3. **Event Subscriptions** → Enable → Subscribe to bot events:
   - `app_mention`, `message.im`
4. **Socket Mode** 활성화 (로컬/간단 배포 시)
5. 앱을 워크스페이스에 설치 후 원하는 채널에 초대

## Google Sheets 권한 설정

1. Google Cloud Console에서 Service Account 생성
2. Google Sheets API 활성화
3. Service Account JSON 키 다운로드
4. **스프레드시트 공유**: Service Account 이메일을 시트 공유 대상에 추가 (뷰어 권한)

## 실행

```bash
# 로컬 (Socket Mode)
pip install -r requirements.txt
python app.py

# Docker
docker build -t cs-bot .
docker run --env-file .env cs-bot
```
