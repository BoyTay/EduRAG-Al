import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { getPageText, savePageCorrection } from "../../services/api";
import { apiErrorMessage, pageReviewQueryKeys } from "./PageReviewBar";

const MAX_CORRECTION_CHARS = 20000;

interface PageEditorProps {
  filename: string;
  /** Số trang đánh số từ 1. */
  page: number;
  onClose: () => void;
}

/** Ô sửa chữ cả trang: hiện sẵn chữ hiện tại (bản sửa hoặc OCR), lưu xong thì tài liệu được nạp lại. */
export function PageEditor({ filename, page, onClose }: PageEditorProps) {
  const queryClient = useQueryClient();
  const textQuery = useQuery({
    queryKey: ["page-text", filename, page],
    queryFn: () => getPageText(filename, page),
    gcTime: 0,
  });
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (textQuery.data) setText(textQuery.data.text);
  }, [textQuery.data]);

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await savePageCorrection(filename, page, text);
      await Promise.all(pageReviewQueryKeys(filename).map((queryKey) => queryClient.invalidateQueries({ queryKey })));
      onClose();
    } catch (caught) {
      setError(apiErrorMessage(caught, "Không lưu được bản sửa. Vui lòng thử lại."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl border border-sky-200 bg-white p-3 text-xs">
      <p className="mb-2 text-slate-500">
        Sửa chữ của trang {page} cho khớp với PDF gốc bên trái. Mỗi dòng bảng nên giữ trên một dòng, các ô ngăn bằng dấu |.
      </p>
      {textQuery.isLoading && <p className="text-slate-400">Đang tải chữ của trang…</p>}
      {textQuery.isError && <p className="text-rose-600">{apiErrorMessage(textQuery.error, "Không tải được chữ của trang.")}</p>}
      {textQuery.data && (
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          maxLength={MAX_CORRECTION_CHARS}
          disabled={saving}
          rows={16}
          aria-label={`Nội dung trang ${page}`}
          className="w-full resize-y rounded-lg border border-slate-200 p-2 font-mono text-[12px] leading-relaxed text-slate-800 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
        />
      )}
      {error && <p className="mt-1 text-rose-600">{error}</p>}
      <div className="mt-2 flex items-center justify-end gap-2">
        {saving && <span className="mr-auto text-slate-500">Đang nạp lại tài liệu…</span>}
        <button
          type="button"
          onClick={onClose}
          disabled={saving}
          className="rounded-lg bg-slate-100 px-3 py-1.5 font-semibold text-slate-700 transition hover:bg-slate-200 disabled:opacity-50"
        >
          Hủy
        </button>
        <button
          type="button"
          onClick={save}
          disabled={saving || !textQuery.data || !text.trim()}
          className="rounded-lg bg-sky-600 px-3 py-1.5 font-semibold text-white transition hover:bg-sky-700 disabled:opacity-50"
        >
          Lưu và nạp lại
        </button>
      </div>
    </div>
  );
}
