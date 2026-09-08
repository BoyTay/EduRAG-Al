import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarBlank,
  CaretDown,
  CaretUp,
  ChatCircleDots,
  Check,
  Copy,
  DotsThreeVertical,
  FileText,
  MagnifyingGlass,
  Trash,
  X,
} from "@phosphor-icons/react";
import { deleteSession, getHistory, getSessions } from "../../services/api";
import { useAuthStore } from "../../stores/authStore";
import { useChatStore } from "../../stores/chatStore";
import type { SessionInfo } from "../../types";

function parseApiDate(timestamp: string) {
  return new Date(
    /[zZ]|[+-]\d\d:\d\d$/.test(timestamp)
      ? timestamp
      : `${timestamp.replace(" ", "T")}Z`
  );
}

function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

function dateGroup(timestamp?: string) {
  if (!timestamp) return "CŨ HƠN";
  const date = parseApiDate(timestamp);
  if (Number.isNaN(date.getTime())) return "CŨ HƠN";
  const days = Math.round(
    (startOfDay(new Date()) - startOfDay(date)) / 86_400_000
  );
  if (days === 0) return "HÔM NAY";
  if (days === 1) return "HÔM QUA";
  if (days <= 7) return "7 NGÀY QUA";
  if (days <= 30) return "30 NGÀY QUA";
  return `THÁNG ${date.getMonth() + 1}/${date.getFullYear()}`;
}

