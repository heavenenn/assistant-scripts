"""
tools/system.py
系統工具：執行指令、查詢狀態等
"""

import os
import subprocess
import sys


def run_command(command: list[str] | str, timeout: int = 30) -> dict:
    """
    執行系統指令。
    command：list（推薦）或 shell string。
    回傳：{"stdout": ..., "stderr": ..., "returncode": ...}
    """
    use_shell = isinstance(command, str)

    result = subprocess.run(
        command,
        shell=use_shell,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"指令執行失敗（returncode={result.returncode}）：\n"
            f"{result.stderr or result.stdout}"
        )

    return {
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "returncode": result.returncode,
    }


def get_env_info() -> dict:
    """回傳基本環境資訊（Python 版本、OS、工作目錄）。"""
    return {
        "python": sys.version,
        "platform": sys.platform,
        "cwd": os.getcwd(),
    }
