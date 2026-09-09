import {
  ArrowUpRight,
  CaretDown,
  CaretLeft,
  CaretRight,
  ChatCircleDots,
  Funnel,
  List,
  MagnifyingGlass,
  Sparkle,
  SquaresFour,
  X,
} from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DocumentCard } from "../components/library/DocumentCard";
import { DocumentRow } from "../components/library/DocumentRow";
import { PreviewDrawer } from "../components/library/PreviewDrawer";
import { QuickQuestionModal } from "../components/library/QuickQuestionModal";
import { getDocuments } from "../services/api";
import { useAuthStore } from "../stores/authStore";
import { useChatStore } from "../stores/chatStore";
import type { Document } from "../types";

type FileFilter = "all" | "pdf" | "docx" | "other";
type SortOrder = "newest" | "oldest" | "name_asc" | "name_desc" | "size_desc";
type ViewMode = "grid" | "list";

const ITEMS_PER_PAGE = 4;

export function Library() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.role === "admin";
  const send = useChatStore((state) => state.send);

  const { data = [], isLoading, isError } = useQuery({
    queryKey: ["documents"],
    queryFn: getDocuments,
  });

  // Filter & Search states
  const [keyword, setKeyword] = useState("");
  const [fileFilter, setFileFilter] = useState<FileFilter>("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);

  // Selected for preview & AI modal
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [questionTargetDoc, setQuestionTargetDoc] = useState<Document | null>(null);

  // Reset page to 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [keyword, fileFilter, categoryFilter, sortOrder]);

  // Counts for filter pills
  const counts = useMemo(() => {
    const total = data.length;
    const pdf = data.filter((d) => d.file_type.toLowerCase() === "pdf").length;
    const docx = data.filter((d) => d.file_type.toLowerCase() === "docx").length;
    const other = total - pdf - docx;
    return { all: total, pdf, docx, other: Math.max(0, other) };
  }, [data]);

  // Unique categories list
  const categories = useMemo(() => {
    const set = new Set<string>();
    data.forEach((doc) => {
      if (doc.category && doc.category.trim()) {
        set.add(doc.category.trim());
      }
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b, "vi"));
  }, [data]);

  // Filtered & Sorted items
  const filteredItems = useMemo(() => {
    return data
      .filter((doc) => {
        const query = keyword.trim().toLowerCase();
        if (!query) return true;
        const searchable = `${doc.filename} ${doc.display_name || ""} ${doc.summary || doc.description || ""} ${
          doc.issuing_unit || ""
        }`.toLowerCase();
        return searchable.includes(query);
      })
      .filter((doc) => {
        const ext = doc.file_type.toLowerCase();
        if (fileFilter === "all") return true;
        if (fileFilter === "pdf") return ext === "pdf";
        if (fileFilter === "docx") return ext === "docx";
        return ext !== "pdf" && ext !== "docx";
      })
      .filter((doc) => {
        if (categoryFilter === "all") return true;
        return (doc.category || "").trim() === categoryFilter;
      })
      .sort((a, b) => {
        switch (sortOrder) {
          case "oldest":
            return new Date(a.uploaded_at).getTime() - new Date(b.uploaded_at).getTime();
          case "name_asc":
            return (a.display_name || a.filename).localeCompare(b.display_name || b.filename, "vi");
          case "name_desc":
            return (b.display_name || b.filename).localeCompare(a.display_name || a.filename, "vi");
          case "size_desc":
            return b.file_size_kb - a.file_size_kb;
          case "newest":
          default:
            return new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime();
        }
      });
  }, [data, keyword, fileFilter, categoryFilter, sortOrder]);

  // Paginated items
  const totalItems = filteredItems.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / ITEMS_PER_PAGE));
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const currentItems = filteredItems.slice(startIndex, startIndex + ITEMS_PER_PAGE);

  // Ask AI handler
  const handleAskQuestion = async (question: string, document?: Document) => {
    setQuestionTargetDoc(null);
    navigate("/chat");
    await send(question, document?.filename);
  };

  return (
    <section className="flex h-full min-h-0 overflow-hidden bg-slate-50/50">
      {/* Main Container */}
      <div className="min-w-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6 md:px-8">
        <div className="mx-auto max-w-6xl">
          {/* Header Section */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-[11px] font-bold tracking-wider text-emerald-700 ring-1 ring-emerald-500/20 uppercase">
                <Sparkle size={13} weight="fill" />
                <span>Kho tài liệu học vụ & quy chế</span>
              </div>
              <h1 className="mt-2.5 text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
                Thư viện tài liệu RAG
              </h1>
              <p className="mt-1.5 text-xs sm:text-sm text-slate-500 max-w-2xl leading-relaxed">
                {data.length} tài liệu đã sẵn sàng & lập chỉ mục vector, phục vụ AI đối chiếu ngữ cảnh theo thời gian thực.
              </p>
            </div>

            {/* Header Right Action */}
            <div className="flex items-center gap-2.5 shrink-0">
              {isAdmin && (
                <button
                  type="button"
                  onClick={() => navigate("/admin")}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:border-emerald-400 hover:text-emerald-700 transition active:scale-[0.98]"
                >
                  <span>Quản trị tài liệu</span>
                  <ArrowUpRight size={14} />
                </button>
              )}
              <button
                type="button"
                onClick={() => navigate("/chat")}
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-sm shadow-emerald-950/20 hover:from-emerald-500 hover:to-teal-500 active:scale-[0.98] transition"
              >
                <ChatCircleDots size={16} weight="bold" />
                <span>Đặt câu hỏi AI</span>
              </button>
            </div>
          </div>

          {/* Search & Control Toolbar */}
          <div className="mt-6 rounded-2xl border border-slate-200/90 bg-white p-3 shadow-[0_4px_16px_rgba(0,0,0,0.02)]">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
              {/* Search input with MagnifyingGlass and Clear icon */}
              <div className="relative flex-1">
                <MagnifyingGlass
                  size={18}
                  className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="Tìm theo tên quy chế, số hiệu, nội dung..."
                  className="h-10 w-full rounded-xl bg-slate-50/80 pl-10 pr-9 text-xs sm:text-sm text-slate-800 placeholder:text-slate-400 outline-none transition focus:bg-white focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 border border-transparent"
                />
                {keyword && (
                  <button
                    type="button"
                    onClick={() => setKeyword("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-slate-400 hover:bg-slate-200/60 hover:text-slate-600 transition"
                    aria-label="Xóa tìm kiếm"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>

              {/* Filters & View Toggles */}
              <div className="flex flex-wrap items-center gap-2">
                {/* Format Pills with Dynamic Counts */}
                <div className="flex rounded-xl bg-slate-100 p-1">
                  <button
                    type="button"
                    onClick={() => setFileFilter("all")}
                    className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold transition ${
                      fileFilter === "all"
                        ? "bg-white text-emerald-700 shadow-xs"
                        : "text-slate-500 hover:text-slate-900"
                    }`}
                  >
                    Tất cả ({counts.all})
                  </button>

                  <button
                    type="button"
                    onClick={() => setFileFilter("pdf")}
                    className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold transition ${
                      fileFilter === "pdf"
                        ? "bg-white text-emerald-700 shadow-xs"
                        : "text-slate-500 hover:text-slate-900"
                    }`}
                  >
                    PDF ({counts.pdf})
                  </button>

                  <button
                    type="button"
                    onClick={() => setFileFilter("docx")}
                    className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold transition ${
                      fileFilter === "docx"
                        ? "bg-white text-emerald-700 shadow-xs"
                        : "text-slate-500 hover:text-slate-900"
                    }`}
                  >
                    DOCX ({counts.docx})
                  </button>

                  {counts.other > 0 && (
                    <button
                      type="button"
                      onClick={() => setFileFilter("other")}
                      className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold transition ${
                        fileFilter === "other"
                          ? "bg-white text-emerald-700 shadow-xs"
                          : "text-slate-500 hover:text-slate-900"
                      }`}
                    >
                      Khác ({counts.other})
                    </button>
                  )}
                </div>

                {/* Category Dropdown */}
                <div className="relative">
                  <select
                    value={categoryFilter}
                    onChange={(e) => setCategoryFilter(e.target.value)}
                    aria-label="Lọc theo danh mục"
                    className="h-9 appearance-none rounded-xl border border-slate-200 bg-white pl-3 pr-7 text-xs font-medium text-slate-700 outline-none hover:border-emerald-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 transition cursor-pointer"
                  >
                    <option value="all">Mọi danh mục</option>
                    {categories.map((category) => (
                      <option key={category} value={category}>
                        {category}
                      </option>
                    ))}
                  </select>
                  <CaretDown
                    size={13}
                    className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
                  />
                </div>

                {/* Sort Order Dropdown */}
                <div className="relative">
                  <select
                    value={sortOrder}
                    onChange={(e) => setSortOrder(e.target.value as SortOrder)}
                    aria-label="Sắp xếp tài liệu"
                    className="h-9 appearance-none rounded-xl border border-slate-200 bg-white pl-3 pr-7 text-xs font-medium text-slate-700 outline-none hover:border-emerald-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 transition cursor-pointer"
                  >
                    <option value="newest">Mới nhất</option>
                    <option value="oldest">Cũ nhất</option>
                    <option value="name_asc">Tên A–Z</option>
                    <option value="name_desc">Tên Z–A</option>
                    <option value="size_desc">Dung lượng</option>
                  </select>
                  <CaretDown
                    size={13}
                    className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
                  />
                </div>

                {/* View Mode Switcher: Grid vs List */}
                <div className="flex items-center rounded-xl border border-slate-200 p-0.5 bg-slate-50/80">
                  <button
                    type="button"
                    onClick={() => setViewMode("grid")}
                    className={`flex size-8 items-center justify-center rounded-lg transition ${
                      viewMode === "grid"
                        ? "bg-white text-emerald-700 shadow-xs"
                        : "text-slate-400 hover:text-slate-700"
                    }`}
                    title="Chế độ xem lưới (Grid)"
                    aria-label="Xem lưới"
                  >
                    <SquaresFour size={18} weight="bold" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode("list")}
                    className={`flex size-8 items-center justify-center rounded-lg transition ${
                      viewMode === "list"
                        ? "bg-white text-emerald-700 shadow-xs"
                        : "text-slate-400 hover:text-slate-700"
                    }`}
                    title="Chế độ xem danh sách (List)"
                    aria-label="Xem danh sách"
                  >
                    <List size={18} weight="bold" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Document Content Area */}
          <div className="mt-6">
            {isLoading ? (
              <div className="grid gap-4 md:grid-cols-2">
                {[1, 2, 3, 4].map((n) => (
                  <div
                    key={n}
                    className="h-44 animate-pulse rounded-2xl border border-slate-200/80 bg-slate-100 p-5"
                  />
                ))}
              </div>
            ) : isError ? (
              <div
                role="alert"
                className="rounded-2xl border border-red-200 bg-red-50/60 p-6 text-center text-xs text-red-700"
              >
                <p className="font-semibold text-sm">Không thể tải thư viện tài liệu</p>
                <p className="mt-1 text-red-500">Vui lòng kiểm tra kết nối mạng và thử lại sau.</p>
              </div>
            ) : totalItems === 0 ? (
              <div className="rounded-3xl border border-dashed border-slate-200 bg-white p-12 text-center">
                <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600">
                  <Funnel size={28} weight="duotone" />
                </div>
                <h3 className="mt-4 text-base font-bold text-slate-800">
                  Không tìm thấy tài liệu phù hợp
                </h3>
                <p className="mt-1 text-xs text-slate-400 max-w-sm mx-auto">
                  Hãy thử thay đổi từ khóa tìm kiếm, đặt lại bộ lọc định dạng hoặc chọn lại danh mục học vụ.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setKeyword("");
                    setFileFilter("all");
                    setCategoryFilter("all");
                  }}
                  className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-200 transition"
                >
                  Xóa bộ lọc
                </button>
              </div>
            ) : viewMode === "grid" ? (
              <div className="grid gap-4 md:grid-cols-2">
                {currentItems.map((doc) => (
                  <DocumentCard
                    key={doc.id}
                    document={doc}
                    isSelected={selectedDocument?.id === doc.id}
                    onPreview={(d) => setSelectedDocument(d)}
                    onAsk={(d) => setQuestionTargetDoc(d)}
                  />
                ))}
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {currentItems.map((doc) => (
                  <DocumentRow
                    key={doc.id}
                    document={doc}
                    isSelected={selectedDocument?.id === doc.id}
                    onPreview={(d) => setSelectedDocument(d)}
                    onAsk={(d) => setQuestionTargetDoc(d)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Pagination & Counter Footer */}
          {totalItems > 0 && (
            <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-t border-slate-200/80 pt-5 text-xs text-slate-500">
              <p>
                Hiển thị{" "}
                <strong className="font-semibold text-slate-800">
                  {startIndex + 1} - {Math.min(startIndex + ITEMS_PER_PAGE, totalItems)}
                </strong>{" "}
                trong tổng số{" "}
                <strong className="font-semibold text-slate-800">{totalItems}</strong> tài liệu học vụ
              </p>

              {/* Page Buttons */}
              <div className="flex items-center gap-1.5 self-center sm:self-auto">
                <button
                  type="button"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-xs hover:border-emerald-400 hover:text-emerald-700 disabled:pointer-events-none disabled:opacity-40 transition"
                >
                  <CaretLeft size={13} weight="bold" />
                  <span>Trước</span>
                </button>

                {Array.from({ length: totalPages }, (_, i) => i + 1).map((pageNum) => (
                  <button
                    key={pageNum}
                    type="button"
                    onClick={() => setCurrentPage(pageNum)}
                    className={`flex size-8 items-center justify-center rounded-xl text-xs font-bold transition ${
                      currentPage === pageNum
                        ? "bg-emerald-600 text-white shadow-xs shadow-emerald-900/20"
                        : "border border-slate-200 bg-white text-slate-600 hover:border-emerald-300 hover:text-emerald-700"
                    }`}
                  >
                    {pageNum}
                  </button>
                ))}

                <button
                  type="button"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-xs hover:border-emerald-400 hover:text-emerald-700 disabled:pointer-events-none disabled:opacity-40 transition"
                >
                  <span>Sau</span>
                  <CaretRight size={13} weight="bold" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right Slide-over Preview Drawer */}
      {selectedDocument && (
        <PreviewDrawer
          document={selectedDocument}
          onClose={() => setSelectedDocument(null)}
          onAsk={(question) => void handleAskQuestion(question, selectedDocument)}
        />
      )}

      {/* Contextual Smart Question Modal */}
      {questionTargetDoc && (
        <QuickQuestionModal
          document={questionTargetDoc}
          onClose={() => setQuestionTargetDoc(null)}
          onAsk={(question) => void handleAskQuestion(question, questionTargetDoc)}
        />
      )}
    </section>
  );
}
