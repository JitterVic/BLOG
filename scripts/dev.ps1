param(
  [switch]$NoOpen
)

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$FrontendDir = Join-Path $Root "frontend"
$RunDir = Join-Path $Root ".run"
New-Item -ItemType Directory -Path $RunDir -Force | Out-Null

function Get-ListeningProcessId {
  param([int]$Port)
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($conn) { return $conn.OwningProcess }
  return $null
}

function Wait-HttpOk {
  param(
    [string]$Url,
    [int]$TimeoutSeconds = 30
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return $true
      }
    } catch {
      Start-Sleep -Milliseconds 600
    }
  } while ((Get-Date) -lt $deadline)

  return $false
}

Write-Host "== BLOG 一键启动 ==" -ForegroundColor Cyan
Write-Host "项目目录: $Root"

$backendPid = Get-ListeningProcessId -Port 5000
if ($backendPid) {
  Write-Host "后端已在 5000 端口运行，PID=$backendPid" -ForegroundColor Yellow
} else {
  Write-Host "正在启动 Flask 后端..." -ForegroundColor Green
  $backend = Start-Process -FilePath "python" `
    -ArgumentList @("backend/app.py") `
    -WorkingDirectory $Root `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $RunDir "backend.out.log") `
    -RedirectStandardError (Join-Path $RunDir "backend.err.log")
  $backendPid = $backend.Id
  Set-Content -Path (Join-Path $RunDir "backend.pid") -Value $backendPid -Encoding ASCII
  Write-Host "后端已启动，PID=$backendPid"
}

$frontendPid = Get-ListeningProcessId -Port 5173
if ($frontendPid) {
  Write-Host "前端已在 5173 端口运行，PID=$frontendPid" -ForegroundColor Yellow
} else {
  if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "警告: frontend/node_modules 不存在，请先在 frontend 目录执行 npm install。" -ForegroundColor Yellow
  }

  Write-Host "正在启动 Vite 前端..." -ForegroundColor Green
  $frontend = Start-Process -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
    -WorkingDirectory $FrontendDir `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $RunDir "frontend.out.log") `
    -RedirectStandardError (Join-Path $RunDir "frontend.err.log")
  $frontendPid = $frontend.Id
  Set-Content -Path (Join-Path $RunDir "frontend.pid") -Value $frontendPid -Encoding ASCII
  Write-Host "前端已启动，PID=$frontendPid"
}

Write-Host "正在等待服务就绪..."
$backendOk = Wait-HttpOk -Url "http://127.0.0.1:5000/api/health" -TimeoutSeconds 30
$frontendOk = Wait-HttpOk -Url "http://127.0.0.1:5173" -TimeoutSeconds 45

Write-Host ""
Write-Host "== 启动结果 ==" -ForegroundColor Cyan
if ($backendOk) {
  Write-Host "后端: http://127.0.0.1:5000  正常" -ForegroundColor Green
} else {
  Write-Host "后端: http://127.0.0.1:5000  未确认就绪，请查看 .run/backend.err.log" -ForegroundColor Red
}

if ($frontendOk) {
  Write-Host "前端: http://127.0.0.1:5173  正常" -ForegroundColor Green
} else {
  Write-Host "前端: http://127.0.0.1:5173  未确认就绪，请查看 .run/frontend.err.log" -ForegroundColor Red
}

Write-Host "后台: http://127.0.0.1:5000/admin/login"
Write-Host "日志目录: $RunDir"

if (-not $NoOpen -and $frontendOk) {
  Start-Process "http://127.0.0.1:5173"
}

Write-Host ""
Write-Host "如需关闭，可在 PowerShell 执行:"
Write-Host ("Stop-Process -Id {0},{1} -Force" -f $backendPid, $frontendPid) -ForegroundColor DarkGray
