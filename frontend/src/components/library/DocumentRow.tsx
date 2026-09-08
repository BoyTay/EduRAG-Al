import { Buildings, Eye, FileDoc, FilePdf, FileText, Sparkle } from "@phosphor-icons/react";
import type { Document } from "../../types";

interface DocumentRowProps {
  document: Document;
  isSelected?: boolean;
  onPreview: (document: Document) => void;
  onAsk: (document: Document) => void;
}

function formatSize(sizeKb: number) {
  return sizeKb >= 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(sizeKb))} KB`;
}

export function DocumentRow({ document, isSelected, onPreview, onAsk }: DocumentRowProps) {
  const isPdf = document.file_type.toLowerCase() === "pdf";
  const isDocx = document.file_type.toLowerCase() === "docx";
  const title = document.display_name || document.filename;
  const category = document.category || "Chưa phân loại";

  const getFormatBadge = () => {
    if (isPdf) return { bg: "bg-emerald-50 text-emerald-600 border-emerald-200/60", label: "PDF" };
    if (isDocx) return { bg: "bg-blue-50 text-blue-600 border-blue-200/60", label: "DOCX" };
    return { bg: "bg-slate-50 text-slate-600 border-slate-200/60", label: "FILE" };
  };

  const getStatusTheme = () => {
    switch (document.status) {
      case "expired":
        return { dot: "bg-rose-500", text: "text-rose-600", label: "Hết hiệu lực" };
      case "updating":
        return { dot: "bg-amber-500", text: "text-amber-600", label: "Đang cập nhật" };
      case "new":
        return { dot: "bg-blue-500", text: "text-blue-600", label: "Mới cập nhật" };
      case "active":
      default:
        return { dot: "bg-emerald-500", text: "text-emerald-700", label: "Còn hiệu lực" };
    }
  };

  const format = getFormatBadge();
  const status = getStatusTheme();

  return (
    <div
      className={`group flex flex-col gap-3 rounded-2xl border bg-white p-4 transition-all duration-150 hover:border-emerald-500/40 hover:shadow-md md:flex-row md:items-center md:justify-between ${
        isSelected ? "border-emerald-500 ring-2 ring-emerald-100" : "border-slate-200/80"
      }`}
    >
      {/* Left: Icon & Main Content */}
      <div className="flex min-w-0 flex-1 items-center gap-3.5">
        <div
          className={`flex size-11 shrink-0 items-center justify-center rounded-xl border ${format.bg}`}
        >
          {isPdf ? (
            <FilePdf size={24} weight="duotone" />
          ) : isDocx ? (
            <FileDoc size={24} weight="duotone" />
          ) : (
            <FileText size={24} weight="duotone" />
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
              {category}
            </span>
            <span className="text-[11px] font-medium text-slate-400">{formatSize(document.file_size_kb)}</span>
          </div>
          <h3
            className="mt-1 truncate text-sm font-bold text-slate-900 group-hover:text-emerald-900"
            title={title}
          >
            {title}
          </h3>
          <p className="mt-0.5 truncate text-xs text-slate-500">
            {document.summary || document.description || "Chưa có mô tả chi tiết."}
          </p>
        </div>
      </div>

      {/* Middle: Issuing unit & Year */}
      <div className="flex shrink-0 items-center gap-4 text-xs text-slate-500 md:w-56 md:justify-start">
        <div className="flex items-center gap-1.5 truncate">
          <Buildings size={14} className="shrink-0 text-slate-400" />
          <span className="truncate">
            {document.issuing_unit || "Phòng Đào Tạo"}
            {document.document_year ? ` • ${document.document_year}` : ""}
          </span>
        </div>
      </div>

      {/* Right: Status & Actions */}
      <div className="flex shrink-0 items-center justify-between gap-3 border-t border-slate-100 pt-2.5 md:border-t-0 md:pt-0">
        <div className="flex items-center gap-2">
          <span className={`size-2 rounded-full ${status.dot}`} />
          <span className={`text-xs font-semibold ${status.text}`}>{status.label}</span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => onPreview(document)}
            className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition"
          >
            <Eye size={15} />
            <span>Xem</span>
          </button>
          <button
            type="button"
            onClick={() => onAsk(document)}
            className="inline-flex items-center gap-1 rounded-lg bg-emerald-50 px-2.5 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 transition"
          >
            <Sparkle size={14} weight="bold" />
            <span>Hỏi AI</span>
          </button>
        </div>
      </div>
    </div>
  );
}
