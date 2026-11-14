import { CaretDown, CheckCircle, FileText, Robot, ThumbsDown, ThumbsUp, UserCircle, WarningCircle } from "@phosphor-icons/react";
import { useState } from "react";
import type { Message } from "../../types";
import { SCAN_REVIEW_WARNING, SourcePreviewModal, type SourcePreviewTarget } from "./SourcePreviewModal";

interface ChatMessageProps {
  message: Message;
  onFeedback?: (messageId: number, feedback: "up" | "down") => Promise<void>;
}

export function ChatMessage({ message, onFeedback }: ChatMessageProps) {
  const isUser = message.role === "user";
  const [isSaving, setIsSaving] = useState(false);
  const [feedbackError, setFeedbackError] = useState("");
  const [showRelatedSources, setShowRelatedSources] = useState(false);
  const [preview, setPreview] = useState<SourcePreviewTarget | null>(null);

  const chooseFeedback = async (feedback: "up" | "down") => {
    if (!message.id || !onFeedback || isSaving) return;
    setIsSaving(true);
    setFeedbackError("");
    try {
      await onFeedback(message.id, feedback);
    } catch {
      setFeedbackError("Không thể lưu phản hồi. Vui lòng thử lại.");
    } finally {
      setIsSaving(false);
    }
  };

  const groupedSources = Array.from(
    (message.sources || []).reduce((groups, source) => {
      const current = groups.get(source.filename);
      if (current) {
        if (source.page && !current.pages.includes(source.page)) current.pages.push(source.page);
        if (source.is_primary) { current.primaryPage = source.page || current.primaryPage; current.isPrimary = true; }
        if (source.needs_review && source.page && !current.reviewPages.includes(source.page)) current.reviewPages.push(source.page);
      } else {
        groups.set(source.filename, { ...source, pages: source.page ? [source.page] : [], primaryPage: source.is_primary ? source.page : undefined, isPrimary: Boolean(source.is_primary), reviewPages: source.needs_review && source.page ? [source.page] : [] });
      }
      return groups;
    }, new Map<string, { filename: string; display_name?: string | null; issuing_unit?: string | null; document_year?: number | null; pages: number[]; primaryPage?: number | null; isPrimary: boolean; reviewPages: number[] }>()).values(),
  ).map((source) => ({ ...source, pages: source.pages.sort((a, b) => a - b) }));
  const primarySource = groupedSources.find((source) => source.isPrimary) || groupedSources[0];
  const primaryPage = primarySource?.primaryPage || primarySource?.pages[0];
  const relatedSources = groupedSources.flatMap((source) => source.pages.filter((page) => !(source.filename === primarySource?.filename && page === primaryPage)).map((page) => ({ ...source, page })));
  const primaryNeedsReview = Boolean(primaryPage && primarySource?.reviewPages.includes(primaryPage));
  const openSource = (source: { filename: string; display_name?: string | null; reviewPages: number[] }, page?: number | null) =>
    setPreview({ filename: source.filename, title: source.display_name || source.filename, page: page ?? null, needsReview: Boolean(page && source.reviewPages.includes(page)) });

  return (
    <article className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <span className={`grid size-9 shrink-0 place-items-center rounded-2xl ${isUser ? "bg-brand text-white" : "border border-line bg-green-50 text-brand"}`}>
        {isUser ? <UserCircle size={21} weight="fill" /> : <Robot size={21} weight="fill" />}
      </span>
      <div className={`flex flex-col max-w-[85%] sm:max-w-[78%] ${isUser ? "items-end text-right" : "items-start text-left"}`}>
        {/* Message Bubble: w-fit ensures the bubble NEVER stretches when sources expand */}
        <div className={`w-fit max-w-full rounded-2xl px-5 py-3.5 text-left text-[15px] leading-7 shadow-xs ${isUser ? "rounded-tr-sm bg-brand text-white" : "rounded-tl-sm border border-line bg-white text-ink"}`}>
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Sources Section */}
        {primarySource ? (
          <div className="mt-2.5 flex flex-col items-start gap-2 max-w-full">
            {/* Primary Source Badge & Expand Button */}
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => openSource(primarySource, primaryPage)}
                title={primaryNeedsReview ? SCAN_REVIEW_WARNING : `${primarySource.issuing_unit || "Chưa có đơn vị ban hành"}${primarySource.document_year ? ` · ${primarySource.document_year}` : ""} · Bấm để mở tài liệu gốc`}
                aria-label={`Mở ${primarySource.display_name || primarySource.filename}${primaryPage ? `, trang ${primaryPage}` : ""}${primaryNeedsReview ? `. ${SCAN_REVIEW_WARNING}` : ""}`}
                className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200/90 bg-emerald-50/90 px-3 py-1 text-xs font-semibold text-emerald-800 shadow-xs transition hover:border-emerald-400 hover:bg-emerald-100 active:scale-95"
              >
                <FileText size={14} weight="duotone" className="text-emerald-600" />
                <span className="truncate max-w-[240px] sm:max-w-[320px]">
                  {primarySource.display_name || primarySource.filename}
                </span>
                {primaryPage ? <span className="text-emerald-700 font-bold">· Tr. {primaryPage}</span> : ""}
                {primaryNeedsReview && <WarningCircle size={14} weight="fill" className="text-amber-500" aria-hidden="true" />}
              </button>

              {relatedSources.length > 0 && (
                <button
                  type="button"
                  onClick={() => setShowRelatedSources((value) => !value)}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition active:scale-95 ${
                    showRelatedSources
                      ? "border-emerald-400 bg-emerald-100/70 text-emerald-800 shadow-xs"
                      : "border-slate-200 bg-white text-slate-600 hover:border-emerald-300 hover:text-emerald-700 shadow-xs"
                  }`}
                >
                  <span>{showRelatedSources ? "Ẩn trang liên quan" : `+ ${relatedSources.length} trang liên quan`}</span>
                  <CaretDown size={13} weight="bold" className={`transition-transform duration-200 ${showRelatedSources ? "rotate-180" : ""}`} />
                </button>
              )}
            </div>

            {/* Expanded Related Sources Box */}
            {showRelatedSources && (
              <div className="w-full max-w-md rounded-2xl border border-slate-200/90 bg-white/95 p-3 shadow-xs backdrop-blur-xs animate-in fade-in slide-in-from-top-1 duration-150">
                <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                  Các trang tài liệu đối chiếu khác:
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {relatedSources.map((source, idx) => {
                    const needsReview = source.reviewPages.includes(source.page);
                    return (
                    <button
                      type="button"
                      key={`${source.filename}-${source.page}-${idx}`}
                      onClick={() => openSource(source, source.page)}
                      title={needsReview ? SCAN_REVIEW_WARNING : "Bấm để mở tài liệu gốc"}
                      aria-label={`Mở ${source.display_name || source.filename}, trang ${source.page}${needsReview ? `. ${SCAN_REVIEW_WARNING}` : ""}`}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200/80 bg-slate-50/90 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-100 transition"
                    >
                      <FileText size={13} className="text-slate-400" />
                      <span className="font-medium truncate max-w-[190px]">{source.display_name || source.filename}</span>
                      {source.page && (
                        <span className="rounded-md bg-emerald-100 px-1.5 py-0.2 text-[10px] font-bold text-emerald-800">
                          Tr. {source.page}
                        </span>
                      )}
                      {needsReview && <WarningCircle size={13} weight="fill" className="text-amber-500" aria-hidden="true" />}
                    </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        ) : null}
        {preview && <SourcePreviewModal target={preview} onClose={() => setPreview(null)} />}

        {!isUser && message.id && onFeedback ? (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="mr-1 text-muted">Câu trả lời này có hữu ích không?</span>
            <button type="button" onClick={() => void chooseFeedback("up")} disabled={isSaving} className={`inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 font-medium transition active:scale-[.98] disabled:cursor-wait ${message.feedback === "up" ? "border-brand bg-green-50 text-brand" : "border-line bg-white text-muted hover:border-brand hover:text-brand"}`}>
              {message.feedback === "up" ? <CheckCircle size={15} weight="fill" /> : <ThumbsUp size={15} />} Hữu ích
            </button>
            <button type="button" onClick={() => void chooseFeedback("down")} disabled={isSaving} className={`inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 font-medium transition active:scale-[.98] disabled:cursor-wait ${message.feedback === "down" ? "border-error bg-red-50 text-error" : "border-line bg-white text-muted hover:border-error hover:text-error"}`}>
              {message.feedback === "down" ? <CheckCircle size={15} weight="fill" /> : <ThumbsDown size={15} />} Chưa hữu ích
            </button>
            {feedbackError && <span role="alert" className="text-error">{feedbackError}</span>}
          </div>
        ) : null}
      </div>
    </article>
  );
}
