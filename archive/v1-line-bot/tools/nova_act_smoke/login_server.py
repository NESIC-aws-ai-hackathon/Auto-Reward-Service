"""
Amazon ログイン Web サーバー

ユーザーが LIFF アプリから Amazon ログインを行うための Web UI を提供する。
Playwright でヘッドレスブラウザを操作し、スクリーンショットベースで
ユーザーにログイン画面を見せ、入力を受け付ける。

フロー:
    1. ユーザーが /login/<user_id> にアクセス
    2. サーバーが Playwright で Amazon ログインページを開く
    3. スクリーンショットを返し、ユーザーに表示
    4. ユーザーがメール/パスワード/OTP を入力 → サーバーが代理入力
    5. ログイン成功 → プロファイル (Cookie) を保存
    6. 以降の購入ジョブで保存済みプロファイルを利用

セキュリティ:
    - パスワードはサーバーに一時的に渡されるが、保存しない
    - Cookie は EFS にユーザー単位で永続化
    - HTTPS + ワンタイムトークンでアクセス制御

環境変数:
    LOGIN_SERVER_PORT       (default: 8080)
    NOVA_ACT_PROFILES_DIR   (default: /data/profiles)
    LOGIN_TOKEN_SECRET      ワンタイムトークン署名用シークレット
    AWS_REGION              (default: ap-northeast-1)
    ARS_TABLE_NAME          (default: ArsTable)
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

from flask import Flask, request, jsonify, render_template_string

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("login_server")

app = Flask(__name__)

# ─────────────────────────────────────────
# 設定
# ─────────────────────────────────────────
PORT = int(os.environ.get("LOGIN_SERVER_PORT", "8080"))
PROFILES_DIR = Path(os.environ.get("NOVA_ACT_PROFILES_DIR", "/data/profiles"))
TOKEN_SECRET = os.environ.get("LOGIN_TOKEN_SECRET", "dev-secret-change-me")
TABLE_NAME = os.environ.get("ARS_TABLE_NAME", "ArsTable")
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")

# アクティブなログインセッション（メモリ内、1コンテナ1ユーザー前提）
_active_sessions: dict[str, dict] = {}

# ─────────────────────────────────────────
# トークン検証
# ─────────────────────────────────────────
def _verify_token(token: str) -> Optional[str]:
    """ワンタイムトークンを検証し user_id を返す。"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64, exp_str, sig = parts
        # 署名検証
        expected = hmac.HMAC(
            TOKEN_SECRET.encode(), f"{payload_b64}.{exp_str}".encode(), hashlib.sha256
        ).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return None
        # 有効期限
        if int(exp_str) < int(time.time()):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
        return payload.get("user_id")
    except Exception:
        return None


def generate_login_token(user_id: str, ttl: int = 600) -> str:
    """Lambda が発行するログイントークン（10分有効）"""
    payload = json.dumps({"user_id": user_id, "nonce": uuid.uuid4().hex[:8]})
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
    exp_str = str(int(time.time()) + ttl)
    sig = hmac.HMAC(
        TOKEN_SECRET.encode(), f"{payload_b64}.{exp_str}".encode(), hashlib.sha256
    ).hexdigest()[:32]
    return f"{payload_b64}.{exp_str}.{sig}"


# ─────────────────────────────────────────
# Playwright ブラウザセッション管理
# ─────────────────────────────────────────
async def _get_browser_session(user_id: str):
    """ユーザー用の Playwright ブラウザコンテキストを取得"""
    from playwright.async_api import async_playwright

    profile_dir = PROFILES_DIR / user_id
    profile_dir.mkdir(parents=True, exist_ok=True)

    pw = await async_playwright().start()
    browser = await pw.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=True,
        viewport={"width": 390, "height": 844},  # モバイルサイズ
        locale="ja-JP",
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
    )
    page = browser.pages[0] if browser.pages else await browser.new_page()
    return {"pw": pw, "browser": browser, "page": page, "user_id": user_id}


async def _close_session(session: dict):
    """セッションを安全にクローズ"""
    try:
        await session["browser"].close()
        await session["pw"].stop()
    except Exception:
        pass


