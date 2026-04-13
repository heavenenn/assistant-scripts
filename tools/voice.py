"""
tools/voice.py
語音工具：TTS 輸出、語音轉文字
"""

import asyncio
import os
import re
import shutil
import subprocess
import speech_recognition as sr

import edge_tts

VOICE      = "zh-TW-HsiaoChenNeural"
TEMP_DIR   = r"C:\Users\heave\OneDrive\文件\薇薇\Temp"
MP3_FILE   = os.path.join(TEMP_DIR, "response.mp3")
OGG_FILE   = os.path.join(TEMP_DIR, "response.ogg")
OUTPUT_OGG = r"C:\Users\heave\.openclaw\workspace\vivi_voice.ogg"


# ── TTS ──────────────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    return re.sub(r"[^一-鿿\w\s\.\,\!\?]", "", text)


async def _tts_async(text: str) -> str:
    text = _clean_text(text)
    if not text.strip():
        text = "收到，請說。"

    os.makedirs(TEMP_DIR, exist_ok=True)

    communicate = edge_tts.Communicate(text, VOICE, rate="+10%", pitch="+5Hz")
    await communicate.save(MP3_FILE)

    result = subprocess.run(
        ["ffmpeg", "-i", MP3_FILE,
         "-c:a", "libopus", "-b:a", "64k",
         "-vbr", "on", "-ar", "48000",
         OGG_FILE, "-y"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 轉換失敗：\n{result.stderr}")

    os.remove(MP3_FILE)
    os.makedirs(os.path.dirname(OUTPUT_OGG), exist_ok=True)
    shutil.copy(OGG_FILE, OUTPUT_OGG)

    return OGG_FILE


def text_to_voice(text: str) -> dict:
    """
    文字轉語音，產生 OGG 檔案。
    回傳：{"ogg_file": ..., "output_copy": ...}
    """
    ogg_path = asyncio.run(_tts_async(text))
    return {
        "ogg_file": ogg_path,
        "output_copy": OUTPUT_OGG,
    }


# ── STT ──────────────────────────────────────────────────────────────────────

def _ogg_to_wav(input_path: str, output_path: str) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_path,
         "-ar", "16000", "-ac", "1", output_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def voice_to_text(ogg_file: str) -> dict:
    """
    OGG 語音轉文字（Google Web Speech API）。
    回傳：{"text": ...}
    """
    if not os.path.exists(ogg_file):
        raise FileNotFoundError(f"語音檔不存在：{ogg_file}")

    wav_file = ogg_file.replace(".ogg", ".wav")
    try:
        _ogg_to_wav(ogg_file, wav_file)

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_file) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="zh-TW")

        return {"text": text}

    except sr.UnknownValueError:
        raise ValueError("無法辨識語音內容")
    except sr.RequestError as e:
        raise RuntimeError(f"無法連線至 Google 服務：{e}")
    finally:
        if os.path.exists(wav_file):
            os.remove(wav_file)
