import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, MockupParams } from "../api";

const PALETTES: { id: MockupParams["palette"]; name: string }[] = [
  { id: "walnut", name: "Walnut" },
  { id: "oak", name: "Oak" },
  { id: "cherry", name: "Cherry" },
  { id: "maple", name: "Maple" },
];

const DEFAULTS: MockupParams = {
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
  { id: "ai",       label: "AI depth", hint: "Best for objects, animals, landscapes." },
  { id: "luminance",label: "Image luminance", hint: "Best for portraits, logos, line art — preserves every feature." },
  { id: "hybrid",   label: "Hybrid",  hint: "AI silhouette × luminance detail. Try if AI alone goes too flat." },
];

export default function Mockup() {
  const { id: projectId, imageId } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useState<MockupParams>(DEFAULTS);
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const debounce = useRef<number | undefined>();

  const render = useCallback(async () => {
    if (!imageId) return;
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
    debounce.current = window.setTimeout(() => {
      render();
    }, 250);
    return () => window.clearTimeout(debounce.current);
  }, [render]);

  useEffect(() => {
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    <div className="col" style={{ gap: 14 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="row">
          <button onClick={() => navigate(`/project/${projectId}`)}>← Back</button>
          <h2 style={{ margin: 0, fontSize: 18 }}>Mockup on wood</h2>
        </div>
        <button
          className="primary"
          onClick={() =>
            navigate(`/project/${projectId}/convert/${imageId}`)
          }
        >
          Looks good → Convert to STL
        </button>
      </div>

      <div className="split">
        <div className="preview">
          <div className="muted row" style={{ justifyContent: "space-between" }}>
            <span>Carved-relief preview</span>
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
            First render takes ~20–40 s on CPU while Depth Anything V2 runs;
            after that, slider changes return in under a second.
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
                setParams({ ...params, wood_seed: Math.floor(Math.random() * 9999) })
              }
              title="Roll a new grain pattern"
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
              Invert (carve the light areas)
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
            onClick={() => {
              if (!url) return;
              const a = document.createElement("a");
              a.href = url;
              a.download = `mockup_${imageId?.slice(0, 8)}.jpg`;
              a.click();
            }}
            disabled={!url}
          >
            Download mockup JPG
          </button>
          <div className="muted" style={{ fontSize: 12 }}>
            Useful for sending a customer a "this is roughly what it'll look
            like carved in walnut" preview before machining.
          </div>
        </div>
      </div>
    </div>
  );
}
