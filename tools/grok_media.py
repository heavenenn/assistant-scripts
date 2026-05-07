"""
tools/grok_media.py
AI 圖片 / 影片生成工具（xAI Imagine API）

圖片：grok-imagine-image — 同步回傳 URL
影片：grok-imagine-video — 非同步，需輪詢 request_id

所有生成結果自動下載到本地目錄，回傳本地路徑。
"""

import os
import time
import base64
import requests
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_secrets import XAI_API_KEY

# ── 設定 ─────────────────────────────────────────────────────────

XAI_API_BASE = "https://api.x.ai/v1"

IMAGE_DIR = r"C:\Users\heave\OneDrive\文件\薇薇\Images"
VIDEO_DIR = r"C:\Users\heave\OneDrive\文件\薇薇\Videos"

_HEADERS = {
    "Authorization": f"Bearer {XAI_API_KEY}",
    "Content-Type":  "application/json",
}


# ── 內部工具 ─────────────────────────────────────────────────────

def _download(url: str, dest_path: str) -> None:
    """下載 URL 到指定路徑。"""
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(r.content)


def _image_to_base64_uri(image_path: str) -> str:
    """將本地圖片轉為 data URI。"""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "webp": "image/webp"}.get(ext, "image/png")
    return f"data:{mime};base64,{b64}"


