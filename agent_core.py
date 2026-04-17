"""
agent_core.py
薇薇任務執行核心

流程：
  1. call_grok_plan()   → 把 TOOLS_SCHEMA 丟給 AI，取得步驟 JSON
  2. validate_params()  → 本地驗證每步驟參數，AI hallucination 在此被攔截
  3. call_api()         → 依 schema 的 endpoint 呼叫 assistant_api.py
  4. call_grok_fix()    → 步驟失敗時，把錯誤 + schema 再丟給 AI 修正
  5. analyze_screen()   → 多次重試仍失敗時截圖讓 AI 判斷
"""

import requests
import json

from tool_registry import TOOLS_SCHEMA, TOOLS_MAP, validate_params

API_BASE = "http://127.0.0.1:5005"
USER_ID  = "8261240503"
GROK_API = "YOUR_GROK_API"   # 👉 換成你的 Grok endpoint


# ═══════════════════════════════════════
# 🧠 Grok 任務規劃（只呼叫一次）
# ═══════════════════════════════════════

def call_grok_plan(task: str) -> list[dict]:
    """
    把任務 + 完整 TOOLS_SCHEMA 丟給 AI，取得步驟清單。

    AI 被要求輸出：
    [
      {"tool": "工具名稱", "params": {"參數名": "值", ...}},
      ...
    ]
    """
    prompt = f"""
你是一個 AI 任務規劃器。

可用工具如下（包含每個工具的描述、參數名稱、型別與說明）：
{json.dumps(TOOLS_SCHEMA, ensure_ascii=False, indent=2)}

請將以下任務拆解為執行步驟，輸出 JSON 陣列，每個步驟格式：
{{"tool": "工具名稱", "params": {{"參數名": "值"}}}}

規則：
1. 只輸出 JSON 陣列，不要任何說明或 markdown
2. tool 必須完全符合上方工具清單的 name 欄位
3. params 必須包含所有 required=true 的參數
4. 參數名稱必須完全符合 schema 定義，不可自行發明

任務：
{task}
"""

    try:
        response = requests.post(GROK_API, json={"prompt": prompt}, timeout=30)
        response.raise_for_status()
        return json.loads(response.text)
    except json.JSONDecodeError:
        print("[警告] Grok 回傳無法解析為 JSON，嘗試提取 JSON 區段")
        return _extract_json(response.text)
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

    try:
        r = requests.post(url, json=payload, timeout=30)
        return r.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ═══════════════════════════════════════
# 🔁 錯誤 → 問 AI 修正
# ═══════════════════════════════════════

def call_grok_fix(step: dict, error_msg: str) -> dict:
    """
    把失敗步驟 + 錯誤訊息 + 對應工具 schema 丟給 AI，取得修正版步驟。
    若 AI 回傳的工具名稱不在 schema 內，保留原步驟。
    """
    tool_schema = TOOLS_MAP.get(step.get("tool"), {})

    prompt = f"""
你是一個 AI 除錯助手。

失敗的步驟：
{json.dumps(step, ensure_ascii=False, indent=2)}

錯誤訊息：
{error_msg}

該工具的完整 Schema（參數規格）：
{json.dumps(tool_schema, ensure_ascii=False, indent=2)}

請根據錯誤訊息與 Schema 修正參數，回傳修正後的單一步驟 JSON：
{{"tool": "工具名稱", "params": {{"參數名": "值"}}}}

只輸出 JSON，不要說明。
"""

    try:
        response = requests.post(GROK_API, json={"prompt": prompt}, timeout=30)
        response.raise_for_status()
        fixed = json.loads(response.text)
        if fixed.get("tool") in TOOLS_MAP:
            return fixed
        print(f"[警告] AI 修正後工具名稱不合法：{fixed.get('tool')}，保留原步驟")
    except Exception as e:
        print(f"[警告] call_grok_fix 失敗：{e}，保留原步驟")

    return step


# ═══════════════════════════════════════
# 👁️ UI 判斷（多次重試後的最後手段）
# ═══════════════════════════════════════

def analyze_screen() -> str:
    print("[薇薇] 分析畫面中...")
    result = call_api("screenshot", {})
    screenshot_path = result.get("data", {}).get("file", "（截圖失敗）")
    # 👉 這裡可以接 Grok Vision / GPT Vision，傳入 screenshot_path 分析
    return f"畫面已截圖：{screenshot_path}（視覺分析尚未串接）"


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

def run_task(task: str, max_retry: int = 2) -> None:
    print(f"\n[任務] {task}")

    steps = call_grok_plan(task)

    if not steps:
        print("[錯誤] 無法解析任務或取得步驟")
        return

    print(f"[計畫] 共 {len(steps)} 個步驟")
    for i, s in enumerate(steps, 1):
        print(f"  步驟 {i}：{s['tool']} → {s.get('params', {})}")

    results = {}  # 儲存每步驟的輸出（供後續步驟參考）

    for step_idx, step in enumerate(steps, 1):
        tool_name = step.get("tool", "")
        print(f"\n[步驟 {step_idx}] {tool_name}")

        for attempt in range(1, max_retry + 1):
            result = call_api(tool_name, step.get("params", {}))

            if result.get("status") == "success":
                data = get_result_data(tool_name, result)
                results[step_idx] = data
                print(f"  ✅ 成功 → {data}")
                break

            else:
                error = result.get("error", "未知錯誤")
                hint  = result.get("hint", "")
                print(f"  ❌ 第 {attempt}/{max_retry} 次失敗：{error}"
                      + (f"（建議：{hint}）" if hint else ""))

                if attempt < max_retry:
                    # 第一次失敗：問 AI 修正參數
                    print("  🔄 請 AI 修正中...")
                    step = call_grok_fix(step, error)

                else:
                    # 最後一次失敗：截圖讓 AI 判斷
                    screen_info = analyze_screen()
                    print(f"  📸 {screen_info}")
                    print(f"  🛑 步驟 {step_idx} 失敗，繼續下一步驟")


# ═══════════════════════════════════════
# 🔧 內部輔助
# ═══════════════════════════════════════

def _extract_json(text: str):
    """嘗試從含有多餘文字的 AI 回覆中提取 JSON。"""
    import re
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
