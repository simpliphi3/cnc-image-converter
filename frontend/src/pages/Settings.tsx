import { useEffect, useState } from "react";
import { api, Settings as S } from "../api";

export default function Settings() {
  const [s, setS] = useState<S | null>(null);
  const [folder, setFolder] = useState("");
  const [units, setUnits] = useState<"mm" | "in">("mm");
  const [saving, setSaving] = useState(false);

  async function refresh() {
    const x = await api.getSettings();
    setS(x);
    setFolder(x.aspire_folder || "");
    setUnits(x.default_units);
  }
  useEffect(() => {
    refresh();
  }, []);

  async function save() {
    setSaving(true);
    try {
      const next = await api.patchSettings({
        aspire_folder: folder,
        default_units: units,
      } as any);
      setS(next);
    } finally {
      setSaving(false);
    }
  }

  const [picking, setPicking] = useState(false);
  async function onBrowse() {
    setPicking(true);
    try {
      const r = await api.pickFolder(folder || null);
      if (r.path) setFolder(r.path);
    } catch (e: any) {
      alert(`Folder picker failed: ${e.message || e}`);
    } finally {
      setPicking(false);
    }
  }

  if (!s) return <div className="muted">Loading…</div>;

  return (
    <div className="col" style={{ gap: 16, maxWidth: 720 }}>
      <div className="card col">
        <h3 style={{ margin: 0 }}>Aspire output folder</h3>
        <div className="muted">
          Full path on this PC where finished STL, depth PNG, and SVG exports
          should be copied. Point this at the folder your Aspire library reads
          from and they'll just appear there.
        </div>
        <div className="row" style={{ alignItems: "stretch" }}>
          <input
            type="text"
            value={folder}
            onChange={(e) => setFolder(e.target.value)}
            placeholder="e.g. C:\Users\dad\Documents\Aspire Imports"
          />
          <button onClick={onBrowse} disabled={picking}>
            {picking ? "…" : "Browse…"}
          </button>
        </div>
        <div>
          <label>Default export units</label>
          <select
            value={units}
            onChange={(e) => setUnits(e.target.value as "mm" | "in")}
          >
            <option value="mm">Millimetres</option>
            <option value="in">Inches</option>
          </select>
        </div>
        <button className="primary" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>

      <div className="card col">
        <h3 style={{ margin: 0 }}>API keys</h3>
        <div className="muted">
          Set keys by editing the <code>.env</code> file in the install
          directory, then restart the app. Never leaves this computer.
        </div>
        <div>
          OpenAI: {s.has_openai_key ? <span className="ok">configured</span> : <span className="error">missing</span>}
        </div>
        <div>
          Google Gemini:{" "}
          {s.has_google_key ? <span className="ok">configured</span> : <span className="error">missing</span>}
        </div>
      </div>

      <div className="card col">
        <h3 style={{ margin: 0 }}>Depth engine</h3>
        <div className="muted">
          Depth estimation runs locally on this PC. The model downloads once on
          first conversion (~100MB).
        </div>
        <div>Device: <b>{s.depth.device}</b></div>
        <div>Model: <code>{s.depth.model || "(not yet loaded)"}</code></div>
        <div>Loaded: {s.depth.loaded ? "yes" : "no (loads on first STL conversion)"}</div>
      </div>
    </div>
  );
}
