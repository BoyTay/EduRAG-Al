import { ChartPieSlice } from "@phosphor-icons/react";
import { useMemo } from "react";
import type { Document } from "../../types";

interface CategoryChartProps {
  documents: Document[];
}

const CATEGORY_COLORS = [
  "#10b981", // Emerald (Công tác sinh viên)
  "#3b82f6", // Blue (Đào tạo)
  "#f59e0b", // Amber (Học bổng)
  "#8b5cf6", // Purple (Học phí & Học phần)
  "#06b6d4", // Cyan
  "#ec4899", // Pink
  "#94a3b8", // Slate (Khác)
];

export function CategoryChart({ documents }: CategoryChartProps) {
  const { slices, total } = useMemo(() => {
    const totalCount = documents.length;
    if (totalCount === 0) {
      return { slices: [], total: 0 };
    }

    const counts: Record<string, number> = {};
    documents.forEach((doc) => {
      const cat = doc.category?.trim() || "Khác";
      counts[cat] = (counts[cat] || 0) + 1;
    });

    const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);

    const circumference = 2 * Math.PI * 46; // radius 46 -> C ≈ 289.02
    let accumulatedAngle = 0;

    const computedSlices = entries.map(([name, count], index) => {
      const percentage = (count / totalCount) * 100;
      const strokeLength = (count / totalCount) * circumference;
      const offset = (accumulatedAngle / 100) * circumference;
      accumulatedAngle += percentage;

      return {
        name,
        count,
        percentage: Math.round(percentage),
        color: CATEGORY_COLORS[index % CATEGORY_COLORS.length],
        strokeDasharray: `${strokeLength} ${circumference - strokeLength}`,
        strokeDashoffset: -offset,
      };
    });

    return { slices: computedSlices, total: totalCount };
  }, [documents]);

  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-[0_2px_12px_rgba(0,0,0,0.03)]">
      {/* Header */}
      <div className="flex items-center gap-2 text-slate-800">
        <ChartPieSlice size={20} weight="duotone" className="text-emerald-600" />
        <h3 className="font-bold text-sm tracking-tight">Phân bố danh mục tài liệu</h3>
      </div>

      {/* Content: Donut Chart + Legend */}
      <div className="mt-6 flex flex-col items-center justify-between gap-6 sm:flex-row sm:gap-8">
        {/* SVG Donut Chart */}
        <div className="relative flex size-36 shrink-0 items-center justify-center">
          <svg className="size-full -rotate-90" viewBox="0 0 120 120">
            {/* Background circle track */}
            <circle
              cx="60"
              cy="60"
              r="46"
              fill="none"
              stroke="#f1f5f9"
              strokeWidth="16"
            />

            {/* Slices */}
            {slices.map((slice) => (
              <circle
                key={slice.name}
                cx="60"
                cy="60"
                r="46"
                fill="none"
                stroke={slice.color}
                strokeWidth="16"
                strokeDasharray={slice.strokeDasharray}
                strokeDashoffset={slice.strokeDashoffset}
                strokeLinecap="butt"
                className="transition-all duration-500 ease-out"
              />
            ))}
          </svg>

          {/* Center Text (Total count + label) */}
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="text-2xl font-black tracking-tight text-slate-900 leading-none">
              {total}
            </span>
            <span className="mt-1 text-[11px] font-semibold text-slate-400">
              Tài liệu
            </span>
          </div>
        </div>

        {/* Category Legend List */}
        <div className="w-full flex-1 space-y-3">
          {slices.length === 0 ? (
            <p className="text-xs text-slate-400">Chưa có tài liệu nào trong hệ thống.</p>
          ) : (
            slices.map((slice) => (
              <div
                key={slice.name}
                className="flex items-center justify-between gap-3 text-xs font-medium"
              >
                <div className="flex items-center gap-2 truncate">
                  <span
                    className="size-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: slice.color }}
                  />
                  <span className="truncate text-slate-700" title={slice.name}>
                    {slice.name}
                  </span>
                </div>
                <span className="shrink-0 text-slate-500 font-semibold">
                  {slice.percentage}% ({slice.count})
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
