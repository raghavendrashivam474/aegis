# ============================================================
# Aegis Local Repository Health & Verification Script
# ============================================================
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== [1/4] Checking Required Directory Structure ===" -ForegroundColor Cyan
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
Write-Host "=== [2/4] Checking Core Root Artifacts ===" -ForegroundColor Cyan
$requiredFiles = @("README.md", ".gitignore", "LICENSE", "pyproject.toml", "compose.yaml")
foreach ($f in $requiredFiles) {
    if (Test-Path $f) {
        Write-Host "  [PASS] $f exists" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] Missing required file: $f" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "=== [3/4] Running Code Formatting and Lint Checks ===" -ForegroundColor Cyan
if (Get-Command ruff -ErrorAction SilentlyContinue) {
    Write-Host "  Running 'ruff check .' ..."
    ruff check .
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [PASS] Ruff linting checks passed." -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] Ruff reported lint issues." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  [WARN] 'ruff' not installed in current environment. Skipping linter." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== [4/4] Running Pytest Suite ===" -ForegroundColor Cyan
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
Write-Host "============================================================" -ForegroundColor Green
Write-Host " [OK] Aegis Foundation Baseline is HEALTHY and VERIFIED" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""