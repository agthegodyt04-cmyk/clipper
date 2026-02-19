# Clipper Local AI Ad Generator

Local-first ad generation stack:

1. AI copy generation
2. AI image generation
3. Brush-mask inpaint editor
4. Storyboard video generation (V1)
5. Capability-gated text-to-video fallback pipeline (V2 adapter)

## Paths

1. Models: `D:\AIModels`
2. App data: `d:\clipper\clipper\data`
3. SQLite DB: `d:\clipper\clipper\data\app.db`
4. Project assets: `d:\clipper\clipper\data\projects`
5. Exports: `d:\clipper\clipper\data\exports`

## Quick Start

```powershell
cd d:\clipper\clipper
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
npm install
npm run dev:all
```

Frontend:

1. `http://127.0.0.1:5173`

Backend:

1. `http://127.0.0.1:8000`
2. `http://127.0.0.1:8000/docs`

## V2 Stack Install (Optional)

```powershell
cd d:\clipper\clipper\backend
.\.venv\Scripts\python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python -m pip install -r requirements-v2.txt --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
cd d:\clipper\clipper
.\backend\.venv\Scripts\python .\scripts\download_models.py --profile full --model-path D:/AIModels
```

Note: true local text-to-video still depends on downloading large video models and suitable hardware.

## Download Real Models

```powershell
cd d:\clipper\clipper
.\backend\.venv\Scripts\python .\scripts\download_real_models.py --model-path D:/AIModels --targets text image inpaint video
```

## Run On Colab

1. Open `colab/Clipper_Colab_Backend.ipynb` in Google Colab.
2. Set `REPO_URL` in the first code cell.
3. Run cells top-to-bottom.
4. Copy `PUBLIC_API_URL` and paste it into the app header `API URL` field, then click `Use API`.

## Backend Tests

```powershell
cd d:\clipper\clipper\backend
.\.venv\Scripts\python -m pytest -q
```

## Notes

1. If `ffmpeg` is missing, storyboard jobs still generate scenes/manifest/subtitles but MP4 may not render.
2. Use `scripts\download_models.py` to prepare starter/full model folder layout.
