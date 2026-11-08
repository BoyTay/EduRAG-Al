import { CheckCircle, FilePdf, Funnel, WarningCircle, X } from "@phosphor-icons/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { getDocumentChunks, getDocumentPreview, setDocumentReview } from "../../services/api";
import type { ChunkFlag, Document, DocumentChunk } from "../../types";

interface ChunkInspectorProps {
  document: Document;
  onClose: () => void;
}

const FLAG_LABELS: Record<ChunkFlag, string> = {
  generic_label: "Thiếu nhãn cột",
  too_short: "Quá ngắn",
  long_label: "Nhãn bất thường",
};

const METHOD_LABELS: Record<string, string> = {
  native: "Văn bản",
  native_table: "Bảng",
  native_low_text: "Văn bản ngắn",
  tesseract: "OCR",
  ppocrv6: "OCR",
};

interface PageGroup {
  page: number | null;
  chunks: DocumentChunk[];
}

/** Tách đoạn bảng "[Tên bảng] Nhãn: giá trị; Nhãn: giá trị" thành tên bảng và các cặp nhãn–giá trị. */
function parseTableChunk(content: string): { caption: string | null; pairs: [string, string][] } {
  const captionMatch = /^\[([^\]]*)\]\s*/.exec(content);
  const body = captionMatch ? content.slice(captionMatch[0].length) : content;
  const pairs = body.split("; ").map((part): [string, string] => {
    const index = part.indexOf(":");
    return index === -1 ? ["", part] : [part.slice(0, index).trim(), part.slice(index + 1).trim()];
  });
  return { caption: captionMatch ? captionMatch[1] : null, pairs };
}

function groupByPage(chunks: DocumentChunk[]): PageGroup[] {
  const groups = new Map<number | null, DocumentChunk[]>();
  for (const chunk of chunks) {
    const list = groups.get(chunk.page) ?? [];
    list.push(chunk);
    groups.set(chunk.page, list);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => (a ?? Number.MAX_SAFE_INTEGER) - (b ?? Number.MAX_SAFE_INTEGER))
    .map(([page, items]) => ({ page, chunks: items }));
}

function ChunkCard({ chunk }: { chunk: DocumentChunk }) {
  const flagged = chunk.flags.length > 0;
  const isTable = chunk.extraction_method === "native_table";
  const method = METHOD_LABELS[chunk.extraction_method ?? ""] ?? chunk.extraction_method ?? "Không rõ";
  const table = isTable ? parseTableChunk(chunk.content) : null;

  return (
    <li
      className={`rounded-xl border bg-white p-3 text-xs leading-relaxed ${
        flagged ? "border-amber-300 ring-1 ring-amber-200" : "border-slate-200"
      }`}
    >
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">{method}</span>
        {chunk.table_continued && (
          <span className="rounded-md bg-sky-50 px-1.5 py-0.5 text-[10px] font-semibold text-sky-700">Nối từ trang trước</span>
        )}
        {chunk.flags.map((flag) => (
          <span key={flag} className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">
            <WarningCircle size={11} weight="fill" />
            {FLAG_LABELS[flag] ?? flag}
          </span>
        ))}
      </div>
      {table ? (
        <>
          {table.caption && <p className="mb-1.5 font-semibold text-slate-700">{table.caption}</p>}
          <dl className="grid grid-cols-[minmax(0,10rem)_1fr] gap-x-3 gap-y-1">
            {table.pairs.map(([label, value], index) => (
              <div key={index} className="contents">
                <dt className="truncate text-slate-500" title={label}>{label || "—"}</dt>
                <dd className="break-words text-slate-800">{value}</dd>
              </div>
            ))}
          </dl>
        </>
      ) : (
        <p className="whitespace-pre-wrap break-words text-slate-700">{chunk.content}</p>
      )}
    </li>
  );
}

