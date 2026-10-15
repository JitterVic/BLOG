param(
  [switch]$SkipFrontend,
  [switch]$StrictLaunch,
  [int]$Port = 5055,
  [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BackendPython = Join-Path $Root "backend\.venv\Scripts\python.exe"
Set-Location $Root

if (-not (Test-Path $BackendPython)) {
  throw "未找到后端虚拟环境 $BackendPython，请先执行: uv sync --directory backend --group dev --group prod"
}

function Test-PortInUse {
  param([int]$Port)
  try {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    return $null -ne $conn
  } catch {
    return $false
  }
}

function Get-EnvValue {
  param(
    [Parameter(Mandatory)] [string]$Name,
    [string]$Default = ""
  )

  # -EnvFile 模式下这份文件是唯一来源：既不读进程变量，也不回落到开发用的 .env。
  # 否则生产核验会被开发配置里的值「补上」，变成假绿。
  if ($Script:EnvFileOnly) {
    if ($Script:EnvFileValues.ContainsKey($Name)) {
      return $Script:EnvFileValues[$Name]
    }
    return $Default
  }

  $current = [Environment]::GetEnvironmentVariable($Name, 'Process')
  if ($null -ne $current -and $current -ne '') {
    return $current
  }

  $envPath = Join-Path $Root '.env'
  if (-not (Test-Path $envPath)) {
    return $Default
  }

  foreach ($rawLine in Get-Content $envPath -Encoding UTF8) {
    $line = $rawLine.Trim()
    if (-not $line -or $line.StartsWith('#')) { continue }
    if ($line.StartsWith('export ')) { $line = $line.Substring(7).Trim() }
    $idx = $line.IndexOf('=')
    if ($idx -lt 1) { continue }
    $key = $line.Substring(0, $idx).Trim()
    if ($key -ne $Name) { continue }
    $value = $line.Substring($idx + 1).Trim()
    if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    return $value
  }

  return $Default
}

<#
  解析一份环境文件为哈希表（不改动当前进程环境）。

  用途：在本机跑 -StrictLaunch 时提供生产取值，而不必改动开发用的 .env——那份 .env
  里的空 BLOG_PUBLIC_BASE_URL 会让严格核验失败，而把它填成真域名又必须同时
  BLOG_COOKIE_SECURE=true，本地 http 登录会因此失效。取值只在严格核验与冒烟服务里生效
  （冒烟服务前才注入进程环境），pytest 仍在日常环境下跑：测试用例对 BLOG_TRUSTED_PROXY_COUNT
  之类取值的假设是开发默认值，把生产取值带进去会让用例失真。
#>
function Read-EnvFile {
  param([Parameter(Mandatory)] [string]$Path)

  $values = @{}
  foreach ($rawLine in Get-Content $Path -Encoding UTF8) {
    $line = $rawLine.Trim()
    if (-not $line -or $line.StartsWith('#')) { continue }
    if ($line.StartsWith('export ')) { $line = $line.Substring(7).Trim() }
    $idx = $line.IndexOf('=')
    if ($idx -lt 1) { continue }
    $key = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1).Trim()
    if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    if ($key) { $values[$key] = $value }
  }
  return $values
}

function Assert-LaunchConfig {
  $issues = New-Object System.Collections.Generic.List[string]

  $debug = (Get-EnvValue -Name 'BLOG_DEBUG' -Default 'false').ToLowerInvariant()
  $secret = Get-EnvValue -Name 'BLOG_SECRET_KEY'
  $adminPassword = Get-EnvValue -Name 'BLOG_ADMIN_PASSWORD'
  $adminPrefix = Get-EnvValue -Name 'BLOG_ADMIN_PREFIX' -Default '/admin'
  $publicBaseUrl = (Get-EnvValue -Name 'BLOG_PUBLIC_BASE_URL').Trim().TrimEnd('/')
  $requirePublicBaseUrl = (Get-EnvValue -Name 'BLOG_REQUIRE_PUBLIC_BASE_URL' -Default 'false').ToLowerInvariant()
  $cookieSecure = (Get-EnvValue -Name 'BLOG_COOKIE_SECURE' -Default 'false').ToLowerInvariant()

  if ($debug -ne 'false') {
    $issues.Add('BLOG_DEBUG must be false for launch verification.')
  }

  if (-not $secret -or $secret.Length -lt 32 -or $secret -eq 'dev-secret-key-change-me' -or $secret -eq 'change-me-before-deploy') {
    $issues.Add('BLOG_SECRET_KEY must be a non-default random secret of at least 32 characters.')
  }

  if (-not $adminPassword -or $adminPassword.Length -lt 12 -or $adminPassword -in @('123', '123456', 'admin', 'admin123456', 'password', 'change-me-before-deploy')) {
    $issues.Add('BLOG_ADMIN_PASSWORD must be a stronger password of at least 12 characters and not a common default.')
  }

  if ($adminPrefix -eq '/admin' -or -not $adminPrefix.StartsWith('/')) {
    $issues.Add('BLOG_ADMIN_PREFIX should be a non-default hidden path that still starts with /.')
  }

  if (-not $publicBaseUrl) {
    $issues.Add('BLOG_PUBLIC_BASE_URL must be set to the real HTTPS public origin before launch.')
  } elseif ($publicBaseUrl -notmatch '^https://') {
    $issues.Add('BLOG_PUBLIC_BASE_URL should use https:// for a public launch.')
  } elseif ($requirePublicBaseUrl -ne 'true') {
    $issues.Add('BLOG_REQUIRE_PUBLIC_BASE_URL should be true for strict launch verification.')
  } elseif ($cookieSecure -ne 'true') {
    $issues.Add('BLOG_COOKIE_SECURE should be true when BLOG_PUBLIC_BASE_URL uses HTTPS.')
  }

  if ($issues.Count -gt 0) {
    throw ("Strict launch checks failed:`n- " + ($issues -join "`n- "))
  }
}

Write-Host "== BLOG 一键验证 ==" -ForegroundColor Cyan

$Script:EnvFileValues = @{}
$Script:EnvFileOnly = $false
if ($EnvFile) {
  $envFilePath = $EnvFile
  if (-not [System.IO.Path]::IsPathRooted($envFilePath)) {
    $envFilePath = Join-Path $Root $envFilePath
  }
  if (-not (Test-Path $envFilePath)) {
    throw "找不到环境文件: $envFilePath"
  }
  $Script:EnvFileValues = Read-EnvFile -Path $envFilePath
  $Script:EnvFileOnly = $true
  Write-Host "环境文件: $EnvFile（$($Script:EnvFileValues.Count) 项；只作用于严格核验与冒烟服务，pytest 仍走日常环境）" -ForegroundColor DarkGray
}

if ($StrictLaunch) {
  Write-Host "[0/3] 严格上线配置检查" -ForegroundColor Green
  Assert-LaunchConfig
}

# 每次使用全新的时间戳 basetemp，避免 pytest 清理旧目录时遇到 Windows 权限问题
$bt = Join-Path $Root "output/pytest-tmp-verify-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

Write-Host "[1/3] 后端测试 pytest" -ForegroundColor Green
& $BackendPython -m pytest backend/tests -q -p no:cacheprovider --basetemp="$bt"
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

# 清理旧的 basetemp 目录（保留本次；删除失败不影响验证结果）
Get-ChildItem (Join-Path $Root "output") -Directory -Filter "pytest-tmp-verify-*" -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -ne $bt } |
  ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

