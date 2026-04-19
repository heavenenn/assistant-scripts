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
import logging
from datetime import datetime

from tools import mail, voice, screenshot, system, audio, ui, grok_media, grok_writer, telegram, scheduler

app = Flask(__name__)

# ── 操作 Log（記錄每次工具呼叫，方便追蹤薇薇的實際行為）──
_LOG_FILE = r"C:\Users\heave\.openclaw\assistant-scripts\api_calls.log"
_log_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
_log_handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
_logger = logging.getLogger("api_calls")
_logger.setLevel(logging.INFO)
_logger.addHandler(_log_handler)

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


def run_with_retry(task_func, max_retry: int = 1):
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
        # ── Log 每次呼叫的 endpoint + 參數 + 結果 ──
        endpoint = request.path
        params = {k: v for k, v in data.items() if k != "user_id"}
        _logger.info(f">>> {endpoint}  params={params}")
        result = f(*args, **kwargs)
        try:
            resp_data = result.get_json() if hasattr(result, 'get_json') else str(result)
            _logger.info(f"<<< {endpoint}  result={resp_data}")
        except Exception:
            pass
        return result
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


@app.route("/screen_record", methods=["POST"])
@require_auth
def api_screen_record():
    """
    螢幕錄影。
    Body JSON 欄位：user_id, [duration, framerate, filename]
    """
    data   = request.json
    result = run_with_retry(lambda: screenshot.screen_record(
        duration  = data.get("duration", 10),
        framerate = data.get("framerate", 15),
        filename  = data.get("filename"),
    ))
    return jsonify(result)


# ── 系統 ─────────────────────────────────────────────────────────

