import { CheckCircle, FileText, Robot, ThumbsDown, ThumbsUp, UserCircle } from "@phosphor-icons/react";
import { useState } from "react";
import type { Message } from "../../types";

interface ChatMessageProps {
  message: Message;
  onFeedback?: (messageId: number, feedback: "up" | "down") => Promise<void>;
}

export function ChatMessage({ message, onFeedback }: ChatMessageProps) {
  const isUser = message.role === "user";
  const [isSaving, setIsSaving] = useState(false);
  const [feedbackError, setFeedbackError] = useState("");

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
      } else {
        groups.set(source.filename, { ...source, pages: source.page ? [source.page] : [] });
      }
      return groups;
    }, new Map<string, { filename: string; display_name?: string | null; issuing_unit?: string | null; document_year?: number | null; pages: number[] }>()).values(),
  ).map((source) => ({ ...source, pages: source.pages.sort((a, b) => a - b) }));

  return (
    <article className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <span className={`grid size-9 shrink-0 place-items-center rounded-2xl ${isUser ? "bg-brand text-white" : "border border-line bg-green-50 text-brand"}`}>
        {isUser ? <UserCircle size={21} weight="fill" /> : <Robot size={21} weight="fill" />}
      </span>
      <div className={`max-w-[78%] ${isUser ? "text-right" : ""}`}>
        <div className={`rounded-2xl px-5 py-3.5 text-left text-[15px] leading-7 ${isUser ? "rounded-tr-sm bg-brand text-white" : "rounded-tl-sm border border-line bg-white text-ink"}`}>
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {groupedSources.length ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {groupedSources.map((source) => (
              <span key={source.filename} title={`${source.issuing_unit || "Chưa có đơn vị ban hành"}${source.document_year ? ` · ${source.document_year}` : ""}`} className="inline-flex items-center gap-1 rounded-full border border-green-200 bg-green-50 px-3 py-1 text-xs font-medium text-brand">
                <FileText size={14} />{source.display_name || source.filename}{source.pages.length ? ` · Tr. ${source.pages.join(", ")}` : ""}
              </span>
            ))}
          </div>
        ) : null}

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
