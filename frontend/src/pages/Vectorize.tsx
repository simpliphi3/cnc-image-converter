import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ExportRec } from "../api";

type VParams = {
  threshold: number;
  invert: boolean;
  turdsize: number;
  alphamax: number;
  opttolerance: number;
  max_dim_px: number;
};

const DEFAULTS: VParams = {
  threshold: 128,
  invert: false,
  turdsize: 4,
  alphamax: 1.0,
  opttolerance: 0.2,
  max_dim_px: 1500,
};

export default function Vectorize() {
  const { id: projectId, imageId } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useState<VParams>(DEFAULTS);
  const [svg, setSvg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [rec, setRec] = useState<ExportRec | null>(null);
  const [name, setName] = useState("");

  async function preview() {
    if (!imageId) return;
    setLoading(true);
    setErr(null);
    try {
      const r = await api.vectorize({
        image_id: imageId,
        params,
        preview_only: true,
      });
      setSvg(r.svg);
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const t = setTimeout(() => preview(), 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(params), imageId]);

  async function onExport() {
    if (!imageId) return;
    setExporting(true);
    setRec(null);
    try {
      const r = await api.vectorize({
        image_id: imageId,
        params,
        output_basename: name.trim() || undefined,
      });
      if (r.svg_export) setRec(r.svg_export);
    } catch (e: any) {
      alert(e.message || String(e));
    } finally {
      setExporting(false);
    }
  }

  function num(key: keyof VParams, label: string, min: number, max: number, step: number) {
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

  return (
    <div className="col" style={{ gap: 14 }}>
      <div className="row">
        <button onClick={() => navigate(`/project/${projectId}`)}>← Back</button>
        <h2 style={{ margin: 0, fontSize: 18 }}>Vectorize → SVG</h2>
      </div>

      <div className="split">
        <div className="preview">
          <div className="muted">Source image</div>
          {imageId && <img src={api.imageUrl(imageId)} alt="source" />}
          <div className="muted">SVG preview</div>
          {loading ? (
            <div className="muted">
              <span className="spinner" /> Tracing…
            </div>
          ) : err ? (
            <div className="error">{err}</div>
          ) : svg ? (
            <div
              dangerouslySetInnerHTML={{ __html: svg }}
              style={{ background: "white", borderRadius: 8 }}
            />
          ) : null}
        </div>

        <div className="card col">
          {num("threshold", "Threshold (darker → solid)", 0, 255, 1)}
          {num("turdsize", "Despeckle", 0, 50, 1)}
          {num("alphamax", "Corner smoothing", 0, 1.3, 0.05)}
          {num("opttolerance", "Curve fit tolerance", 0, 1.5, 0.05)}
          {num("max_dim_px", "Pre-trace max dim (px)", 400, 3000, 50)}

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
            Invert (lighter → solid)
          </label>

          <div>
            <label>Output filename (without extension)</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. logo_paths"
            />
          </div>

          <button className="primary" onClick={onExport} disabled={exporting}>
            {exporting ? (
              <>
                <span className="spinner" /> Exporting…
              </>
            ) : (
              "Export SVG"
            )}
          </button>

          {rec && (
            <div className="col" style={{ gap: 6 }}>
              <div className="ok">
                Exported:{" "}
                <a href={api.exportUrl(rec.id)} download={rec.filename}>
                  {rec.filename}
                </a>
              </div>
              {rec.aspire_copy_path && (
                <div className="ok">
                  Copied to Aspire folder:{" "}
                  <code>{rec.aspire_copy_path}</code>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
