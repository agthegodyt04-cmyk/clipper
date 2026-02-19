param(
    [string]$PythonExe = "python",
    [string]$ModelPath = "D:\AIModels",
    [switch]$InstallFrontendDeps = $true,
    [switch]$InstallV2Stack = $false,
    [switch]$DownloadRealModels = $false
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "==> Clipper setup (Windows)" -ForegroundColor Cyan
Write-Host "Repo root: $root"
Write-Host "Model path: $ModelPath"

Set-Location $root

if (!(Test-Path $ModelPath)) {
    New-Item -ItemType Directory -Path $ModelPath -Force | Out-Null
}
if (!(Test-Path "$ModelPath\.cache")) {
    New-Item -ItemType Directory -Path "$ModelPath\.cache" -Force | Out-Null
}

Set-Location "$root\backend"
if (!(Test-Path ".venv")) {
    & $PythonExe -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

if ($InstallV2Stack) {
    Write-Host "==> Installing V2 stack (CPU torch + diffusers + llama-cpp wheel)..."
    & ".\.venv\Scripts\python.exe" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    & ".\.venv\Scripts\python.exe" -m pip install -r requirements-v2.txt --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
}

if ($DownloadRealModels) {
    & ".\.venv\Scripts\python.exe" "$root\scripts\download_real_models.py" --model-path $ModelPath --targets image_fast_sdxl_turbo image_hq_sdxl_base inpaint_hq_sdxl legacy_sd_turbo legacy_sd_inpaint
}

Set-Location $root

if ($InstallFrontendDeps) {
    Set-Location "$root\frontend"
    npm install
    Set-Location $root
}

Write-Host "==> Checking ffmpeg in PATH..."
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "ffmpeg: OK" -ForegroundColor Green
} else {
    Write-Host "ffmpeg not found. Install ffmpeg for MP4 export support." -ForegroundColor Yellow
}

Write-Host "==> Setup complete." -ForegroundColor Green
