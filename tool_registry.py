"""
tool_registry.py
所有工具的統一 Schema 定義。

作用：
  1. 讓 AI（Grok/薇薇）知道有哪些工具、參數名稱、型別、必填與否
  2. agent_core.py 用來驗證 AI 回傳的步驟，避免 hallucination
  3. 未來新增工具只需在此登記，不需改 agent_core

每個 tool 欄位說明：
  name        工具唯一識別名稱（對應 assistant_api.py 的 route 路徑）
  endpoint    呼叫的 API 路徑
  description 給 AI 看的一句話說明（影響 AI 的規劃品質）
  params      參數定義 dict
    type        python 型別名稱：string / bool / list / int
    required    是否必填
    default     選填時的預設值（選填欄位）
    description 給 AI 看的參數說明（讓 AI 填對值）
  response    回傳值說明（讓 AI 知道如何讀取結果、判斷是否成功）
    success_key 代表成功的頂層欄位（通常是 "status"）
    success_val 成功時該欄位的值（通常是 "success"）
    data_keys   data 層有哪些有意義的欄位
"""

TOOLS_SCHEMA = [

    # ── 郵件 ──────────────────────────────────────────────────────

    {
        "name": "send_mail",
        "endpoint": "/send_mail",
        "description": "寄送電子郵件，支援純文字/HTML 內文、附件、HTML 內嵌圖片",
        "params": {
            "to": {
                "type": "string",
                "required": True,
                "description": "收件人 Email，例如：someone@gmail.com",
            },
            "subject": {
                "type": "string",
                "required": True,
                "description": "郵件主旨",
            },
            "content": {
                "type": "string",
                "required": True,
                "description": "郵件內文；若 is_html=true 則為 HTML 字串，"
                               "內嵌圖片用 <img src='cid:img0'>、<img src='cid:img1'> 依序引用",
            },
            "is_html": {
                "type": "bool",
                "required": False,
                "default": False,
                "description": "true 代表 content 為 HTML，false 為純文字",
            },
            "attachment": {
                "type": "string",
                "required": False,
                "default": None,
                "description": "附件完整路徑，例如：C:\\temp\\report.pdf",
            },
            "inline_images": {
                "type": "list",
                "required": False,
                "default": [],
                "description": "內嵌圖片路徑清單，順序對應 cid:img0、cid:img1…，"
                               "例如：[\"C:\\\\temp\\\\a.jpg\", \"C:\\\\temp\\\\b.png\"]",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message": "寄送結果說明",
                "to":      "收件人",
                "subject": "主旨",
            },
        },
        "example": {
            "tool": "send_mail",
            "params": {
                "to": "test@gmail.com",
                "subject": "會議通知",
                "content": "明天下午三點開會，請準時出席。",
            },
        },
    },

    {
        "name": "sync_mail",
        "endpoint": "/sync_mail",
        "description": "同步 Gmail 收件匣到本地資料夾，可選擇重置後全部重新下載",
        "params": {
            "reset": {
                "type": "bool",
                "required": False,
                "default": False,
                "description": "true 代表清除同步記錄並重新下載所有信件",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "synced":          "本次新同步的信件數",
                "total_on_server": "伺服器上的總信件數",
                "mail_dir":        "本地儲存目錄",
            },
        },
        "example": {
            "tool": "sync_mail",
            "params": {},
        },
    },

    # ── 語音 ──────────────────────────────────────────────────────

    {
        "name": "text_to_voice",
        "endpoint": "/text_to_voice",
        "description": "將文字轉成語音 OGG 檔（繁體中文 TTS）",
        "params": {
            "text": {
                "type": "string",
                "required": True,
                "description": "要轉換成語音的文字內容",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "ogg_file":    "產生的 OGG 檔案路徑",
                "output_copy": "複製到工作區的路徑",
            },
        },
        "example": {
            "tool": "text_to_voice",
            "params": {
                "text": "你好，今天天氣真不錯。",
            },
        },
    },

    {
        "name": "voice_to_text",
        "endpoint": "/voice_to_text",
        "description": "將 OGG 語音檔轉成繁體中文文字（Google STT）",
        "params": {
            "file": {
                "type": "string",
                "required": True,
                "description": "OGG 語音檔的完整路徑",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "text": "辨識出的文字內容",
            },
        },
        "example": {
            "tool": "voice_to_text",
            "params": {
                "file": "C:\\temp\\recording.ogg",
            },
        },
    },

    # ── 截圖 ──────────────────────────────────────────────────────

    {
        "name": "screenshot",
        "endpoint": "/screenshot",
        "description": "截取全螢幕截圖並儲存為 PNG",
        "params": {
            "filename": {
                "type": "string",
                "required": False,
                "default": None,
                "description": "指定檔名（不含路徑），預設自動以時間戳命名",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "file": "截圖完整儲存路徑",
            },
        },
        "example": {
            "tool": "screenshot",
            "params": {},
        },
    },

    {
        "name": "screenshot_region",
        "endpoint": "/screenshot_region",
        "description": "截取螢幕上指定矩形區域的截圖",
        "params": {
            "x": {
                "type": "int",
                "required": True,
                "description": "左上角 X 座標（像素）",
            },
            "y": {
                "type": "int",
                "required": True,
                "description": "左上角 Y 座標（像素）",
            },
            "width": {
                "type": "int",
                "required": True,
                "description": "截圖寬度（像素）",
            },
            "height": {
                "type": "int",
                "required": True,
                "description": "截圖高度（像素）",
            },
            "filename": {
                "type": "string",
                "required": False,
                "default": None,
                "description": "指定檔名（不含路徑），預設自動以時間戳命名",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "file": "截圖完整儲存路徑",
            },
        },
        "example": {
            "tool": "screenshot_region",
            "params": {
                "x": 0,
                "y": 0,
                "width": 1920,
                "height": 1080,
            },
        },
    },

    # ── 系統 ──────────────────────────────────────────────────────

    {
        "name": "run_command",
        "endpoint": "/run_command",
        "description": "在本機執行系統指令（shell 或 list），回傳 stdout/stderr",
        "params": {
            "command": {
                "type": "string",
                "required": True,
                "description": "要執行的指令，字串（shell）或 list（推薦，避免注入），"
                               "例如：\"dir C:\\\\temp\" 或 [\"python\", \"--version\"]",
            },
            "timeout": {
                "type": "int",
                "required": False,
                "default": 30,
                "description": "逾時秒數，預設 30 秒",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "stdout":     "指令標準輸出",
                "stderr":     "指令錯誤輸出",
                "returncode": "指令退出碼（0 為成功）",
            },
        },
        "example": {
            "tool": "run_command",
            "params": {
                "command": "python --version",
            },
        },
    },

    # ── 音訊 ──────────────────────────────────────────────────────

    {
        "name": "normalize_mp3",
        "endpoint": "/normalize_mp3",
        "description": "批次正規化資料夾內所有 MP3 的音量（使用 ffmpeg loudnorm）",
        "params": {
            "input_folder": {
                "type": "string",
                "required": True,
                "description": "來源資料夾完整路徑，例如：C:\\\\music\\\\raw",
            },
            "output_folder": {
                "type": "string",
                "required": False,
                "default": None,
                "description": "輸出資料夾路徑，預設為 input_folder/normalized",
            },
            "loudnorm": {
                "type": "string",
                "required": False,
                "default": "I=-16:TP=-1.5:LRA=11",
                "description": "ffmpeg loudnorm 參數字串，通常不需更改",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "success":       "成功處理的檔名清單",
                "failed":        "失敗清單，每項含 file 與 reason",
                "total":         "總處理檔案數",
                "output_folder": "輸出資料夾路徑",
                "warnings":      "警告訊息清單",
            },
        },
        "example": {
            "tool": "normalize_mp3",
            "params": {
                "input_folder": "C:\\music\\raw",
            },
        },
    },
]


