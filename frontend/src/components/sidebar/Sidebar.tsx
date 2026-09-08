import {
  GearSix,
  Plus,
  SignOut,
} from "@phosphor-icons/react";
import { NavLink, useNavigate } from "react-router-dom";
import { logoutRequest } from "../../services/api";
import { useAuthStore } from "../../stores/authStore";
import { useChatStore } from "../../stores/chatStore";
import { Brand } from "../common/Brand";
import { ConversationHistory } from "./ConversationHistory";
import { Folder3DIcon } from "./Folder3DIcon";

export function Sidebar() {
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);
  const user = useAuthStore((state) => state.user);
  const newChat = useChatStore((state) => state.newChat);

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

  // User initials for avatar
  const userInitial = user?.display_name
    ? user.display_name.trim().charAt(0).toUpperCase()
    : user?.email
    ? user.email.charAt(0).toUpperCase()
    : "U";

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col overflow-hidden border-r border-slate-800/80 bg-[#0b1329] p-3.5 text-slate-200 select-none">
      {/* Brand Header */}
      <div className="shrink-0 pb-1">
        <Brand theme="dark" />
      </div>

      {/* Main Navigation Actions */}
      <div className="mt-5 shrink-0 space-y-2">
        {/* + Đoạn chat mới (Luxury Glass-Emerald Button) */}
        <button
          onClick={start}
          className="group flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 via-emerald-500 to-teal-500 px-4 text-xs font-bold text-white shadow-md shadow-emerald-950/40 ring-1 ring-white/20 transition-all duration-200 hover:from-emerald-500 hover:to-teal-400 hover:shadow-lg hover:shadow-emerald-900/50 active:scale-[0.98]"
        >
          <Plus size={16} weight="bold" className="transition group-hover:rotate-90 duration-200" />
          <span>Đoạn chat mới</span>
        </button>

        {/* Thư viện tài liệu (Vibrant 3D Folder Button matching user's mock) */}
        <NavLink to="/library" className="block">
          {({ isActive }) => (
            <button
              className={`group flex h-13 w-full items-center gap-3.5 rounded-2xl px-3.5 text-left transition-all duration-200 active:scale-[0.98] ${
                isActive
                  ? "border border-teal-500/50 bg-[#0e1b2f] shadow-[0_0_22px_rgba(20,184,166,0.18)] ring-1 ring-teal-500/30"
                  : "border border-slate-800/80 bg-slate-900/60 hover:border-slate-700/90 hover:bg-slate-850/80"
              }`}
            >
              <Folder3DIcon className="size-9" />
              <span className="text-[15px] font-bold text-white tracking-wide transition group-hover:text-emerald-300">
                Thư viện tài liệu
              </span>
            </button>
          )}
        </NavLink>
      </div>

      <div className="my-3.5 shrink-0 border-t border-slate-800/80" />

      {/* Conversation History (Strictly bounded flex-1 container) */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <ConversationHistory />
      </div>

      {/* Bottom Profile & System Section (Strictly pinned at bottom) */}
      <div className="mt-auto shrink-0 border-t border-slate-800/80 pt-3 text-xs bg-[#0b1329] z-10">
        {/* User Card */}
        <div className="mb-2 flex items-center gap-2.5 rounded-xl bg-slate-900/80 border border-slate-800/60 p-2 text-slate-300">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500/25 to-teal-500/25 text-emerald-400 font-bold border border-emerald-500/30 text-xs shadow-xs">
            {userInitial}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold text-slate-200 text-xs" title={user?.display_name || user?.email}>
              {user?.display_name || user?.email?.split("@")[0] || "Người dùng"}
            </p>
            <div className="flex items-center gap-1.5">
              <span className="size-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]" />
              <p className="truncate text-[10px] text-emerald-400/90 font-medium">
                {user?.role === "admin" ? "Quản trị viên" : "Sinh viên"}
              </p>
            </div>
          </div>
        </div>

        {/* Admin Dashboard Link (only if user has admin role) */}
        {user?.role === "admin" && (
          <NavLink
            to="/admin"
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-xl px-2.5 py-2 transition font-medium ${
                isActive
                  ? "bg-slate-800 text-emerald-300 font-semibold"
                  : "text-slate-400 hover:bg-slate-850 hover:text-white"
              }`
            }
          >
            <GearSix size={16} />
            <span>Quản trị hệ thống</span>
          </NavLink>
        )}

        {/* Settings Link */}
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex items-center gap-2.5 rounded-xl px-2.5 py-2 transition font-medium ${
              isActive
                ? "bg-slate-800 text-emerald-300 font-semibold"
                : "text-slate-400 hover:bg-slate-850 hover:text-white"
            }`
          }
        >
          <GearSix size={16} />
          <span>Cài đặt tài khoản</span>
        </NavLink>

        {/* Sign Out Button */}
        <button
          type="button"
          onClick={() => void signOut()}
          className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left text-rose-400 transition hover:bg-rose-950/40 hover:text-rose-300 font-medium mt-0.5"
        >
          <SignOut size={16} />
          <span>Đăng xuất</span>
        </button>
      </div>
    </aside>
  );
}
