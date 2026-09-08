import { UserCircle } from "@phosphor-icons/react";
import { NavLink } from "react-router-dom";
import { useAuthStore } from "../../stores/authStore";

export function Header() {
  const user = useAuthStore((state) => state.user);

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200/60 bg-white/70 px-5 backdrop-blur-md md:px-8">
      {/* Left spacer to balance layout */}
      <div className="hidden lg:block w-32" />

      {/* Center: Pill Navigation Tabs */}
      <nav
        aria-label="Điều hướng chính"
        className="mx-auto flex items-center rounded-full bg-slate-200/60 p-1 backdrop-blur-sm lg:absolute lg:left-1/2 lg:-translate-x-1/2"
      >
        <NavLink
          to="/chat"
          className={({ isActive }) =>
            `rounded-full px-4 py-1.5 text-xs font-medium transition duration-200 ${
              isActive
                ? "bg-white font-semibold text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`
          }
        >
          Trang chat
        </NavLink>
        <NavLink
          to="/library"
          className={({ isActive }) =>
            `rounded-full px-4 py-1.5 text-xs font-medium transition duration-200 ${
              isActive
                ? "bg-white font-semibold text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`
          }
        >
          Tài liệu
        </NavLink>
        {user?.role === "admin" && (
          <NavLink
            to="/admin"
            className={({ isActive }) =>
              `rounded-full px-4 py-1.5 text-xs font-medium transition duration-200 ${
                isActive
                  ? "bg-white font-semibold text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
              }`
            }
          >
            Quản trị
          </NavLink>
        )}
      </nav>

      {/* Right: User status & avatar */}
      <div className="flex items-center gap-3 text-right">
        <div className="hidden sm:block">
          <p className="text-xs font-semibold text-slate-800">
            {user?.display_name || "Phan Trung Hiếu"}
          </p>
          <p className="text-[10px] text-slate-500">Phiên làm việc đang hoạt động</p>
        </div>
        <div className="relative">
          <span className="grid size-9 place-items-center rounded-full bg-slate-100 text-slate-600 ring-2 ring-white shadow-sm">
            <UserCircle size={24} weight="fill" />
          </span>
          {/* Active status indicator dot */}
          <span className="absolute bottom-0 right-0 size-2.5 rounded-full bg-emerald-500 ring-2 ring-white" />
        </div>
      </div>
    </header>
  );
}
