import { Buildings, Eye, FileDoc, FilePdf, FileText, Sparkle } from "@phosphor-icons/react";
import type { Document } from "../../types";

interface DocumentCardProps {
  document: Document;
  isSelected?: boolean;
  onPreview: (document: Document) => void;
  onAsk: (document: Document) => void;
}

function formatSize(sizeKb: number) {
  return sizeKb >= 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(sizeKb))} KB`;
}

export function DocumentCard({ document, isSelected, onPreview, onAsk }: DocumentCardProps) {
  const isPdf = document.file_type.toLowerCase() === "pdf";
  const isDocx = document.file_type.toLowerCase() === "docx";
  const title = document.display_name || document.filename;
  const category = document.category || "Chưa phân loại";

  // Category badge & icon color theme
  const getBadgeTheme = () => {
    const cat = category.toLowerCase();
    if (cat.includes("học bổng")) {
      return {
        badge: "bg-amber-50 text-amber-700 border-amber-200/60",
        iconBg: "bg-amber-50/90 text-amber-600 border-amber-200/70",
      };
    }
    if (cat.includes("học phí") || cat.includes("học phần") || isDocx) {
      return {
        badge: "bg-blue-50 text-blue-700 border-blue-200/60",
        iconBg: "bg-blue-50/90 text-blue-600 border-blue-200/70",
      };
    }
    return {
      badge: "bg-emerald-50 text-emerald-700 border-emerald-200/60",
      iconBg: "bg-emerald-50/90 text-emerald-600 border-emerald-200/70",
    };
  };

  const theme = getBadgeTheme();

  // Status indicator theme
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

  const status = getStatusTheme();

  return (
    <article
      className={`group relative flex flex-col justify-between rounded-2xl border bg-white p-5 shadow-[0_2px_12px_rgba(0,0,0,0.03)] transition-all duration-200 hover:-translate-y-1 hover:border-emerald-500/50 hover:shadow-[0_12px_28px_rgba(5,150,105,0.08)] ${
        isSelected ? "border-emerald-500 ring-2 ring-emerald-100" : "border-slate-200/80"
      }`}
    >
      <div>
        {/* Top bar: Format Icon + Category Pill + File Size */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            {/* Format Icon Container */}
            <div
              className={`flex size-11 shrink-0 items-center justify-center rounded-xl border ${theme.iconBg}`}
            >
              {isPdf ? (
                <FilePdf size={26} weight="duotone" />
              ) : isDocx ? (
                <FileDoc size={26} weight="duotone" />
              ) : (
                <FileText size={26} weight="duotone" />
              )}
            </div>

            {/* Category Pill Tag */}
            <span
              className={`inline-flex items-center rounded-md border px-2.5 py-1 text-[11px] font-semibold ${theme.badge}`}
            >
              {category}
            </span>
          </div>

          {/* File Size */}
          <span className="text-xs font-medium text-slate-400">
            {formatSize(document.file_size_kb)}
          </span>
        </div>

        {/* Title */}
        <h3
          className="mt-3.5 text-[15px] font-bold text-slate-900 leading-snug line-clamp-1 transition group-hover:text-emerald-900"
          title={title}
        >
          {title}
        </h3>

        {/* Summary Description */}
        <p className="mt-1.5 text-xs text-slate-500 leading-relaxed line-clamp-2 min-h-[2.5rem]">
          {document.summary || document.description || "Quy định học vụ và hướng dẫn đào tạo chính quy của nhà trường."}
        </p>

        {/* Issuing Metadata */}
        <div className="mt-3.5 flex items-center gap-1.5 text-xs text-slate-400">
          <Buildings size={14} className="shrink-0 text-slate-400" />
          <span className="truncate">
            {document.issuing_unit || "Phòng Đào Tạo"}
            {document.document_year ? ` • Năm ${document.document_year}` : ""}
          </span>
        </div>
      </div>

      {/* Card Footer Divider & Actions */}
      <div className="mt-4 border-t border-slate-100 pt-3.5 flex items-center justify-between gap-2">
        {/* Left: Status */}
        <div className="flex items-center gap-2">
          <span className={`size-2 rounded-full ${status.dot} shadow-xs`} />
          <span className={`text-xs font-semibold ${status.text}`}>
            {status.label}
          </span>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => onPreview(document)}
            className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition active:scale-95"
          >
            <Eye size={15} />
            <span>Xem trước</span>
          </button>

          <button
            type="button"
            onClick={() => onAsk(document)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-2.5 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 active:scale-95 transition"
          >
            <Sparkle size={14} weight="bold" />
            <span>Hỏi AI</span>
          </button>
        </div>
      </div>
    </article>
  );
}