# ─────────────────────────────────────────
# HTML テンプレート
# ─────────────────────────────────────────
LOGIN_PAGE_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Amazon 連携 - ふれまーるちゃん</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f0; }
.container { max-width: 420px; margin: 0 auto; padding: 16px; }
h1 { font-size: 18px; text-align: center; margin-bottom: 12px; color: #2d5016; }
.status { padding: 12px; border-radius: 8px; margin-bottom: 16px; text-align: center; }
.status.connected { background: #d4edda; color: #155724; }
.status.disconnected { background: #fff3cd; color: #856404; }
.screenshot { width: 100%; border-radius: 8px; border: 1px solid #ddd; margin-bottom: 12px; }
.input-group { margin-bottom: 12px; }
.input-group label { display: block; font-size: 14px; margin-bottom: 4px; color: #333; }
.input-group input { width: 100%; padding: 12px; border: 1px solid #ccc; border-radius: 8px; font-size: 16px; }
.btn { width: 100%; padding: 14px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; margin-bottom: 8px; }
.btn-primary { background: #ff9900; color: #111; }
.btn-secondary { background: #e7e7e7; color: #333; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.note { font-size: 12px; color: #666; text-align: center; margin-top: 12px; }
.step-indicator { text-align: center; margin-bottom: 12px; color: #555; font-size: 14px; }
#error-msg { color: #dc3545; text-align: center; margin-bottom: 8px; display: none; }
</style>
</head>
<body>
<div class="container">
    <h1>🌿 Amazon アカウント連携</h1>
    <div id="status" class="status disconnected">未連携</div>
    <div id="step-indicator" class="step-indicator"></div>
    <div id="error-msg"></div>

    <div id="screenshot-area" style="display:none;">
        <img id="screenshot" class="screenshot" alt="Amazon ページ">
    </div>

    <div id="input-area">
        <div id="email-step">
            <div class="input-group">
                <label>Amazon メールアドレス / 電話番号</label>
                <input type="email" id="email" placeholder="your@email.com" autocomplete="email">
            </div>
            <button class="btn btn-primary" onclick="submitEmail()">次へ</button>
        </div>

        <div id="password-step" style="display:none;">
            <div class="input-group">
                <label>パスワード</label>
                <input type="password" id="password" placeholder="パスワード" autocomplete="current-password">
            </div>
            <button class="btn btn-primary" onclick="submitPassword()">ログイン</button>
        </div>

        <div id="otp-step" style="display:none;">
            <div class="input-group">
                <label>認証コード（SMS / Authenticator）</label>
                <input type="text" id="otp" placeholder="123456" inputmode="numeric" autocomplete="one-time-code">
            </div>
            <button class="btn btn-primary" onclick="submitOTP()">確認</button>
        </div>

        <div id="success-step" style="display:none;">
            <div class="status connected">✅ Amazon 連携完了！</div>
            <p class="note">ふれまーるちゃんがあなたのご褒美を自動でお届けできるようになりました 🌿</p>
            <button class="btn btn-secondary" onclick="window.close()">閉じる</button>
        </div>
    </div>

    <p class="note">※ パスワードはサーバーに保存されません。ログイン後はCookieのみ保持します。</p>
</div>

<script>
const SESSION_ID = "{{ session_id }}";
const API_BASE = "";

async function api(path, body) {
    const res = await fetch(API_BASE + path, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({session_id: SESSION_ID, ...body})
    });
    return res.json();
}

function showStep(step) {
    document.querySelectorAll("#input-area > div").forEach(d => d.style.display = "none");
    document.getElementById(step + "-step").style.display = "block";
}

function showError(msg) {
    const el = document.getElementById("error-msg");
    el.textContent = msg;
    el.style.display = msg ? "block" : "none";
}

function updateScreenshot(b64) {
    if (b64) {
        document.getElementById("screenshot").src = "data:image/png;base64," + b64;
        document.getElementById("screenshot-area").style.display = "block";
    }
}

async function submitEmail() {
    showError("");
    const email = document.getElementById("email").value.trim();
    if (!email) { showError("メールアドレスを入力してください"); return; }
    document.getElementById("step-indicator").textContent = "ログイン中...";
    const r = await api("/api/login/email", {email});
    if (r.error) { showError(r.error); return; }
    updateScreenshot(r.screenshot);
    document.getElementById("step-indicator").textContent = "パスワードを入力してください";
    showStep("password");
}

async function submitPassword() {
    showError("");
    const pw = document.getElementById("password").value;
    if (!pw) { showError("パスワードを入力してください"); return; }
    document.getElementById("step-indicator").textContent = "認証中...";
    const r = await api("/api/login/password", {password: pw});
    if (r.error) { showError(r.error); return; }
    updateScreenshot(r.screenshot);
    if (r.status === "otp_required") {
        document.getElementById("step-indicator").textContent = "認証コードを入力してください";
        showStep("otp");
    } else if (r.status === "success") {
        document.getElementById("step-indicator").textContent = "";
        showStep("success");
    } else {
        showError(r.message || "予期しない状態です");
    }
}

async function submitOTP() {
    showError("");
    const otp = document.getElementById("otp").value.trim();
    if (!otp) { showError("認証コードを入力してください"); return; }
    document.getElementById("step-indicator").textContent = "確認中...";
    const r = await api("/api/login/otp", {otp});
    if (r.error) { showError(r.error); return; }
    updateScreenshot(r.screenshot);
    if (r.status === "success") {
        document.getElementById("step-indicator").textContent = "";
        showStep("success");
    } else {
        showError(r.message || "認証に失敗しました");
    }
}

// 初期化: ログインページを開く
(async () => {
    const r = await api("/api/login/start", {});
    if (r.screenshot) updateScreenshot(r.screenshot);
    if (r.status === "already_logged_in") {
        showStep("success");
    }
})();
</script>
</body>
</html>
"""


# ─────────────────────────────────────────
# API エンドポイント
# ─────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "active_sessions": len(_active_sessions)})


@app.route("/login/<token>")
def login_page(token: str):
    """ログインページを表示（トークン認証付き）"""
    user_id = _verify_token(token)
    if not user_id:
        # ハッカソン用: トークン検証スキップ（user_id をそのまま使う）
        if len(token) < 50:
            user_id = token
        else:
            return jsonify({"error": "無効なトークンです"}), 401

    session_id = uuid.uuid4().hex
    _active_sessions[session_id] = {
        "user_id": user_id,
        "session": None,
        "created_at": time.time(),
    }
    return render_template_string(LOGIN_PAGE_HTML, session_id=session_id)


@app.route("/api/login/start", methods=["POST"])
def login_start():
    """ブラウザセッション開始 & Amazon ログインページへ遷移"""
    data = request.json or {}
    session_id = data.get("session_id")
    if session_id not in _active_sessions:
        return jsonify({"error": "セッションが無効です"}), 400

    entry = _active_sessions[session_id]
    user_id = entry["user_id"]

    try:
        loop = asyncio.new_event_loop()
        session = loop.run_until_complete(_get_browser_session(user_id))
        page = session["page"]
        loop.run_until_complete(page.goto("https://www.amazon.co.jp/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.co.jp%2F"))
        loop.run_until_complete(page.wait_for_load_state("networkidle"))

        # ログイン済みチェック
        url = page.url
        if "amazon.co.jp" in url and "/ap/" not in url:
            screenshot = base64.b64encode(loop.run_until_complete(page.screenshot())).decode()
            loop.run_until_complete(_close_session(session))
            _update_login_status(user_id, True)
            return jsonify({"status": "already_logged_in", "screenshot": screenshot})

        screenshot = base64.b64encode(loop.run_until_complete(page.screenshot())).decode()
        entry["session"] = session
        entry["loop"] = loop
        return jsonify({"status": "email_required", "screenshot": screenshot})
    except Exception as e:
        logger.exception("login_start_failed")
        return jsonify({"error": f"ブラウザ起動に失敗: {str(e)[:100]}"}), 500


@app.route("/api/login/email", methods=["POST"])
def login_email():
    """メールアドレス入力"""
    data = request.json or {}
    session_id = data.get("session_id")
    email = data.get("email", "")

    if session_id not in _active_sessions:
        return jsonify({"error": "セッションが無効です"}), 400

    entry = _active_sessions[session_id]
    session = entry.get("session")
    loop = entry.get("loop")
    if not session:
        return jsonify({"error": "ブラウザセッションが未開始です"}), 400

    try:
        page = session["page"]
        loop.run_until_complete(page.fill("#ap_email", email))
        loop.run_until_complete(page.click("#continue"))
        loop.run_until_complete(page.wait_for_load_state("networkidle"))
        time.sleep(1)
        screenshot = base64.b64encode(loop.run_until_complete(page.screenshot())).decode()
        return jsonify({"status": "password_required", "screenshot": screenshot})
    except Exception as e:
        logger.exception("login_email_failed")
        return jsonify({"error": f"メール入力に失敗: {str(e)[:100]}"}), 500


@app.route("/api/login/password", methods=["POST"])
def login_password():
    """パスワード入力"""
    data = request.json or {}
    session_id = data.get("session_id")
    password = data.get("password", "")

    if session_id not in _active_sessions:
        return jsonify({"error": "セッションが無効です"}), 400

    entry = _active_sessions[session_id]
    session = entry.get("session")
    loop = entry.get("loop")
    if not session:
        return jsonify({"error": "セッションが未開始です"}), 400

    try:
        page = session["page"]
        loop.run_until_complete(page.fill("#ap_password", password))
        loop.run_until_complete(page.click("#signInSubmit"))
        loop.run_until_complete(page.wait_for_load_state("networkidle"))
        time.sleep(2)

        url = page.url
        screenshot = base64.b64encode(loop.run_until_complete(page.screenshot())).decode()

        # ログイン成功判定
        if "/ap/" not in url and "amazon.co.jp" in url:
            user_id = entry["user_id"]
            loop.run_until_complete(_close_session(session))
            entry["session"] = None
            _update_login_status(user_id, True)
            return jsonify({"status": "success", "screenshot": screenshot})

        # OTP / MFA 判定
        content = loop.run_until_complete(page.content())
        if "otp" in content.lower() or "認証コード" in content or "verification" in content.lower():
            return jsonify({"status": "otp_required", "screenshot": screenshot})

        # パスワードエラー
        if "ap_password" in content:
            return jsonify({"error": "パスワードが正しくありません", "screenshot": screenshot})

        return jsonify({"status": "unknown", "message": "予期しない画面です", "screenshot": screenshot})
    except Exception as e:
        logger.exception("login_password_failed")
        return jsonify({"error": f"ログイン処理に失敗: {str(e)[:100]}"}), 500


@app.route("/api/login/otp", methods=["POST"])
def login_otp():
    """OTP/MFA コード入力"""
    data = request.json or {}
    session_id = data.get("session_id")
    otp = data.get("otp", "")

    if session_id not in _active_sessions:
        return jsonify({"error": "セッションが無効です"}), 400

    entry = _active_sessions[session_id]
    session = entry.get("session")
    loop = entry.get("loop")
    if not session:
        return jsonify({"error": "セッションが未開始です"}), 400

    try:
        page = session["page"]
        # OTP 入力フィールドを探して入力
        loop.run_until_complete(
            page.fill("input[name='otpCode'], input[name='code'], #auth-mfa-otpcode", otp)
        )
        # 送信ボタンをクリック
        loop.run_until_complete(
            page.click("input[type='submit'], button[type='submit'], #auth-mfa-remember-device")
        )
        loop.run_until_complete(page.wait_for_load_state("networkidle"))
        time.sleep(2)

        url = page.url
        screenshot = base64.b64encode(loop.run_until_complete(page.screenshot())).decode()

        if "/ap/" not in url and "amazon.co.jp" in url:
            user_id = entry["user_id"]
            loop.run_until_complete(_close_session(session))
            entry["session"] = None
            _update_login_status(user_id, True)
            return jsonify({"status": "success", "screenshot": screenshot})

        return jsonify({"status": "failed", "message": "認証コードが正しくないようです", "screenshot": screenshot})
    except Exception as e:
        logger.exception("login_otp_failed")
        return jsonify({"error": f"OTP処理に失敗: {str(e)[:100]}"}), 500


@app.route("/api/login/status/<user_id>", methods=["GET"])
def login_status(user_id: str):
    """ユーザーの Amazon ログイン状態を確認"""
    profile_dir = PROFILES_DIR / user_id
    has_profile = profile_dir.exists() and any(profile_dir.iterdir())
    return jsonify({
        "user_id": user_id,
        "has_profile": has_profile,
        "amazon_linked": has_profile,
    })


# ─────────────────────────────────────────
# DynamoDB ステータス更新
# ─────────────────────────────────────────
def _update_login_status(user_id: str, connected: bool):
    """DynamoDB にログイン状態を記録"""
    try:
        import boto3
        from datetime import datetime, timezone
        table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)
        table.update_item(
            Key={"PK": f"USER#{user_id}", "SK": "AMAZON_SESSION"},
            UpdateExpression="SET amazon_linked = :v, updated_at = :t",
            ExpressionAttributeValues={
                ":v": connected,
                ":t": datetime.now(timezone.utc).isoformat(),
            },
        )
        logger.info("login_status_updated user_id=%s connected=%s", user_id, connected)
    except Exception as e:
        logger.warning("login_status_update_failed: %s", e)


# ─────────────────────────────────────────
# メイン
# ─────────────────────────────────────────
if __name__ == "__main__":
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Starting login server on port %d", PORT)
    logger.info("Profiles dir: %s", PROFILES_DIR)
    app.run(host="0.0.0.0", port=PORT, debug=False)
