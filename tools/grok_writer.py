"""
tools/grok_writer.py
AI 長文 / 小說生成工具（xAI Chat Completions API）

策略：
  - generate_text:  單次呼叫生成文字，適合短文、部落格、腳本
  - generate_novel: 分章節生成長篇小說
    1. 先讓 AI 生成大綱（章節標題 + 摘要）
    2. 逐章呼叫 AI 生成正文（帶上大綱 + 前一章結尾做銜接）
    3. 合併成一個 Markdown 檔

結果自動存到 薇薇\\Writings\\ 目錄。
"""

import os
import json
import re
import requests
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from secrets import XAI_API_KEY

# ── 設定 ─────────────────────────────────────────────────────────

XAI_API_BASE = "https://api.x.ai/v1"
XAI_MODEL    = "grok-4-0709"

WRITING_DIR = r"C:\Users\heave\OneDrive\文件\薇薇\Writings"

_HEADERS = {
    "Authorization": f"Bearer {XAI_API_KEY}",
    "Content-Type":  "application/json",
}


# ── 內部工具 ─────────────────────────────────────────────────────

def _chat(system_prompt: str, user_prompt: str, timeout: int = 120) -> str:
    """呼叫 xAI chat completions，回傳文字回覆。"""
    payload = {
        "model": XAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    }
    r = requests.post(
        f"{XAI_API_BASE}/chat/completions",
        headers=_HEADERS, json=payload, timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _extract_json(text: str) -> list | dict | None:
    """從 AI 回覆中提取 JSON。"""
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", text)
    if m:
        return json.loads(m.group(1))
    return None


# ═══════════════════════════════════════════════════════════════════
# 通用文字生成
# ═══════════════════════════════════════════════════════════════════

def generate_text(
    prompt: str,
    system_prompt: str = "你是一位專業的繁體中文寫作助手。",
    filename: str | None = None,
) -> dict:
    """
    通用文字生成（部落格、腳本、報告等）。
    回傳：{"file": 本地路徑, "length": 字數, "preview": 前 200 字}
    """
    os.makedirs(WRITING_DIR, exist_ok=True)

    content = _chat(system_prompt, prompt, timeout=120)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = filename if filename else f"text_{ts}.md"
    if not fname.endswith(".md"):
        fname += ".md"
    dest = os.path.join(WRITING_DIR, fname)

    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "file": dest,
        "length": len(content),
        "preview": content[:200],
    }


# ═══════════════════════════════════════════════════════════════════
# 小說生成（分章節）
# ═══════════════════════════════════════════════════════════════════

def generate_novel(
    prompt: str,
    chapters: int = 5,
    style: str = "繁體中文，文筆細膩，對話生動",
    filename: str | None = None,
) -> dict:
    """
    分章節生成長篇小說。

    流程：
      1. AI 產出章節大綱 JSON
      2. 逐章生成正文（每章約 2000~4000 字）
      3. 合併成 Markdown

    回傳：{"file": 本地路徑, "chapters": 實際章數, "total_length": 總字數}
    """
    if chapters < 1 or chapters > 30:
        raise ValueError("章節數必須在 1~30 之間")

    os.makedirs(WRITING_DIR, exist_ok=True)

    # ── Step 1: 產生大綱 ──
    outline_prompt = (
        f"請為以下小說構想產出 {chapters} 個章節的大綱。\n"
        f"小說構想：{prompt}\n\n"
        f"請用 JSON 格式回覆，格式如下：\n"
        f'[{{"chapter": 1, "title": "章節標題", "summary": "章節摘要（2~3句）"}}]\n'
        f"只回覆 JSON，不要其他文字。"
    )
    outline_text = _chat(
        system_prompt=f"你是一位專業小說家。風格：{style}",
        user_prompt=outline_prompt,
        timeout=60,
    )
    outline = _extract_json(outline_text)
    if not outline or not isinstance(outline, list):
        raise RuntimeError(f"大綱生成失敗，AI 回覆無法解析為 JSON：{outline_text[:300]}")

    # ── Step 2: 逐章生成 ──
    full_text = f"# {prompt}\n\n"
    prev_ending = ""

    for i, ch in enumerate(outline):
        ch_num   = ch.get("chapter", i + 1)
        ch_title = ch.get("title", f"第 {ch_num} 章")
        ch_summary = ch.get("summary", "")

        chapter_prompt = (
            f"你正在寫一部小說，以下是完整大綱：\n"
            f"{json.dumps(outline, ensure_ascii=False, indent=2)}\n\n"
            f"現在請寫第 {ch_num} 章：{ch_title}\n"
            f"本章摘要：{ch_summary}\n"
        )
        if prev_ending:
            chapter_prompt += f"\n前一章結尾：\n{prev_ending}\n\n請自然銜接。"
        chapter_prompt += (
            f"\n\n要求：\n"
            f"- 約 2000~4000 字\n"
            f"- 風格：{style}\n"
            f"- 直接寫正文，不要重複章節標題或摘要\n"
        )

        chapter_text = _chat(
            system_prompt=f"你是一位專業小說家。風格：{style}",
            user_prompt=chapter_prompt,
            timeout=180,
        )

        full_text += f"## 第 {ch_num} 章　{ch_title}\n\n"
        full_text += chapter_text.strip() + "\n\n"

        # 保留最後 300 字做銜接
        prev_ending = chapter_text.strip()[-300:]

    # ── Step 3: 存檔 ──
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = filename if filename else f"novel_{ts}.md"
    if not fname.endswith(".md"):
        fname += ".md"
    dest = os.path.join(WRITING_DIR, fname)

    with open(dest, "w", encoding="utf-8") as f:
        f.write(full_text)

    return {
        "file": dest,
        "chapters": len(outline),
        "total_length": len(full_text),
    }