if (-not $SkipFrontend) {
  Write-Host "[2/3] 前端生产构建 npm run build" -ForegroundColor Green
  Push-Location (Join-Path $Root "frontend")
  try {
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }
  } finally {
    Pop-Location
  }
} else {
  Write-Host "[2/3] 跳过前端构建" -ForegroundColor Yellow
}

Write-Host "[3/3] API 冒烟验证（临时后端，端口 $Port）" -ForegroundColor Green

# 冒烟服务要用与严格核验同一套取值：这里才把它们注入进程环境，
# 子进程（临时后端）因此继承到生产配置，而前面的 pytest 仍是日常环境。
if ($Script:EnvFileOnly) {
  foreach ($key in $Script:EnvFileValues.Keys) {
    [Environment]::SetEnvironmentVariable($key, $Script:EnvFileValues[$key], 'Process')
  }
  Write-Host "冒烟服务使用 $EnvFile 的取值" -ForegroundColor DarkGray
}

if (Test-PortInUse -Port $Port) {
  throw "port $Port is already in use; rerun with -Port <free-port>"
}

$smokeLogDir = Join-Path $Root "output/verify-smoke"
New-Item -ItemType Directory -Path $smokeLogDir -Force | Out-Null
$smokeOutLog = Join-Path $smokeLogDir "backend.out.log"
$smokeErrLog = Join-Path $smokeLogDir "backend.err.log"

