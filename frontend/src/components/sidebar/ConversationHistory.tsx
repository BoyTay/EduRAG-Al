import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CaretDown,
  ChatCircleDots,
  Check,
  Copy,
  DotsThreeVertical,
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
      {/* Ô tìm kiếm */}
      <label className="flex h-[38px] shrink-0 items-center gap-2 rounded-[10px] border border-[rgba(148,163,184,.14)] bg-[rgba(148,163,184,.08)] px-3 text-[#8d9bb0] focus-within:border-[#34d399] focus-within:text-[#d1fae5]">
        <MagnifyingGlass size={16} aria-hidden="true" className="shrink-0" />
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Tìm lịch sử hội thoại…"
          aria-label="Tìm lịch sử hội thoại"
          className="min-w-0 flex-1 border-0 bg-transparent text-[13px] text-[#e6edf6] outline-none placeholder:text-[#8d9bb0] [&::-webkit-search-cancel-button]:appearance-none"
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => setSearchQuery("")}
            aria-label="Xóa tìm kiếm"
            title="Xóa tìm kiếm"
            className="shrink-0 rounded text-[#8d9bb0] hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#34d399]"
          >
            <X size={13} aria-hidden="true" />
          </button>
        )}
      </label>

      {/* Danh sách hội thoại */}
      <div className="custom-history-scrollbar -mr-1.5 mt-2.5 min-h-0 flex-1 overflow-y-auto pr-1.5">
        {isLoading ? (
          <div className="space-y-1 py-1" aria-busy="true">
            {[0, 1, 2, 3].map((i) => (
              <span key={i} className="block h-[38px] animate-pulse rounded-[10px] bg-[rgba(148,163,184,.08)]" />
            ))}
          </div>
        ) : filteredSessions.length > 0 ? (
          groups.map(([label, sessions]) => {
            const isCollapsed = Boolean(collapsedGroups[label]);

            return (
              <div key={label} className="mb-1.5">
                <button
                  type="button"
                  onClick={() => toggleGroup(label)}
                  aria-expanded={!isCollapsed}
                  className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-[11px] font-bold uppercase tracking-[.08em] text-[#8d9bb0] transition-colors hover:bg-[rgba(148,163,184,.08)] hover:text-[#dbe4f0] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#34d399]"
                >
                  <CaretDown
                    size={14}
                    weight="bold"
                    aria-hidden="true"
                    className={`shrink-0 transition-transform duration-150 ${isCollapsed ? "-rotate-90" : ""}`}
                  />
                  <span className="flex-1 text-left">{label}</span>
                  <span className="text-[11px] font-bold tracking-normal text-[#8d9bb0]">
                    {sessions.length}
                  </span>
                </button>

                {!isCollapsed && (
                  <div className="mt-0.5 flex flex-col gap-px">
                    {sessions.map((session) => {
                      const active = current === session.session_id;
                      const displayTitle =
                        session.title || `Hội thoại ${session.session_id.slice(0, 8)}`;
                      const timeString = formatTime(session.last_time);
                      const isMenuOpen = activeMenuId === session.session_id;

                      return (
                        <div key={session.session_id} className="group relative">
                          <button
                            type="button"
                            onClick={() => void open(session.session_id)}
                            aria-current={active ? "true" : undefined}
                            title={displayTitle}
                            className={`flex h-[38px] w-full items-center gap-2 rounded-[10px] px-2.5 text-left text-[13px] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#34d399] ${
                              active
                                ? "bg-[rgba(148,163,184,.16)] font-semibold text-white"
                                : "font-medium text-[#c3cddb] hover:bg-[rgba(148,163,184,.10)] hover:text-white"
                            }`}
                          >
                            <span className="min-w-0 flex-1 truncate">{displayTitle}</span>
                            {timeString && (
                              <span className="shrink-0 font-['JetBrains_Mono',ui-monospace,monospace] text-[11px] font-normal text-[#8d9bb0] group-hover:hidden group-focus-within:hidden">
                                {timeString}
                              </span>
                            )}
                          </button>

                          {/* Nút tùy chọn: thay giờ khi hover/focus */}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveMenuId(isMenuOpen ? null : session.session_id);
                            }}
                            aria-label="Tùy chọn hội thoại"
                            aria-haspopup="menu"
                            aria-expanded={isMenuOpen}
                            title="Tùy chọn"
                            className={`absolute right-1 top-1/2 size-7 -translate-y-1/2 items-center justify-center rounded-lg text-[#c3cddb] transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#34d399] group-hover:flex group-focus-within:flex ${
                              isMenuOpen ? "flex" : "hidden"
                            }`}
                          >
                            <DotsThreeVertical size={16} weight="bold" aria-hidden="true" />
                          </button>

                          {isMenuOpen && (
                            <div
                              ref={menuRef}
                              role="menu"
                              className="absolute right-0 top-full z-50 mt-1 w-44 rounded-xl border border-[rgba(148,163,184,.2)] bg-[#0f1d33] p-1.5 shadow-2xl"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <button
                                type="button"
                                role="menuitem"
                                onClick={() => handleCopyTitle(session)}
                                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs text-[#c3cddb] transition hover:bg-[rgba(148,163,184,.12)] hover:text-white"
                              >
                                {copiedId === session.session_id ? (
                                  <>
                                    <Check size={14} className="text-[#34d399]" aria-hidden="true" />
                                    <span className="font-medium text-[#6ee7b7]">Đã sao chép</span>
                                  </>
                                ) : (
                                  <>
                                    <Copy size={14} className="text-[#8d9bb0]" aria-hidden="true" />
                                    <span>Sao chép câu hỏi</span>
                                  </>
                                )}
                              </button>

                              <div className="my-1 border-t border-[rgba(148,163,184,.14)]" />

                              <button
                                type="button"
                                role="menuitem"
                                onClick={() => void handleDelete(session.session_id)}
                                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs text-[#fda4af] transition hover:bg-[rgba(244,63,94,.16)]"
                              >
                                <Trash size={14} aria-hidden="true" />
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
          <div className="px-3 py-6 text-center text-xs text-[#8d9bb0]">
            <p className="font-medium text-[#c3cddb]">Không tìm thấy</p>
            <p className="mt-1 text-[11px]">Không có hội thoại nào khớp với "{searchQuery}"</p>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center px-3 py-8 text-center text-[#8d9bb0]">
            <ChatCircleDots size={28} aria-hidden="true" className="mb-2 text-[#64748b]" />
            <p className="text-xs font-medium text-[#c3cddb]">Chưa có lịch sử hội thoại</p>
            <p className="mt-1 text-[11px]">Bắt đầu đặt câu hỏi để lưu vào đây.</p>
          </div>
        )}
      </div>
    </section>
  );
}
