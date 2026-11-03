import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ChatCircle,
  ClockCounterClockwise,
  FolderSimple,
  GraduationCap,
  Plus,
  ShieldCheck,
  SidebarSimple,
  SignOut,
  SlidersHorizontal,
} from "@phosphor-icons/react";
import { NavLink, useNavigate } from "react-router-dom";
import { getDocuments, logoutRequest } from "../../services/api";
import { useAuthStore } from "../../stores/authStore";
import { useChatStore } from "../../stores/chatStore";
import { ConversationHistory } from "./ConversationHistory";

const COLLAPSE_KEY = "edurag.sidebar.collapsed";

function readCollapsed() {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

const focusRing =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#34d399]";

const navItem = (isActive: boolean) =>
  `flex h-10 items-center gap-3 rounded-[10px] px-3 text-sm font-semibold transition-colors ${focusRing} ${
    isActive
      ? "bg-[rgba(16,185,129,.15)] text-[#6ee7b7]"
      : "text-[#aab6c8] hover:bg-[rgba(148,163,184,.10)] hover:text-white"
  }`;

const railItem = (isActive: boolean) =>
  `flex size-11 items-center justify-center rounded-xl transition-colors ${focusRing} ${
    isActive
      ? "bg-[rgba(16,185,129,.15)] text-[#6ee7b7]"
      : "text-[#aab6c8] hover:bg-[rgba(148,163,184,.14)] hover:text-white"
  }`;

const iconBtn = (danger = false) =>
  `flex size-9 shrink-0 items-center justify-center rounded-[10px] text-[#aab6c8] transition-colors ${focusRing} ${
    danger
      ? "hover:bg-[rgba(244,63,94,.16)] hover:text-[#fda4af]"
      : "hover:bg-[rgba(148,163,184,.14)] hover:text-white"
  }`;

export function Sidebar() {
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);
  const user = useAuthStore((state) => state.user);
  const newChat = useChatStore((state) => state.newChat);
  const [collapsed, setCollapsed] = useState(readCollapsed);

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
    } catch {
      // localStorage không khả dụng: bỏ qua, vẫn hoạt động bình thường.
    }
  }, [collapsed]);

  const { data: documents } = useQuery({
    queryKey: ["documents"],
    queryFn: getDocuments,
    retry: false,
  });
  const activeDocuments = documents
    ? documents.filter((doc) => (doc.status ?? "active") === "active").length
    : null;

  const start = () => {
    newChat();
    navigate("/chat");
  };

  const signOut = async () => {
    try {
      await logoutRequest();
    } finally {
      newChat();
      logout();
      navigate("/login");
    }
  };

  const isAdmin = user?.role === "admin";
  const displayName =
    user?.display_name?.trim() || user?.email?.split("@")[0] || "Người dùng";
  const userInitial = (user?.display_name?.trim() || user?.email || "U")
    .charAt(0)
    .toUpperCase();
  const roleLabel = isAdmin ? "Quản trị viên" : "Sinh viên";

  const statusDot = (
    <span
      aria-hidden="true"
      className="absolute -bottom-0.5 -right-0.5 size-[11px] rounded-full border-2 border-[#0b1329] bg-[#34d399]"
    />
  );

  /* ───────────── Thu gọn (rail 72px) ───────────── */
  if (collapsed) {
    return (
      <aside className="flex h-full w-[72px] shrink-0 select-none flex-col items-center gap-1.5 overflow-hidden border-r border-[rgba(148,163,184,.14)] bg-[#0b1329] pb-3.5 pt-4">
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          aria-label="Mở rộng thanh bên"
          title="Mở rộng thanh bên"
          className={`flex size-10 items-center justify-center rounded-xl bg-[#10b981] text-[#04261b] transition-colors hover:bg-[#34d399] ${focusRing}`}
        >
          <GraduationCap size={22} weight="bold" aria-hidden="true" />
        </button>

        <div className="h-2.5" />

        <button
          type="button"
          onClick={start}
          aria-label="Đoạn chat mới"
          title="Đoạn chat mới"
          className={`flex size-11 items-center justify-center rounded-xl bg-[#10b981] text-[#04261b] transition-colors hover:bg-[#34d399] ${focusRing}`}
        >
          <Plus size={20} weight="bold" aria-hidden="true" />
        </button>

        <div className="my-2 h-px w-8 bg-[rgba(148,163,184,.14)]" />

        <nav aria-label="Điều hướng chính" className="flex flex-col items-center gap-1.5">
          <NavLink
            to="/chat"
            aria-label="Trang chat"
            title="Trang chat"
            className={({ isActive }) => railItem(isActive)}
          >
            <ChatCircle size={20} aria-hidden="true" />
          </NavLink>
          <NavLink
            to="/library"
            aria-label="Thư viện tài liệu"
            title="Thư viện tài liệu"
            className={({ isActive }) => railItem(isActive)}
          >
            <FolderSimple size={20} aria-hidden="true" />
          </NavLink>
          {isAdmin && (
            <NavLink
              to="/admin"
              aria-label="Quản trị hệ thống"
              title="Quản trị hệ thống"
              className={({ isActive }) => railItem(isActive)}
            >
              <ShieldCheck size={20} aria-hidden="true" />
            </NavLink>
          )}
          <button
            type="button"
            onClick={() => setCollapsed(false)}
            aria-label="Lịch sử hội thoại"
            title="Lịch sử hội thoại"
            className={railItem(false)}
          >
            <ClockCounterClockwise size={20} aria-hidden="true" />
          </button>
        </nav>

        <div className="flex-1" />

        <NavLink
          to="/settings"
          aria-label="Cài đặt tài khoản"
          title="Cài đặt tài khoản"
          className={({ isActive }) => railItem(isActive)}
        >
          <SlidersHorizontal size={20} aria-hidden="true" />
        </NavLink>
        <button
          type="button"
          onClick={() => void signOut()}
          aria-label="Đăng xuất"
          title="Đăng xuất"
          className={`flex size-11 items-center justify-center rounded-xl text-[#aab6c8] transition-colors hover:bg-[rgba(244,63,94,.16)] hover:text-[#fda4af] ${focusRing}`}
        >
          <SignOut size={20} aria-hidden="true" />
        </button>
        <div className="relative mt-1.5" title={`${displayName} · ${roleLabel}`}>
          <div className="flex size-10 items-center justify-center rounded-xl bg-[rgba(16,185,129,.16)] text-[15px] font-extrabold text-[#6ee7b7]">
            {userInitial}
          </div>
          {statusDot}
        </div>
      </aside>
    );
  }

  /* ───────────── Mở rộng (288px) ───────────── */
  return (
    <aside className="flex h-full w-72 shrink-0 select-none flex-col overflow-hidden border-r border-[rgba(148,163,184,.14)] bg-[#0b1329] px-3.5 pb-3.5 pt-4 text-[#e6edf6]">
      {/* Header */}
      <div className="flex h-11 shrink-0 items-center gap-3 pl-1 pr-0.5">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-[11px] bg-[#10b981] text-[#04261b]">
          <GraduationCap size={20} weight="bold" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1 leading-tight">
          <div className="flex items-center gap-1.5">
            <span className="text-lg font-extrabold tracking-tight text-white">EduRAG</span>
            <span className="rounded-md bg-[rgba(16,185,129,.18)] px-1.5 py-0.5 text-[10px] font-bold text-[#6ee7b7]">
              AI
            </span>
          </div>
          <div className="mt-0.5 text-xs text-[#8d9bb0]">Trợ lý học vụ</div>
        </div>
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          aria-label="Thu gọn thanh bên"
          title="Thu gọn thanh bên"
          className={iconBtn()}
        >
          <SidebarSimple size={18} aria-hidden="true" />
        </button>
      </div>

      {/* Đoạn chat mới */}
      <button
        type="button"
        onClick={start}
        className={`mt-4 flex h-[42px] w-full shrink-0 items-center justify-center gap-2 rounded-xl bg-[#10b981] text-sm font-bold text-[#04261b] transition hover:bg-[#34d399] active:scale-[0.98] ${focusRing}`}
      >
        <Plus size={16} weight="bold" aria-hidden="true" />
        Đoạn chat mới
      </button>

      {/* Điều hướng */}
      <nav aria-label="Điều hướng chính" className="mt-3.5 flex shrink-0 flex-col gap-0.5">
        <NavLink to="/chat" className={({ isActive }) => navItem(isActive)}>
          <ChatCircle size={18} aria-hidden="true" />
          <span className="flex-1">Trang chat</span>
        </NavLink>
        <NavLink to="/library" className={({ isActive }) => navItem(isActive)}>
          <FolderSimple size={18} aria-hidden="true" />
          <span className="flex-1">Thư viện tài liệu</span>
          {activeDocuments !== null && (
            <span
              className="min-w-[22px] rounded-full bg-[rgba(148,163,184,.16)] px-[7px] py-0.5 text-center text-[11px] font-bold text-[#c3cddb]"
              aria-label={`${activeDocuments} tài liệu đang hoạt động`}
            >
              {activeDocuments}
            </span>
          )}
        </NavLink>
        {isAdmin && (
          <NavLink to="/admin" className={({ isActive }) => navItem(isActive)}>
            <ShieldCheck size={18} aria-hidden="true" />
            <span className="flex-1">Quản trị hệ thống</span>
          </NavLink>
        )}
      </nav>

      <div className="mb-3 mt-3.5 h-px shrink-0 bg-[rgba(148,163,184,.14)]" />

      {/* Tìm kiếm + lịch sử hội thoại */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <ConversationHistory />
      </div>

      {/* Chân: người dùng */}
      <div className="mt-2.5 flex shrink-0 items-center gap-2.5 border-t border-[rgba(148,163,184,.14)] pt-3">
        <div className="relative shrink-0">
          <div className="flex size-[38px] items-center justify-center rounded-xl bg-[rgba(16,185,129,.16)] text-[15px] font-extrabold text-[#6ee7b7]">
            {userInitial}
          </div>
          {statusDot}
        </div>
        <div className="min-w-0 flex-1 leading-tight">
          <div className="truncate text-[13px] font-bold text-white" title={user?.email || displayName}>
            {displayName}
          </div>
          <div className="text-xs text-[#8d9bb0]">{roleLabel}</div>
        </div>
        <NavLink
          to="/settings"
          aria-label="Cài đặt tài khoản"
          title="Cài đặt tài khoản"
          className={({ isActive }) =>
            `${iconBtn()} ${isActive ? "bg-[rgba(16,185,129,.15)] !text-[#6ee7b7]" : ""}`
          }
        >
          <SlidersHorizontal size={18} aria-hidden="true" />
        </NavLink>
        <button
          type="button"
          onClick={() => void signOut()}
          aria-label="Đăng xuất"
          title="Đăng xuất"
          className={iconBtn(true)}
        >
          <SignOut size={18} aria-hidden="true" />
        </button>
      </div>
    </aside>
  );
}
