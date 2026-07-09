const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("exskill_token");
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, { headers, ...options });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Persona ──────────────────────────────────────────

export interface PersonaSummary {
  id: string;
  name: string;
  display_name: string | null;
  status: string;
  tags: Record<string, any>[];
  created_at: string;
  updated_at: string;
}

export interface PersonaDetail extends PersonaSummary {
  hard_rules: Record<string, any>[];
  identity: Record<string, any>;
  speaking_style: Record<string, any>;
  emotional_patterns: Record<string, any>;
  relational_behavior: Record<string, any>;
  avatar_url: string | null;
  source_files: Record<string, any>[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export const personaApi = {
  list: (status?: string, page = 1, pageSize = 20) =>
    request<PaginatedResponse<PersonaSummary>>(
      `/personas?status=${status || ""}&page=${page}&page_size=${pageSize}`
    ),
  get: (id: string) => request<PersonaDetail>(`/personas/${id}`),
  create: (name: string, displayName?: string) =>
    request<PersonaDetail>("/personas", {
      method: "POST",
      body: JSON.stringify({ name, display_name: displayName }),
    }),
  update: (id: string, data: Partial<PersonaDetail>) =>
    request<PersonaDetail>(`/personas/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/personas/${id}`, { method: "DELETE" }),
};

// ── Upload ────────────────────────────────────────────

export interface UploadResponse {
  upload_id: string;
  status: string;
  filename: string;
  file_type: string;
  file_size: number | null;
  created_at: string;
}

export interface UploadStatusResponse {
  upload_id: string;
  status: string;
  progress_pct: number;
  stage: string | null;
  message_count: number | null;
  error_message: string | null;
}

export const uploadApi = {
  upload: async (personaId: string, file: File, fileType: string) => {
    const formData = new FormData();
    formData.append("file", file);
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(
      `${API_BASE}/personas/${personaId}/upload?file_type=${fileType}`,
      { method: "POST", body: formData, headers }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Upload failed");
    }
    return res.json() as Promise<UploadResponse>;
  },
  status: (taskId: string) =>
    request<UploadStatusResponse>(`/upload/${taskId}/status`),
  list: (personaId: string) =>
    request<UploadResponse[]>(`/personas/${personaId}/uploads`),
};

// ── Extraction ────────────────────────────────────────

export interface ExtractionStatusResponse {
  task_id: string;
  status: string;
  progress_pct: number;
  stage: string | null;
  error: string | null;
}

export const extractionApi = {
  extractAll: (personaId: string) =>
    request<{ status: string; persona_id: string }>(
      `/personas/${personaId}/extract/all`,
      { method: "POST" }
    ),
  status: (personaId: string) =>
    request<ExtractionStatusResponse>(
      `/personas/${personaId}/extract/status`
    ),
};

export interface MemoryResponse {
  id: string;
  persona_id: string;
  category: string;
  title: string | null;
  content: string;
  participants: Record<string, any>[];
  occurred_at: string | null;
  location: string | null;
  emotional_tone: string | null;
  importance: number;
  created_at: string;
}

export const memoryApi = {
  list: (personaId: string, category?: string, page = 1, pageSize = 20) =>
    request<PaginatedResponse<MemoryResponse>>(
      `/personas/${personaId}/memories?category=${category || ""}&page=${page}&page_size=${pageSize}`
    ),
  create: (personaId: string, data: Partial<MemoryResponse>) =>
    request<MemoryResponse>(`/personas/${personaId}/memories`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  delete: (memoryId: string) =>
    request<void>(`/memories/${memoryId}`, { method: "DELETE" }),
  deleteAll: (personaId: string) =>
    request<void>(`/personas/${personaId}/memories`, { method: "DELETE" }),
};

// ── Chat ──────────────────────────────────────────────

export interface SessionSummary {
  id: string;
  persona_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface MessageResponse {
  id: string;
  role: string;
  content: string;
  retrieved_memories: Record<string, any>[];
  created_at: string;
}

export const chatApi = {
  sessions: (personaId: string) =>
    request<SessionSummary[]>(`/personas/${personaId}/conversations`),
  createSession: (personaId: string, title?: string) =>
    request<SessionSummary>(`/personas/${personaId}/conversations`, {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  messages: (conversationId: string) =>
    request<MessageResponse[]>(`/conversations/${conversationId}/messages`),
  deleteSession: (conversationId: string) =>
    request<void>(`/conversations/${conversationId}`, { method: "DELETE" }),
  deleteMessage: (messageId: string) =>
    request<void>(`/messages/${messageId}`, { method: "DELETE" }),
};

// ── SSE Chat Stream ───────────────────────────────────

export function streamChat(
  personaId: string,
  content: string,
  onToken: (token: string) => void,
  onDone: (fullText: string, messageId: string) => void,
  onError: (error: string) => void
) {
  const controller = new AbortController();
  const token = getAuthToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  fetch(`${API_BASE}/personas/${personaId}/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({ content }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "token") onToken(data.token);
              else if (data.type === "done") onDone(data.full_text, data.message_id);
              else if (data.type === "error") onError(data.message);
            } catch {
              // Skip unparseable lines
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") onError(err.message);
    });

  return controller;
}
