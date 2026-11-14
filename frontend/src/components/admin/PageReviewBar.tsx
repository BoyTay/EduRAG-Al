import { CheckCircle, PencilSimple, WarningCircle } from "@phosphor-icons/react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { confirmPage, removePageCorrection, unconfirmPage } from "../../services/api";
import type { PageReviewReason, PageSummary } from "../../types";

export const REVIEW_REASON_LABELS: Record<PageReviewReason, string> = {
  low_confidence: "Độ tin cậy thấp",
  garbled_text: "Chữ lỗi",
  row_number_gap: "Số thứ tự đứt quãng",
  malformed_date: "Ngày sai định dạng",
};

/** Câu báo lỗi từ API (`detail`), hoặc câu chung khi không có. */
export function apiErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" && detail ? detail : fallback;
}

/** Các query cần tải lại sau khi trang được xác nhận/sửa (tài liệu đã được nạp lại). */
export function pageReviewQueryKeys(filename: string) {
  return [["document-chunks", filename], ["document-pages", filename], ["documents"]];
}

function readingMethod(summary: PageSummary): string {
  if (summary.extraction_method === "manual") return "sửa tay";
  if (summary.ocr_model?.endsWith("+tesseract-vie")) return "đọc theo ô";
  if (summary.extraction_method === "tesseract") return "Tesseract";
  return summary.extraction_method ?? "OCR";
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleDateString("vi-VN") : "";
}

interface PageReviewBarProps {
  filename: string;
  summary: PageSummary;
  onEdit: () => void;
}

/** Đầu nhóm trang scan: cách đọc, độ tin cậy, trạng thái kiểm tra và các thao tác của admin. */
export function PageReviewBar({ filename, summary, onEdit }: PageReviewBarProps) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const run = async (action: (filename: string, page: number) => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await action(filename, summary.page);
      await Promise.all(pageReviewQueryKeys(filename).map((queryKey) => queryClient.invalidateQueries({ queryKey })));
    } catch (caught) {
      setError(apiErrorMessage(caught, "Không thực hiện được thao tác. Vui lòng thử lại."));
    } finally {
      setBusy(false);
    }
  };

  const confidence = summary.ocr_confidence != null ? ` · tin cậy ${summary.ocr_confidence.toFixed(2).replace(".", ",")}` : "";
  const reviewer = summary.reviewed_by ? ` · ${summary.reviewed_by}, ${formatDate(summary.reviewed_at)}` : "";
  const buttonClass =
    "inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-[11px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <div className="mb-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-slate-500">
          Bản scan · {readingMethod(summary)}
          {confidence}
        </span>
        {summary.review_status === "needs_review" && (
          <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-1.5 py-0.5 font-semibold text-amber-800">
            <WarningCircle size={12} weight="fill" />
            Cần đối chiếu
          </span>
        )}
        {summary.review_status === "confirmed" && (
          <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-1.5 py-0.5 font-semibold text-emerald-700">
            <CheckCircle size={12} weight="fill" />
            Đã xác nhận{reviewer}
          </span>
        )}
        {summary.review_status === "corrected" && (
          <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-1.5 py-0.5 font-semibold text-emerald-700">
            <PencilSimple size={12} weight="bold" />
            Đã sửa tay{reviewer}
          </span>
        )}
      </div>

      {summary.review_status === "needs_review" && summary.review_reasons.length > 0 && (
        <p className="mt-1 text-amber-800">Lý do: {summary.review_reasons.map((reason) => REVIEW_REASON_LABELS[reason] ?? reason).join(" · ")}</p>
      )}

      {summary.editable && (
        <div className="mt-2 flex flex-wrap justify-end gap-1.5">
          {summary.review_status === "confirmed" ? (
            <button type="button" disabled={busy} onClick={() => run(unconfirmPage)} className={`${buttonClass} bg-slate-100 text-slate-700 hover:bg-slate-200`}>
              Bỏ xác nhận
            </button>
          ) : summary.review_status !== "corrected" ? (
            <button type="button" disabled={busy} onClick={() => run(confirmPage)} className={`${buttonClass} bg-emerald-600 text-white hover:bg-emerald-700`}>
              <CheckCircle size={12} weight="bold" />
              Trang này đúng
            </button>
          ) : null}
          {summary.review_status === "corrected" && (
            <button type="button" disabled={busy} onClick={() => run(removePageCorrection)} className={`${buttonClass} bg-slate-100 text-slate-700 hover:bg-slate-200`}>
              Bỏ bản sửa
            </button>
          )}
          <button type="button" disabled={busy} onClick={onEdit} className={`${buttonClass} bg-sky-600 text-white hover:bg-sky-700`}>
            <PencilSimple size={12} weight="bold" />
            Sửa trang
          </button>
        </div>
      )}
      {busy && <p className="mt-1 text-slate-500">Đang nạp lại tài liệu…</p>}
      {error && <p className="mt-1 text-rose-600">{error}</p>}
    </div>
  );
}
