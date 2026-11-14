export type Role = "student" | "admin";

export interface User { id?: number; email: string; display_name?: string; role: Role }
export interface Source { filename: string; page?: number | null; display_name?: string | null; category?: string | null; issuing_unit?: string | null; document_year?: number | null; is_primary?: boolean; needs_review?: boolean; is_scan?: boolean }
export interface Message { id?: number; role: "user" | "assistant"; content: string; sources?: Source[]; score?: number; feedback?: "up" | "down"; timestamp?: string; streaming?: boolean }
export interface Document { id: number; filename: string; file_type: string; chunk_count: number; file_size_kb: number; uploaded_at: string; description?: string | null; display_name?: string | null; category?: string | null; issuing_unit?: string | null; document_year?: number | null; summary?: string | null; status?: string | null; reviewed_at?: string | null; reviewed_by?: string | null; needs_review_pages?: number }
export type ChunkFlag = "generic_label" | "too_short" | "long_label" | "garbled_text";
export interface DocumentChunk { id: string; content: string; page: number | null; extraction_method: string | null; table_index: number | null; table_row: number | null; table_caption: string | null; table_continued: boolean; ocr_model?: string | null; ocr_confidence?: number | null; review_status?: PageReviewStatus | null; review_reasons?: PageReviewReason[]; flags: ChunkFlag[] }
export type PageReviewStatus = "needs_review" | "confirmed" | "corrected";
export type PageReviewReason = "low_confidence" | "garbled_text" | "row_number_gap" | "malformed_date";
export interface PageSummary { page: number; extraction_method: string | null; ocr_model: string | null; ocr_confidence: number | null; review_status: PageReviewStatus | null; review_reasons: PageReviewReason[]; reviewed_by: string | null; reviewed_at: string | null; editable: boolean }
export interface DocumentMetadataInput { display_name?: string; category?: string; issuing_unit?: string; document_year?: number; summary?: string; status?: string }
export interface SessionInfo { session_id: string; title?: string; last_time?: string }
export interface Activity { id: number; action: "document_uploaded" | "document_updated" | "document_deleted" | "chat_processed" | "index_rebuilt" | "rag_refusal"; entity_type: string; entity_name?: string | null; actor_name: string; actor_role: Role; created_at: string }
export interface RagRefusal { id: number; question: string | null; actor: string; created_at: string }
