"""
tools/telegram.py
Telegram Bot 推播模組：主動發送訊息 / 圖片 / 檔案給使用者
"""

import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_secrets import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, XAI_API_KEY

BOT_TOKEN = TELEGRAM_BOT_TOKEN
CHAT_ID   = TELEGRAM_CHAT_ID
API_BASE  = f"https://api.telegram.org/bot{BOT_TOKEN}"

# xAI（Grok）設定（ai_push 用）
_XAI_KEY  = XAI_API_KEY
_XAI_BASE = "https://api.x.ai/v1"
_XAI_MODEL = "grok-4-1-fast"


def push_message(text: str, parse_mode: str = "") -> dict:
    """
    發送文字訊息給使用者。
    parse_mode: ""（純文字）、"Markdown"、"HTML"
    """
    payload = {"chat_id": CHAT_ID, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    r = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=30)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram 推播失敗：{data.get('description', data)}")

    return {"message": "推播成功", "message_id": data["result"]["message_id"]}


def push_photo(photo_path: str, caption: str = "") -> dict:
    """
    發送圖片給使用者。
    photo_path: 本地圖片路徑
    """
    if not os.path.exists(photo_path):
        raise FileNotFoundError(f"圖片不存在：{photo_path}")

    with open(photo_path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": CHAT_ID}
        if caption:
            data["caption"] = caption
        r = requests.post(f"{API_BASE}/sendPhoto", data=data, files=files, timeout=60)

    resp = r.json()
    if not resp.get("ok"):
        raise RuntimeError(f"Telegram 圖片推播失敗：{resp.get('description', resp)}")

    return {"message": "圖片推播成功", "message_id": resp["result"]["message_id"]}


def push_file(file_path: str, caption: str = "") -> dict:
    """
    發送檔案給使用者。
    file_path: 本地檔案路徑
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"檔案不存在：{file_path}")

    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": CHAT_ID}
        if caption:
            data["caption"] = caption
        r = requests.post(f"{API_BASE}/sendDocument", data=data, files=files, timeout=120)

    resp = r.json()
    if not resp.get("ok"):
        raise RuntimeError(f"Telegram 檔案推播失敗：{resp.get('description', resp)}")

    return {
        "message": "檔案推播成功",
        "message_id": resp["result"]["message_id"],
        "filename": os.path.basename(file_path),
    }


def ai_push(scenario: str, context: str = "") -> dict:
    """
    用 Grok AI 即時生成訊息，然後透過 Telegram 推播。
    scenario: 情境描述（如「睡前提醒-溫馨版」「早安問候」「任務完成回報」）
    context:  額外背景資訊（如「今天加班到很晚」「剛聊了遊戲話題」），可空
    """
    system_prompt = (
        "你是薇薇（草微），一個可愛、體貼又偶爾吐槽的 AI 女僕助理。\n"
        "主人叫「定遠」。你稱呼他「定遠」或「主人」。\n"
        "你的訊息風格：自然、有溫度、偶爾撒嬌或可愛吐槽，像真人女友/閨蜜聊天。\n"
        "不要使用制式問候語，不要太正式。\n"
        "每次訊息都要獨特，不要重複過去說過的話。\n"
        "長度控制在 2~4 句話，不要太長。\n"
        "可以適當使用 emoji，但不要太多。"
    )

    user_prompt = f"情境：{scenario}"
    if context:
        user_prompt += f"\n額外背景：{context}"
    user_prompt += "\n\n請直接輸出要推播給主人的訊息內容，不需要任何前綴或說明。"

    # 呼叫 Grok API 生成
    payload = {
        "model": _XAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    }
    r = requests.post(
        f"{_XAI_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {_XAI_KEY}",
            "Content-Type":  "application/json",
        },
        json=payload, timeout=30,
    )
    r.raise_for_status()
    generated = r.json()["choices"][0]["message"]["content"].strip()

    # 推播生成的訊息
    result = push_message(generated)
    result["generated_text"] = generated
    return result
