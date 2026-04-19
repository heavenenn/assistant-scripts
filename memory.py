"""
memory.py
薇薇記憶系統

功能：
  1. 任務記憶 — 記住成功完成的任務與步驟，規劃時參考歷史經驗
  2. 錯誤記憶 — 記住錯誤的修正方式，遇到類似錯誤直接套用
  3. 自動淘汰 — 超過上限時刪除最舊的記錄

儲存位置：
  {script_dir}/memory/
    task_memory.json    ← 成功任務記錄
    error_patterns.json ← 錯誤修正記錄
"""

import json
import os
from datetime import datetime

MEMORY_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
TASK_FILE    = os.path.join(MEMORY_DIR, "task_memory.json")
ERROR_FILE   = os.path.join(MEMORY_DIR, "error_patterns.json")
MAX_ENTRIES  = 200


class Memory:
    """薇薇的長期記憶管理器。"""

    def __init__(self):
        os.makedirs(MEMORY_DIR, exist_ok=True)
        self._tasks:  list[dict] = self._load(TASK_FILE)
        self._errors: list[dict] = self._load(ERROR_FILE)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """
        將文字拆成 token 集合。
        英文：用空格分詞。
        中文：每個字元獨立（中文字各有語意）。
        """
        tokens = set(text.lower().split())
        for ch in text:
            if "\u4e00" <= ch <= "\u9fff":
                tokens.add(ch)
        return tokens

    # ── 讀寫 ─────────────────────────────────────────────────────

    @staticmethod
    def _load(path: str) -> list[dict]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return []
        return []

    @staticmethod
    def _save(path: str, data: list[dict]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _trim(self, data: list[dict]) -> list[dict]:
        """超過上限時淘汰最舊的記錄。"""
        if len(data) > MAX_ENTRIES:
            return data[-MAX_ENTRIES:]
        return data

    # ── 任務記憶 ─────────────────────────────────────────────────

    def save_task(self, task: str, steps: list[dict], results: dict) -> None:
        """任務成功完成後，記錄任務摘要、步驟與結果。"""
        entry = {
            "task": task,
            "steps": steps,
            "results": {str(k): v for k, v in results.items()},
            "timestamp": datetime.now().isoformat(),
        }
        self._tasks.append(entry)
        self._tasks = self._trim(self._tasks)
        self._save(TASK_FILE, self._tasks)

    def find_similar_tasks(self, task: str, limit: int = 3) -> list[dict]:
        """
        用關鍵字交集比對最相似的歷史任務。
        回傳最多 limit 筆，依相似度由高到低排序。
        """
        task_tokens = self._tokenize(task)
        scored = []
        for entry in self._tasks:
            entry_tokens = self._tokenize(entry["task"])
            overlap = len(task_tokens & entry_tokens)
            if overlap > 0:
                scored.append((overlap, entry))
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:limit]]

    # ── 錯誤修正記憶 ─────────────────────────────────────────────

    def save_error_fix(self, tool: str, error_msg: str,
                       original_params: dict, fixed_params: dict) -> None:
        """修正成功的錯誤，記錄工具名、錯誤訊息、原始與修正後的參數。"""
        entry = {
            "tool": tool,
            "error": error_msg,
            "original_params": original_params,
            "fixed_params": fixed_params,
            "timestamp": datetime.now().isoformat(),
        }
        self._errors.append(entry)
        self._errors = self._trim(self._errors)
        self._save(ERROR_FILE, self._errors)

    def find_error_fixes(self, tool: str, error_msg: str,
                         limit: int = 3) -> list[dict]:
        """
        查詢相同工具的歷史錯誤修正記錄。
        用錯誤訊息的關鍵字比對，回傳最多 limit 筆。
        """
        error_tokens = self._tokenize(error_msg)
        results = []
        for entry in self._errors:
            if entry["tool"] != tool:
                continue
            entry_tokens = self._tokenize(entry["error"])
            if error_tokens & entry_tokens:
                results.append(entry)
        return results[-limit:]


# ── 模組級單例 ────────────────────────────────────────────────────
memory = Memory()
