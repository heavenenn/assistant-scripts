# ===== 薇薇 Assistant API 背景啟動器 =====
# 功能：以隱藏視窗啟動 assistant_api.py，開機自動執行
# 用法：以管理員身份執行此腳本即可安裝
#
# 啟動方式：工作排程器（Task Scheduler）
#   - 登入時自動啟動（不需要手動開 PowerShell）
#   - 以最高權限執行（解決事件檢視器等高權限 UI 操作）
#   - 在使用者桌面 Session 執行（screenshot / pyautogui 正常）
#   - 重啟方便：services.msc 看不到，但 Task Scheduler 可管理

$taskName    = "WeiWeiAssistant"
$scriptPath  = "C:\Users\heave\.openclaw\assistant-scripts\assistant_api.py"
$workDir     = "C:\Users\heave\.openclaw\assistant-scripts"

# 用 pythonw.exe 啟動（無 console 視窗）
$pythonDir  = Split-Path (Get-Command python).Source
$pythonwPath = Join-Path $pythonDir "pythonw.exe"
if (-not (Test-Path $pythonwPath)) {
    Write-Host "⚠ 找不到 pythonw.exe，改用 python.exe（會有視窗）"
    $pythonwPath = (Get-Command python).Source
}

Write-Host "=== 薇薇 Assistant 背景服務安裝 ==="
Write-Host "Python: $pythonwPath"
Write-Host "Script: $scriptPath"

# ── 移除舊排程 ──
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "移除舊排程..."
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# ── 建立排程任務 ──
# -WindowStyle Hidden：隱藏 Python 視窗
# -RunLevel Highest：以管理員權限執行（解決 UIPI）
$action = New-ScheduledTaskAction `
    -Execute $pythonwPath `
    -Argument "`"$scriptPath`"" `
    -WorkingDirectory $workDir

# 登入時自動啟動
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# 以最高權限、只在使用者登入時執行（確保在桌面 Session）
$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -RunLevel Highest `
    -LogonType Interactive

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -RestartCount 3 `
    -ExecutionTimeLimit (New-TimeSpan -Days 365)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "薇薇 Assistant API（背景執行，支援 UI 操作）"

Write-Host "✔ 主服務安裝成功！"

# ── 建立提權輔助排程（供 run_command elevated=true 使用）──
$elevatedTask   = "WeiWeiElevatedCmd"
$elevatedScript = Join-Path $workDir "tools\elevated_runner.ps1"

$existingE = Get-ScheduledTask -TaskName $elevatedTask -ErrorAction SilentlyContinue
if ($existingE) {
    Unregister-ScheduledTask -TaskName $elevatedTask -Confirm:$false
}

$elevatedAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$elevatedScript`"" `
    -WorkingDirectory $workDir

# 手動觸發、不綁定排程（僅透過 schtasks /Run 啟動）
$elevatedPrincipal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -RunLevel Highest `
    -LogonType Interactive

$elevatedSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
    -TaskName $elevatedTask `
    -Action $elevatedAction `
    -Principal $elevatedPrincipal `
    -Settings $elevatedSettings `
    -Description "薇薇提權指令執行器（由 run_command elevated=true 觸發）"

Write-Host "✔ 提權輔助排程安裝成功！"

Write-Host ""
Write-Host "  排程名稱：$taskName"
Write-Host "  觸發條件：登入時自動啟動"
Write-Host "  權限：最高（管理員）"
Write-Host "  提權輔助：$elevatedTask（供管理員指令使用）"
Write-Host ""
Write-Host "手動操作："
Write-Host "  啟動：Start-ScheduledTask -TaskName '$taskName'"
Write-Host "  停止：Stop-ScheduledTask -TaskName '$taskName'"
Write-Host "  狀態：Get-ScheduledTask -TaskName '$taskName' | Select State"
Write-Host "  移除：Unregister-ScheduledTask -TaskName '$taskName'"
Write-Host ""
Write-Host "現在要立即啟動嗎？(Y/N)"
$answer = Read-Host
if ($answer -eq "Y" -or $answer -eq "y") {
    Start-ScheduledTask -TaskName $taskName
    Start-Sleep 3
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:5005/health" -UseBasicParsing -TimeoutSec 5
        Write-Host "✔ 服務已啟動：$($r.Content)"
    } catch {
        Write-Host "⚠ 啟動中，請稍候再測試 http://127.0.0.1:5005/health"
    }
}
