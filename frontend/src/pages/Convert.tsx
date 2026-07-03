import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, DepthMode, DimensionPreset, ExportRec } from "../api";
import StlViewer from "../components/StlViewer";

type Params = {
  max_depth_mm: number;
  base_thickness_mm: number;
  width_mm: number;
  gaussian_blur_sigma: number;
  bilateral_strength: number;
  detail: number;
  curve_points: number[][] | null;
  background_threshold: number;
  invert: boolean;
  target_max_dim_px: number;
  include_skirt: boolean;
  close_bottom: boolean;
  units: "mm" | "in";
};

const DEFAULTS: Params = {
  max_depth_mm: 6.0,
  base_thickness_mm: 3.0,
  width_mm: 150.0,
  gaussian_blur_sigma: 1.5,
  bilateral_strength: 0.0,
  detail: 0.0,
  curve_points: null,
  background_threshold: 0.0,
  invert: false,
  target_max_dim_px: 600,
  include_skirt: true,
  close_bottom: true,
  units: "in",
};

// Height-curve presets: S-curves that push highlights (faces) up and shadows
// (background) down to restore bas-relief hierarchy, matching EasyCreate's
// Linear/Gentle/Medium/Aggressive remap presets. null = linear (identity).
const CURVE_PRESETS: Record<string, number[][] | null> = {
  linear: null,
  gentle: [[0, 0], [0.25, 0.18], [0.5, 0.5], [0.75, 0.82], [1, 1]],
  medium: [[0, 0], [0.25, 0.12], [0.5, 0.5], [0.75, 0.88], [1, 1]],
  aggressive: [[0, 0], [0.25, 0.06], [0.5, 0.5], [0.75, 0.94], [1, 1]],
};

