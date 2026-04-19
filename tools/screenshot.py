"""
tools/screenshot.py
截圖 / 螢幕錄影工具
  截圖：使用 nircmd.exe
  錄影：使用 ffmpeg gdigrab
"""

import os
import subprocess
from datetime import datetime

NIRCMD_PATH    = r"C:\Users\heave\.openclaw\assistant-scripts\tools\nircmd.exe"
FFMPEG_PATH    = r"C:\Program Files\ffmpeg-8.1-essentials_build\bin\ffmpeg.exe"
SCREENSHOT_DIR = r"C:\Users\heave\OneDrive\文件\薇薇\Screenshots"
RECORDING_DIR  = r"C:\Users\heave\OneDrive\文件\薇薇\Recordings"


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


# ── 螢幕錄影 ─────────────────────────────────────────────────────

def screen_record(
    duration: int = 10,
    framerate: int = 15,
    filename: str | None = None,
) -> dict:
    """
    錄製全螢幕影片（MP4，使用 ffmpeg gdigrab）。

    duration:   錄影秒數（預設 10 秒）
    framerate:  畫面更新率（預設 15 fps，降低檔案大小）
    filename:   指定檔名（不含路徑），預設以時間戳命名

    回傳：{"file": 完整路徑, "duration": 秒數, "size_kb": 檔案大小}
    """
    if not os.path.exists(FFMPEG_PATH):
        raise FileNotFoundError(f"找不到 ffmpeg：{FFMPEG_PATH}")

    if duration < 1 or duration > 300:
        raise ValueError("錄影秒數必須在 1~300 之間")

    os.makedirs(RECORDING_DIR, exist_ok=True)

    if not filename:
        filename = datetime.now().strftime("recording_%Y%m%d_%H%M%S.mp4")
    elif not filename.endswith(".mp4"):
        filename += ".mp4"

    output_path = os.path.join(RECORDING_DIR, filename)

    cmd = [
        FFMPEG_PATH,
        "-f", "gdigrab",
        "-framerate", str(framerate),
        "-t", str(duration),
        "-i", "desktop",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-y",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=duration + 30)

    if not os.path.exists(output_path):
        raise RuntimeError(
            f"錄影失敗，檔案未產生。ffmpeg stderr：{result.stderr[-500:]}"
        )

    size_kb = round(os.path.getsize(output_path) / 1024, 1)
    return {"file": output_path, "duration": duration, "size_kb": size_kb}
