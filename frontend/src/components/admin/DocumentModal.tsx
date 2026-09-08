import { CloudArrowUp, PencilSimple, X } from "@phosphor-icons/react";
import { useState } from "react";
import type { Document, DocumentMetadataInput } from "../../types";

const CATEGORIES = [
  "Công tác sinh viên",
  "Đào tạo",
  "Học bổng",
  "Học phí & Học phần",
  "Tốt nghiệp & Chuẩn đầu ra",
  "Khen thưởng & Kỷ luật",
  "Khác",
];

interface DocumentModalProps {
  mode: "upload" | "edit";
  initialDoc?: Document | null;
  selectedFile?: File | null;
  onFileSelect?: (file: File) => void;
  onSubmit: (metadata: DocumentMetadataInput, file?: File) => Promise<void>;
  onClose: () => void;
}

export function DocumentModal({
  mode,
  initialDoc,
  selectedFile: initialFile,
  onSubmit,
  onClose,
}: DocumentModalProps) {
  const [file, setFile] = useState<File | null>(initialFile || null);
  const [metadata, setMetadata] = useState<DocumentMetadataInput>({
    display_name:
      initialDoc?.display_name ||
      initialFile?.name.replace(/[_-]/g, " ").replace(/\.[^.]+$/, "") ||
      "",
    category: initialDoc?.category || "Đào tạo",
    issuing_unit: initialDoc?.issuing_unit || "",
    document_year:
      initialDoc?.document_year ||
      (initialDoc?.uploaded_at ? new Date(initialDoc.uploaded_at).getFullYear() : new Date().getFullYear()),
    status: initialDoc?.status || "active",
    summary: initialDoc?.summary || initialDoc?.description || "",
  });

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const update = (field: keyof DocumentMetadataInput, value: string | number) => {
    setMetadata((prev) => ({ ...prev, [field]: value }));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      setFile(f);
      if (!metadata.display_name) {
        update("display_name", f.name.replace(/[_-]/g, " ").replace(/\.[^.]+$/, ""));
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === "upload" && !file) {
      setError("Vui lòng chọn một file PDF hoặc DOCX để tải lên.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await onSubmit(metadata, file || undefined);
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Không thể lưu tài liệu. Vui lòng thử lại.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-xl rounded-3xl border border-slate-200/90 bg-white p-6 shadow-2xl transition-all"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2.5">
            <span
              className={`flex size-10 items-center justify-center rounded-2xl ${
                mode === "upload"
                  ? "bg-emerald-50 text-emerald-600 ring-1 ring-emerald-500/20"
                  : "bg-blue-50 text-blue-600 ring-1 ring-blue-500/20"
              }`}
            >
              {mode === "upload" ? (
                <CloudArrowUp size={22} weight="bold" />
              ) : (
                <PencilSimple size={20} weight="bold" />
              )}
            </span>
            <div>
              <h3 className="text-base font-bold text-slate-900">
                {mode === "upload" ? "Tải lên tài liệu học vụ mới" : "Chỉnh sửa thông tin tài liệu"}
              </h3>
              <p className="text-xs text-slate-400">
                {mode === "upload"
                  ? "Hệ thống sẽ tự động tách đoạn và lập chỉ mục vector RAG."
                  : initialDoc?.filename}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex size-8 items-center justify-center rounded-xl text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-5 space-y-4 text-xs font-semibold text-slate-700">
          {/* File input (if upload mode) */}
          {mode === "upload" && (
            <div>
              <label className="block text-slate-800 font-bold mb-1.5">
                Chọn file văn bản (.pdf, .docx)
              </label>
              <label className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50/60 p-4 text-center hover:border-emerald-400 hover:bg-emerald-50/20 cursor-pointer transition">
                <CloudArrowUp size={28} className="text-emerald-600" />
                <span className="mt-2 text-xs font-medium text-slate-600">
                  {file ? (
                    <strong className="text-emerald-700 font-bold">{file.name}</strong>
                  ) : (
                    "Kéo thả hoặc nhấn để chọn file PDF/DOCX từ máy tính"
                  )}
                </span>
                <input
                  type="file"
                  accept=".pdf,.docx"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </label>
            </div>
          )}

          {/* Display Name */}
          <div>
            <label className="block text-slate-800 font-bold mb-1.5">
              Tên hiển thị văn bản <span className="text-rose-500">*</span>
            </label>
            <input
              required
              value={metadata.display_name || ""}
              onChange={(e) => update("display_name", e.target.value)}
              placeholder="Ví dụ: Quy chế đào tạo theo tín chỉ"
              className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-xs text-slate-900 font-normal outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 transition"
            />
          </div>

          {/* Category & Issuing Unit in 2 columns */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="block text-slate-800 font-bold mb-1.5">
                Danh mục học vụ
              </label>
              <select
                value={metadata.category || "Đào tạo"}
                onChange={(e) => update("category", e.target.value)}
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-900 font-normal outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 transition"
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-slate-800 font-bold mb-1.5">
                Đơn vị ban hành
              </label>
              <input
                value={metadata.issuing_unit || ""}
                onChange={(e) => update("issuing_unit", e.target.value)}
                placeholder="Ví dụ: Phòng Quản lý Đào tạo"
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-xs text-slate-900 font-normal outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 transition"
              />
            </div>
          </div>

          {/* Year & Status in 2 columns */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="block text-slate-800 font-bold mb-1.5">
                Năm ban hành
              </label>
              <input
                type="number"
                min="1990"
                max="2099"
                value={metadata.document_year || new Date().getFullYear()}
                onChange={(e) => update("document_year", Number(e.target.value))}
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-xs text-slate-900 font-normal outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 transition"
              />
            </div>

            <div>
              <label className="block text-slate-800 font-bold mb-1.5">
                Trạng thái hiệu lực
              </label>
              <select
                value={metadata.status || "active"}
                onChange={(e) => update("status", e.target.value)}
                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-900 font-normal outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 transition"
              >
                <option value="active">Còn hiệu lực / Hoạt động</option>
                <option value="updating">Đang cập nhật</option>
                <option value="expired">Hết hiệu lực</option>
              </select>
            </div>
          </div>

          {/* Summary / Description */}
          <div>
            <label className="block text-slate-800 font-bold mb-1.5">
              Tóm tắt văn bản quy chế
            </label>
            <textarea
              rows={3}
              value={metadata.summary || ""}
              onChange={(e) => update("summary", e.target.value)}
              placeholder="Tóm tắt phạm vi, đối tượng áp dụng và nội dung cốt lõi của văn bản để hỗ trợ AI đối chiếu ngữ cảnh."
              className="w-full rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-900 font-normal leading-relaxed outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 transition"
            />
          </div>

          {error && <p className="text-xs text-rose-600 font-semibold">{error}</p>}

          {/* Footer Buttons */}
          <div className="flex items-center justify-end gap-2.5 border-t border-slate-100 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 transition"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-emerald-900/20 hover:bg-emerald-700 disabled:opacity-50 transition"
            >
              {saving ? "Đang xử lý & lập chỉ mục RAG..." : mode === "upload" ? "Tải lên và Index RAG" : "Lưu thay đổi"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