export default function Convert() {
  const { id: projectId, imageId } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useState<Params>(DEFAULTS);
  const [depthUrl, setDepthUrl] = useState<string | null>(null);
  const [depthLoading, setDepthLoading] = useState(false);
  const [depthErr, setDepthErr] = useState<string | null>(null);
  const [converting, setConverting] = useState(false);
  const [exports, setExports] = useState<{
    stl: ExportRec;
    depth_png: ExportRec;
    aspire_steps?: ExportRec;
  } | null>(null);
  const [name, setName] = useState("");
  const [dimPresets, setDimPresets] = useState<DimensionPreset[]>([]);
  const [presetId, setPresetId] = useState<string>("custom");
  const [curvePreset, setCurvePreset] = useState<string>("linear");
  const [depthMode, setDepthMode] = useState<DepthMode>("ai");
  const [autoSelectedLuminance, setAutoSelectedLuminance] = useState(false);
  const [roleResolved, setRoleResolved] = useState(false);

  // Honor the Settings "Default export units" toggle (defaults to inches).
  useEffect(() => {
    api
      .getSettings()
      .then((s) => setParams((prev) => ({ ...prev, units: s.default_units })))
      .catch(() => {});
  }, []);

  useEffect(() => {
    api.listDimensionPresets().then(setDimPresets).catch(() => {});
  }, []);

  // Auto-pick depth mode based on the source image's role. AI bas-relief
  // renders already have the carve baked into their luminance, so AI depth
  // would just give us a silhouette of the subject — luminance is what we
  // want. AI relief outputs also come back JPEG-encoded from Gemini/OpenAI,
  // so we bump default smoothing to neutralize the 8×8 DCT block artifacts
  // that would otherwise show as horizontal banding in the mesh.
  // We gate the depth preview on roleResolved so we don't pay for an AI-mode
  // preview only to immediately re-run in luminance mode.
  useEffect(() => {
    if (!projectId || !imageId) return;
    let cancelled = false;
    api
      .getProject(projectId)
      .then((data) => {
        if (cancelled) return;
        const img = data.images.find((i) => i.id === imageId);
        if (img?.role === "ai_relief") {
          setDepthMode("luminance");
          setAutoSelectedLuminance(true);
          // Start bas-relief sources in the EasyCreate-matching configuration:
          // edge-preserving smoothing to clean the background field and a
          // medium S-curve to restore faces-high / background-low hierarchy.
          setCurvePreset("medium");
          setParams((prev) => ({
            ...prev,
            gaussian_blur_sigma: 3.5,
            detail: 0.3,
            bilateral_strength: 0.5,
            curve_points: CURVE_PRESETS.medium,
          }));
        }
        setRoleResolved(true);
      })
      .catch(() => setRoleResolved(true));
    return () => {
      cancelled = true;
    };
  }, [projectId, imageId]);

  function applyPreset(id: string) {
    setPresetId(id);
    const p = dimPresets.find((x) => x.id === id);
    if (!p) return;
    setParams((prev) => ({
      ...prev,
      width_mm: p.width_mm ?? prev.width_mm,
      max_depth_mm: p.max_depth_mm ?? prev.max_depth_mm,
    }));
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!imageId || !roleResolved) return;
      setDepthLoading(true);
      setDepthErr(null);
      try {
        const blob = await api.depthPreviewBlob(imageId, depthMode);
        if (!cancelled) setDepthUrl(URL.createObjectURL(blob));
      } catch (e: any) {
        if (!cancelled) setDepthErr(e.message || String(e));
      } finally {
        if (!cancelled) setDepthLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [imageId, depthMode, roleResolved]);

  async function onConvert() {
    if (!imageId) return;
    setConverting(true);
    setExports(null);
    try {
      const out = await api.convert({
        image_id: imageId,
        params,
        output_basename: name.trim() || undefined,
        depth_mode: depthMode,
      } as any);
      setExports(out);
    } catch (e: any) {
      alert(e.message || String(e));
    } finally {
      setConverting(false);
    }
  }

  function num(key: keyof Params, label: string, min: number, max: number, step: number) {
    const v = params[key] as number;
    return (
      <div>
        <label>
          {label}: <b>{v}</b>
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

  // Slider for a millimetre-backed physical dimension, displayed in the chosen
  // unit. The backend contract stays in mm; we convert only for display/entry.
  const MM_PER_IN = 25.4;
  function dim(
    key: "max_depth_mm" | "base_thickness_mm",
    label: string,
    minMm: number,
    maxMm: number,
    stepMm: number
  ) {
    const inch = params.units === "in";
    const f = inch ? 1 / MM_PER_IN : 1;
    const disp = (params[key] as number) * f;
    const step = inch ? 0.01 : stepMm;
    return (
      <div>
        <label>
          {label} ({inch ? "in" : "mm"}):{" "}
          <b>{disp.toFixed(inch ? 2 : 1)}</b>
        </label>
        <input
          type="range"
          min={minMm * f}
          max={maxMm * f}
          step={step}
          value={disp}
          onChange={(e) =>
            setParams({ ...params, [key]: Number(e.target.value) / f })
          }
        />
      </div>
    );
  }

  const inchUnits = params.units === "in";
  const widthDisp = inchUnits
    ? params.width_mm / MM_PER_IN
    : params.width_mm;

  return (
    <div className="col" style={{ gap: 14 }}>
      <div className="row">
        <button onClick={() => navigate(`/project/${projectId}`)}>← Back</button>
        <h2 style={{ margin: 0, fontSize: 18 }}>Convert to STL</h2>
      </div>

      <div className="split">
        <div className="preview">
          <div className="muted">Source image</div>
          {imageId && <img src={api.imageUrl(imageId)} alt="source" />}
          <div className="muted">
            {depthMode === "luminance"
              ? "Depth preview — luminance heightmap (bright = high)"
              : depthMode === "hybrid"
              ? "Depth preview — hybrid (AI silhouette × luminance)"
              : "Depth preview — AI depth (Depth Anything V2)"}
          </div>
          {depthLoading ? (
            <div className="muted">
              <span className="spinner" /> Estimating depth…
            </div>
          ) : depthErr ? (
            <div className="error">{depthErr}</div>
          ) : depthUrl ? (
            <img src={depthUrl} alt="depth" />
          ) : null}
        </div>

        <div className="card col">
          <div>
            <label>Depth source</label>
            <select
              value={depthMode}
              onChange={(e) => {
                setDepthMode(e.target.value as DepthMode);
                setAutoSelectedLuminance(false);
              }}
            >
              <option value="ai">AI depth — objects, animals, landscapes</option>
              <option value="luminance">
                Image luminance — portraits, logos, line art, AI bas-relief renders
              </option>
              <option value="hybrid">Hybrid — AI silhouette × luminance detail</option>
            </select>
            {autoSelectedLuminance ? (
              <div className="ok" style={{ fontSize: 12 }}>
                Auto-selected luminance because the source is an AI bas-relief
                render (the carve is already baked into its lighting).
              </div>
            ) : (
              <div className="muted" style={{ fontSize: 12 }}>
                For portraits or stylized bas-relief artwork, luminance preserves
                facial features that AI depth flattens out.
              </div>
            )}
          </div>
          <div>
            <label>Size preset</label>
            <select
              value={presetId}
              onChange={(e) => applyPreset(e.target.value)}
            >
              {dimPresets.length === 0 && (
                <option value="custom">Custom — set values manually</option>
              )}
              {dimPresets.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <div className="muted">
              Sets carve width + a sensible default depth. Tweak below.
            </div>
          </div>
          <div>
            <label>Carve width (physical X dimension)</label>
            <input
              type="number"
              value={Number(widthDisp.toFixed(inchUnits ? 2 : 0))}
              step={inchUnits ? 0.1 : 1}
              onChange={(e) =>
                setParams({
                  ...params,
                  width_mm:
                    Number(e.target.value) * (inchUnits ? MM_PER_IN : 1),
                })
              }
            />
            <div className="muted">
              In {inchUnits ? "inches" : "millimetres"}. Height is computed from
              image aspect ratio.
            </div>
          </div>
          {dim("max_depth_mm", "Max carve depth", 0.5, 30, 0.1)}
          {dim("base_thickness_mm", "Base thickness", 0, 20, 0.5)}
          {num("gaussian_blur_sigma", "Smoothing (blur σ)", 0, 6, 0.1)}
          {num("bilateral_strength", "Background smoothing (edge-preserving)", 0, 1, 0.05)}
          {num("detail", "Detail (sharpen relief)", 0, 1, 0.05)}
          <div>
            <label>Height curve (tonal hierarchy)</label>
            <select
              value={curvePreset}
              onChange={(e) => {
                const id = e.target.value;
                setCurvePreset(id);
                setParams((prev) => ({ ...prev, curve_points: CURVE_PRESETS[id] }));
              }}
            >
              <option value="linear">Linear — no remap</option>
              <option value="gentle">Gentle S — slight face pop</option>
              <option value="medium">Medium S — recess background</option>
              <option value="aggressive">Aggressive S — max hierarchy</option>
            </select>
            <div className="muted" style={{ fontSize: 12 }}>
              Pushes highlights (faces) up and shadows (background) down, like a
              carved bas-relief. Pair with Background smoothing for the cleanest
              subject-vs-field separation.
            </div>
          </div>
          {num("background_threshold", "Background flatten threshold", 0, 0.5, 0.01)}
          {num("target_max_dim_px", "Mesh resolution (max dim, px)", 200, 1200, 50)}

          <div className="row">
            <label
              style={{
                display: "inline-flex",
                gap: 6,
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
              Invert (dark = high)
            </label>
            <label
              style={{
                display: "inline-flex",
                gap: 6,
                textTransform: "none",
                letterSpacing: 0,
                fontSize: 13,
              }}
            >
              <input
                type="checkbox"
                checked={params.include_skirt}
                onChange={(e) =>
                  setParams({ ...params, include_skirt: e.target.checked })
                }
              />
              Skirt walls
            </label>
            <label
              style={{
                display: "inline-flex",
                gap: 6,
                textTransform: "none",
                letterSpacing: 0,
                fontSize: 13,
              }}
            >
              <input
                type="checkbox"
                checked={params.close_bottom}
                onChange={(e) =>
                  setParams({ ...params, close_bottom: e.target.checked })
                }
              />
              Closed bottom
            </label>
          </div>

          <div>
            <label>Units (inputs &amp; export)</label>
            <select
              value={params.units}
              onChange={(e) =>
                setParams({
                  ...params,
                  units: e.target.value as "mm" | "in",
                })
              }
            >
              <option value="mm">Millimetres</option>
              <option value="in">Inches</option>
            </select>
          </div>

          <div>
            <label>Output filename (without extension)</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. eagle_plaque"
            />
          </div>

          <button
            className="primary"
            onClick={onConvert}
            disabled={converting}
          >
            {converting ? (
              <>
                <span className="spinner" /> Building STL…
              </>
            ) : (
              "Export STL + 16-bit depth PNG"
            )}
          </button>

          {exports && (
            <div className="col" style={{ gap: 6 }}>
              <div className="ok">Exported.</div>
              <div className="muted">
                STL:{" "}
                <a href={api.exportUrl(exports.stl.id)} download={exports.stl.filename}>
                  {exports.stl.filename}
                </a>
              </div>
              <div className="muted">
                Depth PNG:{" "}
                <a
                  href={api.exportUrl(exports.depth_png.id)}
                  download={exports.depth_png.filename}
                >
                  {exports.depth_png.filename}
                </a>
              </div>
              {exports.aspire_steps && (
                <div className="muted">
                  Aspire steps:{" "}
                  <a
                    href={api.exportUrl(exports.aspire_steps.id)}
                    download={exports.aspire_steps.filename}
                  >
                    {exports.aspire_steps.filename}
                  </a>
                </div>
              )}
              {exports.stl.aspire_copy_path && (
                <div className="ok">
                  Copied to Aspire folder: <code>{exports.stl.aspire_copy_path}</code>
                </div>
              )}
              {!exports.stl.aspire_copy_path && (
                <div className="muted">
                  No Aspire folder set. Configure it in{" "}
                  <a onClick={() => navigate("/settings")}>Settings</a> to have
                  files saved directly there.
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {exports && (
        <div className="card col">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0, fontSize: 15 }}>
              3D viewer — exactly what Aspire will see
            </h3>
            <div className="muted" style={{ fontSize: 12 }}>
              The bit can't carve anything thinner than ~half its diameter, so
              ground-truth here matters.
            </div>
          </div>
          <StlViewer url={api.exportUrl(exports.stl.id)} height={500} />
        </div>
      )}
    </div>
  );
}
