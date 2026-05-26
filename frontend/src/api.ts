export type Project = {
  id: string;
  name: string;
  created_at: number;
  updated_at: number;
  cover_image_id?: string | null;
  cover_filename?: string | null;
};

export type ImageRec = {
  id: string;
  project_id: string;
  turn_id?: string | null;
  model?: string | null;
  role: "reference" | "generated" | "depth" | "export";
  filename: string;
  width?: number | null;
  height?: number | null;
  error?: string | null;
  created_at: number;
};

export type Turn = {
  id: string;
  project_id: string;
  idx: number;
  prompt: string;
  ref_image_ids: string[];
  models: string[];
  created_at: number;
};

export type ExportRec = {
  id: string;
  project_id: string;
  source_image_id?: string | null;
  kind: "stl" | "svg" | "depth_png";
  params: Record<string, unknown>;
  filename: string;
  aspire_copy_path?: string | null;
  created_at: number;
};

export type Settings = {
  aspire_folder: string | null;
  default_units: "mm" | "in";
  last_used_models: string[];
  has_openai_key: boolean;
  has_google_key: boolean;
  depth: { device: string; model: string | null; loaded: boolean };
};

async function jfetch<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`${r.status}: ${text}`);
  }
  return r.json();
}

export const api = {
  listProjects: () => jfetch<Project[]>("/api/projects"),
  createProject: (name: string) =>
    jfetch<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  getProject: (id: string) =>
    jfetch<{
      project: Project;
      turns: Turn[];
      images: ImageRec[];
      exports: ExportRec[];
    }>(`/api/projects/${id}`),
  renameProject: (id: string, name: string) =>
    jfetch<Project>(`/api/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  deleteProject: (id: string) =>
    jfetch<{ ok: boolean }>(`/api/projects/${id}`, { method: "DELETE" }),

  uploadReference: async (projectId: string, file: File): Promise<ImageRec> => {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`/api/projects/${projectId}/references`, {
      method: "POST",
      body: fd,
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },

  generate: (
    projectId: string,
    body: {
      prompt: string;
      reference_image_ids: string[];
      models: string[];
      use_session_memory?: boolean;
    }
  ) =>
    jfetch<{ turn: Turn; results: ImageRec[] }>(
      `/api/projects/${projectId}/generate`,
      { method: "POST", body: JSON.stringify(body) }
    ),

  convert: (body: {
    image_id: string;
    params: Record<string, unknown>;
    output_basename?: string;
  }) =>
    jfetch<{ stl: ExportRec; depth_png: ExportRec }>("/api/convert", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  vectorize: (body: {
    image_id: string;
    params: Record<string, unknown>;
    output_basename?: string;
    preview_only?: boolean;
  }) =>
    jfetch<{
      svg: string;
      width: number;
      height: number;
      svg_export?: ExportRec;
    }>("/api/vectorize", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getSettings: () => jfetch<Settings>("/api/settings"),
  patchSettings: (body: Partial<Settings>) =>
    jfetch<Settings>("/api/settings", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  imageUrl: (id: string) => `/api/images/${id}/file`,
  exportUrl: (id: string) => `/api/exports/${id}/file`,

  depthPreviewBlob: async (imageId: string): Promise<Blob> => {
    const r = await fetch("/api/depth/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_id: imageId }),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.blob();
  },
};

export function relativeTime(ts: number): string {
  const diff = (Date.now() / 1000 - ts) | 0;
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${(diff / 60) | 0}m ago`;
  if (diff < 86400) return `${(diff / 3600) | 0}h ago`;
  return `${(diff / 86400) | 0}d ago`;
}
