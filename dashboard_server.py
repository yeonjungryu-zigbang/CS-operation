"""로컬 PC에서 스마트홈 판매 KPI 대시보드를 zigbang.com 구글 계정 로그인 뒤에서만 서빙합니다.

실행: python dashboard_server.py
접속: http://localhost:5050/dashboard (127.0.0.1에만 바인딩되어 같은 PC에서만 접근 가능)
"""
import os

from dotenv import load_dotenv
from flask import Flask, redirect, request, send_file, session, url_for
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

load_dotenv()

ALLOWED_DOMAIN = "zigbang.com"
DASHBOARD_HTML_PATH = os.path.join(os.path.dirname(__file__), "smarthome_sales_dashboard.html")
PORT = int(os.environ.get("DASHBOARD_PORT", 5050))
REDIRECT_URI = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", f"http://localhost:{PORT}/oauth2callback")
CLIENT_ID = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]
SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email"]

CLIENT_CONFIG = {
    "web": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]


def _flow(state=None):
    return Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, state=state, redirect_uri=REDIRECT_URI)


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    if not session.get("user"):
        return redirect(url_for("login"))
    return send_file(DASHBOARD_HTML_PATH)


@app.route("/login")
def login():
    auth_url, state = _flow().authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        hd=ALLOWED_DOMAIN,
        prompt="select_account",
    )
    session["oauth_state"] = state
    return redirect(auth_url)


@app.route("/oauth2callback")
def oauth2callback():
    flow = _flow(state=session.get("oauth_state"))
    flow.fetch_token(authorization_response=request.url)
    id_info = id_token.verify_oauth2_token(flow.credentials._id_token, google_requests.Request(), CLIENT_ID)
    email = id_info.get("email", "")
    if id_info.get("hd") != ALLOWED_DOMAIN and not email.endswith("@" + ALLOWED_DOMAIN):
        session.clear()
        return f"접근 권한이 없습니다. {ALLOWED_DOMAIN} 계정으로 로그인해주세요.", 403
    session["user"] = {"email": email, "name": id_info.get("name")}
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")  # localhost http 콜백 허용 (PC 밖으로 노출 안 됨)
    app.run(host="127.0.0.1", port=PORT, debug=False)
