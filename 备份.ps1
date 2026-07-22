# 备份 storage/ 到 storage-backups/backup-<yyyyMMdd-HHmmss>.zip，并只保留最近 N 份。
# 用法: .\备份.ps1
# 可选: .\备份.ps1 -Keep 10
# 注册每日计划任务示例（管理员 PowerShell）:
#   $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"D:\code\projects\BLOG\备份.ps1`""
#   $trigger = New-ScheduledTaskTrigger -Daily -At 2am
#   Register-ScheduledTask -TaskName "BlogStorageBackup" -Action $action -Trigger $trigger

param(
    [int]$Keep = 7
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Storage = Join-Path $Root "storage"
$BackupRoot = Join-Path $Root "storage-backups"

if (-not (Test-Path -LiteralPath $Storage)) {
    Write-Error "storage directory not found: $Storage"
}

New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$zipPath = Join-Path $BackupRoot "backup-$stamp.zip"

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -Path (Join-Path $Storage "*") -DestinationPath $zipPath -Force
Write-Host "Created $zipPath"

$archives = Get-ChildItem -LiteralPath $BackupRoot -Filter "backup-*.zip" |
    Sort-Object LastWriteTime -Descending
if ($archives.Count -gt $Keep) {
    $archives | Select-Object -Skip $Keep | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Force
        Write-Host "Removed old backup $($_.Name)"
    }
}
