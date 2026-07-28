import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AiReliefRequest, ImageRec, MockupParams, api } from "../api";

const PALETTES: { id: MockupParams["palette"]; name: string }[] = [
  { id: "walnut", name: "Walnut" },
  { id: "oak", name: "Oak" },
  { id: "cherry", name: "Cherry" },
  { id: "maple", name: "Maple" },
];

const STYLES: { id: AiReliefRequest["style"]; name: string }[] = [
  { id: "portrait", name: "Portrait plaque" },
  { id: "memorial", name: "Memorial plaque" },
  { id: "scenic", name: "Scenic relief" },
  { id: "sign_logo", name: "Sign / logo" },
];

const FRAMES: { id: AiReliefRequest["frame"]; name: string }[] = [
  { id: "simple", name: "Simple inset frame" },
  { id: "ornate", name: "Ornate carved frame" },
  { id: "none", name: "No frame" },
];

const DEFAULT_PROC: MockupParams = {
  palette: "walnut",
  wood_seed: 7,
  relief_scale: 60,
  ambient: 0.35,
  ao_strength: 0.35,
  light_x: -0.55,
  light_y: -0.55,
  light_z: 0.62,
  smoothing: 1.2,
  invert: false,
  background_threshold: 0,
  max_dim_px: 900,
  depth_mode: "ai",
};

const DEPTH_MODES: { id: MockupParams["depth_mode"]; label: string; hint: string }[] = [
  { id: "ai",        label: "AI depth",        hint: "Best for objects, animals, landscapes." },
  { id: "luminance", label: "Image luminance", hint: "Best for portraits / logos / line art — keeps every feature." },
  { id: "hybrid",    label: "Hybrid",          hint: "AI silhouette × luminance detail." },
];

type Tab = "ai" | "procedural";

