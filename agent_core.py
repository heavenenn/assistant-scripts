"""
agent_core.py
薇薇任務執行核心

流程：
  1. call_grok_plan()   → 把 TOOLS_SCHEMA + 歷史記憶 丟給 AI，取得步驟 JSON
  2. validate_params()  → 本地驗證每步驟參數，AI hallucination 在此被攔截
  3. call_api()         → 依 schema 的 endpoint 呼叫 assistant_api.py
  4. call_grok_fix()    → 步驟失敗時，把錯誤 + schema + 歷史修正 丟給 AI 修正
                          AI 可回 abort 表示無法修正，避免浪費 token
  5. analyze_screen()   → 截圖 + Grok Vision 分析畫面（需設定 XAI_API_KEY）
  6. memory             → 成功任務 / 錯誤修正 自動存入記憶，越用越聰明

重試機制：
  - 每步驟最多重試 3 次
  - AI 可自行判斷 abort 中斷（避免無限重試浪費 token）
  - 最後一次失敗時截圖分析
  - 所有錯誤統一回報，方便人工排查
"""

import requests
import json
import re
import base64
import sys

# ── Windows 終端機 cp950 不支援 emoji，強制 UTF-8 輸出 ──
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from tool_registry import TOOLS_SCHEMA, TOOLS_MAP, validate_params
from memory import memory
from app_secrets import XAI_API_KEY, USER_ID

API_BASE = "http://127.0.0.1:5005"

# ── xAI API 設定（規劃、除錯、視覺分析共用同一組 Key）──
XAI_API_BASE = "https://api.x.ai/v1"
XAI_MODEL    = "grok-4-1-fast"


# ═══════════════════════════════════════
# 🤖 xAI API 統一呼叫
# ═══════════════════════════════════════