@app.route("/run_command", methods=["POST"])
@require_auth
def api_run_command():
    """
    執行系統指令。
    Body JSON 欄位：user_id, command（list 或 string）, [timeout], [elevated]
    """
    data   = request.json
    result = run_with_retry(lambda: system.run_command(
        command  = data["command"],
        timeout  = data.get("timeout", 30),
        elevated = data.get("elevated", False),
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


# ── UI 操作 ──────────────────────────────────────────────────────

@app.route("/click", methods=["POST"])
@require_auth
def api_click():
    """滑鼠點擊。Body JSON：user_id, x, y, [button]"""
    data   = request.json
    result = run_with_retry(lambda: ui.click(
        x=data["x"], y=data["y"], button=data.get("button", "left"),
    ))
    return jsonify(result)


@app.route("/double_click", methods=["POST"])
@require_auth
def api_double_click():
    """滑鼠雙擊。Body JSON：user_id, x, y"""
    data   = request.json
    result = run_with_retry(lambda: ui.double_click(x=data["x"], y=data["y"]))
    return jsonify(result)


@app.route("/right_click", methods=["POST"])
@require_auth
def api_right_click():
    """滑鼠右鍵。Body JSON：user_id, x, y"""
    data   = request.json
    result = run_with_retry(lambda: ui.right_click(x=data["x"], y=data["y"]))
    return jsonify(result)


@app.route("/type_text", methods=["POST"])
@require_auth
def api_type_text():
    """輸入文字。Body JSON：user_id, text, [interval]"""
    data   = request.json
    result = run_with_retry(lambda: ui.type_text(
        text=data["text"], interval=data.get("interval", 0.05),
    ))
    return jsonify(result)


@app.route("/hotkey", methods=["POST"])
@require_auth
def api_hotkey():
    """鍵盤快捷鍵。Body JSON：user_id, keys（例如 "ctrl+c"）"""
    data   = request.json
    result = run_with_retry(lambda: ui.hotkey(keys=data["keys"]))
    return jsonify(result)


@app.route("/press_key", methods=["POST"])
@require_auth
def api_press_key():
    """按下單一按鍵。Body JSON：user_id, key, [presses]"""
    data   = request.json
    result = run_with_retry(lambda: ui.press_key(
        key=data["key"], presses=data.get("presses", 1),
    ))
    return jsonify(result)


@app.route("/wait", methods=["POST"])
@require_auth
def api_wait():
    """等待指定秒數。Body JSON：user_id, [seconds]"""
    data   = request.json
    result = run_with_retry(lambda: ui.wait(
        seconds=data.get("seconds", 1.0),
    ))
    return jsonify(result)


@app.route("/scroll", methods=["POST"])
@require_auth
def api_scroll():
    """滾動滾輪。Body JSON：user_id, clicks, [x, y]"""
    data   = request.json
    result = run_with_retry(lambda: ui.scroll(
        clicks=data["clicks"], x=data.get("x"), y=data.get("y"),
    ))
    return jsonify(result)


@app.route("/locate_image", methods=["POST"])
@require_auth
def api_locate_image():
    """在螢幕上比對圖片位置。Body JSON：user_id, image_path, [confidence]"""
    data   = request.json
    result = run_with_retry(lambda: ui.locate_image(
        image_path=data["image_path"], confidence=data.get("confidence", 0.8),
    ))
    return jsonify(result)


@app.route("/get_screen_size", methods=["POST"])
@require_auth
def api_get_screen_size():
    """取得螢幕解析度。Body JSON：user_id"""
    result = run_with_retry(lambda: ui.get_screen_size())
    return jsonify(result)


# ── AI 圖片 / 影片生成 ───────────────────────────────────────────

@app.route("/generate_image", methods=["POST"])
@require_auth
def api_generate_image():
    """
    AI 文字生成圖片。
    Body JSON：user_id, prompt, [n, aspect_ratio, resolution, filename]
    """
    data   = request.json
    result = run_with_retry(lambda: grok_media.generate_image(
        prompt       = data["prompt"],
        n            = data.get("n", 1),
        aspect_ratio = data.get("aspect_ratio", "auto"),
        resolution   = data.get("resolution", "1k"),
        filename     = data.get("filename"),
    ))
    return jsonify(result)


@app.route("/edit_image", methods=["POST"])
@require_auth
def api_edit_image():
    """
    AI 編輯圖片。
    Body JSON：user_id, prompt, image_path, [aspect_ratio, filename]
    """
    data   = request.json
    result = run_with_retry(lambda: grok_media.edit_image(
        prompt       = data["prompt"],
        image_path   = data["image_path"],
        aspect_ratio = data.get("aspect_ratio"),
        filename     = data.get("filename"),
    ))
    return jsonify(result)


@app.route("/generate_video", methods=["POST"])
@require_auth
def api_generate_video():
    """
    AI 文字/圖片生成影片（非同步，自動等待完成）。
    Body JSON：user_id, prompt, [duration, aspect_ratio, resolution, image_path, filename]
    """
    data   = request.json
    result = run_with_retry(lambda: grok_media.generate_video(
        prompt       = data["prompt"],
        duration     = data.get("duration", 6),
        aspect_ratio = data.get("aspect_ratio", "16:9"),
        resolution   = data.get("resolution", "480p"),
        image_path   = data.get("image_path"),
        filename     = data.get("filename"),
    ))
    return jsonify(result)


@app.route("/edit_video", methods=["POST"])
@require_auth
def api_edit_video():
    """
    AI 編輯影片。
    Body JSON：user_id, prompt, video_url, [filename]
    """
    data   = request.json
    result = run_with_retry(lambda: grok_media.edit_video(
        prompt    = data["prompt"],
        video_url = data["video_url"],
        filename  = data.get("filename"),
    ))
    return jsonify(result)


@app.route("/extend_video", methods=["POST"])
@require_auth
def api_extend_video():
    """
    延伸影片。
    Body JSON：user_id, prompt, video_url, [duration, filename]
    """
    data   = request.json
    result = run_with_retry(lambda: grok_media.extend_video(
        prompt    = data["prompt"],
        video_url = data["video_url"],
        duration  = data.get("duration", 6),
        filename  = data.get("filename"),
    ))
    return jsonify(result)


# ── AI 文字生成 ──────────────────────────────────────────────────

@app.route("/generate_text", methods=["POST"])
@require_auth
def api_generate_text():
    """
    AI 生成文字內容。
    Body JSON：user_id, prompt, [system_prompt, filename]
    """
    data   = request.json
    result = run_with_retry(lambda: grok_writer.generate_text(
        prompt        = data["prompt"],
        system_prompt = data.get("system_prompt", "你是一位專業的繁體中文寫作助手。"),
        filename      = data.get("filename"),
    ))
    return jsonify(result)


@app.route("/generate_novel", methods=["POST"])
@require_auth
def api_generate_novel():
    """
    AI 分章節生成長篇小說。
    Body JSON：user_id, prompt, [chapters, style, filename]
    """
    data   = request.json
    result = run_with_retry(lambda: grok_writer.generate_novel(
        prompt   = data["prompt"],
        chapters = data.get("chapters", 5),
        style    = data.get("style", "繁體中文，文筆細膩，對話生動"),
        filename = data.get("filename"),
    ))
    return jsonify(result)


# ── Telegram 推播 ────────────────────────────────────────────────

@app.route("/push_message", methods=["POST"])
@require_auth
def api_push_message():
    """Telegram 推播文字。Body JSON：user_id, text, [parse_mode]"""
    data   = request.json
    result = run_with_retry(lambda: telegram.push_message(
        text=data["text"], parse_mode=data.get("parse_mode", ""),
    ))
    return jsonify(result)


@app.route("/push_photo", methods=["POST"])
@require_auth
def api_push_photo():
    """Telegram 推播圖片。Body JSON：user_id, photo_path, [caption]"""
    data   = request.json
    result = run_with_retry(lambda: telegram.push_photo(
        photo_path=data["photo_path"], caption=data.get("caption", ""),
    ))
    return jsonify(result)


@app.route("/push_file", methods=["POST"])
@require_auth
def api_push_file():
    """Telegram 推播檔案。Body JSON：user_id, file_path, [caption]"""
    data   = request.json
    result = run_with_retry(lambda: telegram.push_file(
        file_path=data["file_path"], caption=data.get("caption", ""),
    ))
    return jsonify(result)


@app.route("/ai_push", methods=["POST"])
@require_auth
def api_ai_push():
    """AI 即時生成訊息並推播。Body JSON：user_id, scenario, [context]"""
    data   = request.json
    result = run_with_retry(lambda: telegram.ai_push(
        scenario=data["scenario"], context=data.get("context", ""),
    ))
    return jsonify(result)


# ── 排程 ───────────────────────────────────────────────────────

@app.route("/schedule_task", methods=["POST"])
@require_auth
def api_schedule_task():
    """排程延遲或定時執行工具。Body JSON：user_id, tool, [params, delay_seconds, run_at]"""
    data   = request.json
    import json
    params_raw = data.get("params", {})
    if isinstance(params_raw, str):
        params_raw = json.loads(params_raw)
    result = run_with_retry(lambda: scheduler.schedule_task(
        tool=data["tool"],
        params=params_raw,
        delay_seconds=data.get("delay_seconds", 0),
        run_at=data.get("run_at", ""),
    ))
    return jsonify(result)


@app.route("/list_scheduled", methods=["POST"])
@require_auth
def api_list_scheduled():
    """列出所有排程任務。Body JSON：user_id"""
    result = run_with_retry(lambda: scheduler.list_scheduled())
    return jsonify(result)


@app.route("/cancel_scheduled", methods=["POST"])
@require_auth
def api_cancel_scheduled():
    """取消排程任務。Body JSON：user_id, task_id"""
    data   = request.json
    result = run_with_retry(lambda: scheduler.cancel_scheduled(
        task_id=data["task_id"],
    ))
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
