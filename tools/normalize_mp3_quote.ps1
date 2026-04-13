param(
    [Parameter(Mandatory=$true)]
    [string]$inputFolder,

    [Parameter(Mandatory=$false)]
    [string]$outputFolder = "",

    [Parameter(Mandatory=$false)]
    [string]$loudnorm = "I=-16:TP=-1.5:LRA=11"
)

# ── 預設輸出資料夾 ────────────────────────────────────────────────
if (-not $outputFolder) {
    $outputFolder = Join-Path $inputFolder "normalized"
}

# ── 驗證輸入資料夾 ────────────────────────────────────────────────
if (-not (Test-Path $inputFolder)) {
    Write-Output "ERROR: inputFolder not found: $inputFolder"
    exit 1
}

$ffmpegTest = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpegTest) {
    Write-Output "ERROR: ffmpeg not found in PATH"
    exit 1
}

New-Item $outputFolder -ItemType Directory -Force | Out-Null

$filter = "loudnorm=$loudnorm,aresample=44100"
$files  = Get-ChildItem $inputFolder -Filter "*.mp3"

if ($files.Count -eq 0) {
    Write-Output "WARNING: No MP3 files found in $inputFolder"
    exit 0
}

Write-Output "START: $($files.Count) file(s) to process"

$successCount = 0
$failCount    = 0

foreach ($f in $files) {
    $out = Join-Path $outputFolder $f.Name

    # 執行 ffmpeg，stderr 導向暫存檔以便擷取錯誤訊息
    $tmpErr = [System.IO.Path]::GetTempFileName()

    $proc = Start-Process -FilePath "ffmpeg" `
        -ArgumentList "-i `"$($f.FullName)`" -af $filter `"$out`" -y" `
        -NoNewWindow -Wait -PassThru `
        -RedirectStandardError $tmpErr

    $errContent = Get-Content $tmpErr -Raw -ErrorAction SilentlyContinue
    Remove-Item $tmpErr -ErrorAction SilentlyContinue

    if ($proc.ExitCode -eq 0 -and (Test-Path $out)) {
        Write-Output "OK: $($f.Name)"
        $successCount++
    } else {
        # 擷取 ffmpeg 最後一行有意義的錯誤
        $errLine = ($errContent -split "`n" |
            Where-Object { $_ -match "Error|Invalid|No such|failed" } |
            Select-Object -Last 1)
        Write-Output "FAIL: $($f.Name) | $errLine"
        $failCount++
    }
}

Write-Output "DONE: success=$successCount fail=$failCount outputFolder=$outputFolder"
exit 0
