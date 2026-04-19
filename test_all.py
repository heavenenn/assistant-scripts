"""快速驗證所有模組的測試腳本。"""

import sys
print(f"Python {sys.version}\n")

passed = 0
failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ✅ {msg}")


def fail(msg):
    global failed
    failed += 1
    print(f"  ❌ {msg}")


# ── 1. tool_registry ─────────────────────────────────────────────
print("[tool_registry]")

from tool_registry import TOOLS_SCHEMA, TOOLS_MAP, validate_params

ok(f"載入成功：{len(TOOLS_SCHEMA)} 個工具")
names = [t["name"] for t in TOOLS_SCHEMA]
print(f"     {names}")

# 正常通過
errs = validate_params("send_mail", {"to": "a@b.com", "subject": "hi", "content": "yo"})
ok("正常參數通過") if not errs else fail(f"應通過: {errs}")

# 缺必填
errs = validate_params("send_mail", {"to": "a@b.com"})
ok(f"缺必填攔截（{len(errs)} 個錯誤）") if len(errs) == 2 else fail(f"應有2個: {errs}")

# int 型別錯誤
errs = validate_params("click", {"x": "abc", "y": 100})
ok("int 型別錯誤攔截") if any("型別錯誤" in e for e in errs) else fail(f"{errs}")

# float 型別
errs = validate_params("type_text", {"text": "hi", "interval": "bad"})
ok("float 字串攔截") if any("型別錯誤" in e for e in errs) else fail(f"{errs}")

errs = validate_params("type_text", {"text": "hi", "interval": 0.05})
ok("float 正確值通過") if not errs else fail(f"{errs}")

errs = validate_params("type_text", {"text": "hi", "interval": 1})
ok("float 允許 int") if not errs else fail(f"{errs}")

# 未知工具
errs = validate_params("fake_tool", {})
ok("未知工具攔截") if errs else fail("應攔截未知工具")

# 每個 tool 都有 example
for t in TOOLS_SCHEMA:
    if "example" not in t:
        fail(f"{t['name']} 缺少 example")
        break
else:
    ok("所有工具都有 example")

# 每個 tool 都有 response
for t in TOOLS_SCHEMA:
    if "response" not in t:
        fail(f"{t['name']} 缺少 response")
        break
else:
    ok("所有工具都有 response")


# ── 2. memory ─────────────────────────────────────────────────────
print("\n[memory]")

from memory import memory

ok("載入成功")

memory.save_task(
    "寄一封測試信",
    [{"tool": "send_mail", "params": {"to": "a@b.com", "subject": "hi", "content": "yo"}}],
    {1: {"message": "ok"}},
)
ok("save_task 成功")

similar = memory.find_similar_tasks("寄信給同事")
ok(f"find_similar_tasks: 找到 {len(similar)} 筆") if similar else fail("應找到至少1筆")

memory.save_error_fix("click", "座標超出螢幕", {"x": 9999, "y": 0}, {"x": 500, "y": 0})
ok("save_error_fix 成功")

fixes = memory.find_error_fixes("click", "座標超出範圍")
ok(f"find_error_fixes: 找到 {len(fixes)} 筆") if fixes else fail("應找到至少1筆")


# ── 3. agent_core helpers ────────────────────────────────────────
print("\n[agent_core]")

from agent_core import _resolve_refs, _extract_json

# 步驟引用解析
refs = _resolve_refs(
    {"attachment": "$1.file", "to": "a@b.com"},
    {1: {"file": "screenshot.png"}},
)
if refs["attachment"] == "screenshot.png" and refs["to"] == "a@b.com":
    ok(f"_resolve_refs 正常: {refs}")
else:
    fail(f"_resolve_refs 錯誤: {refs}")

# 引用找不到時保留原值
refs2 = _resolve_refs({"x": "$99.missing"}, {})
ok("_resolve_refs 找不到時保留原值") if refs2["x"] == "$99.missing" else fail(f"{refs2}")

# JSON 提取
result = _extract_json('blah [{"tool": "screenshot", "params": {}}] end')
if len(result) == 1 and result[0]["tool"] == "screenshot":
    ok(f"_extract_json 正常")
else:
    fail(f"_extract_json 錯誤: {result}")

# 無 JSON
result2 = _extract_json("no json here")
ok("_extract_json 無 JSON 回空") if result2 == [] else fail(f"{result2}")


# ── 4. tools/ui ──────────────────────────────────────────────────
print("\n[tools/ui]")

from tools import ui

ok("載入成功")

size = ui.get_screen_size()
if "width" in size and "height" in size:
    ok(f"螢幕解析度: {size['width']}x{size['height']}")
else:
    fail(f"get_screen_size 格式錯誤: {size}")


# ── 5. assistant_api import ──────────────────────────────────────
print("\n[assistant_api]")

try:
    import assistant_api
    ok("載入成功（Flask app 已建立）")
except Exception as e:
    fail(f"載入失敗: {e}")


# ── 結果 ─────────────────────────────────────────────────────────
print(f"\n{'='*40}")
print(f"結果：{passed} 通過 / {failed} 失敗")
if failed == 0:
    print("全部測試通過 ✅")
else:
    print("有測試失敗 ❌")
    sys.exit(1)
