"""
tools/system.py
系統工具：執行指令、查詢狀態等
"""

import os
import subprocess
import sys
import tempfile


def run_command(command: list[str] | str, timeout: int = 30,
                elevated: bool = False) -> dict:
    """
    執行系統指令。
    command：list（推薦）或 shell string。
    elevated：True 時以管理員權限執行（透過排程任務提權，無 UAC 彈窗）。
    回傳：{"stdout": ..., "stderr": ..., "returncode": ...}
    """
    if elevated:
        return _run_elevated(command, timeout)

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


# ── 提權執行 ─────────────────────────────────────────────────────

_ELEVATED_TASK = "WeiWeiElevatedCmd"
_ELEVATED_DIR  = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".elevated"
)  # → tools/.elevated/


def _run_elevated(command: list[str] | str, timeout: int = 30) -> dict:
    """
    透過預先建立的 Task Scheduler 排程以最高權限執行指令。
    前提：需先以管理員身份執行 install_vivy_task.ps1 建立 WeiWeiElevatedCmd 排程。
    """
    if isinstance(command, list):
        cmd_str = " ".join(command)
    else:
        cmd_str = command

    # 使用固定路徑（避免 TEMP 在不同 session 不同）
    os.makedirs(_ELEVATED_DIR, exist_ok=True)
    cmd_file = os.path.join(_ELEVATED_DIR, "cmd.ps1")
    out_file = os.path.join(_ELEVATED_DIR, "out.txt")
    err_file = os.path.join(_ELEVATED_DIR, "err.txt")
    rc_file  = os.path.join(_ELEVATED_DIR, "rc.txt")

    for f in (out_file, err_file, rc_file):
        if os.path.exists(f):
            os.remove(f)

    # 寫入要執行的指令
    with open(cmd_file, "w", encoding="utf-8") as f:
        f.write(cmd_str + "\n")

    # 觸發預先建立的提權排程
    result = subprocess.run(
        f'schtasks /Run /TN "{_ELEVATED_TASK}"',
        shell=True, capture_output=True,
        encoding="utf-8", errors="replace", timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"無法觸發提權排程（請先以管理員執行 install_vivy_task.ps1）：\n"
            f"{result.stderr or result.stdout}"
        )

    # 等待完成（輪詢 rc_file 出現）
    import time
    elapsed = 0
    while elapsed < timeout:
        if os.path.exists(rc_file):
            time.sleep(0.3)
            break
        time.sleep(0.5)
        elapsed += 0.5

    # 讀取結果
    stdout = _read_temp(out_file)
    stderr = _read_temp(err_file)
    try:
        returncode = int(_read_temp(rc_file).strip() or "1")
    except (ValueError, FileNotFoundError):
        returncode = 1
        stderr = stderr or f"提權指令逾時（{timeout}s）"

    if returncode != 0:
        raise RuntimeError(
            f"提權指令執行失敗（returncode={returncode}）：\n"
            f"{stderr or stdout}"
        )

    return {
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
        "returncode": returncode,
    }


def _read_temp(path: str) -> str:
    """安全讀取臨時檔案（自動處理 BOM）。"""
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()
