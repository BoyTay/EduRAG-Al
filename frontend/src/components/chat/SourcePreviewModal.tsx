import { DownloadSimple, FilePdf, WarningCircle, X } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { getDocumentPreview } from "../../services/api";

export const SCAN_REVIEW_WARNING = "Trích từ bản scan chưa được kiểm tra, nên đối chiếu bản gốc";

export interface SourcePreviewTarget {
  filename: string;
  title: string;
  /** Số trang đánh số từ 1; null khi tài liệu không có trang (DOCX). */
  page: number | null;
  needsReview: boolean;
}

interface SourcePreviewModalProps {
  target: SourcePreviewTarget;
  onClose: () => void;
}

/** Mở tài liệu nguồn của câu trả lời, nhảy tới đúng trang được trích (PDF). */
export function SourcePreviewModal({ target, onClose }: SourcePreviewModalProps) {
  const isPdf = target.filename.toLowerCase().endsWith(".pdf");
  const previewQuery = useQuery({
    queryKey: ["document-preview", target.filename],
    queryFn: () => getDocumentPreview(target.filename),
    staleTime: 5 * 60 * 1000,
  });

  const [blobUrl, setBlobUrl] = useState("");
  useEffect(() => {
    if (!previewQuery.data) return;
    const url = URL.createObjectURL(previewQuery.data);
    setBlobUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [previewQuery.data]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const src = blobUrl && isPdf && target.page ? `${blobUrl}#page=${target.page}` : blobUrl;

  return (
    <div
      className="fixed inset-0 z-50 flex items-stretch justify-center bg-slate-900/40 p-0 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label={`Tài liệu nguồn: ${target.title}`}
      onClick={onClose}
    >
      <div className="flex min-h-0 w-full max-w-4xl flex-col overflow-hidden bg-white shadow-2xl sm:rounded-2xl" onClick={(event) => event.stopPropagation()}>
        <header className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-bold text-slate-900" title={target.title}>{target.title}</h2>
            {target.page ? <p className="text-xs text-slate-500">Trang {target.page}</p> : null}
            {target.needsReview && (
              <p className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-amber-800">
                <WarningCircle size={13} weight="fill" />
                {SCAN_REVIEW_WARNING}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex size-9 shrink-0 items-center justify-center rounded-xl text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            aria-label="Đóng"
          >
            <X size={18} />
          </button>
        </header>
        <div className="min-h-0 flex-1 bg-slate-100/70">
          {previewQuery.isLoading && <div className="flex h-full items-center justify-center text-xs text-slate-400">Đang tải tài liệu…</div>}
          {previewQuery.isError && (
            <div className="flex h-full items-center justify-center p-6 text-center text-xs text-slate-500">Không tải được tài liệu nguồn.</div>
          )}
          {src && isPdf && <iframe key={src} title={`Nguồn: ${target.title}`} src={src} className="h-[75vh] w-full border-0 sm:h-full" />}
          {blobUrl && !isPdf && (
            <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center text-xs text-slate-500">
              <FilePdf size={36} className="text-slate-300" weight="duotone" />
              <p>Tài liệu Word không xem trước theo trang được.</p>
              <a
                href={blobUrl}
                download={target.filename}
                className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-1.5 font-semibold text-white hover:bg-slate-700"
              >
                <DownloadSimple size={14} />
                Tải tài liệu
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
