"""
assistant_api.py
薇薇中央 API 入口

架構：
  - 統一回傳格式 success / error
  - Tool Registry：所有工具集中在 tools/ 資料夾
  - run_with_retry：自動分析錯誤並重試

啟動：python assistant_api.py
"""

from flask import Flask, request, jsonify
from functools import wraps
import traceback

from tools import mail, voice, screenshot, system, audio

app = Flask(__name__)

ALLOWED_USER = "8261240503"


# ══════════════════════════════════════════════════════════════════
# 統一回傳格式
# ══════════════════════════════════════════════════════════════════

def success(data: dict | str) -> dict:
    return {"status": "success", "data": data}


def fail(error: Exception | str, hint: str | None = None) -> dict:
    resp = {"status": "error", "error": str(error)}
    if hint:
        resp["hint"] = hint
    return resp


# ══════════════════════════════════════════════════════════════════
# 錯誤分析與重試
# ══════════════════════════════════════════════════════════════════

ERROR_HINTS = {
    "file not found":       "請確認路徑是否正確，或檔案是否存在",
    "filenotfounderror":    "請確認路徑是否正確，或檔案是否存在",
    "permission denied":    "請確認程式有足夠的存取權限",
    "permissionerror":      "請確認程式有足夠的存取權限",
    "connection refused":   "目標服務可能未啟動，請確認服務狀態",
    "timeout":              "操作逾時，請確認網路或服務狀態",
    "unauthorized":         "請確認 user_id 是否正確",
    "smtp":                 "郵件伺服器錯誤，請確認帳密與網路",
    "ffmpeg":               "FFmpeg 轉換失敗，請確認 FFmpeg 已正確安裝",
    "credential":           "找不到憑證檔，請確認 CRED_FILE 路徑",
}


def _analyze_error(error_msg: str) -> str:
    lower = error_msg.lower()
    for keyword, hint in ERROR_HINTS.items():
        if keyword in lower:
            return hint
    return "未知錯誤，請查看 error 欄位並手動排查"


def run_with_retry(task_func, max_retry: int = 3):
    """
    執行 task_func（無引數 callable，應回傳 dict 或拋出例外）。
    失敗時自動分析錯誤訊息並最多重試 max_retry 次。
    最終回傳統一格式 dict。
    """
    last_error = None
    for attempt in range(1, max_retry + 1):
        try:
            data   = task_func()
            return success(data)
        except Exception as e:
            last_error = e
            hint = _analyze_error(str(e))
            print(f"[薇薇重試] 第 {attempt}/{max_retry} 次失敗："
                  f"{e} → 分析：{hint}")
            # 最後一次也分析，讓呼叫端看到 hint
            if attempt == max_retry:
                return fail(e, hint=hint)
    return fail(last_error or "未知錯誤")


# ══════════════════════════════════════════════════════════════════
# 授權裝飾器
# ══════════════════════════════════════════════════════════════════

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        data = request.json or {}
        if str(data.get("user_id", "")) != ALLOWED_USER:
            return jsonify(fail("Unauthorized：user_id 不符", hint="請確認 user_id 是否正確")), 403
        return f(*args, **kwargs)
    return wrapper


# ══════════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════════

# ── 郵件 ─────────────────────────────────────────────────────────

@app.route("/send_mail", methods=["POST"])
@require_auth
def api_send_mail():
    """
    寄送郵件。
    Body JSON 欄位：
      user_id, to, subject, content
      [is_html, attachment, inline_images]
    """
    data = request.json
    result = run_with_retry(lambda: mail.send_mail(
        to_email           = data["to"],
        subject            = data["subject"],
        content            = data["content"],
        attachment_path    = data.get("attachment"),
        is_html            = data.get("is_html", False),
        inline_image_paths = data.get("inline_images", []),
    ))
    return jsonify(result)


@app.route("/sync_mail", methods=["POST"])
@require_auth
def api_sync_mail():
    """
    同步 Gmail 收件匣。
    Body JSON 欄位：
      user_id
      [reset: bool]  # true 代表清除記錄重新同步
    """
    data   = request.json
    result = run_with_retry(lambda: mail.sync_mail(
        reset=data.get("reset", False)
    ))
    return jsonify(result)