def _call_xai(prompt: str, *, image_path: str | None = None, timeout: int = 60) -> str:
    """
    統一呼叫 xAI chat completions API。
    可選傳入圖片（base64）做 Vision 分析。
    回傳 AI 的文字回覆。
    """
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type":  "application/json",
    }

    if image_path:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {
                "url": f"data:image/png;base64,{b64}",
            }},
        ]
    else:
        content = prompt

    payload = {
        "model": XAI_MODEL,
        "messages": [{"role": "user", "content": content}],
    }

    r = requests.post(
        f"{XAI_API_BASE}/chat/completions",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


# ═══════════════════════════════════════
# 🧠 Grok 任務規劃（只呼叫一次）
# ═══════════════════════════════════════

def call_grok_plan(task: str) -> list[dict]:
    """
    把任務 + 完整 TOOLS_SCHEMA + 歷史記憶 丟給 AI，取得步驟清單。

    AI 被要求輸出：
    [
      {"tool": "工具名稱", "params": {"參數名": "值", ...}},
      ...
    ]
    """
    # 查詢歷史記憶
    similar = memory.find_similar_tasks(task)
    memory_context = ""
    if similar:
        memory_context = "\n以下是類似任務的成功經驗（供參考，可直接套用或調整）：\n"
        for s in similar:
            memory_context += (
                f"- 任務：{s['task']}\n"
                f"  步驟：{json.dumps(s['steps'], ensure_ascii=False)}\n"
            )

    prompt = f"""
你是一個 AI 任務規劃器。

可用工具如下（包含每個工具的描述、參數名稱、型別與說明）：
{json.dumps(TOOLS_SCHEMA, ensure_ascii=False, indent=2)}
{memory_context}
請將以下任務拆解為執行步驟，輸出 JSON 陣列，每個步驟格式：
{{"tool": "工具名稱", "params": {{"參數名": "值"}}}}

規則：
1. 只輸出 JSON 陣列，不要任何說明或 markdown
2. tool 必須完全符合上方工具清單的 name 欄位
3. params 必須包含所有 required=true 的參數
4. 參數名稱必須完全符合 schema 定義，不可自行發明
5. 若步驟需要使用前面步驟的輸出，在參數值中寫 "$步驟編號.欄位名"，
   例如：步驟1 screenshot 的輸出有 file 欄位，步驟2 可寫 "$1.file"

任務：
{task}
"""

    try:
        text = _call_xai(prompt, timeout=30)
        return json.loads(text)
    except json.JSONDecodeError:
        print("[警告] Grok 回傳無法解析為 JSON，嘗試提取 JSON 區段")
        return _extract_json(text)
    except Exception as e:
        print(f"[錯誤] call_grok_plan 失敗：{e}")
        return []


# ═══════════════════════════════════════
# 🔧 呼叫本地 API
# ═══════════════════════════════════════

def call_api(tool_name: str, params: dict) -> dict:
    """
    依 tool_registry 的 endpoint 呼叫 assistant_api.py。
    呼叫前先做本地參數驗證，減少不必要的網路請求。
    """
    tool = TOOLS_MAP.get(tool_name)
    if not tool:
        return {"status": "error", "error": f"未知工具：{tool_name}"}

    # ── 本地驗證（快速攔截 AI hallucination）──
    errors = validate_params(tool_name, params)
    if errors:
        return {"status": "error", "error": " / ".join(errors)}

    # ── 補上選填參數的預設值 ──
    filled_params = {}
    for param_name, meta in tool["params"].items():
        if param_name in params:
            filled_params[param_name] = params[param_name]
        elif not meta["required"] and "default" in meta:
            filled_params[param_name] = meta["default"]

    url     = API_BASE + tool["endpoint"]
    payload = {"user_id": USER_ID, **filled_params}

    # ── 依工具類型動態調整 timeout ──
    _LONG_TIMEOUT_TOOLS = {
        "screen_record", "normalize_mp3",                        # 本地耗時
        "generate_video", "edit_video", "extend_video",          # xAI 非同步輪詢
        "generate_novel",                                         # 多次 AI 呼叫
    }
    timeout = 660 if tool_name in _LONG_TIMEOUT_TOOLS else 120

    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return r.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ═══════════════════════════════════════
# 🔁 錯誤 → 問 AI 修正（支援 abort）
# ═══════════════════════════════════════

def call_grok_fix(step: dict, error_msg: str, *,
                  known_fixes: list[dict] | None = None,
                  prev_results: dict | None = None) -> dict:
    """
    把失敗步驟 + 錯誤訊息 + schema + 歷史修正經驗 丟給 AI，取得修正版步驟。

    AI 可回傳：
      {"tool": "...", "params": {...}}  → 修正後的步驟
      {"abort": true, "reason": "..."}  → 判斷無法修正，中斷重試

    若 AI 回傳的工具名稱不在 schema 內，保留原步驟。
    """
    tool_schema = TOOLS_MAP.get(step.get("tool"), {})

    # 組裝歷史修正經驗
    fix_context = ""
    if known_fixes:
        fix_context = "\n過去類似錯誤的成功修正經驗：\n"
        for f in known_fixes:
            fix_context += (
                f"- 錯誤：{f['error']}\n"
                f"  原始參數：{json.dumps(f['original_params'], ensure_ascii=False)}\n"
                f"  修正參數：{json.dumps(f['fixed_params'], ensure_ascii=False)}\n"
            )

    # 組裝前面步驟的輸出
    result_context = ""
    if prev_results:
        result_context = "\n前面步驟的輸出（可引用）：\n"
        for idx, data in prev_results.items():
            result_context += f"  步驟 {idx}：{json.dumps(data, ensure_ascii=False)}\n"

    prompt = f"""
你是一個 AI 除錯助手。

失敗的步驟：
{json.dumps(step, ensure_ascii=False, indent=2)}

錯誤訊息：
{error_msg}

該工具的完整 Schema（參數規格）：
{json.dumps(tool_schema, ensure_ascii=False, indent=2)}
{fix_context}{result_context}
請根據錯誤訊息與 Schema 修正參數，回傳修正後的單一步驟 JSON：
{{"tool": "工具名稱", "params": {{"參數名": "值"}}}}

⚠️ 如果你判斷此錯誤無法透過修改參數解決（例如：服務未啟動、檔案不存在、權限不足等），
請直接回傳：
{{"abort": true, "reason": "無法修正的原因說明"}}

只輸出 JSON，不要說明。
"""

    try:
        text = _call_xai(prompt, timeout=30)
        fixed = json.loads(text)

        # AI 判斷放棄
        if fixed.get("abort"):
            return fixed

        # 正常修正
        if fixed.get("tool") in TOOLS_MAP:
            return fixed

        print(f"[警告] AI 修正後工具名稱不合法：{fixed.get('tool')}，保留原步驟")
    except Exception as e:
        print(f"[警告] call_grok_fix 失敗：{e}，保留原步驟")

    return step


# ═══════════════════════════════════════
# 👁️ 截圖視覺分析
# ═══════════════════════════════════════

def analyze_screen(error_context: str = "") -> str:
    """
    截圖 + 用 Grok Vision 分析當前畫面。
    若 XAI_API_KEY 未設定，只回傳截圖路徑。
    """
    print("[薇薇] 截圖分析畫面中...")
    result = call_api("screenshot", {})
    file_path = result.get("data", {}).get("file")

    if not file_path:
        return "截圖失敗，無法分析畫面"

    if not XAI_API_KEY:
        return f"畫面已截圖：{file_path}（請設定 XAI_API_KEY 以啟用視覺分析）"

    prompt = (
        "分析這張螢幕截圖。"
        + (f"\n目前遇到的錯誤：{error_context}" if error_context else "")
        + "\n請描述：\n1. 畫面上顯示什麼\n2. 是否有錯誤提示或異常\n3. 建議的下一步操作"
    )

    try:
        analysis = _call_xai(prompt, image_path=file_path)
        return f"畫面截圖：{file_path}\n視覺分析：{analysis}"
    except Exception as e:
        return f"畫面已截圖：{file_path}（視覺分析失敗：{e}）"


# ═══════════════════════════════════════
# 📊 結果讀取輔助
# ═══════════════════════════════════════

def get_result_data(tool_name: str, response: dict) -> dict:
    """
    依據 schema 的 response.data_keys，從 API 回傳中取出有意義的資料。
    方便後續步驟讀取上一步的輸出（例如截圖路徑、STT 文字等）。
    """
    tool = TOOLS_MAP.get(tool_name)
    if not tool:
        return {}

    data = response.get("data", {})
    if not isinstance(data, dict):
        return {"raw": data}

    keys = tool.get("response", {}).get("data_keys", {})
    return {k: data[k] for k in keys if k in data}


# ═══════════════════════════════════════
# 🚀 主執行流程
# ═══════════════════════════════════════

def _resolve_refs(params: dict, results: dict) -> dict:
    """
    解析參數中的步驟引用。
    "$1.file" → 取步驟 1 的 file 欄位值。
    """
    resolved = {}
    for k, v in params.items():
        if isinstance(v, str):
            match = re.match(r"^\$(\d+)\.(\w+)$", v)
            if match:
                step_idx = int(match.group(1))
                field    = match.group(2)
                if step_idx in results and field in results[step_idx]:
                    resolved[k] = results[step_idx][field]
                    continue
                else:
                    print(f"  ⚠️ 無法解析引用 {v}（步驟 {step_idx} 欄位 {field} 不存在）")
        resolved[k] = v
    return resolved


def _run_steps(task: str, steps: list[dict], max_retry: int = 3) -> dict:
    """
    內部步驟執行引擎（run_task 和 execute_steps 共用）。
    負責：逐步執行、重試、錯誤修正、記憶存取。
    """
    results      = {}
    failed_steps = []

    for step_idx, step in enumerate(steps, 1):
        tool_name = step.get("tool", "")
        print(f"\n[步驟 {step_idx}] {tool_name}")

        step_success    = False
        last_error      = ""
        original_params = step.get("params", {}).copy()

        for attempt in range(1, max_retry + 1):
            params = _resolve_refs(step.get("params", {}), results)
            result = call_api(tool_name, params)

            if result.get("status") == "success":
                data = get_result_data(tool_name, result)
                results[step_idx] = data
                print(f"  ✅ 成功 → {data}")
                step_success = True

                if attempt > 1:
                    memory.save_error_fix(
                        tool_name, last_error,
                        original_params, step.get("params", {}),
                    )
                    print(f"  💾 錯誤修正已存入記憶")
                break

            else:
                last_error = result.get("error", "未知錯誤")
                hint       = result.get("hint", "")
                print(f"  ❌ 第 {attempt}/{max_retry} 次失敗：{last_error}"
                      + (f"（建議：{hint}）" if hint else ""))

                if attempt < max_retry:
                    known_fixes = memory.find_error_fixes(tool_name, last_error)
                    if known_fixes:
                        print(f"  📚 找到 {len(known_fixes)} 筆歷史修正經驗")

                    print("  🔄 請 AI 修正中...")
                    fixed = call_grok_fix(
                        step, last_error,
                        known_fixes=known_fixes,
                        prev_results=results,
                    )

                    if fixed.get("abort"):
                        reason = fixed.get("reason", "AI 判斷無法修正")
                        print(f"  🚫 AI 主動中斷：{reason}")
                        failed_steps.append({
                            "step": step_idx, "tool": tool_name,
                            "error": last_error, "abort_reason": reason,
                        })
                        break

                    step = fixed
                else:
                    screen_info = analyze_screen(last_error)
                    print(f"  📸 {screen_info}")
                    failed_steps.append({
                        "step": step_idx, "tool": tool_name,
                        "error": last_error, "screen_analysis": screen_info,
                    })

        if not step_success and not any(f["step"] == step_idx for f in failed_steps):
            failed_steps.append({
                "step": step_idx, "tool": tool_name,
                "error": last_error or "未知錯誤",
            })

    # ── 任務報告 ──
    print(f"\n{'='*50}")
    if not failed_steps:
        print("[任務報告] 所有步驟完成 ✅")
        memory.save_task(task, steps, results)
        print("[💾 記憶] 任務已存入記憶，下次類似任務可直接參考")
        return {"success": True, "results": results}
    else:
        print("[任務報告] 以下步驟失敗：")
        for f in failed_steps:
            reason = f.get("abort_reason", "")
            screen = f.get("screen_analysis", "")
            print(f"  步驟 {f['step']} ({f['tool']})：{f['error']}")
            if reason:
                print(f"    AI 判斷：{reason}")
            if screen:
                print(f"    畫面分析：{screen[:200]}")
        print("\n請根據以上資訊協助薇薇排查問題。")
        return {"success": False, "results": results, "failed": failed_steps}


def execute_steps(steps: list[dict], task: str = "",
                  max_retry: int = 3) -> dict:
    """
    👉 薇薇的主要入口：直接傳入已規劃好的步驟清單。

    薇薇自己規劃步驟後，呼叫此函數執行。
    不需要再呼叫 AI 做規劃（省 token、免繞路）。

    參數：
      steps     步驟清單，格式：
                [{"tool": "工具名", "params": {"參數": "值"}}, ...]
      task      任務描述（選填，用於記憶標記）
      max_retry 每步驟最多重試次數（預設 3）

    步驟串接：
      若後續步驟需引用前面步驟的輸出，在參數值中寫 "$步驟編號.欄位名"
      例如：步驟 1 screenshot 回傳 file，步驟 2 寫 "$1.file"

    回傳：
      {"success": True/False, "results": {...}, "failed": [...]}

    範例：
      execute_steps([
          {"tool": "screenshot", "params": {}},
          {"tool": "send_mail", "params": {
              "to": "test@gmail.com",
              "subject": "截圖",
              "content": "請查看附件",
              "attachment": "$1.file"
          }}
      ], task="截圖並寄信")
    """
    print(f"\n{'='*50}")
    print(f"[任務] {task or '（薇薇直接執行）'}")
    print(f"[計畫] 共 {len(steps)} 個步驟")
    for i, s in enumerate(steps, 1):
        print(f"  步驟 {i}：{s['tool']} → {s.get('params', {})}")
    print(f"{'='*50}")

    return _run_steps(task or "薇薇直接執行", steps, max_retry)


def run_task(task: str, max_retry: int = 3) -> dict:
    """
    傳入自然語言任務，由 AI 自動規劃步驟後執行。
    （用於獨立測試，或非 OpenClaw 環境使用）

    回傳：
      {"success": bool, "results": dict, "failed": list}
    """
    print(f"\n{'='*50}")
    print(f"[任務] {task}")
    print(f"{'='*50}")

    steps = call_grok_plan(task)
    if not steps:
        print("[錯誤] 無法解析任務或取得步驟")
        return {"success": False, "error": "無法解析任務或取得步驟"}

    print(f"\n[計畫] 共 {len(steps)} 個步驟")
    for i, s in enumerate(steps, 1):
        print(f"  步驟 {i}：{s['tool']} → {s.get('params', {})}")

    return _run_steps(task, steps, max_retry)


# ═══════════════════════════════════════
# 🔧 內部輔助
# ═══════════════════════════════════════

def _extract_json(text: str):
    """嘗試從含有多餘文字的 AI 回覆中提取 JSON。"""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return []


# ═══════════════════════════════════════
# 🧪 互動測試
# ═══════════════════════════════════════

if __name__ == "__main__":
    print("薇薇 Agent Core 啟動（輸入 exit 離開）")
    while True:
        user_input = input("\n請輸入任務：").strip()
        if user_input.lower() in ("exit", "quit", "q"):
            break
        if user_input:
            run_task(user_input)
