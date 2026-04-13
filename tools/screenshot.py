"""
tools/screenshot.py
截圖工具：使用 nircmd.exe 截圖並儲存
"""

import os
import subprocess
from datetime import datetime

NIRCMD_PATH  = r"C:\Users\heave\.openclaw\assistant-scripts\tools\nircmd.exe"
SCREENSHOT_DIR = r"C:\Users\heave\OneDrive\文件\薇薇\Screenshots"


def take_screenshot(filename: str | None = None) -> dict:
    """
    截取全螢幕截圖，儲存為 PNG。
    filename：指定檔名（不含路徑），預設自動以時間戳命名。
    回傳：{"file": 完整路徑}
    """
    if not os.path.exists(NIRCMD_PATH):
        raise FileNotFoundError(f"找不到 nircmd.exe：{NIRCMD_PATH}")

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    if not filename:
        filename = datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png")

    output_path = os.path.join(SCREENSHOT_DIR, filename)

    result = subprocess.run(
        [NIRCMD_PATH, "savescreenshot", output_path],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"截圖失敗（returncode={result.returncode}）：{result.stderr}"
        )

    if not os.path.exists(output_path):
        raise RuntimeError(f"截圖指令執行完畢，但找不到輸出檔案：{output_path}")

    return {"file": output_path}


def take_screenshot_region(
    x: int, y: int, width: int, height: int,
    filename: str | None = None,
) -> dict:
    """
    截取指定區域截圖。
    回傳：{"file": 完整路徑}
    """
    if not os.path.exists(NIRCMD_PATH):
        raise FileNotFoundError(f"找不到 nircmd.exe：{NIRCMD_PATH}")

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    if not filename:
        filename = datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png")

    output_path = os.path.join(SCREENSHOT_DIR, filename)

    result = subprocess.run(
        [NIRCMD_PATH, "savescreenshotwin",
         str(x), str(y), str(width), str(height), output_path],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"區域截圖失敗：{result.stderr}")

    return {"file": output_path}
