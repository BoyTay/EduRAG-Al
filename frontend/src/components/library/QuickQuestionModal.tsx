import { ChatCircleDots, PaperPlaneTilt, Sparkle, X } from "@phosphor-icons/react";
import type { Document } from "../../types";

interface QuickQuestionModalProps {
  document: Document;
  onClose: () => void;
  onAsk: (question: string) => void;
}

export function QuickQuestionModal({ document, onClose, onAsk }: QuickQuestionModalProps) {
  const title = document.display_name || document.filename;
  const category = (document.category || "").toLowerCase();

  // Dynamic context-aware suggested questions based on document title and category
  const getSuggestedQuestions = () => {
    if (category.includes("học bổng") || title.toLowerCase().includes("học bổng")) {
      return [
        `Điều kiện GPA và Điểm rèn luyện để được xét học bổng trong "${title}" là gì?`,
        `Hồ sơ, thủ tục và thời hạn đăng ký xét cấp học bổng quy định như thế nào?`,
        `Các mức học bổng và tiêu chí ưu tiên xét tuyển bao gồm những gì?`,
      ];
    }
    if (category.includes("học phí") || title.toLowerCase().includes("học phí") || title.toLowerCase().includes("học phần")) {
      return [
        `Quy định thời hạn và các hình thức đóng học phí theo "${title}"?`,
        `Quy trình hủy môn, rút bớt học phần hoặc bảo lưu học phí như thế nào?`,
        `Sinh viên có hoàn cảnh khó khăn có được gia hạn hoặc miễn giảm học phí không?`,
      ];
    }
    if (category.includes("đào tạo") || title.toLowerCase().includes("tín chỉ") || title.toLowerCase().includes("chuẩn đầu ra")) {
      return [
        `Nội dung cốt lõi và các mốc quy định quan trọng nhất trong "${title}"?`,
        `Điều kiện xét tốt nghiệp và chuẩn đầu ra được quy định cụ thể ra sao?`,
        `Quy định về đăng ký học lại, cải thiện điểm và xử lý cảnh báo học vụ?`,
      ];
    }
    if (category.includes("công tác") || category.includes("kỷ luật") || title.toLowerCase().includes("khen thưởng")) {
      return [
        `Các mức khen thưởng hoặc hình thức xử lý vi phạm được quy định thế nào?`,
        `Quy trình đánh giá điểm rèn luyện và khiếu nại nếu có sai sót?`,
        `Quyền lợi và nghĩa vụ của sinh viên được đề cập trong văn bản này là gì?`,
      ];
    }
    return [
      `Tóm tắt 3 nội dung cốt lõi sinh viên cần nắm trong "${title}"?`,
      `Đối tượng áp dụng và phạm vi hiệu lực của quy định này là gì?`,
      `Những lưu ý hoặc mốc thời gian quan trọng cần tuân thủ?`,
    ];
  };

  const suggestions = getSuggestedQuestions();

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-lg rounded-3xl border border-slate-200/80 bg-white p-6 shadow-2xl shadow-emerald-950/15 transition-all"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <span className="flex size-10 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 ring-1 ring-emerald-500/20">
              <Sparkle size={20} weight="duotone" />
            </span>
            <div>
              <p className="text-[11px] font-bold tracking-wider text-emerald-700 uppercase">Hỏi đáp AI theo ngữ cảnh</p>
              <h3 className="text-base font-bold text-slate-900 line-clamp-1" title={title}>
                {title}
              </h3>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex size-8 items-center justify-center rounded-xl text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
            aria-label="Đóng"
          >
            <X size={18} />
          </button>
        </div>

        <p className="mt-4 text-xs text-slate-500 leading-relaxed">
          Chọn một câu hỏi gợi ý bên dưới hoặc bấm nút <strong className="text-slate-700">Hỏi tổng quát</strong> để AI phân tích toàn bộ văn bản này cho bạn:
        </p>

        {/* Suggestion Chips */}
        <div className="mt-3.5 space-y-2.5">
          {suggestions.map((q, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => onAsk(q)}
              className="group flex w-full items-center justify-between gap-3 rounded-2xl border border-slate-100 bg-slate-50/70 p-3.5 text-left text-xs font-medium text-slate-700 transition hover:border-emerald-300 hover:bg-emerald-50/50 hover:text-emerald-900 active:scale-[0.99]"
            >
              <div className="flex items-center gap-2.5">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-lg bg-white text-emerald-600 shadow-xs ring-1 ring-slate-200/60 group-hover:bg-emerald-600 group-hover:text-white transition">
                  <ChatCircleDots size={14} weight="bold" />
                </span>
                <span className="line-clamp-2">{q}</span>
              </div>
              <PaperPlaneTilt
                size={14}
                className="shrink-0 text-slate-400 group-hover:translate-x-0.5 group-hover:text-emerald-600 transition"
              />
            </button>
          ))}
        </div>

        {/* Quick actions footer */}
        <div className="mt-5 flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl px-4 py-2 text-xs font-medium text-slate-500 hover:bg-slate-100 transition"
          >
            Đóng
          </button>
          <button
            type="button"
            onClick={() => onAsk(`Cho tôi biết tóm tắt nội dung chính và các quy định cốt lõi của tài liệu: ${title}`)}
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm shadow-emerald-900/20 hover:bg-emerald-700 active:scale-[0.98] transition"
          >
            <Sparkle size={15} weight="bold" />
            <span>Hỏi tổng quát văn bản này</span>
          </button>
        </div>
      </div>
    </div>
  );
}
