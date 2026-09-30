# ============================================================
# Aegis Local Repository Health & Verification Script
# ============================================================
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== [1/5] Checking Required Directory Structure ===" -ForegroundColor Cyan
$requiredDirs = @(
    "apps\backend", "apps\simulator", "apps\edge",
    "packages\contracts", "packages\domain",
    "infrastructure\docker", "infrastructure\config",
    "docs\architecture", "docs\decisions", "docs\development",
    "tests", "scripts", ".github\workflows"
)
$missingDirs = 0
foreach ($d in $requiredDirs) {
    if (-not (Test-Path $d)) {
        Write-Host "  [MISSING] $d" -ForegroundColor Red
        $missingDirs++
    }
}
if ($missingDirs -eq 0) {
    Write-Host "  [PASS] All 13 architectural directories exist." -ForegroundColor Green
} else {
    Write-Host "  [FAIL] $missingDirs required directories missing!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== [2/5] Checking Core Root Artifacts ===" -ForegroundColor Cyan
$requiredFiles = @("README.md", ".gitignore", ".gitattributes", "LICENSE", "pyproject.toml", "docker-compose.yml")
foreach ($f in $requiredFiles) {
    if (Test-Path $f) {
        Write-Host "  [PASS] $f exists" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] Missing required file: $f" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "=== [3/5] Running Code Formatting and Lint Checks ===" -ForegroundColor Cyan
if (Get-Command ruff -ErrorAction SilentlyContinue) {
    Write-Host "  Running 'ruff check .' ..."
    ruff check .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [FAIL] Ruff reported lint issues." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Running 'ruff format --check .' ..."
    ruff format --check .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [FAIL] Ruff format check reported unformatted files." -ForegroundColor Red
        exit 1
    }
    Write-Host "  [PASS] Ruff linting and formatting checks passed." -ForegroundColor Green
} else {
    Write-Host "  [WARN] 'ruff' not installed in current environment. Skipping linter." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== [4/5] Running Pytest Suite ===" -ForegroundColor Cyan
if (Get-Command pytest -ErrorAction SilentlyContinue) {
    pytest -v
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "  [PASS] All pytest test suites passed cleanly." -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "  [FAIL] Pytest test suite failed!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  Running fallback test discovery via Python unittest runner..."
    python -m unittest discover -s tests -p "test_*.py"
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "  [PASS] All tests passed via unittest fallback." -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "  [FAIL] Tests failed!" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "=== [5/5] Running System Showcase ===" -ForegroundColor Cyan
# Execute P1.S5 showcase if Docker infrastructure is accessible, otherwise run World Model showcase
try {
    $socket = New-Object System.Net.Sockets.TcpClient
    $asyncResult = $socket.BeginConnect("localhost", 5434, $null, $null)
    $wait = $asyncResult.AsyncWaitHandle.WaitOne(1000, $false)
    if ($wait) {
        $socket.EndConnect($asyncResult)
        $socket.Close()
        Write-Host "  Docker infrastructure detected. Running P1.S5 Showcase..." -ForegroundColor Yellow
        python scripts/showcase_p1_s6.py
    } else {
        $socket.Close()
        Write-Host "  Docker infrastructure offline. Falling back to World Model Showcase..." -ForegroundColor Yellow
        python scripts/showcase_world_model.py
    }
} catch {
    Write-Host "  Docker infrastructure offline. Falling back to World Model Showcase..." -ForegroundColor Yellow
    python scripts/showcase_world_model.py
}

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "  [PASS] Showcase executed successfully." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  [FAIL] Showcase execution failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " [OK] Aegis P1.S6 System is HEALTHY and VERIFIED" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