$smokeLauncher = Join-Path $smokeLogDir "launch_smoke_server.py"
$launcherContent = @"
import os
import sys
from pathlib import Path

root = Path(r"$Root")
os.chdir(root)
sys.stdout = open(r"$smokeOutLog", "a", encoding="utf-8", buffering=1)
sys.stderr = open(r"$smokeErrLog", "a", encoding="utf-8", buffering=1)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["BLOG_DEBUG"] = "false"
os.environ["BLOG_HOST"] = "127.0.0.1"
os.environ["BLOG_PORT"] = "$Port"
if "$StrictLaunch" == "True":
    os.environ["BLOG_REQUIRE_PUBLIC_BASE_URL"] = "true"
from blog.app import app
app.run(host="127.0.0.1", port=int("$Port"), debug=False)
"@
Set-Content -Path $smokeLauncher -Value $launcherContent -Encoding UTF8

$serverProcess = Start-Process -FilePath $BackendPython `
  -ArgumentList @($smokeLauncher) `
  -WorkingDirectory $Root `
  -PassThru `
  -WindowStyle Hidden

try {
  $baseUrl = "http://127.0.0.1:$Port"
  $ok = $false
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    try {
      $health = Invoke-RestMethod -Uri "$baseUrl/api/health" -TimeoutSec 2
      if ($health.status -eq "ok") { $ok = $true; break }
    } catch {
      $serverProcess.Refresh()
      if ($serverProcess.HasExited) { break }
    }
  }
  if (-not $ok) {
    if (Test-Path $smokeOutLog) { Get-Content $smokeOutLog -Encoding UTF8 | Write-Host }
    if (Test-Path $smokeErrLog) { Get-Content $smokeErrLog -Encoding UTF8 | Write-Host }
    throw "backend health check failed"
  }

  $posts = Invoke-WebRequest -Uri "$baseUrl/api/posts?page=1&limit=2" -UseBasicParsing -TimeoutSec 5
  if ($posts.StatusCode -ne 200) { throw "posts endpoint failed" }

  try {
    $trap = Invoke-WebRequest -Uri "$baseUrl/uploads/../blog.db" -UseBasicParsing -TimeoutSec 5
    if ($trap.Headers["Content-Type"] -match "sqlite|octet-stream") {
      throw "database path is publicly downloadable"
    }
  } catch {
    if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 404) {
      # good
    } elseif ($_.Exception.Message -match "database path") {
      throw
    }
  }

  Write-Host "smoke ok: health + posts + upload traversal guard" -ForegroundColor Green
}
finally {
  if ($serverProcess -and -not $serverProcess.HasExited) {
    Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
  }
  Remove-Item $smokeLauncher -Force -ErrorAction SilentlyContinue
}
Write-Host ""
Write-Host "全部验证通过。" -ForegroundColor Green
