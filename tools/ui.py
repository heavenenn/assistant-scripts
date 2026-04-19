"""
tools/ui.py
薇薇 UI 自動化工具（基於 pyautogui + opencv）

功能：
  click / double_click / right_click  → 滑鼠操作
  type_text     → 輸入文字（支援中文，透過剪貼簿貼上）
  hotkey        → 鍵盤快捷鍵
  scroll        → 滾輪
  locate_image  → 在螢幕上比對圖片位置（需 opencv-python）
  get_screen_size → 取得螢幕解析度

需安裝：
  pip install pyautogui opencv-python pyperclip
"""

import time
import pyautogui

# 安全措施：滑鼠移到螢幕左上角可中止操作
pyautogui.FAILSAFE = True
# 每次操作間隔（秒），避免太快
pyautogui.PAUSE = 0.1


# ── 滑鼠 ─────────────────────────────────────────────────────────

def click(x: int, y: int, button: str = "left") -> dict:
    """在指定座標點擊滑鼠。"""
    pyautogui.click(x, y, button=button)
    return {"message": f"已點擊 ({x}, {y})，按鍵={button}"}


def double_click(x: int, y: int) -> dict:
    """在指定座標雙擊滑鼠。"""
    pyautogui.doubleClick(x, y)
    return {"message": f"已雙擊 ({x}, {y})"}


def right_click(x: int, y: int) -> dict:
    """在指定座標按右鍵。"""
    pyautogui.rightClick(x, y)
    return {"message": f"已右鍵點擊 ({x}, {y})"}


# ── 鍵盤 ─────────────────────────────────────────────────────────

def type_text(text: str, interval: float = 0.05) -> dict:
    """
    輸入文字。
    ASCII 用鍵盤逐字輸入；非 ASCII（中文等）透過剪貼簿貼上。
    """
    if not text:
        raise ValueError("文字內容不能為空")

    if text.isascii():
        pyautogui.typewrite(text, interval=interval)
    else:
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.15)

    display = text[:50] + ("..." if len(text) > 50 else "")
    return {"message": f"已輸入文字：{display}"}


def hotkey(keys: str) -> dict:
    """
    按下鍵盤快捷鍵。
    keys 以 + 分隔，例如 "ctrl+c"、"alt+tab"、"ctrl+shift+s"。
    """
    if not keys:
        raise ValueError("快捷鍵不能為空")

    key_list = [k.strip() for k in keys.split("+")]
    pyautogui.hotkey(*key_list)
    return {"message": f"已按下：{keys}"}


def press_key(key: str, presses: int = 1) -> dict:
    """
    按下單一按鍵（非組合鍵）。
    key: 按鍵名稱，例如 "enter"、"tab"、"down"、"up"、"left"、"right"、
         "escape"、"space"、"backspace"、"delete"、"f1"~"f12"、"a"~"z"、"0"~"9"
    presses: 按幾次（預設 1）
    """
    if not key:
        raise ValueError("按鍵名稱不能為空")
    pyautogui.press(key.strip(), presses=presses)
    times = f" ×{presses}" if presses > 1 else ""
    return {"message": f"已按下：{key}{times}"}


# ── 等待 ─────────────────────────────────────────────────────────

def wait(seconds: float = 1.0) -> dict:
    """
    等待指定秒數。
    用於步驟之間需要暫停，讓視窗切換、動畫完成等。
    """
    if seconds < 0 or seconds > 30:
        raise ValueError("等待秒數必須在 0~30 之間")
    time.sleep(seconds)
    return {"message": f"已等待 {seconds} 秒"}


# ── 滾輪 ─────────────────────────────────────────────────────────

def scroll(clicks: int, x: int | None = None, y: int | None = None) -> dict:
    """
    滾動滑鼠滾輪。
    clicks 正數向上、負數向下。可指定座標位置。
    """
    pyautogui.scroll(clicks, x=x, y=y)
    direction = "上" if clicks > 0 else "下"
    pos = f" 於 ({x}, {y})" if x is not None else ""
    return {"message": f"已向{direction}滾動 {abs(clicks)} 格{pos}"}


# ── 圖片定位 ─────────────────────────────────────────────────────

def locate_image(image_path: str, confidence: float = 0.8) -> dict:
    """
    在螢幕上尋找指定圖片的位置（需 opencv-python）。
    回傳找到的中心座標與區域。
    """
    import os
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"圖片不存在：{image_path}")

    location = pyautogui.locateOnScreen(image_path, confidence=confidence)

    if location:
        center = pyautogui.center(location)
        return {
            "found": True,
            "x": center.x,
            "y": center.y,
            "region": {
                "left": location.left,
                "top": location.top,
                "width": location.width,
                "height": location.height,
            },
        }

    return {"found": False, "message": "畫面上未找到指定圖片"}


# ── 螢幕資訊 ─────────────────────────────────────────────────────

def get_screen_size() -> dict:
    """取得螢幕解析度。"""
    width, height = pyautogui.size()
    return {"width": width, "height": height}
