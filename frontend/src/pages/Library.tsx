import { FileDoc, FilePdf, Funnel, MagnifyingGlass, PaperPlaneTilt, X } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getDocumentPreview, getDocuments } from "../services/api";
import { useChatStore } from "../stores/chatStore";
import type { Document } from "../types";

type FileFilter = "all" | "pdf" | "docx";
type SortOrder = "newest" | "name";

function formatSize(sizeKb: number) {
  return sizeKb >= 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(sizeKb))} KB`;
}

function statusLabel(status?: string | null) {
  return status === "expired" ? "Hết hiệu lực" : status === "updating" ? "Đang cập nhật" : "Còn hiệu lực";
}

function PreviewPanel({ document, onClose }: { document: Document; onClose: () => void }) {
  const isPdf = document.file_type.toLowerCase() === "pdf";
  const { data: fileBlob, isLoading, isError } = useQuery({
    queryKey: ["document-preview", document.filename],
    queryFn: () => getDocumentPreview(document.filename),
    enabled: isPdf,
    staleTime: 5 * 60 * 1000,
  });
  const [previewUrl, setPreviewUrl] = useState("");

  useEffect(() => {
    setPreviewUrl("");
  }, [document.filename]);

  useEffect(() => {
    if (!fileBlob) return;
    const url = URL.createObjectURL(fileBlob);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [fileBlob]);

  return (
    <aside aria-label="Xem trước tài liệu" className="flex min-h-0 w-full shrink-0 flex-col border-t border-line bg-white xl:w-[min(40%,34rem)] xl:border-l xl:border-t-0">
      <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
        <div className="min-w-0"><p className="text-[10px] font-bold tracking-[.14em] text-brand">XEM TRƯỚC</p><h2 className="mt-1 truncate text-sm font-semibold text-ink" title={document.display_name || document.filename}>{document.display_name || document.filename}</h2><p className="mt-1 truncate text-[11px] text-muted">{document.issuing_unit || "Chưa có đơn vị ban hành"}{document.document_year ? ` · ${document.document_year}` : ""}</p></div>
        <button type="button" onClick={onClose} className="grid size-9 shrink-0 place-items-center rounded-lg text-muted transition hover:bg-green-50 hover:text-brand" aria-label="Đóng xem trước"><X size={19} /></button>
      </div>
      {isPdf ? <div className="min-h-0 flex-1 bg-green-50/50 p-3">{isLoading && <div className="h-full animate-pulse rounded-xl bg-green-100" />}{isError && <div className="grid h-full place-items-center rounded-xl border border-dashed border-line bg-white p-6 text-center text-sm leading-6 text-muted">Không thể tải bản xem trước. Hãy thử lại sau.</div>}{previewUrl && <iframe title={`Xem trước ${document.filename}`} src={previewUrl} className="h-full w-full rounded-xl border border-line bg-white" />}</div> : <div className="grid flex-1 place-items-center p-8 text-center"><div><span className="mx-auto grid size-14 place-items-center rounded-2xl bg-green-100 text-brand"><FileDoc size={30} weight="duotone" /></span><h3 className="mt-4 font-semibold text-ink">DOCX chưa có xem trước trực tiếp</h3><p className="mt-2 max-w-xs text-sm leading-6 text-muted">Tài liệu này vẫn có thể được tra cứu trong hội thoại EduRAG.</p></div></div>}
    </aside>
  );
}

export function Library() {
  const { data = [], isLoading, isError } = useQuery({ queryKey: ["documents"], queryFn: getDocuments });
  const [keyword, setKeyword] = useState("");
  const [fileFilter, setFileFilter] = useState<FileFilter>("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const navigate = useNavigate();
  const send = useChatStore((state) => state.send);
  const categories = useMemo(() => [...new Set(data.map((doc) => doc.category || "Chưa phân loại"))].sort((a, b) => a.localeCompare(b, "vi")), [data]);
  const items = useMemo(() => data
    .filter((doc) => `${doc.filename} ${doc.display_name || ""} ${doc.summary || doc.description || ""}`.toLowerCase().includes(keyword.trim().toLowerCase()))
    .filter((doc) => fileFilter === "all" || doc.file_type.toLowerCase() === fileFilter)
    .filter((doc) => categoryFilter === "all" || (doc.category || "Chưa phân loại") === categoryFilter)
    .sort((a, b) => sortOrder === "name" ? (a.display_name || a.filename).localeCompare(b.display_name || b.filename, "vi") : new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime()), [data, keyword, fileFilter, categoryFilter, sortOrder]);
  const ask = async (name: string) => { navigate("/chat"); await send(`Cho tôi biết nội dung chính của tài liệu ${name}`); };

  return (
    <section className="flex h-full min-h-0 overflow-hidden bg-canvas">
      <div className="min-w-0 flex-1 overflow-y-auto px-5 py-7 md:px-8">
        <div className="mx-auto max-w-6xl">
          <p className="text-xs font-bold tracking-[.14em] text-brand">KHO TÀI LIỆU</p>
          <div className="mt-2 flex flex-wrap items-end justify-between gap-3"><div><h1 className="text-3xl font-bold tracking-tight text-ink">Thư viện tài liệu</h1><p className="mt-2 text-sm text-muted">{data.length} tài liệu đã sẵn sàng để tra cứu.</p></div></div>
          <div className="mt-6 flex flex-col gap-3 rounded-2xl border border-line/90 bg-white p-3 shadow-[0_6px_20px_rgba(46,125,50,.045)] md:flex-row md:items-center">
            <div className="relative flex-1"><MagnifyingGlass className="absolute left-3 top-3 text-muted" size={18} /><input value={keyword} onChange={(event) => setKeyword(event.target.value)} className="h-10 w-full rounded-xl bg-green-50/70 pl-10 pr-4 text-sm text-ink outline-none transition placeholder:text-muted focus:bg-white focus:ring-2 focus:ring-green-200" placeholder="Tìm theo tên hoặc nội dung mô tả" /></div>
            <div className="flex flex-wrap items-center gap-2"><Funnel size={17} className="text-muted" /><div className="flex rounded-xl bg-green-50 p-1">{(["all", "pdf", "docx"] as FileFilter[]).map((filter) => <button key={filter} type="button" onClick={() => setFileFilter(filter)} className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${fileFilter === filter ? "bg-white text-brand shadow-sm" : "text-muted hover:text-brand"}`}>{filter === "all" ? "Tất cả" : filter.toUpperCase()}</button>)}</div><select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)} aria-label="Lọc theo danh mục" className="h-9 max-w-40 rounded-lg border border-line bg-white px-2 text-xs font-medium text-muted outline-none focus:border-brand"><option value="all">Mọi danh mục</option>{categories.map((category) => <option key={category} value={category}>{category}</option>)}</select><select value={sortOrder} onChange={(event) => setSortOrder(event.target.value as SortOrder)} aria-label="Sắp xếp tài liệu" className="h-9 rounded-lg border border-line bg-white px-2 text-xs font-medium text-muted outline-none focus:border-brand"><option value="newest">Mới nhất</option><option value="name">Tên A–Z</option></select></div>
          </div>
          {isLoading ? <div className="mt-8 grid gap-5 md:grid-cols-2"><div className="h-72 animate-pulse rounded-2xl bg-green-100" /><div className="h-72 animate-pulse rounded-2xl bg-green-100" /></div> : isError ? <p role="alert" className="mt-8 rounded-xl bg-red-50 p-4 text-sm text-error">Không thể tải thư viện tài liệu. Vui lòng thử lại.</p> : items.length ? <div className="mt-7 grid gap-4 md:grid-cols-2">{items.map((doc) => { const isPdf = doc.file_type.toLowerCase() === "pdf"; const Icon = isPdf ? FilePdf : FileDoc; const title = doc.display_name || doc.filename; return <article key={doc.id} className={`group rounded-2xl border bg-white p-4 shadow-[0_4px_14px_rgba(46,125,50,.04)] transition duration-200 hover:-translate-y-0.5 hover:border-brand hover:shadow-[0_14px_28px_rgba(46,125,50,.1)] ${selectedDocument?.id === doc.id ? "border-brand ring-2 ring-green-100" : "border-line"}`}><button type="button" onClick={() => setSelectedDocument(doc)} className="flex w-full gap-4 text-left"><span className="grid size-14 shrink-0 place-items-center rounded-2xl bg-green-100 text-brand"><Icon size={29} weight="duotone" /></span><span className="min-w-0 flex-1"><span className="flex items-center justify-between gap-2"><span className="rounded-md bg-green-50 px-2 py-1 text-[10px] font-bold tracking-wide text-brand">{doc.category || "Chưa phân loại"}</span><span className="text-[11px] text-muted">{formatSize(doc.file_size_kb)}</span></span><h2 className="mt-2 truncate text-sm font-semibold text-ink" title={title}>{title}</h2><p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{doc.summary || doc.description || "Chưa có tóm tắt văn bản."}</p><p className="mt-2 truncate text-[11px] text-muted">{doc.issuing_unit || "Chưa có đơn vị ban hành"}{doc.document_year ? ` · ${doc.document_year}` : ""}</p></span></button><div className="mt-4 flex items-center justify-between gap-3 border-t border-line pt-3"><span className={`text-[11px] font-medium ${doc.status === "expired" ? "text-error" : doc.status === "updating" ? "text-amber-700" : "text-brand"}`}>{statusLabel(doc.status)}</span><div className="flex gap-2"><button type="button" onClick={() => setSelectedDocument(doc)} className="text-xs font-semibold text-brand hover:text-brand-dark">Xem trước</button><button type="button" onClick={() => void ask(title)} className="inline-flex items-center gap-1 text-xs font-semibold text-brand hover:text-brand-dark"><PaperPlaneTilt size={14} />Hỏi</button></div></div></article>; })}</div> : <div className="mt-8 rounded-2xl border border-dashed border-line bg-white p-10 text-center"><FilePdf className="mx-auto text-brand" size={32} weight="duotone" /><h2 className="mt-4 font-semibold text-ink">Không tìm thấy tài liệu phù hợp</h2><p className="mt-2 text-sm text-muted">Thử đổi từ khóa hoặc bộ lọc định dạng.</p></div>}
        </div>
      </div>
      {selectedDocument && <PreviewPanel document={selectedDocument} onClose={() => setSelectedDocument(null)} />}
    </section>
  );
}