export default function Mockup() {
  const { id: projectId, imageId } = useParams();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("ai");

  return (
    <div className="col" style={{ gap: 14 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="row">
          <button onClick={() => navigate(`/project/${projectId}`)}>← Back</button>
          <h2 style={{ margin: 0, fontSize: 18 }}>Bas-relief preview</h2>
        </div>
        <div className="row">
          <button
            className={tab === "ai" ? "primary" : ""}
            onClick={() => setTab("ai")}
          >
            AI render (becomes STL source)
          </button>
          <button
            className={tab === "procedural" ? "primary" : ""}
            onClick={() => setTab("procedural")}
          >
            Quick procedural preview
          </button>
        </div>
      </div>

      {tab === "ai" ? (
        <AiPanel projectId={projectId!} imageId={imageId!} />
      ) : (
        <ProceduralPanel projectId={projectId!} imageId={imageId!} />
      )}
    </div>
  );
}

// ----- AI render tab -----

function AiPanel({ projectId, imageId }: { projectId: string; imageId: string }) {
  const navigate = useNavigate();
  const [req, setReq] = useState<AiReliefRequest>({
    image_id: imageId,
    style: "portrait",
    palette: "walnut",
    frame: "simple",
    text: "",
    sunburst_background: true,
    additional_notes: "",
    provider: "gemini",
  });
  const [result, setResult] = useState<ImageRec | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Reset result when imageId changes (different source picked)
  useEffect(() => {
    setReq((r) => ({ ...r, image_id: imageId }));
    setResult(null);
  }, [imageId]);

  async function onGenerate() {
    setErr(null);
    setLoading(true);
    setResult(null);
    try {
      const rec = await api.aiRelief({ ...req, image_id: imageId });
      setResult(rec);
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="split">
      <div className="preview">
        <div className="muted">Source image</div>
        <img src={api.imageUrl(imageId)} alt="source" />
        <div className="muted">AI bas-relief render</div>
        {loading && (
          <div className="muted">
            <span className="spinner" /> Generating — two chained steps (mockup
            render, then its height map), typically 30–60 s total…
          </div>
        )}
        {err && <div className="error">{err}</div>}
        {result?.error && <div className="error">{result.error}</div>}
        {result && !result.error && (
          <>
            <img src={api.imageUrl(result.id)} alt="ai relief" />
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <button
                className="primary"
                onClick={() =>
                  navigate(
                    `/project/${projectId}/convert/${
                      result.heightmap_image_id ?? result.id
                    }`
                  )
                }
                title="Carve from the height map derived from this exact render — full composition with correct elevations"
              >
                Looks good → Convert to STL
              </button>
              {result.heightmap_image_id && (
                <button
                  onClick={() =>
                    navigate(`/project/${projectId}/convert/${result.id}`)
                  }
                  title="Advanced: carve straight from this lit render's luminance. Wood tone and shading become height — dark-stained areas carve low."
                >
                  Carve lit render directly (advanced)
                </button>
              )}
              <button onClick={onGenerate} disabled={loading}>
                Regenerate
              </button>
              <a
                href={api.imageUrl(result.id)}
                download={`ai_relief_${result.id.slice(0, 8)}.png`}
              >
                <button>Download mockup PNG</button>
              </a>
            </div>
            <div className="muted" style={{ fontSize: 12 }}>
              The STL carves from a shadowless height map converted from this
              exact render — same frame, sunburst, and caption, but with
              brightness meaning <i>elevation</i> instead of wood tone, so the
              subject stands proud of its surroundings. The advanced button
              instead uses the render's raw luminance (occasionally better for
              flat line-art styles; usually worse for stained-wood scenes).
            </div>
          </>
        )}
      </div>

      <div className="card col">
        <div>
          <label>Provider</label>
          <select
            value={req.provider}
            onChange={(e) =>
              setReq({ ...req, provider: e.target.value as AiReliefRequest["provider"] })
            }
          >
            <option value="gemini">Google Gemini</option>
            <option value="openai">OpenAI (gpt-image-1)</option>
          </select>
        </div>

        <div>
          <label>Style</label>
          <select
            value={req.style}
            onChange={(e) =>
              setReq({ ...req, style: e.target.value as AiReliefRequest["style"] })
            }
          >
            {STYLES.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label>Wood species (also drives the procedural fallback)</label>
          <select
            value={req.palette}
            onChange={(e) =>
              setReq({ ...req, palette: e.target.value as AiReliefRequest["palette"] })
            }
          >
            {PALETTES.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label>Frame</label>
          <select
            value={req.frame}
            onChange={(e) =>
              setReq({ ...req, frame: e.target.value as AiReliefRequest["frame"] })
            }
          >
            {FRAMES.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </div>

        <label
          style={{
            display: "inline-flex",
            gap: 6,
            alignItems: "center",
            textTransform: "none",
            letterSpacing: 0,
            fontSize: 13,
          }}
        >
          <input
            type="checkbox"
            checked={req.sunburst_background}
            onChange={(e) =>
              setReq({ ...req, sunburst_background: e.target.checked })
            }
          />
          Radiating sunburst background
        </label>

        <div>
          <label>Caption / inscription (optional)</label>
          <input
            type="text"
            value={req.text}
            onChange={(e) => setReq({ ...req, text: e.target.value })}
            placeholder={'e.g. "In Loving Memory, Jamson Millmon, 1935–2026"'}
          />
        </div>

        <div>
          <label>Extra notes for the AI (optional)</label>
          <textarea
            value={req.additional_notes}
            onChange={(e) =>
              setReq({ ...req, additional_notes: e.target.value })
            }
            placeholder='e.g. "leave wide margin at top", "subjects looking slightly upward"'
          />
        </div>

        <button className="primary" onClick={onGenerate} disabled={loading}>
          {loading ? (
            <>
              <span className="spinner" /> Generating…
            </>
          ) : result ? (
            "Regenerate"
          ) : (
            "Generate AI bas-relief"
          )}
        </button>
        <div className="muted" style={{ fontSize: 12 }}>
          Results are cached per (image + every parameter), so identical
          requests don't re-bill. Tweaking any field generates a new render.
        </div>
      </div>
    </div>
  );
}

// ----- Procedural tab (existing logic) -----

function ProceduralPanel({
  projectId,
  imageId,
}: {
  projectId: string;
  imageId: string;
}) {
  const navigate = useNavigate();
  const [params, setParams] = useState<MockupParams>(DEFAULT_PROC);
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const debounce = useRef<number | undefined>();

  const render = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const blob = await api.mockupBlob(imageId, params);
      setUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return URL.createObjectURL(blob);
      });
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [imageId, params]);

  useEffect(() => {
    window.clearTimeout(debounce.current);
    debounce.current = window.setTimeout(render, 250);
    return () => window.clearTimeout(debounce.current);
  }, [render]);

  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  function num(
    key: keyof MockupParams,
    label: string,
    min: number,
    max: number,
    step: number
  ) {
    const v = params[key] as number;
    return (
      <div>
        <label>
          {label}: <b>{Number(v).toFixed(step < 1 ? 2 : 0)}</b>
        </label>
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={v}
          onChange={(e) =>
            setParams({ ...params, [key]: Number(e.target.value) })
          }
        />
      </div>
    );
  }

  return (
    <div className="split">
      <div className="preview">
        <div className="muted row" style={{ justifyContent: "space-between" }}>
          <span>Procedural depth-map preview</span>
          {loading && (
            <span>
              <span className="spinner" /> rendering…
            </span>
          )}
        </div>
        {err ? (
          <div className="error">{err}</div>
        ) : url ? (
          <img src={url} alt="mockup" />
        ) : (
          <div className="muted">Preparing first render…</div>
        )}
        <div className="muted" style={{ fontSize: 12 }}>
          Useful for checking depth-map quality offline. For a client-facing
          render, use the AI tab — that's what becomes the STL source.
        </div>
      </div>

      <div className="card col">
        <div>
          <label>Depth source</label>
          <select
            value={params.depth_mode}
            onChange={(e) =>
              setParams({
                ...params,
                depth_mode: e.target.value as MockupParams["depth_mode"],
              })
            }
          >
            {DEPTH_MODES.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
          <div className="muted" style={{ fontSize: 12 }}>
            {DEPTH_MODES.find((m) => m.id === params.depth_mode)?.hint}
          </div>
        </div>

        <div>
          <label>Wood species</label>
          <select
            value={params.palette}
            onChange={(e) =>
              setParams({
                ...params,
                palette: e.target.value as MockupParams["palette"],
              })
            }
          >
            {PALETTES.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <div className="row">
          <button
            onClick={() =>
              setParams({
                ...params,
                wood_seed: Math.floor(Math.random() * 9999),
              })
            }
          >
            Re-shuffle grain
          </button>
          <label
            style={{
              display: "inline-flex",
              gap: 6,
              alignItems: "center",
              textTransform: "none",
              letterSpacing: 0,
              fontSize: 13,
            }}
          >
            <input
              type="checkbox"
              checked={params.invert}
              onChange={(e) =>
                setParams({ ...params, invert: e.target.checked })
              }
            />
            Invert
          </label>
        </div>

        {num("relief_scale", "Carve sharpness", 10, 180, 5)}
        {num("smoothing", "Smoothing", 0, 5, 0.1)}
        {num("ao_strength", "Recess darkening", 0, 0.8, 0.05)}
        {num("ambient", "Ambient light", 0.1, 0.6, 0.05)}
        {num("light_x", "Light X (− = left)", -1, 1, 0.05)}
        {num("light_y", "Light Y (− = top)", -1, 1, 0.05)}
        {num("background_threshold", "Background flatten", 0, 0.5, 0.01)}

        <button
          className="primary"
          onClick={() => navigate(`/project/${projectId}/convert/${imageId}`)}
        >
          Convert to STL (from original source)
        </button>
      </div>
    </div>
  );
}
