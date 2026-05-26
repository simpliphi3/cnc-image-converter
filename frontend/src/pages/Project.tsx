import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ImageRec, Project as P, Turn } from "../api";

const ALL_MODELS = [
  { id: "openai", label: "OpenAI (gpt-image-1)" },
  { id: "gemini", label: "Google Gemini" },
];

export default function Project() {
  const { id } = useParams();
  const projectId = id!;
  const navigate = useNavigate();

  const [project, setProject] = useState<P | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [images, setImages] = useState<ImageRec[]>([]);
  const [prompt, setPrompt] = useState("");
  const [refIds, setRefIds] = useState<string[]>([]);
  const [refRecs, setRefRecs] = useState<ImageRec[]>([]);
  const [selectedModels, setSelectedModels] = useState<string[]>([
    "openai",
    "gemini",
  ]);
  const [useMemory, setUseMemory] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const d = await api.getProject(projectId);
    setProject(d.project);
    setTurns(d.turns);
    setImages(d.images);
  }, [projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    setRefRecs(refIds.map((rid) => images.find((i) => i.id === rid)).filter(Boolean) as ImageRec[]);
  }, [refIds, images]);

  const byTurnByModel = useMemo(() => {
    const m: Record<string, Record<string, ImageRec>> = {};
    for (const im of images) {
      if (im.role !== "generated" || !im.turn_id || !im.model) continue;
      (m[im.turn_id] ||= {})[im.model] = im;
    }
    return m;
  }, [images]);

  async function uploadFiles(files: FileList | File[]) {
    setErr(null);
    const arr = Array.from(files);
    const uploaded: string[] = [];
    for (const f of arr) {
      if (!f.type.startsWith("image/")) continue;
      try {
        const rec = await api.uploadReference(projectId, f);
        uploaded.push(rec.id);
      } catch (e: any) {
        setErr(e.message || String(e));
      }
    }
    await refresh();
    setRefIds((cur) => [...cur, ...uploaded]);
  }

  function removeRef(refId: string) {
    setRefIds((cur) => cur.filter((x) => x !== refId));
  }

  function toggleModel(mid: string) {
    setSelectedModels((cur) =>
      cur.includes(mid) ? cur.filter((m) => m !== mid) : [...cur, mid]
    );
  }

  async function onGenerate() {
    if (!prompt.trim()) {
      setErr("Add a prompt before generating.");
      return;
    }
    if (selectedModels.length === 0) {
      setErr("Pick at least one model.");
      return;
    }
    setErr(null);
    setGenerating(true);
    try {
      await api.generate(projectId, {
        prompt: prompt.trim(),
        reference_image_ids: refIds,
        models: selectedModels,
        use_session_memory: useMemory,
      });
      setRefIds([]);
      await refresh();
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setGenerating(false);
    }
  }

  function onRename() {
    if (!project) return;
    const n = prompt2("Rename project", project.name);
    if (n && n.trim()) api.renameProject(projectId, n.trim()).then(refresh);
  }

  return (
    <div className="col" style={{ gap: 16 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="row" style={{ gap: 12 }}>
          <button onClick={() => navigate("/")}>← Gallery</button>
          <h2 style={{ margin: 0, fontSize: 18 }}>{project?.name}</h2>
          <button onClick={onRename} title="Rename">
            ✎
          </button>
        </div>
        <div className="muted">
          {turns.length} turn{turns.length === 1 ? "" : "s"}
        </div>
      </div>

      <div
        className="prompt-bar"
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (e.dataTransfer.files?.length) uploadFiles(e.dataTransfer.files);
        }}
      >
        <textarea
          placeholder="Describe the carving you want. e.g. 'A bald eagle in flight, bas-relief style, plain background, high contrast.'"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />

        {refRecs.length > 0 && (
          <div className="refs-strip">
            {refRecs.map((r) => (
              <div className="ref-thumb" key={r.id}>
                <img src={api.imageUrl(r.id)} alt="reference" />
                <button onClick={() => removeRef(r.id)} title="Remove">
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        <div className={`drop-hint ${drag ? "dragover" : ""}`}>
          Drag-drop image(s) here to attach as reference — or generate from
          prompt only. Both work equally well.{" "}
          <label
            style={{
              display: "inline",
              cursor: "pointer",
              textDecoration: "underline",
              color: "var(--accent-2)",
              margin: 0,
              textTransform: "none",
              letterSpacing: 0,
              fontSize: 13,
            }}
          >
            browse
            <input
              type="file"
              accept="image/*"
              multiple
              hidden
              onChange={(e) =>
                e.target.files && uploadFiles(e.target.files)
              }
            />
          </label>
        </div>

        <div
          className="row"
          style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}
        >
          <div className="row" style={{ gap: 14, flexWrap: "wrap" }}>
            {ALL_MODELS.map((m) => (
              <label
                key={m.id}
                style={{
                  display: "inline-flex",
                  gap: 6,
                  alignItems: "center",
                  textTransform: "none",
                  letterSpacing: 0,
                  fontSize: 13,
                  color: "var(--text)",
                }}
              >
                <input
                  type="checkbox"
                  checked={selectedModels.includes(m.id)}
                  onChange={() => toggleModel(m.id)}
                />
                {m.label}
              </label>
            ))}
            <label
              style={{
                display: "inline-flex",
                gap: 6,
                alignItems: "center",
                textTransform: "none",
                letterSpacing: 0,
                fontSize: 13,
                color: "var(--muted)",
              }}
              title="Carry the most recent generation from each model into the next turn so iteration has memory."
            >
              <input
                type="checkbox"
                checked={useMemory}
                onChange={(e) => setUseMemory(e.target.checked)}
              />
              session memory
            </label>
          </div>
          <button
            className="primary"
            onClick={onGenerate}
            disabled={generating}
          >
            {generating ? (
              <>
                <span className="spinner" /> Generating…
              </>
            ) : refIds.length > 0 ? (
              "Generate from prompt + references"
            ) : (
              "Generate from prompt"
            )}
          </button>
        </div>
        {err && <div className="error">{err}</div>}
      </div>

      <div className="model-grid">
        {selectedModels.map((m) => (
          <div key={m} className="model-col">
            <h3>{ALL_MODELS.find((x) => x.id === m)?.label ?? m}</h3>
            {turns.length === 0 && (
              <div className="muted">Results will appear here.</div>
            )}
            {[...turns].reverse().map((t) => {
              const img = byTurnByModel[t.id]?.[m];
              return (
                <div className="model-turn" key={t.id}>
                  <div className="prompt">
                    Turn {t.idx + 1}: {t.prompt}{" "}
                    {t.ref_image_ids.length > 0 && (
                      <span style={{ color: "var(--accent)" }}>
                        + {t.ref_image_ids.length} ref
                      </span>
                    )}
                  </div>
                  {!img ? (
                    <div className="muted">— no result —</div>
                  ) : img.error ? (
                    <div className="error">{img.error}</div>
                  ) : (
                    <>
                      <img src={api.imageUrl(img.id)} alt={t.prompt} />
                      <div className="actions">
                        <button
                          onClick={() => setRefIds((cur) => [...cur, img.id])}
                        >
                          Use as reference for next turn
                        </button>
                        <button
                          onClick={() =>
                            navigate(`/project/${projectId}/mockup/${img.id}`)
                          }
                          title="See what this would look like carved into wood"
                        >
                          Mockup on wood
                        </button>
                        <button
                          className="primary"
                          onClick={() =>
                            navigate(`/project/${projectId}/convert/${img.id}`)
                          }
                        >
                          Convert to STL
                        </button>
                        <button
                          onClick={() =>
                            navigate(
                              `/project/${projectId}/vectorize/${img.id}`
                            )
                          }
                        >
                          Vectorize (SVG)
                        </button>
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function prompt2(msg: string, def: string): string | null {
  return window.prompt(msg, def);
}
