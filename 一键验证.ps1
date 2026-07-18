param(
  [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

Write-Host "== BLOG 一键验证 ==" -ForegroundColor Cyan

$bt = Join-Path $Root "output/pytest-tmp-verify"
New-Item -ItemType Directory -Path $bt -Force | Out-Null

Write-Host "[1/3] pytest" -ForegroundColor Green
python -m pytest backend/tests/ -q -p no:cacheprovider --basetemp="$bt"
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

if (-not $SkipFrontend) {
  Write-Host "[2/3] npm run build" -ForegroundColor Green
  Push-Location (Join-Path $Root "frontend")
  try {
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }
  } finally {
    Pop-Location
  }
} else {
  Write-Host "[2/3] skip frontend build" -ForegroundColor Yellow
}

Write-Host "[3/3] API smoke (temporary server)" -ForegroundColor Green
$env:PYTHONDONTWRITEBYTECODE = "1"
$job = Start-Job -ScriptBlock {
  param($root)
  Set-Location $root
  python backend/app.py
} -ArgumentList $Root

try {
  $ok = $false
  for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    try {
      $health = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/health" -TimeoutSec 2
      if ($health.status -eq "ok") { $ok = $true; break }
    } catch {}
  }
  if (-not $ok) { throw "backend health check failed" }

  $posts = Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/posts?page=1&limit=2" -UseBasicParsing -TimeoutSec 5
  if ($posts.StatusCode -ne 200) { throw "posts envelope failed" }

  try {
    $trap = Invoke-WebRequest -Uri "http://127.0.0.1:5000/uploads/../blog.db" -UseBasicParsing -TimeoutSec 5
    # SPA fallback may return 200 HTML; ensure it is not raw sqlite
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

  Write-Host "smoke ok: health + posts" -ForegroundColor Green
}
finally {
  Stop-Job $job -ErrorAction SilentlyContinue
  Remove-Job $job -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "全部验证通过。" -ForegroundColor Green
