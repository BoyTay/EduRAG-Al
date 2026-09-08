import { GraduationCap, Sparkle } from "@phosphor-icons/react";

export function Brand({
  compact = false,
  theme = "dark",
}: {
  compact?: boolean;
  theme?: "light" | "dark";
}) {
  const isDark = theme === "dark";

  return (
    <div className="flex items-center gap-3">
      {/* Premium Gradient Logo Icon */}
      <div className="relative flex size-10 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-tr from-emerald-600 via-teal-500 to-emerald-400 p-0.5 shadow-md shadow-emerald-950/50 ring-1 ring-white/25">
        <div className="flex size-full items-center justify-center rounded-[14px] bg-slate-950/20 backdrop-blur-xs">
          <GraduationCap size={22} weight="duotone" className="text-white drop-shadow-xs" />
        </div>
        <span className="absolute -bottom-0.5 -right-0.5 flex size-3.5 items-center justify-center rounded-full bg-emerald-400 text-slate-950 shadow-xs">
          <Sparkle size={9} weight="fill" />
        </span>
      </div>

      {/* Typography */}
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <p className={`text-xl font-extrabold tracking-tight ${isDark ? "text-white" : "text-slate-900"}`}>
            Edu<span className="bg-gradient-to-r from-emerald-400 to-teal-300 bg-clip-text text-transparent">RAG</span>
          </p>
          <span className="rounded-md border border-emerald-500/30 bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-black tracking-wider text-emerald-400 uppercase">
            AI
          </span>
        </div>
        {!compact && (
          <p className={`text-[11px] font-medium tracking-wide truncate ${isDark ? "text-slate-400" : "text-slate-500"}`}>
            Hệ thống Trợ lý Học vụ AI
          </p>
        )}
      </div>
    </div>
  );
}