export function ChunkInspector({ document, onClose }: ChunkInspectorProps) {
  const queryClient = useQueryClient();
  const isPdf = document.file_type.toLowerCase() === "pdf";
  const title = document.display_name || document.filename;
  const [onlyFlagged, setOnlyFlagged] = useState(false);
  const [activePage, setActivePage] = useState<number | null>(null);
  const [reviewedAt, setReviewedAt] = useState<string | null>(document.reviewed_at ?? null);
  const [savingReview, setSavingReview] = useState(false);
  const [reviewError, setReviewError] = useState("");

  const chunksQuery = useQuery({
    queryKey: ["document-chunks", document.filename],
    queryFn: () => getDocumentChunks(document.filename),
  });
  const previewQuery = useQuery({
    queryKey: ["document-preview", document.filename],
    queryFn: () => getDocumentPreview(document.filename),
    enabled: isPdf,
    staleTime: 5 * 60 * 1000,
  });

  const [previewUrl, setPreviewUrl] = useState("");
  useEffect(() => {
    if (!previewQuery.data) return;
    const url = URL.createObjectURL(previewQuery.data);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [previewQuery.data]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const chunks = chunksQuery.data?.chunks ?? [];
  const groups = useMemo(
    () => groupByPage(onlyFlagged ? chunks.filter((chunk) => chunk.flags.length > 0) : chunks),
    [chunks, onlyFlagged],
  );

  const toggleReview = async () => {
    setSavingReview(true);
    setReviewError("");
    try {
      const result = await setDocumentReview(document.filename, !reviewedAt);
      setReviewedAt(result.reviewed_at);
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
    } catch {
      setReviewError("Không lưu được trạng thái kiểm tra. Vui lòng thử lại.");
    } finally {
      setSavingReview(false);
    }
  };

  // Chrome/Edge chỉ nhảy trang khi iframe nạp lại, nên key đổi theo trang đang chọn.
  const pdfSrc = previewUrl && activePage !== null ? `${previewUrl}#page=${activePage + 1}` : previewUrl;

  return (
    <div className="fixed inset-0 z-50 flex bg-slate-900/40 p-0 sm:p-4" role="dialog" aria-modal="true" aria-label={`Kiểm tra dữ liệu nạp: ${title}`}>
      <div className="flex min-h-0 w-full flex-col overflow-hidden bg-white shadow-2xl sm:rounded-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div className="min-w-0">
            <span className="rounded-md bg-sky-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-sky-700">Kiểm tra dữ liệu nạp</span>
            <h2 className="mt-1 truncate text-base font-bold text-slate-900" title={title}>{title}</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              {chunksQuery.data
                ? `${chunksQuery.data.total} đoạn đã lập chỉ mục · ${chunksQuery.data.flagged} đoạn nghi lỗi`
                : "Đang tải các đoạn đã lập chỉ mục…"}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={toggleReview}
              disabled={savingReview}
              className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold transition disabled:opacity-60 ${
                reviewedAt ? "bg-slate-100 text-slate-700 hover:bg-slate-200" : "bg-emerald-600 text-white hover:bg-emerald-700"
              }`}
            >
              <CheckCircle size={15} weight={reviewedAt ? "fill" : "bold"} />
              {reviewedAt ? "Bỏ đánh dấu đã kiểm tra" : "Đánh dấu đã kiểm tra"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex size-9 items-center justify-center rounded-xl text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
              aria-label="Đóng"
            >
              <X size={18} />
            </button>
          </div>
        </header>
        {reviewError && <p className="border-b border-rose-100 bg-rose-50 px-5 py-2 text-xs text-rose-700">{reviewError}</p>}

        <div className="grid min-h-0 flex-1 grid-rows-[minmax(16rem,40vh)_1fr] lg:grid-cols-2 lg:grid-rows-1">
          <section className="min-h-0 border-b border-slate-200 bg-slate-100/70 p-3 lg:border-b-0 lg:border-r" aria-label="Tài liệu gốc">
            <div className="h-full overflow-hidden rounded-xl border border-slate-200 bg-white">
              {!isPdf && (
                <div className="flex h-full flex-col items-center justify-center p-6 text-center text-xs text-slate-500">
                  <FilePdf size={36} className="text-slate-300" weight="duotone" />
                  <p className="mt-3 font-semibold text-slate-700">Xem trước theo trang chỉ hỗ trợ PDF</p>
                  <p className="mt-1">Đối chiếu nội dung ở bên phải với file gốc.</p>
                </div>
              )}
              {isPdf && previewQuery.isLoading && (
                <div className="flex h-full items-center justify-center text-xs text-slate-400">Đang tải PDF…</div>
              )}
              {isPdf && previewQuery.isError && (
                <div className="flex h-full items-center justify-center p-6 text-center text-xs text-slate-500">Không tải được bản xem trước PDF.</div>
              )}
              {isPdf && pdfSrc && (
                <iframe key={pdfSrc} title={`PDF gốc ${document.filename}`} src={pdfSrc} className="h-full w-full border-0" />
              )}
            </div>
          </section>

          <section className="flex min-h-0 flex-col" aria-label="Các đoạn đã lập chỉ mục">
            <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-2.5">
              <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-600">
                <input
                  type="checkbox"
                  checked={onlyFlagged}
                  onChange={(event) => setOnlyFlagged(event.target.checked)}
                  className="size-3.5 accent-amber-600"
                />
                <Funnel size={13} />
                Chỉ hiện đoạn nghi lỗi
              </label>
              <span className="text-[11px] text-slate-400">Bấm tiêu đề trang để mở trang đó trong PDF</span>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto bg-slate-50/60 px-4 py-3">
              {chunksQuery.isLoading && <p className="text-xs text-slate-400">Đang tải…</p>}
              {chunksQuery.isError && <p className="text-xs text-rose-600">Không tải được danh sách đoạn. Chỉ mục có thể chưa sẵn sàng.</p>}
              {chunksQuery.data && groups.length === 0 && (
                <p className="text-xs text-slate-500">
                  {onlyFlagged ? "Không có đoạn nào bị gắn cờ nghi lỗi." : "Tài liệu này chưa có đoạn nào trong chỉ mục. Hãy tạo lại chỉ mục."}
                </p>
              )}
              {groups.map((group) => (
                <div key={group.page ?? "unknown"} className="mb-4">
                  <button
                    type="button"
                    disabled={group.page === null || !isPdf}
                    onClick={() => setActivePage(group.page)}
                    className={`mb-2 text-xs font-bold transition ${
                      activePage === group.page && group.page !== null ? "text-sky-700" : "text-slate-700 hover:text-sky-700"
                    } disabled:cursor-default disabled:hover:text-slate-700`}
                  >
                    {group.page === null ? "Không rõ trang" : `Trang ${group.page + 1}`}
                    <span className="ml-1.5 font-normal text-slate-400">({group.chunks.length} đoạn)</span>
                  </button>
                  <ul className="space-y-2">
                    {group.chunks.map((chunk) => <ChunkCard key={chunk.id} chunk={chunk} />)}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
