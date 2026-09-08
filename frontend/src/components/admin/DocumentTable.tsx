import {
  CaretDown,
  CaretLeft,
  CaretRight,
  FileDoc,
  FilePdf,
  FileText,
  MagnifyingGlass,
  PencilSimple,
  Trash,
  X,
} from "@phosphor-icons/react";
import { useEffect, useMemo, useState } from "react";
import type { Document } from "../../types";

interface DocumentTableProps {
  documents: Document[];
  onEdit: (document: Document) => void;
  onDelete: (document: Document) => void;
}

const ITEMS_PER_PAGE = 5;

function formatDate(dateStr?: string) {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    const day = String(d.getDate()).padStart(2, "0");
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const year = d.getFullYear();
    return `${day}/${month}/${year}`;
  } catch {
    return dateStr;
  }
}

export function DocumentTable({ documents, onEdit, onDelete }: DocumentTableProps) {
  const [keyword, setKeyword] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sortOrder, setSortOrder] = useState<"newest" | "oldest" | "name" | "chunks">("newest");
  const [currentPage, setCurrentPage] = useState(1);

  // Extract unique categories
  const categories = useMemo(() => {
    const set = new Set<string>();
    documents.forEach((doc) => {
      if (doc.category && doc.category.trim()) {
        set.add(doc.category.trim());
      }
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b, "vi"));
  }, [documents]);

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [keyword, categoryFilter, sortOrder]);

  // Filter & Sort
  const filtered = useMemo(() => {
    return documents
      .filter((doc) => {
        const query = keyword.trim().toLowerCase();
        if (!query) return true;
        const searchable = `${doc.filename} ${doc.display_name || ""} ${doc.issuing_unit || ""} ${
          doc.category || ""
        }`.toLowerCase();
        return searchable.includes(query);
      })
      .filter((doc) => {
        if (categoryFilter === "all") return true;
        return (doc.category || "").trim() === categoryFilter;
      })
      .sort((a, b) => {
        switch (sortOrder) {
          case "oldest":
            return new Date(a.uploaded_at).getTime() - new Date(b.uploaded_at).getTime();
          case "name":
            return (a.display_name || a.filename).localeCompare(b.display_name || b.filename, "vi");
          case "chunks":
            return b.chunk_count - a.chunk_count;
          case "newest":
          default:
            return new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime();
        }
      });
  }, [documents, keyword, categoryFilter, sortOrder]);

  // Pagination
  const totalItems = filtered.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / ITEMS_PER_PAGE));
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const currentDocs = filtered.slice(startIndex, startIndex + ITEMS_PER_PAGE);

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-[0_2px_12px_rgba(0,0,0,0.03)]">
      {/* Table Toolbar */}
      <div className="flex flex-col gap-4 border-b border-slate-100 p-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
              <FileText size={18} weight="duotone" />
            </span>
            <h2 className="text-base font-bold text-slate-900">Danh sách tài liệu</h2>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Quản lý các tài liệu đang được sử dụng trong hệ thống.
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Search Input */}
          <div className="relative min-w-[200px] flex-1 sm:w-60">
            <MagnifyingGlass
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="Tìm kiếm tài liệu..."
              className="h-9 w-full rounded-xl border border-slate-200 bg-slate-50/70 pl-9 pr-7 text-xs text-slate-800 placeholder:text-slate-400 outline-none transition focus:border-emerald-500 focus:bg-white focus:ring-2 focus:ring-emerald-100"
            />
            {keyword && (
              <button
                type="button"
                onClick={() => setKeyword("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X size={13} />
              </button>
            )}
          </div>

          {/* Category Dropdown */}
          <div className="relative">
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="h-9 appearance-none rounded-xl border border-slate-200 bg-white pl-3 pr-7 text-xs font-medium text-slate-700 outline-none hover:border-emerald-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 transition cursor-pointer"
            >
              <option value="all">Tất cả danh mục</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <CaretDown
              size={13}
              className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
            />
          </div>

          {/* Sort Dropdown */}
          <div className="relative">
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as any)}
              className="h-9 appearance-none rounded-xl border border-slate-200 bg-white pl-3 pr-7 text-xs font-medium text-slate-700 outline-none hover:border-emerald-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 transition cursor-pointer"
            >
              <option value="newest">⇅ Mới nhất</option>
              <option value="oldest">⇅ Cũ nhất</option>
              <option value="name">⇅ Tên A–Z</option>
              <option value="chunks">⇅ Số đoạn dữ liệu</option>
            </select>
            <CaretDown
              size={13}
              className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
            />
          </div>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#f8fafc] text-slate-500 font-semibold border-b border-slate-100">
            <tr>
              <th className="px-5 py-3">Tên hiển thị / Danh mục</th>
              <th className="px-4 py-3">Đơn vị ban hành</th>
              <th className="px-3 py-3 text-center">Năm</th>
              <th className="px-3 py-3 text-center">Đoạn dữ liệu</th>
              <th className="px-4 py-3 text-center">Trạng thái</th>
              <th className="px-4 py-3">Cập nhật</th>
              <th className="px-5 py-3 text-right">Thao tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {currentDocs.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-10 text-center text-slate-400 text-xs">
                  Không tìm thấy tài liệu nào phù hợp với điều kiện tìm kiếm.
                </td>
              </tr>
            ) : (
              currentDocs.map((doc) => {
                const isPdf = doc.file_type.toLowerCase() === "pdf";
                const isDocx = doc.file_type.toLowerCase() === "docx";
                const title = doc.display_name || doc.filename;

                return (
                  <tr key={doc.id} className="hover:bg-slate-50/70 transition">
                    {/* Title & Format Icon */}
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <span
                          className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${
                            isPdf
                              ? "bg-rose-50 text-rose-600"
                              : isDocx
                              ? "bg-blue-50 text-blue-600"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {isPdf ? (
                            <FilePdf size={20} weight="duotone" />
                          ) : isDocx ? (
                            <FileDoc size={20} weight="duotone" />
                          ) : (
                            <FileText size={20} weight="duotone" />
                          )}
                        </span>
                        <div className="min-w-0">
                          <p className="font-bold text-slate-900 truncate max-w-xs" title={title}>
                            {title}
                          </p>
                          <span className="mt-0.5 inline-block text-[11px] font-medium text-slate-400">
                            {doc.category || "Chưa phân loại"}
                          </span>
                        </div>
                      </div>
                    </td>

                    {/* Issuing Unit */}
                    <td className="px-4 py-3.5 text-slate-600 font-medium">
                      {doc.issuing_unit || "—"}
                    </td>

                    {/* Year */}
                    <td className="px-3 py-3.5 text-center text-slate-600 font-medium">
                      {doc.document_year || "—"}
                    </td>

                    {/* Chunks */}
                    <td className="px-3 py-3.5 text-center text-slate-600 font-semibold">
                      {doc.chunk_count}
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3.5 text-center">
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                        <span className="size-1.5 rounded-full bg-emerald-500" />
                        <span>Hoạt động</span>
                      </span>
                    </td>

                    {/* Updated At */}
                    <td className="px-4 py-3.5 text-slate-500 font-medium">
                      {formatDate(doc.uploaded_at)}
                    </td>

                    {/* Action Buttons */}
                    <td className="px-5 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => onEdit(doc)}
                          className="flex size-7 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
                          title="Chỉnh sửa tài liệu"
                        >
                          <PencilSimple size={15} />
                        </button>
                        <button
                          type="button"
                          onClick={() => onDelete(doc)}
                          className="flex size-7 items-center justify-center rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-600 transition"
                          title="Xóa tài liệu"
                        >
                          <Trash size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="flex flex-col gap-3 border-t border-slate-100 px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between text-xs text-slate-500">
        <p>
          Hiển thị{" "}
          <strong className="font-semibold text-slate-800">
            {totalItems > 0 ? startIndex + 1 : 0} - {Math.min(startIndex + ITEMS_PER_PAGE, totalItems)}
          </strong>{" "}
          của <strong className="font-semibold text-slate-800">{totalItems}</strong> tài liệu
        </p>

        {/* Page Buttons */}
        <div className="flex items-center gap-1 self-center sm:self-auto">
          <button
            type="button"
            disabled={currentPage === 1}
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            className="flex size-7 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:border-emerald-400 hover:text-emerald-700 disabled:opacity-40 disabled:pointer-events-none transition"
            aria-label="Trang trước"
          >
            <CaretLeft size={13} weight="bold" />
          </button>

          {Array.from({ length: totalPages }, (_, i) => i + 1).map((pageNum) => (
            <button
              key={pageNum}
              type="button"
              onClick={() => setCurrentPage(pageNum)}
              className={`flex size-7 items-center justify-center rounded-lg text-xs font-bold transition ${
                currentPage === pageNum
                  ? "bg-emerald-600 text-white shadow-xs"
                  : "border border-slate-200 text-slate-600 hover:border-emerald-300 hover:text-emerald-700"
              }`}
            >
              {pageNum}
            </button>
          ))}

          <button
            type="button"
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            className="flex size-7 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:border-emerald-400 hover:text-emerald-700 disabled:opacity-40 disabled:pointer-events-none transition"
            aria-label="Trang sau"
          >
            <CaretRight size={13} weight="bold" />
          </button>
        </div>
      </div>
    </div>
  );
}