function formatTime(timestamp?: string) {
  if (!timestamp) return "";
  const date = parseApiDate(timestamp);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function groupedSessions(sessions: SessionInfo[]) {
  const groups = new Map<string, SessionInfo[]>();
  for (const session of sessions) {
    const label = dateGroup(session.last_time);
    groups.set(label, [...(groups.get(label) || []), session]);
  }
  return [...groups.entries()];
}

export function ConversationHistory() {
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const current = useChatStore((state) => state.sessionId);
  const loadSession = useChatStore((state) => state.loadSession);
  const newChat = useChatStore((state) => state.newChat);

  const [searchQuery, setSearchQuery] = useState("");
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const { data = [], isLoading } = useQuery({
    queryKey: ["sessions", user?.role, user?.id],
    queryFn: getSessions,
    retry: false,
  });

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setActiveMenuId(null);
      }
    }
    if (activeMenuId) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [activeMenuId]);

  const toggleGroup = (label: string) => {
    setCollapsedGroups((prev) => ({
      ...prev,
      [label]: !prev[label],
    }));
  };

  const open = async (id: string) => {
    setActiveMenuId(null);
    const messages = await getHistory(id);
    loadSession(id, messages);
  };

  const handleCopyTitle = (session: SessionInfo) => {
    const text = session.title || session.session_id;
    navigator.clipboard.writeText(text);
    setCopiedId(session.session_id);
    setTimeout(() => {
      setCopiedId(null);
      setActiveMenuId(null);
    }, 1200);
  };

  const handleDelete = async (sessionId: string) => {
    try {
      await deleteSession(sessionId);
      if (current === sessionId) {
        newChat();
      }
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    } catch {
      // Ignored
    } finally {
      setActiveMenuId(null);
    }
  };

  // Filter sessions by title or session ID
  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return data;
    const q = searchQuery.toLowerCase().trim();
    return data.filter(
      (s) =>
        (s.title && s.title.toLowerCase().includes(q)) ||
        s.session_id.toLowerCase().includes(q)
    );
  }, [data, searchQuery]);

  const groups = useMemo(
    () => groupedSessions(filteredSessions),
    [filteredSessions]
  );

  return (
    <section className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      {/* Search Input matching reference image */}
      <div className="relative mb-3 shrink-0">
        <MagnifyingGlass
          size={14}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
        />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Tìm lịch sử hội thoại..."
          className="w-full rounded-xl border border-slate-700/60 bg-[#0d1c31]/80 py-2 pl-9 pr-8 text-xs text-slate-200 placeholder-slate-400 transition-colors focus:border-teal-500/50 focus:bg-[#0e2038] focus:outline-none focus:ring-1 focus:ring-teal-500/30"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery("")}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
            title="Xóa tìm kiếm"
          >
            <X size={13} />
          </button>
        )}
      </div>

      {/* Scrollable Conversation List */}
      <div className="custom-history-scrollbar min-h-0 flex-1 space-y-3.5 overflow-y-auto pr-1">
        {isLoading ? (
          <div className="space-y-2 px-1 py-1">
            <span className="block h-10 animate-pulse rounded-xl bg-slate-800/60" />
            <span className="block h-9 animate-pulse rounded-xl bg-slate-800/60" />
            <span className="block h-9 animate-pulse rounded-xl bg-slate-800/60" />
            <span className="block h-9 animate-pulse rounded-xl bg-slate-800/60" />
          </div>
        ) : filteredSessions.length > 0 ? (
          groups.map(([label, sessions]) => {
            const isCollapsed = Boolean(collapsedGroups[label]);
            const isToday = label === "HÔM NAY";

            return (
              <div key={label} className="space-y-1.5">
                {/* Accordion Group Header Card matching mockup */}
                <button
                  type="button"
                  onClick={() => toggleGroup(label)}
                  className="flex w-full items-center justify-between rounded-xl border border-slate-700/50 bg-[#0e1f38]/90 px-3 py-2 text-left transition-colors hover:bg-[#112644] active:scale-[0.99]"
                >
                  {/* Left: Calendar Icon + Group Label */}
                  <div className="flex items-center gap-2.5">
                    <CalendarBlank
                      size={17}
                      weight="fill"
                      className="text-emerald-400"
                    />
                    <span className="text-xs font-bold tracking-wider text-slate-100">
                      {label}
                    </span>
                  </div>

                  {/* Right: Badge Count + Accordion Chevron */}
                  <div className="flex items-center gap-2">
                    <span
                      className={`min-w-5 rounded-full px-2 py-0.5 text-center text-[11px] font-bold ${
                        isToday
                          ? "bg-emerald-600 text-white shadow-xs"
                          : "border border-slate-700/60 bg-slate-800 text-slate-300 font-semibold"
                      }`}
                    >
                      {sessions.length}
                    </span>
                    {isCollapsed ? (
                      <CaretDown size={14} className="text-slate-400" />
                    ) : (
                      <CaretUp size={14} className="text-slate-400" />
                    )}
                  </div>
                </button>

                {/* Session Items List */}
                {!isCollapsed && (
                  <div className="space-y-1 pt-0.5">
                    {sessions.map((session) => {
                      const active = current === session.session_id;
                      const displayTitle =
                        session.title || `Hội thoại ${session.session_id.slice(0, 8)}`;
                      const timeString = formatTime(session.last_time);
                      const isMenuOpen = activeMenuId === session.session_id;

                      return (
                        <div
                          key={session.session_id}
                          className="relative flex items-center"
                        >
                          {/* Left Glowing Indicator Bar (for Active item) */}
                          <div
                            className={`w-1.5 shrink-0 transition-all ${
                              active
                                ? "mr-1.5 h-7 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.9)] opacity-100"
                                : "mr-1.5 h-7 opacity-0 pointer-events-none"
                            }`}
                            aria-hidden="true"
                          />

                          {/* Session Item Card */}
                          <div
                            onClick={() => void open(session.session_id)}
                            className={`group relative flex min-w-0 flex-1 cursor-pointer items-center gap-2.5 rounded-xl px-2.5 py-2 transition duration-150 select-none ${
                              active
                                ? "border border-emerald-500/40 bg-[#082b2b] text-white shadow-sm"
                                : "border border-transparent text-slate-300 hover:border-slate-750 hover:bg-slate-850/70 hover:text-white"
                            }`}
                          >
                            {/* File/Document Icon in Squircle */}
                            <div
                              className={`flex size-7 shrink-0 items-center justify-center rounded-lg border transition-colors ${
                                active
                                  ? "border-emerald-500/40 bg-emerald-500/25 text-emerald-300"
                                  : "border-slate-700/60 bg-slate-800/90 text-slate-400 group-hover:border-slate-600 group-hover:text-slate-200"
                              }`}
                            >
                              <FileText size={15} weight="regular" />
                            </div>

                            {/* Session Title */}
                            <span
                              className={`min-w-0 flex-1 truncate text-xs ${
                                active ? "font-semibold text-white" : "font-medium text-slate-200"
                              }`}
                              title={displayTitle}
                            >
                              {displayTitle}
                            </span>

                            {/* Timestamp (e.g. 14:32) */}
                            {timeString && (
                              <span className="shrink-0 font-mono text-[11px] text-slate-400">
                                {timeString}
                              </span>
                            )}

                            {/* 3-Dots Action Button */}
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setActiveMenuId(isMenuOpen ? null : session.session_id);
                              }}
                              className="shrink-0 rounded p-1 text-slate-400 transition hover:bg-white/10 hover:text-white"
                              title="Tùy chọn"
                            >
                              <DotsThreeVertical size={16} weight="bold" />
                            </button>
                          </div>

                          {/* Floating Action Menu for 3-Dots */}
                          {isMenuOpen && (
                            <div
                              ref={menuRef}
                              className="absolute right-0 top-full z-50 mt-1 w-44 rounded-xl border border-slate-700/80 bg-[#0f1d33] p-1.5 shadow-2xl backdrop-blur-md animate-in fade-in zoom-in-95 duration-100"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {/* Copy Title */}
                              <button
                                type="button"
                                onClick={() => handleCopyTitle(session)}
                                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs text-slate-300 transition hover:bg-slate-800 hover:text-white"
                              >
                                {copiedId === session.session_id ? (
                                  <>
                                    <Check size={14} className="text-emerald-400" />
                                    <span className="text-emerald-300 font-medium">Đã sao chép</span>
                                  </>
                                ) : (
                                  <>
                                    <Copy size={14} className="text-slate-400" />
                                    <span>Sao chép câu hỏi</span>
                                  </>
                                )}
                              </button>

                              <div className="my-1 border-t border-slate-800" />

                              {/* Delete Session */}
                              <button
                                type="button"
                                onClick={() => void handleDelete(session.session_id)}
                                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs text-rose-400 transition hover:bg-rose-950/40 hover:text-rose-300"
                              >
                                <Trash size={14} />
                                <span>Xóa đoạn chat này</span>
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        ) : searchQuery ? (
          <div className="px-3 py-6 text-center text-xs text-slate-400">
            <p className="font-medium text-slate-300">Không tìm thấy</p>
            <p className="mt-1 text-[11px] text-slate-500">
              Không có hội thoại nào khớp với "{searchQuery}"
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center px-3 py-8 text-center text-slate-400">
            <ChatCircleDots size={28} className="mb-2 text-slate-600" />
            <p className="text-xs font-medium text-slate-300">
              Chưa có lịch sử hội thoại
            </p>
            <p className="mt-1 text-[11px] text-slate-500">
              Bắt đầu đặt câu hỏi để lưu vào đây.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
