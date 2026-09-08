import {
  Buildings,
  CalendarBlank,
  DownloadSimple,
  FileDoc,
  FilePdf,
  HardDrive,
  Sparkle,
  X,
} from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { renderAsync } from "docx-preview";
import { useEffect, useRef, useState } from "react";
import { getDocumentPreview } from "../../services/api";
import type { Document } from "../../types";

interface PreviewDrawerProps {
  document: Document;
  onClose: () => void;
  onAsk: (question: string) => void;
}

function formatSize(sizeKb: number) {
  return sizeKb >= 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(sizeKb))} KB`;
}

export function PreviewDrawer({ document, onClose, onAsk }: PreviewDrawerProps) {
  const isPdf = document.file_type.toLowerCase() === "pdf";
  const isDocx = document.file_type.toLowerCase() === "docx";
  const title = document.display_name || document.filename;

  const { data: fileBlob, isLoading, isError } = useQuery({
    queryKey: ["document-preview", document.filename],
    queryFn: () => getDocumentPreview(document.filename),
    enabled: isPdf || isDocx,
    staleTime: 5 * 60 * 1000,
  });

  const [previewUrl, setPreviewUrl] = useState("");
  const docxContainerRef = useRef<HTMLDivElement>(null);
  const [docxRendering, setDocxRendering] = useState(false);
  const [docxRenderFailed, setDocxRenderFailed] = useState(false);

  useEffect(() => {
    setPreviewUrl("");
    setDocxRenderFailed(false);
  }, [document.filename]);

  useEffect(() => {
    if (!fileBlob || !isPdf) return;
    const url = URL.createObjectURL(fileBlob);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [fileBlob, isPdf]);

  // Render DOCX with docx-preview
  useEffect(() => {
    if (!fileBlob || !isDocx || !docxContainerRef.current) return;
    setDocxRendering(true);
    setDocxRenderFailed(false);
    docxContainerRef.current.innerHTML = "";

    renderAsync(fileBlob, docxContainerRef.current, undefined, {
      inWrapper: false,
      ignoreWidth: true,
      ignoreHeight: true,
      className: "docx-preview-content",
    })
      .then(() => {
        setDocxRendering(false);
      })
      .catch((err) => {
        console.error("DOCX render failed:", err);
        setDocxRendering(false);
        setDocxRenderFailed(true);
      });
  }, [fileBlob, isDocx]);

  const handleDownload = () => {
    if (fileBlob) {
      const url = URL.createObjectURL(fileBlob);
      const link = window.document.createElement("a");
      link.href = url;
      link.download = document.filename;
      window.document.body.appendChild(link);
      link.click();
      window.document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }
  };

  return (
    <aside
      aria-label="Xem trước tài liệu"
      className="flex min-h-0 w-full shrink-0 flex-col border-t border-slate-200 bg-white shadow-2xl xl:w-[min(48%,42rem)] xl:border-l xl:border-t-0 animate-in slide-in-from-right-4 duration-200"
    >
      {/* Top Header */}
      <div className="flex items-start justify-between gap-4 border-b border-slate-200/80 px-6 py-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-[10px] font-bold tracking-wider text-emerald-700 uppercase">
              XEM TRƯỚC VĂN BẢN
            </span>
            <span className="text-[11px] text-slate-400 font-medium">{formatSize(document.file_size_kb)}</span>
            <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600 uppercase">
              {document.file_type}
            </span>
          </div>
          <h2 className="mt-1 truncate text-base font-bold text-slate-900" title={title}>
            {title}
          </h2>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
            {document.issuing_unit && (
              <span className="inline-flex items-center gap-1">
                <Buildings size={13} className="text-slate-400" />
                {document.issuing_unit}
              </span>
            )}
            {document.document_year && (
              <span className="inline-flex items-center gap-1">
                <CalendarBlank size={13} className="text-slate-400" />
                Năm {document.document_year}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1">
          {fileBlob && (
            <button
              type="button"
              onClick={handleDownload}
              className="flex size-9 items-center justify-center rounded-xl text-slate-500 hover:bg-slate-100 hover:text-emerald-700 transition"
              title="Tải văn bản về máy"
              aria-label="Tải xuống"
            >
              <DownloadSimple size={18} weight="bold" />
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="flex size-9 items-center justify-center rounded-xl text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
            aria-label="Đóng xem trước"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Content Area */}
      <div className="min-h-0 flex-1 bg-slate-100/70 p-3 sm:p-4">
        {/* PDF Viewer */}
        {isPdf && (
          <div className="relative h-full w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
            {isLoading && (
              <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-slate-400">
                <div className="size-8 animate-spin rounded-full border-2 border-emerald-600 border-t-transparent" />
                <p className="text-xs">Đang tải bản xem trước PDF...</p>
              </div>
            )}
            {isError && (
              <div className="flex h-full flex-col items-center justify-center p-6 text-center text-xs leading-5 text-slate-500">
                <FilePdf size={36} className="text-slate-300" weight="duotone" />
                <p className="mt-3 font-semibold text-slate-700">Không thể tải trực tiếp bản xem trước</p>
                <p className="mt-1 max-w-xs text-slate-400">Vui lòng bấm nút tải về hoặc hỏi đáp nội dung qua AI bên dưới.</p>
              </div>
            )}
            {previewUrl && (
              <iframe
                title={`Xem trước ${document.filename}`}
                src={previewUrl}
                className="h-full w-full border-0"
              />
            )}
          </div>
        )}

        {/* DOCX Viewer with docx-preview */}
        {isDocx && (
          <div className="relative h-full w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs flex flex-col">
            {(isLoading || docxRendering) && (
              <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-slate-400">
                <div className="size-8 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
                <p className="text-xs">Đang dựng bản xem trước tài liệu Word (.docx)...</p>
              </div>
            )}

            {(isError || docxRenderFailed) && (
              <div className="flex h-full flex-col items-center justify-center rounded-2xl p-8 text-center">
                <span className="flex size-16 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 ring-1 ring-blue-500/20">
                  <FileDoc size={36} weight="duotone" />
                </span>
                <h3 className="mt-4 text-base font-bold text-slate-800">Tài liệu định dạng DOCX</h3>
                <p className="mt-2 max-w-sm text-xs leading-relaxed text-slate-500">
                  {document.summary || document.description || "Tài liệu Word này đã được trích xuất ngữ cảnh và lập chỉ mục vector RAG đầy đủ."}
                </p>
                <div className="mt-5 flex flex-wrap items-center justify-center gap-2 text-xs text-slate-500">
                  <span className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-2.5 py-1">
                    <HardDrive size={13} /> {formatSize(document.file_size_kb)}
                  </span>
                  <span className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-2.5 py-1">
                    {document.chunk_count} đoạn vector index
                  </span>
                </div>
                {fileBlob && (
                  <button
                    type="button"
                    onClick={handleDownload}
                    className="mt-5 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 transition"
                  >
                    <DownloadSimple size={15} weight="bold" />
                    <span>Tải file DOCX về máy</span>
                  </button>
                )}
              </div>
            )}

            {/* Container where docx-preview injects parsed DOM */}
            <div
              ref={docxContainerRef}
              className={`h-full w-full overflow-y-auto overflow-x-hidden p-6 text-slate-800 text-xs sm:text-sm leading-relaxed ${
                isLoading || docxRendering || isError || docxRenderFailed ? "hidden" : "block"
              }`}
            />
          </div>
        )}

        {/* Other Formats Fallback */}
        {!isPdf && !isDocx && (
          <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center">
            <span className="flex size-16 items-center justify-center rounded-2xl bg-slate-100 text-slate-600">
              <FileDoc size={36} weight="duotone" />
            </span>
            <h3 className="mt-4 text-base font-bold text-slate-800">Tài liệu định dạng khác</h3>
            <p className="mt-2 max-w-sm text-xs leading-relaxed text-slate-500">
              {document.summary || document.description || "Tài liệu đã được phân đoạn và sẵn sàng cho AI tra cứu."}
            </p>
          </div>
        )}
      </div>

      {/* Footer CTA Bar */}
      <div className="flex items-center justify-between gap-3 border-t border-slate-200/80 bg-white px-6 py-3.5">
        <span className="text-xs text-slate-500">
          Có thắc mắc về điều khoản này?
        </span>
        <button
          type="button"
          onClick={() => onAsk(`Cho tôi biết tóm tắt các điểm quan trọng nhất của văn bản ${title}`)}
          className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-emerald-700 active:scale-[0.98] transition"
        >
          <Sparkle size={15} weight="bold" />
          <span>Hỏi AI về văn bản này</span>
        </button>
      </div>
    </aside>
  );
}
