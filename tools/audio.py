"""
tools/audio.py
音訊工具：MP3 音量正規化（透過 normalize_mp3_quote.ps1）

PS1 輸出格式約定（assistant_api.py 依此解析）：
  START: N file(s) to process
  OK:   filename.mp3
  FAIL: filename.mp3 | <錯誤訊息>
  WARNING: ...
  ERROR: ...
  DONE: success=N fail=N outputFolder=<路徑>
"""

import os
import subprocess

# PS1 腳本的絕對路徑，可依實際部署位置修改
PS1_PATH = r"C:\Users\heave\.openclaw\assistant-scripts\tools\normalize_mp3_quote.ps1"


def _find_ps1() -> str:
    """優先用環境變數 VIVI_PS1_PATH，找不到再用預設值。"""
    path = os.environ.get("VIVI_PS1_PATH", PS1_PATH)
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到 PS1 腳本：{path}")
    return path


def _parse_output(stdout: str) -> dict:
    """
    解析 PS1 的結構化輸出，回傳：
    {
        "success": [...],
        "failed":  [{"file": ..., "reason": ...}],
        "total":   N,
        "output_folder": "...",
        "warnings": [...],
    }
    """
    result = {
        "success": [],
        "failed": [],
        "total": 0,
        "output_folder": "",
        "warnings": [],
    }

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("OK:"):
            result["success"].append(line[3:].strip())

        elif line.startswith("FAIL:"):
            body = line[5:].strip()
            if "|" in body:
                fname, reason = body.split("|", 1)
                result["failed"].append({
                    "file": fname.strip(),
                    "reason": reason.strip(),
                })
            else:
                result["failed"].append({"file": body, "reason": "未知錯誤"})

        elif line.startswith("START:"):
            try:
                result["total"] = int(line.split()[1])
            except (IndexError, ValueError):
                pass

        elif line.startswith("DONE:"):
            # DONE: success=N fail=N outputFolder=<路徑>
            for token in line[5:].split():
                if token.startswith("outputFolder="):
                    result["output_folder"] = token[len("outputFolder="):]

        elif line.startswith("WARNING:"):
            result["warnings"].append(line[8:].strip())

        elif line.startswith("ERROR:"):
            # 腳本層級錯誤，直接拋出讓 run_with_retry 接管
            raise RuntimeError(line[6:].strip())

    return result


def normalize_mp3(
    input_folder: str,
    output_folder: str | None = None,
    loudnorm: str = "I=-16:TP=-1.5:LRA=11",
) -> dict:
    """
    對 input_folder 內所有 MP3 進行音量正規化。

    參數：
      input_folder   來源資料夾（必填）
      output_folder  輸出資料夾（選填，預設 input_folder/normalized）
      loudnorm       ffmpeg loudnorm 參數字串

    回傳（統一格式 data 層）：
      {
        "success": ["a.mp3", ...],
        "failed":  [{"file": "b.mp3", "reason": "..."}],
        "total":   N,
        "output_folder": "...",
        "warnings": [...],
      }

    例外：
      FileNotFoundError  — 找不到 PS1 / 輸入資料夾
      RuntimeError       — ffmpeg / 腳本層級錯誤
    """
    if not os.path.isdir(input_folder):
        raise FileNotFoundError(f"輸入資料夾不存在：{input_folder}")

    ps1 = _find_ps1()

    args = [
        "powershell", "-ExecutionPolicy", "Bypass",
        "-File", ps1,
        "-inputFolder", input_folder,
        "-loudnorm", loudnorm,
    ]
    if output_folder:
        args += ["-outputFolder", output_folder]

    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    # PowerShell 的 exit code 不為 0 時才算腳本層級錯誤
    # （ffmpeg 個別失敗已在 PS1 裡轉成 FAIL: 行，不影響 exit code）
    if proc.returncode != 0:
        # 優先從 stdout 找 ERROR: 行；找不到就用 stderr
        for line in proc.stdout.splitlines():
            if line.strip().startswith("ERROR:"):
                raise RuntimeError(line.strip()[6:].strip())
        stderr_msg = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(
            f"PowerShell 異常退出（code={proc.returncode}）：{stderr_msg[:300]}"
        )

    parsed = _parse_output(proc.stdout)

    # 有任何個別失敗時，仍算 success（部分成功），
    # 但把 failed 清單帶回讓薇薇知道需要處理
    return parsed
