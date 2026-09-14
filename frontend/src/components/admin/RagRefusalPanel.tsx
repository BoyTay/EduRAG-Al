import { ArrowRight, ShieldWarning } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getRagRefusals } from "../../services/api";

function relativeTime(dateStr: string) {
  const diff = Math.max(0, Date.now() - new Date(dateStr).getTime());
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "Vừa xong";
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  const days = Math.floor(hours / 24);
  return days < 30 ? `${days} ngày trước` : new Date(dateStr).toLocaleDateString("vi-VN");
}

function parseScore(question: string | null): string | null {
  if (!question) return null;
  const match = question.match(/\[low_score=([0-9.]+)\]/);
  return match ? match[1] : null;
}

function cleanQuestion(question: string | null): string {
  if (!question) return "Không rõ câu hỏi";
  return question.replace(/\s*\[.*?\]\s*$/, "").trim() || "Không rõ câu hỏi";
}

export function RagRefusalPanel() {
  const [expanded, setExpanded] = useState(false);
  const { data: refusals = [] } = useQuery({
    queryKey: ["rag-refusals"],
    queryFn: () => getRagRefusals(50),
    refetchInterval: 60_000,
  });

  const visible = expanded ? refusals : refusals.slice(0, 5);

  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-[0_2px_12px_rgba(0,0,0,0.03)]">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-slate-800">
          <ShieldWarning size={20} weight="duotone" className="text-orange-500" />
          <h3 className="text-sm font-bold tracking-tight">Câu hỏi bị từ chối</h3>
          {refusals.length > 0 && (
            <span className="inline-flex items-center rounded-md bg-orange-50 px-2 py-0.5 text-[11px] font-semibold text-orange-600">
              {refusals.length}
            </span>
          )}
        </div>
        {refusals.length > 5 && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="inline-flex items-center gap-1 text-xs font-semibold text-orange-600 transition hover:text-orange-700"
          >
            <span>{expanded ? "Thu gọn" : "Xem thêm"}</span>
            <ArrowRight size={13} weight="bold" className={expanded ? "rotate-90" : ""} />
          </button>
        )}
      </div>

      {/* List */}
      <div className="mt-5 space-y-3">
        {visible.length ? (
          visible.map((r) => {
            const score = parseScore(r.question);
            return (
              <div key={r.id} className="flex items-start justify-between gap-3 text-xs">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-slate-700" title={cleanQuestion(r.question)}>
                    {cleanQuestion(r.question)}
                  </p>
                  <div className="mt-0.5 flex items-center gap-2 text-slate-400">
                    <span>{r.actor}</span>
                    {score && (
                      <span className="inline-flex items-center rounded bg-orange-50 px-1.5 py-0.5 text-[10px] font-semibold text-orange-600">
                        score {score}
                      </span>
                    )}
                  </div>
                </div>
                <span className="shrink-0 whitespace-nowrap font-medium text-slate-400">
                  {relativeTime(r.created_at)}
                </span>
              </div>
            );
          })
        ) : (
          <p className="rounded-xl border border-dashed border-slate-200 px-4 py-5 text-center text-xs text-slate-400">
            Chưa có câu hỏi nào bị từ chối.
          </p>
        )}
      </div>

      {/* Tuning hint */}
      {refusals.length > 0 && (
        <p className="mt-4 rounded-lg bg-slate-50 px-3 py-2 text-[11px] leading-relaxed text-slate-500">
          Nếu nhiều câu hỏi hợp lệ bị từ chối, hãy giảm{" "}
          <code className="rounded bg-slate-100 px-1 py-0.5 text-[10px] font-semibold text-slate-600">
            MIN_RELEVANCE_SCORE
          </code>{" "}
          trong <code className="rounded bg-slate-100 px-1 py-0.5 text-[10px] font-semibold text-slate-600">.env</code>{" "}
          (hiện tại: 0.30).
        </p>
      )}
    </div>
  );
}
