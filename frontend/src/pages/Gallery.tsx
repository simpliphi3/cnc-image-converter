import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Project, relativeTime } from "../api";

export default function Gallery() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const navigate = useNavigate();

  async function refresh() {
    setLoading(true);
    try {
      setProjects(await api.listProjects());
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    refresh();
  }, []);

  async function onCreate() {
    const n = name.trim() || `Project ${new Date().toLocaleString()}`;
    const p = await api.createProject(n);
    setName("");
    navigate(`/project/${p.id}`);
  }

  async function onDelete(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm("Delete this project? Files on disk are removed too.")) return;
    await api.deleteProject(id);
    await refresh();
  }

  return (
    <div className="col" style={{ gap: 18 }}>
      <div className="card row" style={{ justifyContent: "space-between" }}>
        <div style={{ flex: 1 }}>
          <label>New project name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Eagle plaque, Kitchen sign…"
            onKeyDown={(e) => e.key === "Enter" && onCreate()}
          />
        </div>
        <div style={{ alignSelf: "end" }}>
          <button className="primary" onClick={onCreate}>
            + New Project
          </button>
        </div>
      </div>

      {loading ? (
        <div className="muted">
          <span className="spinner" /> Loading…
        </div>
      ) : projects.length === 0 ? (
        <div className="card muted">
          No projects yet. Create one above to start generating images.
        </div>
      ) : (
        <div className="gallery-grid">
          {projects.map((p) => (
            <div
              key={p.id}
              className="gallery-card"
              onClick={() => navigate(`/project/${p.id}`)}
            >
              <div className="gallery-thumb">
                {p.cover_image_id ? (
                  <img src={api.imageUrl(p.cover_image_id)} alt={p.name} />
                ) : (
                  <span>No images yet</span>
                )}
              </div>
              <div className="gallery-meta">
                <div className="name">{p.name}</div>
                <div
                  className="time row"
                  style={{ justifyContent: "space-between" }}
                >
                  <span>updated {relativeTime(p.updated_at)}</span>
                  <button className="danger" onClick={(e) => onDelete(p.id, e)}>
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
