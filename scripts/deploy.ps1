# Deploy Spreadsheet Analyzer ke Vercel (production)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "=== Spreadsheet Analyzer — Deploy ke Vercel ===" -ForegroundColor Cyan

# 1. Env vars dari file lokal
if (-not (Test-Path "service_account.json")) {
    Write-Host "ERROR: service_account.json tidak ditemukan" -ForegroundColor Red
    exit 1
}

$gsaJson = (Get-Content "service_account.json" -Raw -Encoding UTF8).Trim()
$gsaJson = $gsaJson -replace "`r`n", "" -replace "`n", ""

$anthropicKey = ""
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*ANTHROPIC_API_KEY\s*=\s*(.+)\s*$') {
            $anthropicKey = $matches[1].Trim().Trim('"').Trim("'")
        }
    }
}

function Set-VercelEnv($name, $value, $envName) {
    if (-not $value) { return }
    Write-Host "  Set env: $name ($envName)" -ForegroundColor DarkGray
    $value | npx vercel env add $name $envName --force 2>&1 | Out-Null
}

Write-Host "`n[1/3] Upload environment variables..." -ForegroundColor Yellow
foreach ($env in @("production", "preview", "development")) {
    Set-VercelEnv "GOOGLE_SERVICE_ACCOUNT_JSON" $gsaJson $env
    if ($anthropicKey) {
        Set-VercelEnv "ANTHROPIC_API_KEY" $anthropicKey $env
    }
}

Write-Host "`n[2/3] Deploy preview..." -ForegroundColor Yellow
npx vercel deploy --yes
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[3/3] Deploy production..." -ForegroundColor Yellow
npx vercel deploy --prod --yes
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== Deploy selesai! ===" -ForegroundColor Green
Write-Host "Cek URL di output di atas, atau jalankan: npx vercel ls" -ForegroundColor Gray
