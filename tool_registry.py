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
                "default": True,
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

    {
        "name": "screen_record",
        "endpoint": "/screen_record",
        "description": "錄製全螢幕影片（MP4），可指定錄影秒數",
        "params": {
            "duration": {
                "type": "int",
                "required": False,
                "default": 10,
                "description": "錄影秒數，預設 10 秒，最大 300 秒",
            },
            "framerate": {
                "type": "int",
                "required": False,
                "default": 15,
                "description": "畫面更新率 fps，預設 15（降低檔案大小）",
            },
            "filename": {
                "type": "string",
                "required": False,
                "default": None,
                "description": "指定檔名（不含路徑），預設以時間戳命名，例如：demo.mp4",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "file":     "影片完整儲存路徑",
                "duration": "錄影秒數",
                "size_kb":  "檔案大小（KB）",
            },
        },
        "example": {
            "tool": "screen_record",
            "params": {"duration": 10},
        },
    },

    # ── 系統 ──────────────────────────────────────────────────────

    {
        "name": "run_command",
        "endpoint": "/run_command",
        "description": "在本機執行系統指令（shell 或 list），回傳 stdout/stderr。需要管理員權限時設 elevated=true",
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
            "elevated": {
                "type": "bool",
                "required": False,
                "default": False,
                "description": "是否以管理員權限執行（寫入系統目錄、修改系統設定時設為 true）",
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

    # ── UI 操作 ───────────────────────────────────────────────────

    {
        "name": "click",
        "endpoint": "/click",
        "description": "在螢幕指定座標點擊滑鼠左鍵／右鍵／中鍵",
        "params": {
            "x": {
                "type": "int",
                "required": True,
                "description": "點擊位置 X 座標（像素）",
            },
            "y": {
                "type": "int",
                "required": True,
                "description": "點擊位置 Y 座標（像素）",
            },
            "button": {
                "type": "string",
                "required": False,
                "default": "left",
                "description": "滑鼠按鍵：left / right / middle",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message": "操作結果說明",
            },
        },
        "example": {
            "tool": "click",
            "params": {"x": 500, "y": 300},
        },
    },

    {
        "name": "double_click",
        "endpoint": "/double_click",
        "description": "在螢幕指定座標雙擊滑鼠",
        "params": {
            "x": {
                "type": "int",
                "required": True,
                "description": "雙擊位置 X 座標（像素）",
            },
            "y": {
                "type": "int",
                "required": True,
                "description": "雙擊位置 Y 座標（像素）",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message": "操作結果說明",
            },
        },
        "example": {
            "tool": "double_click",
            "params": {"x": 500, "y": 300},
        },
    },

    {
        "name": "right_click",
        "endpoint": "/right_click",
        "description": "在螢幕指定座標按滑鼠右鍵",
        "params": {
            "x": {
                "type": "int",
                "required": True,
                "description": "右鍵位置 X 座標（像素）",
            },
            "y": {
                "type": "int",
                "required": True,
                "description": "右鍵位置 Y 座標（像素）",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message": "操作結果說明",
            },
        },
        "example": {
            "tool": "right_click",
            "params": {"x": 500, "y": 300},
        },
    },

    {
        "name": "type_text",
        "endpoint": "/type_text",
        "description": "輸入文字到目前焦點位置，支援中文（透過剪貼簿貼上）",
        "params": {
            "text": {
                "type": "string",
                "required": True,
                "description": "要輸入的文字內容",
            },
            "interval": {
                "type": "float",
                "required": False,
                "default": 0.05,
                "description": "每個字元間隔秒數（僅 ASCII 有效）",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message": "操作結果說明",
            },
        },
        "example": {
            "tool": "type_text",
            "params": {"text": "Hello 你好"},
        },
    },

    {
        "name": "hotkey",
        "endpoint": "/hotkey",
        "description": "按下鍵盤快捷鍵組合，用 + 分隔按鍵",
        "params": {
            "keys": {
                "type": "string",
                "required": True,
                "description": "快捷鍵組合，用 + 分隔，例如：ctrl+c、alt+tab、ctrl+shift+s",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message": "操作結果說明",
            },
        },
        "example": {
            "tool": "hotkey",
            "params": {"keys": "ctrl+s"},
        },
    },

    {
        "name": "press_key",
        "endpoint": "/press_key",
        "description": "按下單一按鍵（非組合鍵），例如方向鍵、Enter、字母鍵等",
        "params": {
            "key": {
                "type": "string",
                "required": True,
                "description": "按鍵名稱：down / up / left / right / enter / tab / escape / "
                               "space / backspace / delete / f1~f12 / a~z / 0~9",
            },
            "presses": {
                "type": "int",
                "required": False,
                "default": 1,
                "description": "連續按幾次，預設 1",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message": "操作結果說明",
            },
        },
        "example": {
            "tool": "press_key",
            "params": {"key": "down"},
        },
    },

    {
        "name": "wait",
        "endpoint": "/wait",
        "description": "等待指定秒數，用於步驟之間暫停（讓視窗切換完成、動畫結束等）",
        "params": {
            "seconds": {
                "type": "float",
                "required": False,
                "default": 1.0,
                "description": "等待秒數，0~30 秒，預設 1 秒",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message": "操作結果說明",
            },
        },
        "example": {
            "tool": "wait",
            "params": {"seconds": 2},
        },
    },

    {
        "name": "scroll",
        "endpoint": "/scroll",
        "description": "滾動滑鼠滾輪，正數向上、負數向下",
        "params": {
            "clicks": {
                "type": "int",
                "required": True,
                "description": "滾動格數，正數向上、負數向下",
            },
            "x": {
                "type": "int",
                "required": False,
                "default": None,
                "description": "滾動時的 X 座標（選填，預設目前位置）",
            },
            "y": {
                "type": "int",
                "required": False,
                "default": None,
                "description": "滾動時的 Y 座標（選填，預設目前位置）",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message": "操作結果說明",
            },
        },
        "example": {
            "tool": "scroll",
            "params": {"clicks": -3},
        },
    },

    {
        "name": "locate_image",
        "endpoint": "/locate_image",
        "description": "在螢幕上比對圖片位置（需 opencv-python），回傳中心座標",
        "params": {
            "image_path": {
                "type": "string",
                "required": True,
                "description": "要搜尋的圖片完整路徑",
            },
            "confidence": {
                "type": "float",
                "required": False,
                "default": 0.8,
                "description": "比對信心度 0~1，預設 0.8",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "found":   "是否找到（true/false）",
                "x":       "找到時的中心 X 座標",
                "y":       "找到時的中心 Y 座標",
                "region":  "找到時的區域（left, top, width, height）",
                "message": "未找到時的說明",
            },
        },
        "example": {
            "tool": "locate_image",
            "params": {"image_path": "C:\\temp\\button.png"},
        },
    },

    {
        "name": "get_screen_size",
        "endpoint": "/get_screen_size",
        "description": "取得螢幕解析度（寬 × 高像素）",
        "params": {},
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "width":  "螢幕寬度（像素）",
                "height": "螢幕高度（像素）",
            },
        },
        "example": {
            "tool": "get_screen_size",
            "params": {},
        },
    },

    # ── AI 圖片生成 ───────────────────────────────────────────────

    {
        "name": "generate_image",
        "endpoint": "/generate_image",
        "description": "用文字描述生成圖片（xAI grok-imagine-image），可一次生成多張",
        "params": {
            "prompt": {
                "type": "string",
                "required": True,
                "description": "圖片描述文字，例如：一隻穿太空裝的柴犬在月球漫步",
            },
            "n": {
                "type": "int",
                "required": False,
                "default": 1,
                "description": "生成張數，1~10",
            },
            "aspect_ratio": {
                "type": "string",
                "required": False,
                "default": "auto",
                "description": "比例：auto / 1:1 / 16:9 / 9:16 / 4:3 / 3:2 等",
            },
            "resolution": {
                "type": "string",
                "required": False,
                "default": "1k",
                "description": "解析度：1k 或 2k",
            },
            "filename": {
                "type": "string",
                "required": False,
                "default": None,
                "description": "指定檔名（僅 n=1 時有效），例如：logo.jpg",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "files": "生成圖片的本地路徑清單",
                "count": "成功生成的張數",
            },
        },
        "example": {
            "tool": "generate_image",
            "params": {"prompt": "夕陽下的台北101，油畫風格"},
        },
    },

    {
        "name": "edit_image",
        "endpoint": "/edit_image",
        "description": "用文字指示編輯現有圖片（風格轉換、修改內容等）",
        "params": {
            "prompt": {
                "type": "string",
                "required": True,
                "description": "編輯指示，例如：把背景換成海邊",
            },
            "image_path": {
                "type": "string",
                "required": True,
                "description": "來源圖片的完整路徑",
            },
            "aspect_ratio": {
                "type": "string",
                "required": False,
                "default": None,
                "description": "輸出比例（選填），不指定則保持原圖比例",
            },
            "filename": {
                "type": "string",
                "required": False,
                "default": None,
                "description": "指定輸出檔名",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "file": "編輯後圖片的本地路徑",
            },
        },
        "example": {
            "tool": "edit_image",
            "params": {
                "prompt": "把這張照片轉成鉛筆素描風格",
                "image_path": "C:\\Users\\heave\\OneDrive\\文件\\薇薇\\Images\\photo.jpg",
            },
        },
    },

    # ── AI 影片生成 ───────────────────────────────────────────────

    {
        "name": "generate_video",
        "endpoint": "/generate_video",
        "description": "用文字（或圖片）生成影片（xAI grok-imagine-video），非同步生成，自動等待完成",
        "params": {
            "prompt": {
                "type": "string",
                "required": True,
                "description": "影片描述文字，例如：一朵花在陽光下慢慢綻放的縮時攝影",
            },
            "duration": {
                "type": "int",
                "required": False,
                "default": 6,
                "description": "影片秒數，1~15 秒",
            },
            "aspect_ratio": {
                "type": "string",
                "required": False,
                "default": "16:9",
                "description": "比例：16:9 / 9:16 / 1:1 / 4:3 / 3:2",
            },
            "resolution": {
                "type": "string",
                "required": False,
                "default": "480p",
                "description": "解析度：480p 或 720p（720p 處理較慢）",
            },
            "image_path": {
                "type": "string",
                "required": False,
                "default": None,
                "description": "來源圖片路徑（圖片轉影片模式），不提供則純文字生成",
            },
            "filename": {
                "type": "string",
                "required": False,
                "default": None,
                "description": "指定輸出檔名，例如：demo.mp4",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "file":     "影片本地路徑",
                "duration": "影片秒數",
            },
        },
        "example": {
            "tool": "generate_video",
            "params": {
                "prompt": "一隻貓在窗台上曬太陽，尾巴慢慢晃動",
                "duration": 8,
            },
        },
    },

    {
        "name": "edit_video",
        "endpoint": "/edit_video",
        "description": "用文字指示編輯現有影片（輸入影片最長 8.7 秒）",
        "params": {
            "prompt": {
                "type": "string",
                "required": True,
                "description": "編輯指示，例如：給影片中的人物加上墨鏡",
            },
            "video_url": {
                "type": "string",
                "required": True,
                "description": "來源影片的公開 URL（必須是 .mp4 格式）",
            },
            "filename": {
                "type": "string",
                "required": False,
                "default": None,
                "description": "指定輸出檔名",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "file": "編輯後影片的本地路徑",
            },
        },
        "example": {
            "tool": "edit_video",
            "params": {
                "prompt": "把影片中人物的衣服換成紅色",
                "video_url": "https://example.com/video.mp4",
            },
        },
    },

    {
        "name": "extend_video",
        "endpoint": "/extend_video",
        "description": "延伸現有影片（從最後一幀繼續生成 2~10 秒）",
        "params": {
            "prompt": {
                "type": "string",
                "required": True,
                "description": "描述接下來要發生的內容，例如：鏡頭慢慢拉遠，露出整座城市天際線",
            },
            "video_url": {
                "type": "string",
                "required": True,
                "description": "來源影片的公開 URL（2~15 秒，.mp4 格式）",
            },
            "duration": {
                "type": "int",
                "required": False,
                "default": 6,
                "description": "延伸秒數，2~10 秒",
            },
            "filename": {
                "type": "string",
                "required": False,
                "default": None,
                "description": "指定輸出檔名",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "file":     "延伸後影片的本地路徑",
                "duration": "延伸秒數",
            },
        },
        "example": {
            "tool": "extend_video",
            "params": {
                "prompt": "鏡頭緩緩上升，拍攝天空中的星星",
                "video_url": "https://example.com/video.mp4",
                "duration": 8,
            },
        },
    },

    # ── AI 文字生成 ───────────────────────────────────────────────

    {
        "name": "generate_text",
        "endpoint": "/generate_text",
        "description": "AI 生成文字內容（部落格、腳本、報告等），存成 Markdown 檔",
        "params": {
            "prompt": {
                "type": "string",
                "required": True,
                "description": "生成指示，例如：寫一篇關於量子計算的科普文章，約 1000 字",
            },
            "system_prompt": {
                "type": "string",
                "required": False,
                "default": "你是一位專業的繁體中文寫作助手。",
                "description": "系統提示詞，控制寫作風格和角色",
            },
            "filename": {
                "type": "string",
                "required": False,
                "default": None,
                "description": "指定檔名，例如：quantum_article.md",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "file":    "文字檔本地路徑",
                "length":  "總字數",
                "preview": "前 200 字預覽",
            },
        },
        "example": {
            "tool": "generate_text",
            "params": {
                "prompt": "寫一篇 1000 字的部落格文章，主題是居家咖啡沖泡技巧",
            },
        },
    },

    {
        "name": "generate_novel",
        "endpoint": "/generate_novel",
        "description": "AI 分章節生成長篇小說（先產大綱，再逐章生成，合併成 Markdown）",
        "params": {
            "prompt": {
                "type": "string",
                "required": True,
                "description": "小說構想描述，例如：一個高中生意外穿越到戰國時代的冒險故事",
            },
            "chapters": {
                "type": "int",
                "required": False,
                "default": 5,
                "description": "章節數量，1~30",
            },
            "style": {
                "type": "string",
                "required": False,
                "default": "繁體中文，文筆細膩，對話生動",
                "description": "寫作風格描述",
            },
            "filename": {
                "type": "string",
                "required": False,
                "default": None,
                "description": "指定檔名，例如：my_novel.md",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "file":         "小說檔本地路徑",
                "chapters":     "實際章節數",
                "total_length": "總字數",
            },
        },
        "example": {
            "tool": "generate_novel",
            "params": {
                "prompt": "一個AI管家意外產生自我意識的科幻故事",
                "chapters": 8,
            },
        },
    },

    # ── Telegram 推播 ─────────────────────────────────────────────────

    {
        "name": "push_message",
        "endpoint": "/push_message",
        "description": "透過 Telegram Bot 主動推播文字訊息給使用者",
        "params": {
            "text": {
                "type": "string",
                "required": True,
                "description": "要推播的文字內容",
            },
            "parse_mode": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "格式：空字串（純文字）、Markdown、HTML",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message":    "推播結果訊息",
                "message_id": "Telegram 訊息 ID",
            },
        },
        "example": {
            "tool": "push_message",
            "params": {
                "text": "定遠，您的任務已完成！",
            },
        },
    },

    {
        "name": "push_photo",
        "endpoint": "/push_photo",
        "description": "透過 Telegram Bot 主動推播圖片給使用者",
        "params": {
            "photo_path": {
                "type": "string",
                "required": True,
                "description": "本地圖片檔案路徑",
            },
            "caption": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "圖片說明文字",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message":    "推播結果訊息",
                "message_id": "Telegram 訊息 ID",
            },
        },
        "example": {
            "tool": "push_photo",
            "params": {
                "photo_path": "C:\\Users\\heave\\screenshot.png",
                "caption": "這是目前的畫面",
            },
        },
    },

    {
        "name": "push_file",
        "endpoint": "/push_file",
        "description": "透過 Telegram Bot 主動推播檔案給使用者",
        "params": {
            "file_path": {
                "type": "string",
                "required": True,
                "description": "本地檔案路徑",
            },
            "caption": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "檔案說明文字",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message":    "推播結果訊息",
                "message_id": "Telegram 訊息 ID",
                "filename":   "檔案名稱",
            },
        },
        "example": {
            "tool": "push_file",
            "params": {
                "file_path": "C:\\Users\\heave\\report.pdf",
                "caption": "這是您要的報告",
            },
        },
    },

    {
        "name": "ai_push",
        "endpoint": "/ai_push",
        "description": "用 Grok AI 即時生成訊息並透過 Telegram 推播（每次內容都不同，可配合情境）",
        "params": {
            "scenario": {
                "type": "string",
                "required": True,
                "description": "情境描述，例如：睡前提醒-溫馨版、早安問候、任務完成回報、下班提醒",
            },
            "context": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "額外背景資訊，例如：今天加班到很晚、剛聊了遊戲話題、天氣很冷",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message":        "推播結果訊息",
                "message_id":     "Telegram 訊息 ID",
                "generated_text": "AI 生成的訊息內容",
            },
        },
        "example": {
            "tool": "ai_push",
            "params": {
                "scenario": "睡前提醒-可愛吐槽版",
                "context": "主人今天玩遊戲玩到很晚",
            },
        },
    },

    # ── 排程 ───────────────────────────────────────────────────────

    {
        "name": "schedule_task",
        "endpoint": "/schedule_task",
        "description": "排程延遲或定時執行任何工具（例如 N 分鐘後推播、指定時間截圖）",
        "params": {
            "tool": {
                "type": "string",
                "required": True,
                "description": "要排程執行的工具名稱（如 push_message、screenshot、run_command 等）",
            },
            "params": {
                "type": "string",
                "required": False,
                "default": "{}",
                "description": "工具參數，JSON 字串，例如 {\"text\": \"提醒！\"}",
            },
            "delay_seconds": {
                "type": "int",
                "required": False,
                "default": 0,
                "description": "延遲秒數（與 run_at 擇一），例如 300 = 5分鐘後",
            },
            "run_at": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "指定執行時間，格式 HH:MM 或 YYYY-MM-DD HH:MM（與 delay_seconds 擇一）",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "task_id":        "排程任務 ID",
                "tool":           "工具名稱",
                "scheduled_time": "預計執行時間",
                "delay_seconds":  "延遲秒數",
            },
        },
        "example": {
            "tool": "schedule_task",
            "params": {
                "tool": "push_message",
                "params": "{\"text\": \"主人，5分鐘到了！\"}",
                "delay_seconds": 300,
            },
        },
    },

    {
        "name": "list_scheduled",
        "endpoint": "/list_scheduled",
        "description": "列出所有排程任務（含等待中、已完成、已取消）",
        "params": {},
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "tasks": "排程任務清單",
            },
        },
        "example": {
            "tool": "list_scheduled",
            "params": {},
        },
    },

    {
        "name": "cancel_scheduled",
        "endpoint": "/cancel_scheduled",
        "description": "取消一個等待中的排程任務",
        "params": {
            "task_id": {
                "type": "string",
                "required": True,
                "description": "要取消的排程任務 ID",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message": "取消結果",
            },
        },
        "example": {
            "tool": "cancel_scheduled",
            "params": {
                "task_id": "a1b2c3d4",
            },
        },
    },

    # ── OpenClaw Cron 排程管理（防呆版）─────────────────────────

    {
        "name": "cron_add",
        "endpoint": "/cron_add",
        "description": "新增定時 ai_push 排程（自動帶正確 Telegram delivery 設定，不需手動指定 channel/to）",
        "params": {
            "name": {
                "type": "string",
                "required": True,
                "description": "任務名稱（如「睡前提醒-21:30」「早安問候」）",
            },
            "scenario": {
                "type": "string",
                "required": True,
                "description": "ai_push 的 scenario 參數（如「睡前提醒-溫馨版」「早安問候」）",
            },
            "cron_expr": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "Cron 表達式，週期性任務（如「30 21 * * *」= 每天 21:30，「0 7 * * 1-5」= 平日 7:00），與 at 擇一",
            },
            "at": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "一次性任務時間（ISO 格式如「2026-04-23T20:30:00」），與 cron_expr 擇一",
            },
            "context": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "ai_push 的額外背景資訊（如「主人今天加班」），選填",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message":  "結果訊息",
                "job_id":   "排程任務 ID",
                "name":     "任務名稱",
                "schedule": "排程時間",
            },
        },
        "example": {
            "tool": "cron_add",
            "params": {
                "name": "睡前提醒-21:30",
                "scenario": "睡前提醒-溫馨版",
                "cron_expr": "30 21 * * *",
            },
        },
    },

    {
        "name": "cron_list",
        "endpoint": "/cron_list",
        "description": "列出所有 OpenClaw Cron 排程任務（含狀態、delivery 設定）",
        "params": {},
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message": "結果訊息",
                "total":   "任務總數",
                "jobs":    "任務列表",
            },
        },
        "example": {
            "tool": "cron_list",
            "params": {},
        },
    },

    {
        "name": "cron_remove",
        "endpoint": "/cron_remove",
        "description": "移除指定的 OpenClaw Cron 排程任務",
        "params": {
            "job_id": {
                "type": "string",
                "required": True,
                "description": "要移除的任務 ID（可用 cron_list 查詢）",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message": "結果訊息",
            },
        },
        "example": {
            "tool": "cron_remove",
            "params": {
                "job_id": "b46ed720-6912-49b1-b0a7-90e13dae4fe0",
            },
        },
    },

    {
        "name": "cron_edit",
        "endpoint": "/cron_edit",
        "description": "修改現有 Cron 排程（自動帶正確 delivery 設定）",
        "params": {
            "job_id": {
                "type": "string",
                "required": True,
                "description": "要修改的任務 ID",
            },
            "name": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "新名稱（選填）",
            },
            "scenario": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "新的 ai_push scenario（選填）",
            },
            "cron_expr": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "新的 Cron 表達式（選填）",
            },
            "enabled": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "啟用或停用（\"true\" / \"false\"）（選填）",
            },
        },
        "response": {
            "success_key": "status",
            "success_val": "success",
            "data_keys": {
                "message": "結果訊息",
                "job_id":  "任務 ID",
                "name":    "任務名稱",
            },
        },
        "example": {
            "tool": "cron_edit",
            "params": {
                "job_id": "b46ed720-6912-49b1-b0a7-90e13dae4fe0",
                "scenario": "睡前提醒-可愛吐槽版",
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
    "float": (float, int),  # 允許整數（JSON 1 vs 1.0）
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