def _poll_video(request_id: str, poll_interval: int = 5,
                poll_timeout: int = 600) -> dict:
    """
    輪詢影片生成結果。
    回傳 API response dict（含 status, video.url 等）。
    """
    deadline = time.time() + poll_timeout
    while time.time() < deadline:
        r = requests.get(
            f"{XAI_API_BASE}/videos/{request_id}",
            headers={"Authorization": f"Bearer {XAI_API_KEY}"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        status = data.get("status", "")
        if status == "done":
            return data
        if status == "failed":
            raise RuntimeError(f"影片生成失敗：{data}")
        if status == "expired":
            raise RuntimeError("影片生成請求已過期")
        # pending — 繼續等
        time.sleep(poll_interval)
    raise TimeoutError(f"影片生成逾時（已等 {poll_timeout} 秒）")


# ═══════════════════════════════════════════════════════════════════
# 圖片工具
# ═══════════════════════════════════════════════════════════════════

def generate_image(
    prompt: str,
    n: int = 1,
    aspect_ratio: str = "auto",
    resolution: str = "1k",
    filename: str | None = None,
) -> dict:
    """
    文字生成圖片。
    回傳：{"files": [本地路徑, ...], "count": N}
    """
    os.makedirs(IMAGE_DIR, exist_ok=True)

    payload = {
        "model": "grok-imagine-image",
        "prompt": prompt,
        "n": min(n, 10),
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "response_format": "url",
    }

    r = requests.post(
        f"{XAI_API_BASE}/images/generations",
        headers=_HEADERS, json=payload, timeout=60,
    )
    r.raise_for_status()
    result = r.json()

    files = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    for i, item in enumerate(result.get("data", [])):
        url = item.get("url")
        if not url:
            continue
        if filename and n == 1:
            fname = filename if "." in filename else f"{filename}.jpg"
        else:
            fname = f"img_{ts}_{i}.jpg"
        dest = os.path.join(IMAGE_DIR, fname)
        _download(url, dest)
        files.append(dest)

    return {"files": files, "count": len(files)}


def edit_image(
    prompt: str,
    image_path: str,
    aspect_ratio: str | None = None,
    filename: str | None = None,
) -> dict:
    """
    編輯圖片（以文字指示修改現有圖片）。
    回傳：{"file": 本地路徑}
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"找不到來源圖片：{image_path}")

    os.makedirs(IMAGE_DIR, exist_ok=True)

    data_uri = _image_to_base64_uri(image_path)

    payload = {
        "model": "grok-imagine-image",
        "prompt": prompt,
        "image": {"url": data_uri, "type": "image_url"},
    }
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio

    r = requests.post(
        f"{XAI_API_BASE}/images/edits",
        headers=_HEADERS, json=payload, timeout=60,
    )
    r.raise_for_status()
    result = r.json()

    url = result["data"][0]["url"]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = filename if filename else f"edit_{ts}.jpg"
    if "." not in fname:
        fname += ".jpg"
    dest = os.path.join(IMAGE_DIR, fname)
    _download(url, dest)

    return {"file": dest}


# ═══════════════════════════════════════════════════════════════════
# 影片工具
# ═══════════════════════════════════════════════════════════════════

def generate_video(
    prompt: str,
    duration: int = 6,
    aspect_ratio: str = "16:9",
    resolution: str = "480p",
    image_path: str | None = None,
    filename: str | None = None,
) -> dict:
    """
    文字（或圖片）生成影片。
    非同步生成，內建輪詢等待完成。
    回傳：{"file": 本地路徑, "duration": 秒數}
    """
    if duration < 1 or duration > 15:
        raise ValueError("影片秒數必須在 1~15 之間")

    os.makedirs(VIDEO_DIR, exist_ok=True)

    payload = {
        "model": "grok-imagine-video",
        "prompt": prompt,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
    }
    if image_path:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"找不到來源圖片：{image_path}")
        payload["image_url"] = _image_to_base64_uri(image_path)

    # Step 1: 發起生成請求
    r = requests.post(
        f"{XAI_API_BASE}/videos/generations",
        headers=_HEADERS, json=payload, timeout=30,
    )
    r.raise_for_status()
    request_id = r.json()["request_id"]

    # Step 2: 輪詢等待完成
    result = _poll_video(request_id)
    video_url = result["video"]["url"]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = filename if filename else f"video_{ts}.mp4"
    if not fname.endswith(".mp4"):
        fname += ".mp4"
    dest = os.path.join(VIDEO_DIR, fname)
    _download(video_url, dest)

    return {
        "file": dest,
        "duration": result["video"].get("duration", duration),
    }


def edit_video(
    prompt: str,
    video_url: str,
    filename: str | None = None,
) -> dict:
    """
    編輯影片（以文字指示修改現有影片）。
    輸入影片最長 8.7 秒。
    回傳：{"file": 本地路徑}
    """
    payload = {
        "model": "grok-imagine-video",
        "prompt": prompt,
        "video": {"url": video_url},
    }

    r = requests.post(
        f"{XAI_API_BASE}/videos/edits",
        headers=_HEADERS, json=payload, timeout=30,
    )
    r.raise_for_status()
    request_id = r.json()["request_id"]

    result = _poll_video(request_id)
    out_url = result["video"]["url"]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = filename if filename else f"edit_video_{ts}.mp4"
    if not fname.endswith(".mp4"):
        fname += ".mp4"
    dest = os.path.join(VIDEO_DIR, fname)
    _download(out_url, dest)

    return {"file": dest}


def extend_video(
    prompt: str,
    video_url: str,
    duration: int = 6,
    filename: str | None = None,
) -> dict:
    """
    延伸影片（從最後一幀繼續生成）。
    延伸秒數 2~10 秒，輸入影片 2~15 秒。
    回傳：{"file": 本地路徑, "duration": 延伸秒數}
    """
    if duration < 2 or duration > 10:
        raise ValueError("延伸秒數必須在 2~10 之間")

    payload = {
        "model": "grok-imagine-video",
        "prompt": prompt,
        "video": {"url": video_url},
        "duration": duration,
    }

    r = requests.post(
        f"{XAI_API_BASE}/videos/extensions",
        headers=_HEADERS, json=payload, timeout=30,
    )
    r.raise_for_status()
    request_id = r.json()["request_id"]

    result = _poll_video(request_id)
    out_url = result["video"]["url"]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = filename if filename else f"extend_video_{ts}.mp4"
    if not fname.endswith(".mp4"):
        fname += ".mp4"
    dest = os.path.join(VIDEO_DIR, fname)
    _download(out_url, dest)

    return {"file": dest, "duration": duration}