# ── 語音 ─────────────────────────────────────────────────────────

@app.route("/text_to_voice", methods=["POST"])
@require_auth
def api_text_to_voice():
    """
    文字轉語音（TTS）。
    Body JSON 欄位：user_id, text
    """
    data   = request.json
    result = run_with_retry(lambda: voice.text_to_voice(data["text"]))
    return jsonify(result)


@app.route("/voice_to_text", methods=["POST"])
@require_auth
def api_voice_to_text():
    """
    語音轉文字（STT）。
    Body JSON 欄位：user_id, file（OGG 路徑）
    """
    data   = request.json
    result = run_with_retry(lambda: voice.voice_to_text(data["file"]))
    return jsonify(result)


# ── 截圖 ─────────────────────────────────────────────────────────

@app.route("/screenshot", methods=["POST"])
@require_auth
def api_screenshot():
    """
    全螢幕截圖。
    Body JSON 欄位：user_id, [filename]
    """
    data   = request.json
    result = run_with_retry(lambda: screenshot.take_screenshot(
        filename=data.get("filename")
    ))
    return jsonify(result)


@app.route("/screenshot_region", methods=["POST"])
@require_auth
def api_screenshot_region():
    """
    區域截圖。
    Body JSON 欄位：user_id, x, y, width, height, [filename]
    """
    data   = request.json
    result = run_with_retry(lambda: screenshot.take_screenshot_region(
        x        = data["x"],
        y        = data["y"],
        width    = data["width"],
        height   = data["height"],
        filename = data.get("filename"),
    ))
    return jsonify(result)


# ── 系統 ─────────────────────────────────────────────────────────

@app.route("/run_command", methods=["POST"])
@require_auth
def api_run_command():
    """
    執行系統指令。
    Body JSON 欄位：user_id, command（list 或 string）, [timeout]
    """
    data   = request.json
    result = run_with_retry(lambda: system.run_command(
        command = data["command"],
        timeout = data.get("timeout", 30),
    ))
    return jsonify(result)


@app.route("/env_info", methods=["GET"])
def api_env_info():
    """回傳執行環境資訊（無需授權）。"""
    return jsonify(success(system.get_env_info()))


# ── 音訊 ─────────────────────────────────────────────────────────

@app.route("/normalize_mp3", methods=["POST"])
@require_auth
def api_normalize_mp3():
    """
    MP3 音量正規化（批次處理整個資料夾）。

    Body JSON 欄位：
      user_id        授權 ID
      input_folder   來源資料夾（必填）
      output_folder  輸出資料夾（選填，預設 input_folder/normalized）
      loudnorm       loudnorm 參數（選填，預設 I=-16:TP=-1.5:LRA=11）

    回傳 data：
      {
        "success": ["a.mp3", ...],        # 成功的檔名清單
        "failed":  [{"file":..., "reason":...}],  # 失敗清單
        "total":   N,
        "output_folder": "...",
        "warnings": [...]
      }

    注意：部分檔案失敗時 status 仍為 "success"，
          請檢查 data.failed 清單確認是否需要人工介入。
    """
    data   = request.json
    result = run_with_retry(lambda: audio.normalize_mp3(
        input_folder  = data["input_folder"],
        output_folder = data.get("output_folder"),
        loudnorm      = data.get("loudnorm", "I=-16:TP=-1.5:LRA=11"),
    ))

    # 額外警示：有失敗檔案時，在頂層加 warning 欄位，方便薇薇快速偵測
    if (result.get("status") == "success"
            and result.get("data", {}).get("failed")):
        result["warning"] = (
            f"{len(result['data']['failed'])} 個檔案處理失敗，"
            "請查看 data.failed 清單"
        )

    return jsonify(result)


# ══════════════════════════════════════════════════════════════════
# 健康檢查
# ══════════════════════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    return jsonify(success({"message": "薇薇在線 ✅"}))


# ══════════════════════════════════════════════════════════════════
# 啟動
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("薇薇 Assistant API 啟動中...")
    print("Available routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.methods} {rule.rule}")
    app.run(port=5005, debug=False)
