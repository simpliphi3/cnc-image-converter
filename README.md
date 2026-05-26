# CNC Image Converter

A local web app that bundles two CNC woodworking workflows for use alongside Vectric Aspire:

1. **Multi-model image generation** with iteration memory — fan a single prompt out to OpenAI (`gpt-image-1`) and Google Gemini at the same time, with full support for **prompt-only** or **prompt + reference image(s)** on every turn. Iteration carries memory so you can refine across several turns without re-attaching the previous image.
2. **Image → STL conversion** powered by a local Depth Anything V2 model, with tunable carve depth, smoothing, base thickness, units, etc. Also emits a 16-bit grayscale depth PNG for Aspire's `Component from Bitmap` importer as a backup path.

Bonus: **raster → SVG vectorization** for v-carving lettering / line art, and a local project library so past work is easy to revisit.

Everything runs on the woodworker's own PC. API keys never leave the machine. Outputs save directly to a configurable Aspire-import folder.

## First-time setup (Windows)

Prereqs: **Node 20+** ([nodejs.org](https://nodejs.org/)) and **Git**. Everything else (Python, `uv`, model weights) the script handles.

```powershell
git clone <repo-url> cnc-image-converter
cd cnc-image-converter
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
```

The script will:
- Install `uv` (fast Python package manager) if missing.
- Create the Python env and install backend dependencies (`fastapi`, `torch`, `transformers`, `trimesh`, `potracer`, OpenAI + Gemini SDKs).
- Install Node deps for the frontend and build the static UI into `frontend/dist/`.
- Copy `.env.example` → `.env` and prompt for your `OPENAI_API_KEY` and `GOOGLE_API_KEY`.

## Launching

Double-click **`scripts\start.bat`**. It starts the local server and opens your browser at <http://127.0.0.1:7777>.

To stop the app, close the console window.

## First-time configuration

Open **Settings** in the top right and fill in:
- **Aspire output folder** — e.g. `C:\Users\<you>\Documents\Aspire Imports`. Every export is copied there automatically.
- **Default export units** — millimetres or inches.

The Depth Anything V2 model (~100MB) downloads the first time you convert an image to STL. After that everything runs offline (except image generation, which calls OpenAI / Gemini).

## Workflow

1. **New project** from the gallery.
2. In the project view, type a prompt, optionally drag-drop one or more reference images into the prompt area, pick which models to fan out to, hit **Generate**.
3. Iterate: change the prompt, hit Generate again. The previous result is carried into the next turn automatically (toggle off via "session memory" if you want a clean slate). You can also click **Use as reference for next turn** on any specific result.
4. When you like a result, click **Convert to STL**. Tune the depth, base thickness, smoothing, etc. with live depth-map preview. Export drops `<name>.stl` + `<name>_depth.png` into your Aspire folder.
5. Alternatively, click **Vectorize (SVG)** to produce a clean SVG for v-carve lettering / logos.
6. Open Aspire, import the STL (or the depth PNG via `Component from Bitmap`), generate toolpaths, carve.

## Updating

Pull a new version with `scripts\update.bat`.

## Development

Run backend and Vite dev server separately for hot reload:

```bash
# terminal 1
uv run python -m backend.app

# terminal 2
cd frontend && npm run dev
```

The Vite dev server proxies `/api/*` and `/healthz` to `http://127.0.0.1:7777`.

## Data layout

All user data lives under `~/.cnc-image-converter/`:

```
~/.cnc-image-converter/
├── projects.db        # SQLite: projects, turns, images, exports
├── config.json        # Aspire folder, default units
├── hf_cache/          # Cached Depth Anything V2 weights
└── files/<project_id>/
    ├── <image_id>.png # uploaded references + generations
    ├── <name>.stl
    └── <name>_depth.png
```

## Architecture

```
[ Browser at http://localhost:7777 ]
            │
            ▼
[ FastAPI (uvicorn) ]
  ├─ image_gen/      OpenAI + Gemini SDK calls (parallel fan-out)
  ├─ depth/          Depth Anything V2 via transformers (GPU if available)
  ├─ stl/            heightmap → mesh via numpy + trimesh
  ├─ vectorize/      raster → SVG via potracer
  ├─ store/          SQLite + on-disk files
  └─ static/         serves built Vite app from frontend/dist
```

Frontend: Vite + React + React Router (hash router, fully static).
