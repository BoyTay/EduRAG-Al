import { Trash, WarningCircle, X } from "@phosphor-icons/react";
import { useState } from "react";
import type { Document } from "../../types";

interface DeleteConfirmModalProps {
  document: Document;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

export function DeleteConfirmModal({
  document,
  onConfirm,
  onClose,
}: DeleteConfirmModalProps) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");

  const handleConfirm = async () => {
    setDeleting(true);
    setError("");
    try {
      await onConfirm();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Không thể xóa tài liệu. Vui lòng thử lại.");
      setDeleting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl transition-all"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header with red warning icon */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="flex size-11 items-center justify-center rounded-2xl bg-rose-50 text-rose-600 ring-1 ring-rose-500/20">
              <WarningCircle size={24} weight="duotone" />
            </span>
            <div>
              <h3 className="text-base font-bold text-slate-900">Xác nhận xóa tài liệu</h3>
              <p className="text-xs text-slate-400">Hành động này không thể hoàn tác</p>
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

        {/* Content */}
        <div className="mt-4 rounded-xl bg-slate-50 p-3.5 text-xs text-slate-600 leading-relaxed">
          <p>
            Bạn có chắc chắn muốn xóa vĩnh viễn tài liệu{" "}
            <strong className="font-bold text-slate-900">
              "{document.display_name || document.filename}"
            </strong>
            ?
          </p>
          <p className="mt-1.5 text-rose-600 font-medium">
            Toàn bộ {document.chunk_count} đoạn dữ liệu vector embedding trong ChromaDB sẽ bị xóa hoàn toàn.
          </p>
        </div>

        {error && <p className="mt-3 text-xs text-rose-600 font-semibold">{error}</p>}

        {/* Footer buttons */}
        <div className="mt-6 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            disabled={deleting}
            className="rounded-xl px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 transition"
          >
            Hủy bỏ
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={deleting}
            className="inline-flex items-center gap-1.5 rounded-xl bg-rose-600 px-4 py-2 text-xs font-semibold text-white shadow-sm shadow-rose-900/20 hover:bg-rose-700 disabled:opacity-50 transition"
          >
            <Trash size={15} weight="bold" />
            <span>{deleting ? "Đang xóa..." : "Xác nhận xóa"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
