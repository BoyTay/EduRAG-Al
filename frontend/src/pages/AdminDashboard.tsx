import {
  ChatCircleText,
  ChartPieSlice,
  FileText,
  Plus,
} from "@phosphor-icons/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CategoryChart } from "../components/admin/CategoryChart";
import { DeleteConfirmModal } from "../components/admin/DeleteConfirmModal";
import { DocumentModal } from "../components/admin/DocumentModal";
import { DocumentTable } from "../components/admin/DocumentTable";
import { RecentActivities } from "../components/admin/RecentActivities";
import {
  deleteDocument,
  getActivities,
  getDocuments,
  getStats,
  updateDocumentMetadata,
  uploadDocument,
} from "../services/api";
import type { Document, DocumentMetadataInput } from "../types";

export function AdminDashboard() {
  const queryClient = useQueryClient();

  const { data: docs = [] } = useQuery({
    queryKey: ["documents"],
    queryFn: getDocuments,
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });

  const { data: activities = [] } = useQuery({
    queryKey: ["activities"],
    queryFn: getActivities,
  });

  // Modal states
  const [modalMode, setModalMode] = useState<"upload" | "edit" | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [deletingDoc, setDeletingDoc] = useState<Document | null>(null);

  // Stats calculation
  const totalFeedback = (stats?.total_feedback_up || 0) + (stats?.total_feedback_down || 0);
  const satisfaction = totalFeedback ? Math.round((stats.total_feedback_up / totalFeedback) * 100) : null;

  const refreshData = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["documents"] }),
      queryClient.invalidateQueries({ queryKey: ["stats"] }),
      queryClient.invalidateQueries({ queryKey: ["activities"] }),
    ]);
  };

  const handleSaveDocument = async (metadata: DocumentMetadataInput, file?: File) => {
    if (modalMode === "upload" && file) {
      await uploadDocument(file, metadata);
    } else if (modalMode === "edit" && selectedDoc) {
      await updateDocumentMetadata(selectedDoc.filename, metadata);
    }
    await refreshData();
  };

  const handleDeleteDocument = async () => {
    if (!deletingDoc) return;
    await deleteDocument(deletingDoc.filename);
    await refreshData();
  };

  return (
    <section className="h-full min-h-0 overflow-y-auto bg-[#f8fafc] px-4 py-6 sm:px-6 md:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        {/* Header Bar */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-bold tracking-[0.14em] text-emerald-600 uppercase">
              QUẢN TRỊ
            </p>
            <h1 className="mt-1 text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
              Tổng quan hệ thống
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-slate-500">
              Theo dõi và quản lý dữ liệu, câu hỏi và hiệu quả hoạt động của EduRAG.
            </p>
          </div>

          {/* + Tải tài liệu mới Button */}
          <button
            type="button"
            onClick={() => {
              setSelectedDoc(null);
              setModalMode("upload");
            }}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-bold text-white shadow-sm shadow-emerald-950/20 hover:bg-emerald-700 active:scale-[0.98] transition self-start sm:self-auto"
          >
            <Plus size={16} weight="bold" />
            <span>Tải tài liệu mới</span>
          </button>
        </div>

        {/* 3 Metric Summary Cards */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* Card 1: Tổng tài liệu */}
          <div className="relative overflow-hidden rounded-2xl border border-slate-200/90 bg-white p-5 shadow-[0_2px_12px_rgba(0,0,0,0.03)] flex items-center justify-between">
            <div>
              <div className="flex size-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
                <FileText size={22} weight="duotone" />
              </div>
              <p className="mt-4 text-xs font-medium text-slate-500">Tổng tài liệu</p>
              <div className="mt-1 flex items-baseline gap-2.5">
                <span className="text-3xl font-extrabold tracking-tight text-slate-900">
                  {docs.length}
                </span>
                <span className="inline-flex items-center rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                  {stats?.total_chunks || 0} đoạn vector
                </span>
              </div>
            </div>

            {/* Decorative Soft Watermark Icon */}
            <div className="absolute -right-2 -bottom-2 flex size-24 items-center justify-center rounded-3xl bg-emerald-50/60 text-emerald-600/25 pointer-events-none">
              <FileText size={52} weight="duotone" />
            </div>
          </div>

          {/* Card 2: Tổng câu hỏi */}
          <div className="relative overflow-hidden rounded-2xl border border-slate-200/90 bg-white p-5 shadow-[0_2px_12px_rgba(0,0,0,0.03)] flex items-center justify-between">
            <div>
              <div className="flex size-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                <ChatCircleText size={22} weight="duotone" />
              </div>
              <p className="mt-4 text-xs font-medium text-slate-500">Tổng câu hỏi</p>
              <div className="mt-1 flex items-baseline gap-2.5">
                <span className="text-3xl font-extrabold tracking-tight text-slate-900">
                  {stats?.total_messages || 0}
                </span>
                <span className="inline-flex items-center rounded-md bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-700">
                  {stats?.total_sessions || 0} phiên chat
                </span>
              </div>
            </div>

            {/* Decorative Soft Watermark Icon */}
            <div className="absolute -right-2 -bottom-2 flex size-24 items-center justify-center rounded-3xl bg-blue-50/60 text-blue-600/25 pointer-events-none">
              <ChatCircleText size={52} weight="duotone" />
            </div>
          </div>

          {/* Card 3: Tỷ lệ hài lòng */}
          <div className="relative overflow-hidden rounded-2xl border border-slate-200/90 bg-white p-5 shadow-[0_2px_12px_rgba(0,0,0,0.03)] flex items-center justify-between sm:col-span-2 lg:col-span-1">
            <div>
              <div className="flex size-10 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
                <ChartPieSlice size={22} weight="duotone" />
              </div>
              <p className="mt-4 text-xs font-medium text-slate-500">Tỷ lệ hài lòng</p>
              <div className="mt-1 flex items-baseline gap-2.5">
                <span className="text-3xl font-extrabold tracking-tight text-slate-900">
                  {satisfaction === null ? "—" : `${satisfaction}%`}
                </span>
                <span className="inline-flex items-center rounded-md bg-purple-50 px-2 py-0.5 text-[11px] font-semibold text-purple-700">
                  {stats?.total_feedback_up || 0} đánh giá tốt
                </span>
              </div>
            </div>

            {/* Decorative Soft Watermark Icon */}
            <div className="absolute -right-2 -bottom-2 flex size-24 items-center justify-center rounded-3xl bg-purple-50/60 text-purple-600/25 pointer-events-none">
              <ChartPieSlice size={52} weight="duotone" />
            </div>
          </div>
        </div>

        {/* Center: Document Table */}
        <DocumentTable
          documents={docs}
          onEdit={(doc) => {
            setSelectedDoc(doc);
            setModalMode("edit");
          }}
          onDelete={(doc) => setDeletingDoc(doc)}
        />

        {/* Bottom Grid: Recent Activities & Category Distribution */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Left: Hoạt động gần đây */}
          <RecentActivities activities={activities} />

          {/* Right: Phân bố danh mục tài liệu */}
          <CategoryChart documents={docs} />
        </div>
      </div>

      {/* Document Upload / Edit Modal */}
      {modalMode && (
        <DocumentModal
          mode={modalMode}
          initialDoc={selectedDoc}
          onSubmit={handleSaveDocument}
          onClose={() => {
            setModalMode(null);
            setSelectedDoc(null);
          }}
        />
      )}

      {/* Delete Confirmation Dialog */}
      {deletingDoc && (
        <DeleteConfirmModal
          document={deletingDoc}
          onConfirm={handleDeleteDocument}
          onClose={() => setDeletingDoc(null)}
        />
      )}
    </section>
  );
}
