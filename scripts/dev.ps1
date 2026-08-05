param(
  [switch]$NoOpen
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $Root "frontend"
$BackendPython = Join-Path $Root "backend\.venv\Scripts\python.exe"
$Watchdog = Join-Path $PSScriptRoot "dev_watchdog.py"

if (-not (Test-Path $BackendPython)) {
  Write-Error "未找到后端虚拟环境 $BackendPython，请先在仓库根目录执行: uv sync --directory backend --group dev --group prod"
}

function Get-ListeningProcessId {
  param([int]$Port)
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($conn) { return $conn.OwningProcess }
  return $null
}

Write-Host "== BLOG 一键启动 ==" -ForegroundColor Cyan
Write-Host "项目目录: $Root"

$backendPid = Get-ListeningProcessId -Port 5000
$frontendPid = Get-ListeningProcessId -Port 5173
if ($backendPid -or $frontendPid) {
  if ($backendPid) { Write-Host "5000 端口已被占用（PID=$backendPid）" -ForegroundColor Yellow }
  if ($frontendPid) { Write-Host "5173 端口已被占用（PID=$frontendPid）" -ForegroundColor Yellow }
  Write-Host "请先停止已有服务再运行本脚本，否则本次启动不会管理这些进程。" -ForegroundColor Yellow
  exit 1
}

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
  Write-Host "警告: frontend/node_modules 不存在，请先在 frontend 目录执行 npm install。" -ForegroundColor Yellow
}

Write-Host "启动前后端并进入守护模式..." -ForegroundColor Green
Write-Host "关闭此终端窗口或按 Ctrl+C 时，前后端进程将一并停止。" -ForegroundColor DarkGray

$watchdogArgs = @($Watchdog)
if ($NoOpen) { $watchdogArgs += "--no-open" }

# 前台运行守护进程：它把前后端放进 KILL_ON_CLOSE 的 Job Object，
# 终端关闭 -> 守护进程退出 -> Job 句柄关闭 -> Windows 终止全部子进程。
& $BackendPython @watchdogArgs
