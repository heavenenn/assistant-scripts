"""
tools/scheduler.py
排程工具：延遲執行或定時執行任何 API 工具

用法範例（薇薇）：
  - 5 分鐘後推播：schedule_task(tool="push_message", params={"text":"提醒！"}, delay_seconds=300)
  - 20:36 推播：schedule_task(tool="push_message", params={"text":"時間到！"}, run_at="20:36")
  - 10 分鐘後截圖：schedule_task(tool="screenshot", params={}, delay_seconds=600)
"""

import os
import threading
import time
import uuid
import requests
from datetime import datetime, timedelta

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from secrets import USER_ID

API_BASE = "http://127.0.0.1:5005"

# 追蹤所有排程任務
_scheduled: dict[str, dict] = {}
_lock = threading.Lock()


def schedule_task(
    tool: str,
    params: dict | None = None,
    delay_seconds: int = 0,
    run_at: str = "",
) -> dict:
    """
    排程執行一個工具。

    tool:          要執行的工具名稱（如 push_message, screenshot 等）
    params:        工具的參數 dict
    delay_seconds: 延遲秒數（與 run_at 擇一）
    run_at:        指定執行時間，格式 "HH:MM" 或 "YYYY-MM-DD HH:MM"（與 delay_seconds 擇一）
    """
    params = params or {}
    task_id = uuid.uuid4().hex[:8]

    # 計算等待秒數
    if run_at:
        target = _parse_time(run_at)
        wait = (target - datetime.now()).total_seconds()
        if wait < 0:
            raise ValueError(f"指定時間 {run_at} 已過去")
        scheduled_time = target.strftime("%Y-%m-%d %H:%M:%S")
    elif delay_seconds > 0:
        wait = delay_seconds
        target = datetime.now() + timedelta(seconds=wait)
        scheduled_time = target.strftime("%Y-%m-%d %H:%M:%S")
    else:
        raise ValueError("必須指定 delay_seconds（延遲秒數）或 run_at（執行時間）")

    # 上限 24 小時
    if wait > 86400:
        raise ValueError("排程最長 24 小時")

    with _lock:
        _scheduled[task_id] = {
            "task_id": task_id,
            "tool": tool,
            "params": params,
            "scheduled_time": scheduled_time,
            "status": "waiting",
        }

    # 啟動背景執行緒
    t = threading.Thread(
        target=_run_after_delay,
        args=(task_id, tool, params, wait),
        daemon=True,
    )
    t.start()

    return {
        "task_id": task_id,
        "tool": tool,
        "scheduled_time": scheduled_time,
        "delay_seconds": int(wait),
        "message": f"已排程：{tool} 將於 {scheduled_time} 執行",
    }


def list_scheduled() -> dict:
    """列出所有排程任務（含已完成）。"""
    with _lock:
        return {"tasks": list(_scheduled.values())}


def cancel_scheduled(task_id: str) -> dict:
    """取消一個等待中的排程任務。"""
    with _lock:
        task = _scheduled.get(task_id)
        if not task:
            raise ValueError(f"找不到排程任務：{task_id}")
        if task["status"] != "waiting":
            raise ValueError(f"任務 {task_id} 狀態為 {task['status']}，無法取消")
        task["status"] = "cancelled"
    return {"message": f"已取消排程：{task_id}"}


# ── 內部 ─────────────────────────────────────────────────────────

def _parse_time(time_str: str) -> datetime:
    """解析時間字串，支援 HH:MM 和 YYYY-MM-DD HH:MM"""
    time_str = time_str.strip()
    # 嘗試完整格式
    for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            pass
    # 只有 HH:MM → 今天或明天
    try:
        t = datetime.strptime(time_str, "%H:%M").time()
        target = datetime.combine(datetime.now().date(), t)
        if target < datetime.now():
            target += timedelta(days=1)
        return target
    except ValueError:
        pass
    raise ValueError(f"無法解析時間：{time_str}（請用 HH:MM 或 YYYY-MM-DD HH:MM）")


def _run_after_delay(task_id: str, tool: str, params: dict, wait: float):
    """背景執行：等待後呼叫 API。"""
    # 分段 sleep，方便取消檢查
    elapsed = 0
    while elapsed < wait:
        time.sleep(min(1, wait - elapsed))
        elapsed += 1
        with _lock:
            if _scheduled.get(task_id, {}).get("status") == "cancelled":
                return

    with _lock:
        task = _scheduled.get(task_id)
        if not task or task["status"] == "cancelled":
            return
        task["status"] = "running"

    # 呼叫 API
    try:
        from tool_registry import TOOLS_MAP
        tool_schema = TOOLS_MAP.get(tool)
        if not tool_schema:
            raise ValueError(f"未知工具：{tool}")

        endpoint = tool_schema["endpoint"]
        payload = {"user_id": USER_ID, **params}

        r = requests.post(
            f"{API_BASE}{endpoint}",
            json=payload,
            timeout=120,
        )
        result = r.json()

        with _lock:
            _scheduled[task_id]["status"] = "completed"
            _scheduled[task_id]["result"] = result

    except Exception as e:
        with _lock:
            _scheduled[task_id]["status"] = "failed"
            _scheduled[task_id]["error"] = str(e)