# ── 快速查詢用 dict（name → schema） ──────────────────────────────

TOOLS_MAP: dict[str, dict] = {t["name"]: t for t in TOOLS_SCHEMA}


def get_tool(name: str) -> dict | None:
    """依名稱取得單一工具 schema，找不到回傳 None。"""
    return TOOLS_MAP.get(name)


_TYPE_MAP = {
    "string": str,
    "int":    int,
    "bool":  (bool, int),   # JSON 無 bool，允許 0/1
    "list":   list,
}


def validate_params(tool_name: str, params: dict) -> list[str]:
    """
    驗證 params 是否符合 schema。
    1. 檢查必填參數是否存在
    2. 檢查已提供參數的型別是否正確
    回傳錯誤訊息清單；空清單代表驗證通過。
    """
    tool = get_tool(tool_name)
    if not tool:
        return [f"未知工具：{tool_name}"]

    errors = []
    for param_name, meta in tool["params"].items():
        if meta["required"] and param_name not in params:
            errors.append(f"缺少必填參數：{param_name}（{meta['description']}）")

        if param_name in params and params[param_name] is not None:
            expected = _TYPE_MAP.get(meta["type"])
            if expected and not isinstance(params[param_name], expected):
                errors.append(
                    f"參數 {param_name} 型別錯誤：期望 {meta['type']}，"
                    f"實際 {type(params[param_name]).__name__}"
                )

    return errors
