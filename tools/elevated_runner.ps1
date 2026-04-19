# elevated_runner.ps1
# 由 Task Scheduler 以最高權限執行
# 讀取固定路徑的 cmd.ps1 並執行，結果寫回同目錄

$elevDir  = Join-Path $PSScriptRoot ".elevated"
$cmdFile  = Join-Path $elevDir "cmd.ps1"
$outFile  = Join-Path $elevDir "out.txt"
$errFile  = Join-Path $elevDir "err.txt"
$rcFile   = Join-Path $elevDir "rc.txt"

if (-not (Test-Path $cmdFile)) {
    "ERROR: cmd file not found" | Out-File $errFile -Encoding utf8
    "1" | Out-File $rcFile -Encoding utf8
    exit 1
}

try {
    # 執行命令腳本，收集輸出
    $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $cmdFile 2>&1
    $output | Out-File $outFile -Encoding utf8
    "0" | Out-File $rcFile -Encoding utf8
} catch {
    $_.Exception.Message | Out-File $errFile -Encoding utf8
    "1" | Out-File $rcFile -Encoding utf8
}
