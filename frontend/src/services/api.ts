import axios from "axios";
import type { Activity, Document, DocumentMetadataInput, Message, RagRefusal, SessionInfo, Source, User } from "../types";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000", headers: { "Content-Type": "application/json" } });
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("edurag_token") || sessionStorage.getItem("edurag_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const requestUrl = String(error.config?.url || "");
    const isLoginRequest = requestUrl.includes("/auth/login") || requestUrl.includes("/admin/login");

    // Backend giữ access token trong bộ nhớ. Khi container khởi động lại,
    // token cũ ở trình duyệt không còn hợp lệ và người dùng cần đăng nhập lại.
    if (status === 401 && !isLoginRequest) {
      [localStorage, sessionStorage].forEach((storage) => { storage.removeItem("edurag_token"); storage.removeItem("edurag_user"); });
      if (window.location.pathname !== "/login") {
        window.location.replace("/login");
      }
    }
    return Promise.reject(error);
  },
);

export async function login(username: string, password: string, remember = false): Promise<{ access_token: string; user: User }> {
  try {
    const { data } = await api.post("/auth/login", { username, password, remember });
    return { access_token: data.access_token, user: { ...data.user, role: "student" } };
  } catch {
    const { data } = await api.post("/admin/login", { username, password, remember });
    return { access_token: data.access_token, user: { ...data.user, role: "admin" } };
  }
}
export async function register(email: string, password: string, display_name: string) { const { data } = await api.post("/auth/register", { email, password, display_name }); return { access_token: data.access_token, user: { ...data.user, role: "student" as const } }; }
export async function requestPasswordReset(email: string) { const { data } = await api.post("/auth/forgot-password", { email }); return data; }
export async function resetPassword(token: string, new_password: string) { const { data } = await api.post("/auth/reset-password", { token, new_password }); return data; }
export async function getAuthProviders(): Promise<{ google: { enabled: boolean; client_id: string } }> { const { data } = await api.get("/auth/providers"); return data; }
export async function googleLogin(credential: string) { const { data } = await api.post("/auth/google", { credential }); return { access_token: data.access_token, user: { ...data.user, role: "student" as const } }; }
export async function logoutRequest() { await api.post("/auth/logout"); }
export async function getAccount(): Promise<User> { const { data } = await api.get("/account"); return data.user; }
export async function updateAccountProfile(display_name: string): Promise<User> { const { data } = await api.patch("/account/profile", { display_name }); return data.user; }
export async function changeAccountPassword(current_password: string, new_password: string) { const { data } = await api.post("/account/password", { current_password, new_password }); return data; }
export interface ChatAnswer { answer: string; sources: Source[]; retrieval_score: number; message_id: number; session_id: string }

/** Lỗi từ /chat/stream; `detail` là thông báo tiếng Việt an toàn để hiển thị cho người dùng. */
export class ChatStreamError extends Error {
  constructor(public detail: string) { super(detail); }
}

/**
 * Gọi /chat/stream (SSE). `onToken` nhận chữ nháp khi LLM đang sinh; kết quả trả về là
 * câu trả lời đã chuẩn hóa và phải thay thế phần chữ nháp.
 */
export async function askStream(
  question: string,
  session_id: string,
  document_filename: string | undefined,
  onToken: (text: string) => void,
): Promise<ChatAnswer> {
  const token = localStorage.getItem("edurag_token") || sessionStorage.getItem("edurag_token");
  const response = await fetch(`${api.defaults.baseURL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ question, session_id, document_filename }),
  });
  if (response.status === 401) {
    [localStorage, sessionStorage].forEach((storage) => { storage.removeItem("edurag_token"); storage.removeItem("edurag_user"); });
    if (window.location.pathname !== "/login") window.location.replace("/login");
  }
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null);
    throw new ChatStreamError(typeof body?.detail === "string" ? body.detail : "Không thể gửi câu hỏi lúc này. Vui lòng thử lại.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let final: ChatAnswer | null = null;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = /^event: (.+)$/m.exec(block)?.[1];
      const data = /^data: (.+)$/m.exec(block)?.[1];
      if (!event || !data) continue;
      const payload = JSON.parse(data);
      if (event === "token") onToken(payload.text);
      else if (event === "final") final = payload;
      else if (event === "error") throw new ChatStreamError(payload.detail);
    }
  }
  if (!final) throw new ChatStreamError("Kết nối bị gián đoạn trước khi nhận đủ câu trả lời. Vui lòng thử lại.");
  return final;
}

export async function ask(question: string, session_id: string, document_filename?: string): Promise<{ answer: string; sources: Source[]; retrieval_score: number; message_id: number; session_id: string }> { const { data } = await api.post("/chat", { question, session_id, document_filename }); return data; }
export async function saveFeedback(messageId: number, feedback: "up" | "down") { const { data } = await api.post(`/chat/${messageId}/feedback`, { feedback }); return data; }
export async function getSessions(): Promise<SessionInfo[]> { const { data } = await api.get("/sessions"); return data.sessions_detail || data.sessions.map((session_id: string) => ({ session_id })); }
export async function deleteSession(sessionId: string): Promise<{ status: string; session_id: string; count: number }> { const { data } = await api.delete(`/sessions/${encodeURIComponent(sessionId)}`); return data; }
export async function getHistory(sessionId: string): Promise<Message[]> { const { data } = await api.get(`/history/${sessionId}`); return data.messages.flatMap((item: { id: number; user_message: string; bot_response: string; sources: Source[]; retrieval_score: number; feedback?: "up" | "down"; timestamp: string }) => [{ role: "user" as const, content: item.user_message, timestamp: item.timestamp }, { id: item.id, role: "assistant" as const, content: item.bot_response, sources: item.sources, score: item.retrieval_score, feedback: item.feedback, timestamp: item.timestamp }]); }
export async function getDocuments(): Promise<Document[]> { const { data } = await api.get("/admin/documents"); return data.documents; }
export async function getDocumentPreview(filename: string): Promise<Blob> { const { data } = await api.get(`/documents/${encodeURIComponent(filename)}/preview`, { responseType: "blob" }); return data; }
export async function getStats() { const { data } = await api.get("/admin/stats"); return data; }
export async function getActivities(): Promise<Activity[]> { const { data } = await api.get("/admin/activities?limit=20"); return data.activities; }
export async function uploadDocument(file: File, metadata: DocumentMetadataInput = {}) { const form = new FormData(); form.append("file", file); Object.entries(metadata).forEach(([key, value]) => { if (value !== undefined && value !== "") form.append(key, String(value)); }); const { data } = await api.post("/admin/upload", form, { headers: { "Content-Type": "multipart/form-data" } }); return data; }
export async function updateDocumentMetadata(filename: string, metadata: DocumentMetadataInput) { const { data } = await api.patch(`/admin/documents/${encodeURIComponent(filename)}`, metadata); return data; }
export async function deleteDocument(filename: string) { await api.delete(`/admin/delete/${encodeURIComponent(filename)}`); }
export async function rebuildIndex(): Promise<{ message: string; processed_files: string[]; total_chunks: number; previous_collection: string }> {
  const { data } = await api.post("/admin/rebuild-index");
  return data;
}
export async function getRagRefusals(limit = 50): Promise<RagRefusal[]> { const { data } = await api.get(`/admin/rag-refusals?limit=${limit}`); return data.refusals; }
export default api;
