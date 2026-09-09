export type Role = "student" | "admin";

export interface User { id?: number; email: string; display_name?: string; role: Role }
export interface Source { filename: string; page?: number | null; display_name?: string | null; category?: string | null; issuing_unit?: string | null; document_year?: number | null; is_primary?: boolean }
export interface Message { id?: number; role: "user" | "assistant"; content: string; sources?: Source[]; score?: number; feedback?: "up" | "down"; timestamp?: string }
export interface Document { id: number; filename: string; file_type: string; chunk_count: number; file_size_kb: number; uploaded_at: string; description?: string | null; display_name?: string | null; category?: string | null; issuing_unit?: string | null; document_year?: number | null; summary?: string | null; status?: string | null }
export interface DocumentMetadataInput { display_name?: string; category?: string; issuing_unit?: string; document_year?: number; summary?: string; status?: string }
export interface SessionInfo { session_id: string; title?: string; last_time?: string }
export interface Activity { id: number; action: "document_uploaded" | "document_updated" | "document_deleted" | "chat_processed" | "index_rebuilt"; entity_type: string; entity_name?: string | null; actor_name: string; actor_role: Role; created_at: string }
